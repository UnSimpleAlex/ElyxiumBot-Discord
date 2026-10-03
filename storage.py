"""MySQL document persistence with local JSON recovery copies."""
import asyncio
import json
import logging
import os
from pathlib import Path


class Storage:
    def __init__(self):
        self.pool = None
        self.pending = {}
        self.changed = asyncio.Event()
        self.worker = None

    async def start(self):
        if not os.getenv("MYSQL_HOST"):
            logging.warning("MYSQL_HOST missing: using local JSON storage")
            return
        import aiomysql
        self.pool = await aiomysql.create_pool(
            host=os.environ["MYSQL_HOST"], port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
            db=os.environ["MYSQL_DATABASE"], charset="utf8mb4", autocommit=True,
            minsize=1, maxsize=3, connect_timeout=10,
        )
        async with self.pool.acquire() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute("CREATE TABLE IF NOT EXISTS bot_documents (name VARCHAR(191) PRIMARY KEY, payload LONGTEXT NOT NULL)")
                # Existing database documents win; missing documents are imported once.
                from common import write_json
                for path in Path("data").glob("*.json"):
                    await cursor.execute("INSERT IGNORE INTO bot_documents (name, payload) VALUES (%s, %s)", (path.name, path.read_text(encoding="utf-8")))
                await cursor.execute("SELECT name, payload FROM bot_documents")
                for name, payload in await cursor.fetchall():
                    if Path(name).name != name or not name.endswith(".json"):
                        raise ValueError("Invalid database document name")
                    write_json(Path("data") / name, json.loads(payload))
        self.worker = asyncio.create_task(self.run(), name="mysql-persistence")

    def enqueue(self, path, data):
        if self.pool is not None:
            self.pending[Path(path).name] = json.dumps(data, ensure_ascii=False)
            self.changed.set()

    async def flush(self):
        while self.pending:
            name, payload = next(iter(self.pending.items()))
            async with self.pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("INSERT INTO bot_documents (name, payload) VALUES (%s, %s) ON DUPLICATE KEY UPDATE payload=VALUES(payload)", (name, payload))
            if self.pending.get(name) == payload:
                del self.pending[name]

    async def run(self):
        while True:
            await self.changed.wait()
            self.changed.clear()
            try:
                await self.flush()
            except Exception:
                logging.exception("MySQL save failed; local JSON preserved, retrying")
                await asyncio.sleep(5)
                self.changed.set()

    async def close(self):
        if self.worker:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        if self.pool:
            try:
                await asyncio.wait_for(self.flush(), timeout=10)
            finally:
                self.pool.close()
                await self.pool.wait_closed()


storage = Storage()

import time
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import suggestions as module


class SuggestionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        with patch('suggestions.read_json', return_value={}):
            self.service = module.SuggestionService(MagicMock())
        self.service.save = MagicMock()
        self.service.sync = AsyncMock()
        self.service.config = {'10': {'enabled': True, 'public_channel_id': 100,
                                     'staff_channel_id': 200, 'review_role_id': 30}}
        self.record = {'id': 'abc', 'guild_id': 10, 'author_id': 1, 'title': 'Idea',
                       'description': 'Una mejora', 'created_at': time.time() - 200,
                       'status': 'pending', 'votes': {}, 'public_channel_id': 100,
                       'staff_channel_id': 200, 'public_message_id': 111, 'staff_message_id': 222}
        self.service.records = {'abc': self.record}

    def interaction(self, user_id=2, staff=False):
        user = MagicMock(spec=discord.Member)
        user.id = user_id
        user.guild = SimpleNamespace(id=10)
        user.roles = [SimpleNamespace(id=30)] if staff else []
        return SimpleNamespace(user=user, guild_id=10, channel_id=200 if staff else 100,
                               message=SimpleNamespace(id=222 if staff else 111),
                               response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock(), send_modal=AsyncMock()),
                               followup=SimpleNamespace(send=AsyncMock()))

    async def test_one_vote_change_and_withdraw(self):
        interaction = self.interaction()
        with patch('suggestions.time.time', return_value=100):
            await self.service.vote(interaction, 'abc', 1)
        self.assertEqual(module.count_votes(self.record), (1, 0))
        with patch('suggestions.time.time', return_value=106):
            await self.service.vote(interaction, 'abc', -1)
        self.assertEqual(module.count_votes(self.record), (0, 1))
        with patch('suggestions.time.time', return_value=112):
            await self.service.vote(interaction, 'abc', -1)
        self.assertEqual(module.count_votes(self.record), (0, 0))

    async def test_fast_vote_click_does_not_change_state(self):
        interaction = self.interaction()
        with patch('suggestions.time.time', return_value=100):
            await self.service.vote(interaction, 'abc', 1)
            await self.service.vote(interaction, 'abc', -1)
        self.assertEqual(module.count_votes(self.record), (1, 0))
        self.service.sync.assert_awaited_once()

    async def test_wrong_message_and_guild_rejected(self):
        interaction = self.interaction()
        interaction.message.id = 999
        await self.service.vote(interaction, 'abc', 1)
        interaction.message.id = 111
        interaction.guild_id = 11
        await self.service.vote(interaction, 'abc', 1)
        self.assertEqual(self.record['votes'], {})

    async def test_staff_role_required_even_for_admin(self):
        interaction = self.interaction()
        interaction.user.guild_permissions = SimpleNamespace(administrator=True)
        interaction.channel_id = 200
        await self.service.review(interaction, 'abc', 'accepted', '')
        self.assertEqual(self.record['status'], 'pending')
        self.service.save.assert_not_called()

    async def test_decision_changes_color_and_closes_votes(self):
        interaction = self.interaction(staff=True)
        await self.service.review(interaction, 'abc', 'accepted', 'Buena idea')
        self.assertEqual(module.render(self.record).color.value, module.COLORS['accepted'])
        self.assertTrue(all(child.disabled for child in module.VoteView(self.service, 'abc').children))
        await self.service.vote(self.interaction(), 'abc', 1)
        self.assertEqual(self.record['votes'], {})
        await self.service.review(interaction, 'abc', 'denied', 'Otra decision')
        self.assertEqual(self.record['status'], 'accepted')

    async def test_denial_reason_and_red_color(self):
        await self.service.review(self.interaction(staff=True), 'abc', 'denied', 'No corresponde')
        self.assertEqual(self.record['reason'], 'No corresponde')
        self.assertEqual(module.render(self.record).color.value, module.COLORS['denied'])

    async def test_delete_removes_both_messages_retains_audit(self):
        public, staff = MagicMock(), MagicMock()
        public.get_partial_message.return_value.delete = AsyncMock()
        staff.get_partial_message.return_value.delete = AsyncMock()
        self.service.channel = AsyncMock(side_effect=[public, staff])
        await self.service.review(self.interaction(staff=True), 'abc', 'deleted', 'Spam')
        self.assertEqual(self.record['status'], 'deleted')
        public.get_partial_message.return_value.delete.assert_awaited_once()
        staff.get_partial_message.return_value.delete.assert_awaited_once()
        self.assertEqual(self.record['reviewer_id'], 2)

    async def test_persistent_views_restore_and_embed_limits(self):
        self.service.restore()
        self.assertEqual(self.service.bot.add_view.call_count, 2)
        for call in self.service.bot.add_view.call_args_list:
            self.assertTrue(call.args[0].is_persistent())
        for status in module.STATUS:
            self.record['status'] = status
            self.record['title'] = '*' * 150
            self.record['description'] = 'x' * 2400
            self.record['reason'] = 'x' * 500
            self.record['reviewer_id'] = 2
            embed = module.render(self.record, staff=True)
            self.assertLessEqual(len(embed), 6000)
            self.assertLessEqual(len(embed.description), 4096)
            self.assertTrue(all(len(field.value) <= 1024 for field in embed.fields))

    async def test_outdated_panel_cannot_open_form(self):
        view = module.PanelView(self.service, 10)
        interaction = self.interaction()
        self.service.config['10']['panel_message_id'] = 999
        await view.suggest.callback(interaction)
        interaction.response.send_modal.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_publish_replay_and_partial_delivery_saved(self):
        view = module.FormRequest(10, 1, 100)
        self.service.requests[(10, 1)] = view
        self.service.sync.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'No permission')
        interaction = self.interaction(user_id=1)
        with self.assertLogs(level='ERROR'):
            await self.service.publish(interaction, view, 'Idea', 'Una mejora')
        self.assertEqual(len(self.service.records), 2)
        await self.service.publish(interaction, view, 'Idea', 'Duplicada')
        self.assertEqual(len(self.service.records), 2)
        self.service.sync.assert_awaited_once()

    async def test_completed_form_publishes_without_source_message(self):
        view = module.FormRequest(10, 1, 100)
        self.service.requests[(10, 1)] = view
        interaction = self.interaction(user_id=1)
        async def publish(record):
            interaction.response.defer.assert_awaited_once()
            record['public_message_id'] = 333
            record['staff_message_id'] = 444
        self.service.sync.side_effect = publish
        await self.service.publish(interaction, view, 'Idea', 'Una mejora')
        self.assertEqual(len(self.service.records), 2)
        self.assertTrue(view.submitted)

    async def test_expired_form_cannot_publish(self):
        view = module.FormRequest(10, 1, 100)
        view.deadline = time.monotonic() - 1
        self.service.requests[(10, 1)] = view
        await self.service.publish(self.interaction(user_id=1), view, 'Idea', 'Una mejora')
        self.assertEqual(len(self.service.records), 1)
        self.service.sync.assert_not_awaited()

    async def test_persistent_panel_opens_modal_and_cleans_expired_requests(self):
        self.service.config['10']['panel_message_id'] = 111
        expired = module.FormRequest(10, 9, 100, deadline=time.monotonic() - 1)
        self.service.requests[(10, 9)] = expired
        view = module.PanelView(self.service, 10)
        self.assertTrue(view.is_persistent())
        interaction = self.interaction()
        await view.suggest.callback(interaction)
        interaction.response.send_modal.assert_awaited_once()
        self.assertNotIn((10, 9), self.service.requests)
        self.assertEqual(self.service.requests[(10, 2)].author_id, 2)

    async def test_second_modal_after_recent_submission_is_rejected(self):
        self.record['created_at'] = time.time()
        view = module.FormRequest(10, 1, 100)
        self.service.requests[(10, 1)] = view
        await self.service.publish(self.interaction(user_id=1), view, 'Otra idea', 'Duplicada')
        self.service.sync.assert_not_awaited()
        self.assertEqual(len(self.service.records), 1)

    async def test_commands_allow_everyone_only_in_configured_channel(self):
        interaction = self.interaction()
        await self.service.open_form(interaction)
        interaction.response.send_modal.assert_awaited_once()
        interaction.response.send_modal.reset_mock()
        interaction.channel_id = 999
        await self.service.open_form(interaction)
        interaction.response.send_modal.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_command_role_can_suggest_elsewhere_without_review_privileges(self):
        interaction = self.interaction()
        interaction.channel_id = 999
        interaction.user.roles = [SimpleNamespace(id=40)]
        self.service.config['10']['command_role_id'] = 40
        await self.service.open_form(interaction)
        interaction.response.send_modal.assert_awaited_once()
        request = self.service.requests[(10, 2)]
        self.assertEqual(request.channel_id, 100)
        self.assertFalse(self.service.reviewer(interaction.user, 10))
        await self.service.publish(interaction, request, 'Idea', 'Contenido')
        record = next(r for r in self.service.records.values() if r['author_id'] == 2)
        self.assertEqual(record['public_channel_id'], 100)

    async def test_command_role_revoked_before_submission_blocks_publish(self):
        interaction = self.interaction()
        interaction.channel_id = 999
        self.service.config['10']['command_role_id'] = 40
        interaction.user.roles = [SimpleNamespace(id=40)]
        await self.service.open_form(interaction)
        request = self.service.requests[(10, 2)]
        interaction.user.roles = []
        await self.service.publish(interaction, request, 'Idea', 'Contenido')
        self.service.sync.assert_not_awaited()

    async def test_prefix_command_launcher_checks_owner(self):
        view = module.CommandFormView(self.service, author_id=1)
        interaction = self.interaction(user_id=2)
        await view.open.callback(interaction)
        interaction.response.send_modal.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_prefix_command_respects_channel_permissions(self):
        bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
        try:
            with patch('suggestions.read_json', return_value={}):
                module.setup(bot)
            bot.suggestions.config = self.service.config
            interaction = self.interaction()
            ctx = SimpleNamespace(guild=SimpleNamespace(id=10), author=interaction.user,
                                  channel=SimpleNamespace(id=100), send=AsyncMock())
            await bot.get_command('sugerencias').callback(ctx)
            self.assertIsInstance(ctx.send.await_args.kwargs['view'], module.CommandFormView)
            ctx.send.reset_mock()
            ctx.channel.id = 999
            await bot.get_command('sugerencias').callback(ctx)
            self.assertNotIn('view', ctx.send.await_args.kwargs)
        finally:
            await bot.close()

    async def test_move_panel_sends_replacement_before_deleting_old(self):
        config = self.service.config['10']
        config['panel_message_id'] = 111
        channel = MagicMock()
        channel.id = 100
        events = []
        async def send(**kwargs):
            self.assertIsInstance(kwargs['view'], module.PanelView)
            events.append('send')
            return SimpleNamespace(id=555)
        async def delete():
            self.assertEqual(config['panel_message_id'], 555)
            events.append('delete')
        channel.send = AsyncMock(side_effect=send)
        channel.get_partial_message.return_value.delete = AsyncMock(side_effect=delete)
        self.service.channel = AsyncMock(return_value=channel)
        with patch('suggestions.write_json'):
            await self.service.move_panel(10)
        self.assertEqual(events, ['send', 'delete'])
        self.assertEqual(config['obsolete_panels'], [])

    async def test_failed_panel_send_preserves_old_panel(self):
        self.service.config['10']['panel_message_id'] = 111
        channel = MagicMock()
        channel.id = 100
        channel.send = AsyncMock(side_effect=discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'No permission'))
        channel.get_partial_message.return_value.delete = AsyncMock()
        self.service.channel = AsyncMock(return_value=channel)
        with self.assertRaises(discord.Forbidden):
            await self.service.move_panel(10)
        self.assertEqual(self.service.config['10']['panel_message_id'], 111)
        channel.get_partial_message.return_value.delete.assert_not_awaited()

    async def test_failed_panel_deletion_keeps_retry_id(self):
        self.service.config['10']['panel_message_id'] = 111
        channel = MagicMock()
        channel.id = 100
        channel.send = AsyncMock(return_value=SimpleNamespace(id=555))
        channel.get_partial_message.return_value.delete = AsyncMock(side_effect=discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'No permission'))
        self.service.channel = AsyncMock(return_value=channel)
        with patch('suggestions.write_json'), self.assertLogs(level='ERROR'):
            await self.service.move_panel(10)
        self.assertEqual(self.service.config['10']['panel_message_id'], 555)
        self.assertEqual(self.service.config['10']['obsolete_panels'], [{'channel_id': 100, 'message_id': 111}])

    async def test_ready_does_not_duplicate_existing_panel(self):
        self.service.config['10']['panel_message_id'] = 111
        channel = MagicMock()
        channel.fetch_message = AsyncMock(return_value=SimpleNamespace(id=111, edit=AsyncMock()))
        self.service.channel = AsyncMock(return_value=channel)
        self.service.move_panel = AsyncMock()
        with patch('suggestions.write_json'):
            await self.service.ensure_panels()
        self.service.move_panel.assert_not_awaited()

    async def test_concurrent_forms_leave_one_panel_after_suggestions(self):
        public, staff = MagicMock(), MagicMock()
        public.id, staff.id = 100, 200
        events, issued = [], []
        async def send_public(**kwargs):
            kind = 'panel' if isinstance(kwargs['view'], module.PanelView) else 'suggestion'
            events.append(kind)
            message_id = 1000 + len(events)
            issued.append((kind, message_id))
            return SimpleNamespace(id=message_id)
        public.send = AsyncMock(side_effect=send_public)
        public.get_partial_message.return_value.delete = AsyncMock()
        staff.send = AsyncMock(return_value=SimpleNamespace(id=2000))
        self.service.channel = AsyncMock(side_effect=lambda channel_id: public if channel_id == 100 else staff)
        self.service.sync = lambda record: module.SuggestionService.sync(self.service, record)
        self.service.config['10']['panel_message_id'] = 111
        first, second = module.FormRequest(10, 3, 100), module.FormRequest(10, 4, 100)
        self.service.requests.update({(10, 3): first, (10, 4): second})
        with patch('suggestions.write_json'):
            await asyncio.gather(
                self.service.publish(self.interaction(user_id=3), first, 'Primera', 'Idea 1'),
                self.service.publish(self.interaction(user_id=4), second, 'Segunda', 'Idea 2'),
            )
        self.assertEqual(events, ['suggestion', 'panel', 'suggestion', 'panel'])
        self.assertEqual(self.service.config['10']['panel_message_id'], issued[-1][1])
        self.assertEqual(public.get_partial_message.return_value.delete.await_count, 2)
        self.assertEqual(len(self.service.records), 3)

    async def test_setup_registers_commands_without_replacing_message_handler(self):
        bot = commands.Bot(command_prefix='!', intents=discord.Intents.default())
        try:
            with patch('suggestions.read_json', return_value={}):
                module.setup(bot)
            group = bot.tree.get_command('sugerencias_admin')
            self.assertEqual({command.name for command in group.commands}, {'configurar', 'sincronizar', 'desactivar', 'panel', 'acceso'})
            self.assertIsNotNone(bot.tree.get_command('sugerencias'))
            self.assertIsNotNone(bot.get_command('sugerencias'))
            self.assertNotIn('on_message', bot.extra_events)
            self.assertIn('on_ready', bot.extra_events)
        finally:
            await bot.close()


if __name__ == '__main__':
    unittest.main()

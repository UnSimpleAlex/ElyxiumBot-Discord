import unittest
from unittest.mock import patch

import captcha
from storage import Storage


class CaptchaSecurityTests(unittest.TestCase):
    def setUp(self):
        self.state = patch.dict(captcha.captcha_codes, {}, clear=True)
        self.state.start()
        self.save = patch.object(captcha, 'save_captcha_codes')
        self.save.start()

    def tearDown(self):
        self.save.stop()
        self.state.stop()

    def test_duplicate_does_not_refresh_expiry(self):
        first = captcha.create_captcha_code('1', 10, 20)
        second = captcha.create_captcha_code('1', 10, 20)
        self.assertFalse(second['success'])
        self.assertEqual(first['timestamp'], second['timestamp'])

    def test_attempt_limit_and_replay(self):
        result = captcha.create_captcha_code('1', 10, 20)
        for _ in range(5):
            self.assertFalse(captcha.verify_captcha_code('1', '!!!!!!', 10, 20)['success'])
        self.assertFalse(captcha.verify_captcha_code('1', result['code'], 10, 20)['success'])
        result = captcha.create_captcha_code('2', 10, 20)
        self.assertTrue(captcha.verify_captcha_code('2', result['code'], 10, 20)['success'])
        self.assertFalse(captcha.verify_captcha_code('2', result['code'], 10, 20)['success'])

    def test_scope_and_expiration(self):
        result = captcha.create_captcha_code('1', 10, 20)
        self.assertFalse(captcha.verify_captcha_code('1', result['code'], 11, 20)['success'])
        with patch.object(captcha.time, 'time', return_value=result['timestamp'] + 181):
            self.assertFalse(captcha.verify_captcha_code('1', result['code'], 10, 20)['success'])
            self.assertTrue(captcha.create_captcha_code('1', 10, 20)['success'])

    def test_database_pending_snapshot(self):
        storage = Storage()
        storage.pool = object()
        data = {'title': 'original'}
        storage.enqueue('data/config.json', data)
        data['title'] = 'changed'
        self.assertIn('original', storage.pending['config.json'])
        storage.enqueue('data/config.json', data)
        self.assertEqual(len(storage.pending), 1)
        self.assertIn('changed', storage.pending['config.json'])


if __name__ == '__main__':
    unittest.main()

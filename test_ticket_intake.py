import asyncio
import time
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord

import ticket
from common import BRAND_FOOTER, CUSTOM_EMOJI_PATTERN


class TicketIntakeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        state = patch.dict(ticket.active_tickets, {}, clear=True)
        state.start()
        self.addCleanup(state.stop)
        writer = patch('ticket.save_active_tickets')
        self.save = writer.start()
        self.addCleanup(writer.stop)
        self.user = MagicMock(spec=discord.Member)
        self.user.id, self.user.mention, self.user.display_name = 1, '<@1>', 'Alex'
        self.guild = MagicMock()
        self.guild.id = 10
        self.guild.get_channel.return_value = None
        self.channel = MagicMock()
        self.channel.id, self.channel.mention = 123, '<#123>'
        self.channel.send = AsyncMock()
        self.guild.create_text_channel = AsyncMock(return_value=self.channel)
        self.interaction = SimpleNamespace(user=self.user, guild=self.guild, client=SimpleNamespace(),
            response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock(), send_modal=AsyncMock(), is_done=lambda: True),
            followup=SimpleNamespace(send=AsyncMock()))

    def modal(self, category='soporte'):
        modal = ticket.TicketIntakeModal(category, 1, 10)
        for field in modal.questions:
            field._value = 'Detalle de prueba'
        return modal

    async def test_category_selection_opens_form_without_creating_channel(self):
        select = ticket.TicketCategorySelect()
        select._values = ['reportar']
        await select.callback(self.interaction)
        modal = self.interaction.response.send_modal.await_args.args[0]
        self.assertIsInstance(modal, ticket.TicketIntakeModal)
        self.assertEqual(modal.category, 'reportar')
        self.guild.create_text_channel.assert_not_awaited()

    async def test_every_category_has_matching_banner_color_and_unique_emojis(self):
        select = ticket.TicketCategorySelect()
        expected = {'soporte': 0xF1C40F, 'consulta': 0x85C1E9, 'reportar': 0xF39C12,
                    'sugerencia': 0x9B59B6, 'otro': 0x3498DB}
        for category, info in ticket.TICKET_DETAILS.items():
            modal = self.modal(category)
            self.assertLessEqual(len(modal.questions), 5)
            answers = {label: field.value for (label, _, _), field in zip(info['questions'], modal.questions)}
            embed = select.create_category_embed(category, self.user, answers)
            data = embed.to_dict()
            self.assertEqual(data['color'], expected[category])
            self.assertEqual(data['image']['url'], info['banner'])
            self.assertEqual(data['footer']['text'], BRAND_FOOTER)
            self.assertEqual(len(data['fields']), len(info['questions']))
            text = data['title'] + data['description'] + ''.join(field['name'] + field['value'] for field in data['fields'])
            ids = CUSTOM_EMOJI_PATTERN.findall(text)
            self.assertEqual(len(ids), len(set(ids)))
            self.assertLess(len(text), 6000)
            self.assertTrue(all(field['value'] == 'Detalle de prueba' for field in data['fields']))

    async def test_submission_acknowledges_and_persists_answers(self):
        modal = self.modal()
        async def create(**kwargs):
            self.interaction.response.defer.assert_awaited_once()
            self.assertFalse(kwargs['overwrites'][self.guild.default_role].read_messages)
            return self.channel
        self.guild.create_text_channel.side_effect = create
        await modal.on_submit(self.interaction)
        self.assertTrue(modal.submitted)
        self.assertEqual(ticket.active_tickets[123]['guild_id'], 10)
        self.assertEqual(ticket.active_tickets[123]['answers']['Problema principal'], 'Detalle de prueba')
        self.channel.send.assert_awaited_once()
        self.save.assert_called_once()
        await modal.on_submit(self.interaction)
        self.guild.create_text_channel.assert_awaited_once()

    async def test_existing_ticket_rechecked_before_creation(self):
        modal = self.modal()
        ticket.active_tickets[123] = {'user_id': 1}
        self.guild.get_channel.return_value = self.channel
        await modal.on_submit(self.interaction)
        self.guild.create_text_channel.assert_not_awaited()

    async def test_wrong_owner_guild_and_expired_forms_rejected(self):
        modal = self.modal()
        modal.user_id = 2
        await modal.on_submit(self.interaction)
        modal.user_id, modal.guild_id = 1, 11
        await modal.on_submit(self.interaction)
        modal.guild_id, modal.deadline = 10, time.monotonic() - 1
        await modal.on_submit(self.interaction)
        self.guild.create_text_channel.assert_not_awaited()

    async def test_required_answers_and_pending_requests_rejected(self):
        modal = self.modal()
        modal.questions[0]._value = '  '
        await modal.on_submit(self.interaction)
        modal.questions[0]._value = 'Detalles'
        self.interaction.client._pending_tickets = {(10, 1)}
        await modal.on_submit(self.interaction)
        self.guild.create_text_channel.assert_not_awaited()

    async def test_two_simultaneous_forms_do_not_create_two_tickets(self):
        first, second = self.modal(), self.modal('reportar')
        async def create(**kwargs):
            await asyncio.sleep(0)
            return self.channel
        self.guild.create_text_channel.side_effect = create
        await asyncio.gather(first.on_submit(self.interaction), second.on_submit(self.interaction))
        self.guild.create_text_channel.assert_awaited_once()
        self.assertEqual(self.interaction.client._pending_tickets, set())

    async def test_ticket_buttons_use_server_emojis_only(self):
        for view in (ticket.TicketControlView(123), ticket.ConfirmCloseView(123)):
            for button in view.children:
                self.assertIsNotNone(button.emoji.id)
                self.assertIsNotNone(CUSTOM_EMOJI_PATTERN.fullmatch(str(button.emoji)))

    async def test_failed_creation_releases_pending_guard(self):
        self.guild.create_text_channel.side_effect = discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'Denied')
        modal = self.modal()
        await modal.on_submit(self.interaction)
        self.assertFalse(modal.submitted)
        self.assertEqual(self.interaction.client._pending_tickets, set())
        self.assertEqual(ticket.active_tickets, {})

    async def test_transcript_includes_intake_embed_answers(self):
        self.user.guild_permissions.administrator = True
        self.interaction.channel = self.channel
        embed = ticket.TicketCategorySelect().create_category_embed('consulta', self.user, {'Tu pregunta': '¿Cómo ingreso?'})
        message = SimpleNamespace(created_at=datetime.now(), author='Alex',
                                  content='', embeds=[embed])
        async def history(**kwargs):
            yield message
        self.channel.history = history
        self.channel.name = 'ticket-alex'
        view = ticket.TicketControlView(123)
        await view.generate_transcript.callback(self.interaction)
        file = self.interaction.followup.send.await_args.kwargs['file']
        text = file.fp.getvalue().decode('utf-8')
        self.assertIn('¿Cómo ingreso?', text)
        self.assertIn('TU PREGUNTA', text)

    async def test_everyone_support_role_cannot_expose_private_ticket(self):
        role = MagicMock()
        role.is_default.return_value = True
        self.guild.get_role.return_value = role
        with patch('ticket.SUPPORT_ROLE_ID', 20):
            await self.modal().on_submit(self.interaction)
        self.guild.create_text_channel.assert_not_awaited()

    async def test_long_answers_fit_discord_limits(self):
        for category in ticket.TICKET_DETAILS:
            answers = {label: '*' * 500 for label, _, _ in ticket.TICKET_DETAILS[category]['questions']}
            data = ticket.TicketCategorySelect().create_category_embed(category, self.user, answers).to_dict()
            self.assertTrue(all(len(field['value']) <= 1024 for field in data['fields']))
            self.assertLess(len(data['title']) + len(data['description']) + sum(len(f['name']) + len(f['value']) for f in data['fields']), 6000)


if __name__ == '__main__':
    unittest.main()

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import captcha
import general_embeds
import suggestions
import ticket
import verificacion
from common import BRAND_FOOTER, BRAND_LOGO, CUSTOM_EMOJI_PATTERN, SERVER_EMOJIS, StudioEmbed, TICKET_BANNER, VERIFICATION_BANNER, update_panel_banners


class BrandingTests(unittest.TestCase):
    def check_footer(self, embed):
        self.assertEqual(embed.footer.text, BRAND_FOOTER)
        self.assertEqual(embed.footer.icon_url, BRAND_LOGO)

    def test_footer_is_identical_for_all_embed_builders(self):
        for builder in (general_embeds.EmbedBuilder(), ticket.TicketBuilder(), verificacion.EmbedBuilder()):
            builder.footer_text = 'Old footer'
            builder.footer_icon = 'https://example.com/old.png'
            self.check_footer(builder.to_embed())
        user = SimpleNamespace(id=1, mention='<@1>', display_name='User')
        guild = SimpleNamespace(name='Elyxium Studio')
        self.check_footer(captcha.build_captcha_embed(user, guild, {'code': 'ABC123'}))
        self.check_footer(captcha.build_captcha_prompt_embed(user, guild, True))
        self.check_footer(captcha.build_captcha_prompt_embed(user, guild, False))
        self.check_footer(suggestions.render_panel())

    def test_individual_footer_calls_keep_studio_signature(self):
        embed = StudioEmbed(title='Title')
        embed.set_footer(text='Old footer', icon_url='https://example.com/old.png')
        self.check_footer(embed)

    def test_suggestion_panel_uses_requested_banner(self):
        self.assertEqual(suggestions.render_panel().image.url, suggestions.PANEL_BANNER)

    def test_titles_receive_emoji_without_duplicate_prefix(self):
        embed = StudioEmbed(title='𝙲𝙾́𝙳𝙸𝙶𝙾 𝙳𝙴 𝚅𝙴𝚁𝙸𝙵𝙸𝙲𝙰𝙲𝙸𝙾́𝙽')
        self.assertEqual(embed.to_dict()['title'], SERVER_EMOJIS['key'] + ' ' + embed.title)
        embed.title = '📜 Normas'
        rendered = embed.to_dict()
        self.assertEqual(rendered['title'], SERVER_EMOJIS['document'] + ' Normas')
        self.assertNotIn('📜', rendered['title'])
        self.assertNotIn(SERVER_EMOJIS['document'], rendered.get('description', ''))
        self.assertTrue(suggestions.render_panel().to_dict()['title'].startswith(SERVER_EMOJIS['pencil']))

    def test_custom_emojis_replace_defaults_without_mutating_saved_fields(self):
        embed = StudioEmbed(title='Normas', description='✅ Confirmado ⚠️ Aviso')
        embed.add_field(name='📝 Nota', value='🔑 Código')
        original = embed.fields[0].name
        rendered = embed.to_dict()
        self.assertIn(SERVER_EMOJIS['check'], rendered['description'])
        self.assertIn(SERVER_EMOJIS['warning'], rendered['description'])
        self.assertIn(SERVER_EMOJIS['key'], rendered['fields'][0]['value'])
        self.assertEqual(embed.fields[0].name, original)
        self.assertEqual(rendered, embed.to_dict())

    def test_footer_uses_transparent_isotipo(self):
        self.assertEqual(BRAND_LOGO, 'https://res.cloudinary.com/y08rn1qr/image/upload/v1790138294/IsotipoSinFondo.png')

    def test_emojis_are_unique_across_heading_description_and_fields(self):
        emoji = SERVER_EMOJIS['pencil']
        embed = StudioEmbed(title='Sugerencias', description=f'{emoji} Idea {emoji} Propuesta')
        embed.add_field(name=f'{emoji} Detalles', value=f"{SERVER_EMOJIS['check']} Si {emoji} Nota")
        data = embed.to_dict()
        text = data['title'] + data['description'] + ''.join(field['name'] + field['value'] for field in data['fields'])
        ids = CUSTOM_EMOJI_PATTERN.findall(text)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 6)
        self.assertIn(SERVER_EMOJIS['check'], data['fields'][0]['value'])
        self.assertEqual(data, embed.to_dict())

    def test_exhausted_emoji_pool_preserves_words_without_duplicates(self):
        embed = StudioEmbed(description=(SERVER_EMOJIS['document'] + ' Texto ') * 25)
        text = embed.to_dict()['description']
        ids = CUSTOM_EMOJI_PATTERN.findall(text)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(text.count('Texto'), 25)

    def test_all_builders_have_native_titles_without_description_headings(self):
        embeds = [builder.to_embed() for builder in (general_embeds.EmbedBuilder(), ticket.TicketBuilder(), verificacion.EmbedBuilder())]
        embeds.extend((suggestions.render_panel(), StudioEmbed(title=None), StudioEmbed(title='  ')))
        for embed in embeds:
            data = embed.to_dict()
            self.assertTrue(data['title'].strip())
            self.assertIsNotNone(CUSTOM_EMOJI_PATTERN.match(data['title']))
            self.assertNotIn('**' + data['title'] + '**', data.get('description', ''))

    def test_original_title_emoji_kept_and_not_repeated_in_description(self):
        emoji = SERVER_EMOJIS['announcement']
        embed = StudioEmbed(title=f'{emoji} 𝚂𝙸𝚂𝚃𝙴𝙼𝙰 𝙳𝙴 𝚅𝙴𝚁𝙸𝙵𝙸𝙲𝙰𝙲𝙸𝙾𝙽', description=f'{emoji} Bienvenido')
        data = embed.to_dict()
        self.assertEqual(data['title'], embed.title)
        self.assertNotIn(emoji, data['description'])
        self.assertIn('Bienvenido', data['description'])
        self.assertEqual(embed.description, f'{emoji} Bienvenido')

    def test_long_titles_keep_complete_emoji_and_stay_within_limit(self):
        data = StudioEmbed(title='A' * 256).to_dict()
        self.assertLessEqual(len(data['title']), 256)
        self.assertTrue(data['title'].startswith(SERVER_EMOJIS['document'] + ' '))

    def test_new_builders_use_requested_banners(self):
        self.assertEqual(ticket.TicketBuilder().to_embed().image.url, TICKET_BANNER)
        self.assertEqual(verificacion.EmbedBuilder().to_embed().image.url, VERIFICATION_BANNER)

    def test_banner_migration_preserves_other_saved_settings_and_runs_once(self):
        ticket_data = {'ticket_1': {'image_url': 'old', 'title': 'Custom title', 'color': '#FF0000'}}
        verification_data = {'verification_1': {'image_url': 'old', 'description': 'Custom description', 'fields': []}}
        with patch('common.read_json', side_effect=[{}, ticket_data, verification_data]), patch('common.write_json') as write:
            update_panel_banners()
        self.assertEqual(ticket_data['ticket_1'], {'image_url': TICKET_BANNER, 'title': 'Custom title', 'color': '#FF0000'})
        self.assertEqual(verification_data['verification_1']['description'], 'Custom description')
        self.assertEqual(verification_data['verification_1']['image_url'], VERIFICATION_BANNER)
        self.assertEqual(write.call_count, 3)
        with patch('common.read_json', return_value={'panel-banners-2026-10-03-v1': True}), patch('common.write_json') as write:
            update_panel_banners()
        write.assert_not_called()


if __name__ == '__main__':
    unittest.main()

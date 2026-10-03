import unittest
from types import SimpleNamespace

import captcha
import general_embeds
import suggestions
import ticket
import verificacion
from common import BRAND_FOOTER, BRAND_LOGO, SERVER_EMOJIS, StudioEmbed


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
        self.assertTrue(embed.to_dict()['description'].startswith('**' + SERVER_EMOJIS['key']))
        embed.title = '📜 Normas'
        rendered = embed.to_dict()
        self.assertNotIn('title', rendered)
        self.assertNotIn('📜', rendered['description'])
        self.assertEqual(rendered['description'].count(SERVER_EMOJIS['document']), 1)
        self.assertTrue(suggestions.render_panel().to_dict()['description'].startswith('**' + SERVER_EMOJIS['pencil']))

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


if __name__ == '__main__':
    unittest.main()

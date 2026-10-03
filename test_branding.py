import unittest
from types import SimpleNamespace

import captcha
import general_embeds
import suggestions
import ticket
import verificacion
from common import BRAND_FOOTER, BRAND_LOGO, StudioEmbed


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
        self.assertTrue(embed.title.startswith('🔑 '))
        embed.title = '📜 Normas'
        self.assertEqual(embed.title, '📜 Normas')
        self.assertTrue(suggestions.render_panel().title.startswith('💡 '))

    def test_footer_uses_transparent_isotipo(self):
        self.assertEqual(BRAND_LOGO, 'https://res.cloudinary.com/y08rn1qr/image/upload/v1790138294/IsotipoSinFondo.png')


if __name__ == '__main__':
    unittest.main()

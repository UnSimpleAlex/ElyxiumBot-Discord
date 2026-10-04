import unittest
from types import SimpleNamespace
from unittest.mock import patch
from common import update_verification_emojis, update_verification_color, update_ticket_option_emojis, TICKET_OPTION_EMOJIS, FAQ_BANNER, update_faq_banner

import captcha
import general_embeds
import suggestions
import ticket
import verificacion
from common import BRAND_FOOTER, BRAND_LOGO, CUSTOM_EMOJI_PATTERN, SERVER_EMOJIS, StudioEmbed, TICKET_BANNER, VERIFICATION_BANNER, update_panel_banners


class BrandingTests(unittest.TestCase):
    def test_faq_banner_migration_changes_only_faq_image_once(self):
        documents = {'faq': {'title': 'Custom FAQ', 'description': 'Custom text', 'image_url': None},
                     'reglas': {'image_url': 'rules-banner'}}
        with patch('common.read_json', side_effect=[{}, documents]), patch('common.write_json') as save:
            update_faq_banner()
        self.assertEqual(documents['faq'], {'title': 'Custom FAQ', 'description': 'Custom text', 'image_url': FAQ_BANNER})
        self.assertEqual(documents['reglas']['image_url'], 'rules-banner')
        self.assertEqual(general_embeds.build_faq().to_embed().image.url, FAQ_BANNER)
        self.assertEqual(save.call_count, 2)
        with patch('common.read_json', return_value={'faq-banner-2026-10-03-v1': True}), patch('common.write_json') as save:
            update_faq_banner()
        save.assert_not_called()

    def test_faq_native_title_footer_unique_server_emojis_and_limits(self):
        data = general_embeds.build_faq().to_embed().to_dict()
        self.assertIn('𝙿𝚁𝙴𝙶𝚄𝙽𝚃𝙰𝚂', data['title'])
        self.assertEqual(data['footer']['text'], BRAND_FOOTER)
        self.assertEqual(len(data['fields']), 7)
        text = data['title'] + data['description'] + ''.join(field['name'] + field['value'] for field in data['fields'])
        ids = CUSTOM_EMOJI_PATTERN.findall(text)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 9)
        self.assertLess(len(text) + len(BRAND_FOOTER), 6000)

    def test_faq_install_does_not_overwrite_existing_embeds_or_custom_faq(self):
        documents = {'reglas': {'title': 'Custom rules'}}
        with patch('general_embeds.read_json', return_value=documents), patch('general_embeds.write_json') as save:
            general_embeds.ensure_faq()
        self.assertEqual(documents['reglas'], {'title': 'Custom rules'})
        self.assertIn('faq', documents)
        save.assert_called_once()
        documents['faq'] = {'title': 'Edited FAQ'}
        with patch('general_embeds.read_json', return_value=documents), patch('general_embeds.write_json') as save:
            general_embeds.ensure_faq()
        save.assert_not_called()
        self.assertEqual(documents['faq']['title'], 'Edited FAQ')

    def test_ticket_emojis_migration_preserves_labels_and_descriptions(self):
        options = {key: {'label': 'Custom label', 'description': 'Custom text', 'emoji': 'old'}
                   for key in TICKET_OPTION_EMOJIS}
        with patch('common.read_json', side_effect=[{}, options]), patch('common.write_json') as save:
            update_ticket_option_emojis()
        for key, option in options.items():
            self.assertEqual(option, {'label': 'Custom label', 'description': 'Custom text', 'emoji': TICKET_OPTION_EMOJIS[key]})
        self.assertEqual(len(set(option['emoji'] for option in options.values())), 5)
        self.assertEqual(save.call_count, 2)
        with patch('common.read_json', return_value={'ticket-option-emojis-2026-10-03-v1': True}), patch('common.write_json') as save:
            update_ticket_option_emojis()
        save.assert_not_called()

    def test_default_ticket_options_use_only_server_emojis(self):
        for key, option in ticket.ticket_options.items():
            self.assertEqual(option['emoji'], TICKET_OPTION_EMOJIS[key])
            self.assertIsNotNone(CUSTOM_EMOJI_PATTERN.fullmatch(option['emoji']))

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

    def test_verification_green_migration_only_changes_color_once(self):
        document = {'color': '#8A001E', 'title': 'Title', 'description': 'Description', 'image_url': 'banner'}
        with patch('common.read_json', side_effect=[{}, {'verification_2': document}]), patch('common.write_json') as save:
            update_verification_color()
        self.assertEqual(document, {'color': '#2ECC71', 'title': 'Title', 'description': 'Description', 'image_url': 'banner'})
        self.assertEqual(save.call_count, 2)
        self.assertEqual(verificacion.EmbedBuilder().to_embed().color.value, 0x2ECC71)
        with patch('common.read_json', return_value={'verification-green-2026-10-03-v1': True}), patch('common.write_json') as save:
            update_verification_color()
        save.assert_not_called()

    def test_verification_migration_uses_user_provided_emojis_preserving_settings(self):
        documents = {'verification_2': {'title': 'Title', 'image_url': 'banner',
            'description': '<:bad:123> Este procedimiento garantiza una experiencia **ORDENADA **y **PERSONALIZADA **dentro de nuestra comunidad.\n\n<:bad:456> Por favor, **HAZ CLIC EN EL BOTÓN INFERIOR** para continuar con la verificación.'}}
        with patch('common.read_json', side_effect=[{}, documents]), patch('common.write_json') as save:
            update_verification_emojis()
        description = documents['verification_2']['description']
        self.assertIn(SERVER_EMOJIS['document'] + ' Este procedimiento', description)
        self.assertIn(SERVER_EMOJIS['online'] + ' Por favor,', description)
        self.assertIn('**INGRESA EL CÓDIGO**', description)
        self.assertNotIn('<:bad:', description)
        self.assertEqual(documents['verification_2']['image_url'], 'banner')
        self.assertEqual(documents['verification_2']['title'], 'Title')
        self.assertEqual(save.call_count, 2)
        with patch('common.read_json', return_value={'verification-emojis-2026-10-03-v1': True}), patch('common.write_json') as save:
            update_verification_emojis()
        save.assert_not_called()

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

"""Regression checks for the redesigned login page.
This suite must not depend on real user records.
"""
import unittest
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree
from app import app
ROOT = Path(__file__).resolve().parent.parent
class FormInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.inputs = {}
        self.labels = set()
        self.buttons = []
        self.anchors = []
        self.scripts = 0
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.forms.append(attrs)
        if tag == 'input':
            self.inputs[attrs.get('name', attrs.get('id'))] = attrs
        if tag == 'label':
            self.labels.add(attrs.get('for'))
        if tag == 'button':
            self.buttons.append(attrs)
        if tag == 'a':
            self.anchors.append(attrs)
        if tag == 'script':
            self.scripts += 1
class LoginVisualStructureTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
    def test_login_keeps_authentication_contract(self):
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        inspector = FormInspector()
        inspector.feed(html)
        self.assertEqual(len(inspector.forms), 1)
        self.assertEqual(inspector.forms[0]['method'], 'POST')
        self.assertEqual(inspector.forms[0]['action'], '/login')
        self.assertEqual(inspector.inputs['email']['type'], 'email')
        self.assertEqual(inspector.inputs['senha']['type'], 'password')
        self.assertIn('required', inspector.inputs['email'])
        self.assertIn('required', inspector.inputs['senha'])
        self.assertIn('email', inspector.labels)
        self.assertIn('senha', inspector.labels)
        self.assertIn('remember', inspector.inputs)
        self.assertEqual(inspector.inputs['senha']['autocomplete'], 'current-password')
    def test_accessibility_and_links(self):
        html = self.client.get('/login').get_data(as_text=True)
        inspector = FormInspector()
        inspector.feed(html)
        self.assertTrue(any(b.get('aria-controls') == 'senha' and b.get('type') == 'button'
                            for b in inspector.buttons))
        self.assertIn('neuro-ajuda', html)
        self.assertTrue(any(a.get('href') == '#neuro-ajuda' for a in inspector.anchors))
        self.assertTrue(any(a.get('href') == '/register' for a in inspector.anchors))
        self.assertIn('neuro-hero.svg', html)
        self.assertIn('login-v2.css', html)
        self.assertIn('aria-label=', html)
        self.assertNotIn('href="#"', html)
    def test_responsive_css_and_valid_svg(self):
        css = (ROOT / 'static' / 'login-v2.css').read_text(encoding='utf-8-sig')
        self.assertEqual(css.count('{'), css.count('}'))
        self.assertIn('@media (max-width: 860px)', css)
        self.assertIn('@media (max-width: 520px)', css)
        self.assertIn('prefers-reduced-motion', css)
        self.assertIn('grid-template-columns', css)
        svg = ElementTree.parse(ROOT / 'static' / 'neuro-hero.svg')
        self.assertTrue(svg.getroot().tag.endswith('svg'))
if __name__ == '__main__':
    unittest.main()

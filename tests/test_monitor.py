import calendar
from datetime import date
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from monitor import decide


class StateTests(unittest.TestCase):
    config = {'target_date': '2026-10-08', 'people': 2, 'notification': 'telegram', 'errors_before_alert': 3, 'url': 'https://reservation-spa.yonahotel.com/'}

    def transition(self, state, offers):
        return decide(state, None if offers is None else {'offers': offers}, self.config, 'TEST TIME')

    def test_initial_unavailable_notifies_once(self):
        state, message = self.transition({}, [])
        self.assertIn('initialisee', message)
        same, message = self.transition(state, [])
        self.assertEqual(same, state)
        self.assertIsNone(message)

    def test_available_no_spam_reappears(self):
        state, message = self.transition({}, ['Day'])
        self.assertIn('DISPONIBILITE', message)
        state, message = self.transition(state, ['Day'])
        self.assertIsNone(message)
        state, message = self.transition(state, [])
        self.assertIsNone(message)
        state, message = self.transition(state, ['Night'])
        self.assertIn('Night', message)

    def test_error_keeps_previous_availability(self):
        state, _ = self.transition({}, ['Day'])
        for n in range(1, 4):
            state, message = self.transition(state, None)
            self.assertEqual(state['offers'], ['Day'])
            self.assertEqual(state['failures'], n)
            self.assertEqual(message is not None, n == 3)
        state, message = self.transition(state, None)
        self.assertIsNone(message)
        state, message = self.transition(state, ['Day'])
        self.assertIn('retablie', message)
        self.assertNotIn('DISPONIBILITE', message)

    def test_additional_formula_notifies(self):
        state, _ = self.transition({}, ['Day'])
        _, message = self.transition(state, ['Day', 'Night'])
        self.assertIn('DISPONIBILITE', message)

    def test_changed_target_reinitializes(self):
        state, _ = self.transition({}, [])
        config = {**self.config, 'people': 3}
        _, message = decide(state, {'offers': []}, config, 'TEST TIME')
        self.assertIn('initialisee', message)


def fixture(offers=None, target_disabled=False, people=2, month_name='OCTOBRE', markers=True, legends=True, pseudo=False, broken_grid=False):
    offers = offers if offers is not None else {'2026-10-02': ['Day'], '2026-10-06': ['Night']}
    dates = list(calendar.Calendar(firstweekday=0).itermonthdates(2026, 10))
    # The screenshot includes six rows, including the following month.
    from datetime import timedelta
    while len(dates) < 42:
        dates.append(dates[-1] + timedelta(days=1))
    cells = []
    for d in dates:
        iso = d.isoformat()
        disabled = ' disabled aria-disabled="true"' if target_disabled and iso == '2026-10-08' else ''
        kind = offers.get(iso, []) if markers else []
        classes = 'cell ' + ' '.join('has-' + v.lower() for v in kind)
        dots = '' if pseudo else ''.join(f'<i class="dot {v.lower()}"></i>' for v in kind)
        label = 17 if broken_grid and iso == '2026-10-08' else d.day
        cells.append(f'<button class="{classes}"{disabled}><span>{label}</span>{dots}</button>')
    legend = '<aside><p><i class="dot day"></i><span>Day Spa disponible</span></p><p><i class="dot night"></i><span>Night Spa disponible</span></p></aside>' if legends else ''
    return '''<!doctype html><html><head><style>
    body { font-family: sans-serif; background: #111; color: #bbb; }
    .calendar {width: 420px; padding: 16px; background: #222;}
    .week, .days {display: grid; grid-template-columns: repeat(7, 54px); gap: 5px;}
    .week span {text-align:center; padding:10px 0;}
    h2 {text-align:center;}
    .cell {height:54px; border:1px solid #555; background:#333; color:white; position:relative;}
    .dot {display:inline-block; height:8px; width:8px; border-radius:50%;}
    .day {background:rgb(76,175,80);} .night {background:rgb(33,150,243);}
    .cell .dot {position:absolute; right:4px; bottom:4px;}
    aside {position:absolute; left:510px; top:300px;} aside p {display:flex; align-items:center; gap:16px;}
    .has-day::after {content:"";position:absolute;right:4px;bottom:4px;width:8px;height:8px;background:rgb(76,175,80);border-radius:50%;}
    .has-night::before {content:"";position:absolute;right:14px;bottom:4px;width:8px;height:8px;background:rgb(33,150,243);border-radius:50%;}
    </style></head><body><div><span>''' + str(people) + ''' personnes</span></div><section class="calendar"><h2>''' + month_name + ''' 2026</h2><div class="week">''' + ''.join(f'<span>{d}</span>' for d in ['LU','MA','ME','JE','VE','SA','DI']) + '''</div><div class="days">''' + ''.join(cells) + '</div></section>' + legend + '</body></html>'


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        args = {'headless': True}
        if os.getenv('PW_EXECUTABLE_PATH'):
            args['executable_path'] = os.environ['PW_EXECUTABLE_PATH']
        cls.browser = cls.pw.chromium.launch(**args)
        cls.page = cls.browser.new_page(viewport={'width':1280, 'height':1000})
        cls.adapter = (ROOT / 'calendar.js').read_text()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def read(self, **kwargs):
        self.page.set_content(fixture(**kwargs))
        return self.page.evaluate(self.adapter, {'target':'2026-10-08', 'people':2})

    def test_unavailable_with_other_valid_markers(self):
        out = self.read()
        self.assertTrue(out['ready'], out)
        self.assertEqual(out['offers'], [])
        self.assertEqual(out['status'], 'unavailable')

    def test_day(self):
        out = self.read(offers={'2026-10-08':['Day']})
        self.assertTrue(out['ready'], out)
        self.assertEqual(out['offers'], ['Day'])

    def test_night(self):
        out = self.read(offers={'2026-10-08':['Night']})
        self.assertTrue(out['ready'], out)
        self.assertEqual(out['offers'], ['Night'])

    def test_both_formulas(self):
        out = self.read(offers={'2026-10-08':['Day','Night']})
        self.assertTrue(out['ready'], out)
        self.assertEqual(out['offers'], ['Day','Night'])

    def test_css_pseudo_markers(self):
        out = self.read(offers={'2026-10-08':['Night']}, pseudo=True)
        self.assertTrue(out['ready'], out)
        self.assertEqual(out['offers'], ['Night'])

    def test_next_month_eighth_does_not_match(self):
        out = self.read(offers={'2026-11-08':['Day']})
        self.assertTrue(out['ready'], out)
        self.assertEqual(out['offers'], [])
        day8 = [d for d in out['days'] if d['day'] == 8]
        self.assertEqual(len(day8), 2)

    def test_wrong_people(self):
        self.assertFalse(self.read(people=3)['ready'])

    def test_wrong_month(self):
        self.assertFalse(self.read(month_name='NOVEMBRE')['ready'])

    def test_missing_legends_unknown(self):
        self.assertFalse(self.read(legends=False)['ready'])

    def test_all_missing_markers_unknown(self):
        self.assertFalse(self.read(offers={})['ready'])

    def test_explicitly_disabled(self):
        out = self.read(offers={}, target_disabled=True)
        self.assertTrue(out['ready'], out)
        self.assertEqual(out['offers'], [])

    def test_conflicting_status_unknown(self):
        self.assertFalse(self.read(offers={'2026-10-08':['Day']}, target_disabled=True)['ready'])

    def test_broken_grid_unknown(self):
        self.assertFalse(self.read(broken_grid=True)['ready'])

    def test_busy_page_unknown(self):
        self.page.set_content(fixture())
        self.page.locator('body').evaluate('(e) => e.setAttribute("aria-busy", "true")')
        out = self.page.evaluate(self.adapter, {'target':'2026-10-08', 'people':2})
        self.assertFalse(out['ready'])


if __name__ == '__main__':
    unittest.main()

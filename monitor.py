#!/usr/bin/env python3
"""Read-only Yonaguni calendar monitor; live validation is required.

Modes:
  diagnostic: inspect the public calendar; save screenshot and redacted evidence.
  notification: send a test notification, without visiting the spa website.
  monitor: inspect, persist state, and notify on newly observed availability.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from notify import NotificationError, send
from state_store import StateError, Store

ROOT = Path(__file__).resolve().parent
PARIS = ZoneInfo('Europe/Paris')


class CheckError(RuntimeError):
    pass


def config_load() -> dict:
    config = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
    date.fromisoformat(config['target_date'])
    if not isinstance(config.get('people'), int) or config['people'] < 1:
        raise ValueError('Le nombre de personnes doit etre un entier positif.')
    if config.get('url') != 'https://reservation-spa.yonahotel.com/':
        raise ValueError('Ce script est configure exclusivement pour le site Yonaguni fourni.')
    return config


def expired(config: dict) -> bool:
    return datetime.now(PARIS).date() > date.fromisoformat(config['target_date'])


def public_url(value: str) -> str:
    parsed = urlparse(value)
    return f'{parsed.scheme}://{parsed.netloc}{parsed.path}' if parsed.scheme in ('http','https') else parsed.scheme


def summary(message: str) -> None:
    print(message, flush=True)
    path = os.getenv('GITHUB_STEP_SUMMARY')
    if path:
        with open(path, 'a', encoding='utf-8') as out:
            out.write(message + '\n\n')


def inspect_calendar(config: dict, diagnostic: bool = False) -> dict:
    from playwright.sync_api import sync_playwright

    adapter = (ROOT / 'calendar.js').read_text(encoding='utf-8')
    report = {'target': config['target_date'], 'people': config['people'], 'checked_at': datetime.now(PARIS).isoformat(), 'result': None}
    folder = ROOT / 'diagnostics'
    inflight = set()
    failures = []
    last_observations = []
    result = None
    context = None
    browser = None
    page = None

    def relevant(request):
        host = urlparse(request.url).hostname or ''
        return request.resource_type in ('xhr', 'fetch') and not any(host == d or host.endswith('.' + d) for d in ('google-analytics.com', 'googletagmanager.com', 'doubleclick.net'))

    def request_started(request):
        if relevant(request):
            inflight.add(request)

    def request_finished(request):
        inflight.discard(request)

    def request_failed(request):
        if relevant(request):
            inflight.discard(request)
            failures.append({'kind': 'network', 'url': public_url(request.url)})

    def response_received(response):
        if relevant(response.request) and response.status >= 400:
            failures.append({'kind': 'http', 'status': response.status, 'url': public_url(response.url)})

    def save_diagnostics():
        if not diagnostic:
            return
        folder.mkdir(exist_ok=True)
        report['network_failures'] = failures[:20]
        report['observations'] = last_observations
        report['result'] = result
        report['pages'] = []
        if context:
            for index, item in enumerate(context.pages[:3]):
                try:
                    item.screenshot(path=str(folder / f'page-{index + 1}.png'), full_page=True, timeout=10000)
                    report['pages'].append({'url': public_url(item.url), 'text': item.locator('body').inner_text(timeout=3000)[:16000]})
                except Exception:
                    report['pages'].append({'screenshot_error': True})
        (folder / 'rapport.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

    try:
        with sync_playwright() as pw:
            options = {'headless': True}
            if os.getenv('PW_EXECUTABLE_PATH'):
                options['executable_path'] = os.environ['PW_EXECUTABLE_PATH']
            browser = pw.chromium.launch(**options)
            context = browser.new_context(locale='fr-FR', timezone_id='Europe/Paris', viewport={'width': 1280, 'height': 1000})
            context.on('request', request_started)
            context.on('requestfinished', request_finished)
            context.on('requestfailed', request_failed)
            context.on('response', response_received)
            page = context.new_page()
            try:
                response = page.goto(config['url'], wait_until='domcontentloaded', timeout=45000)
                if response is not None and response.status >= 400:
                    raise CheckError(f'Le site a repondu HTTP {response.status}. Aucun contournement n\'est tente.')
                link = page.get_by_role('link', name=re.compile(r'r[e\u00e9]server\s+yonaguni', re.I))
                button = page.get_by_role('button', name=re.compile(r'r[e\u00e9]server\s+yonaguni', re.I))
                link.or_(button).first.click(timeout=20000)
                deadline = time.monotonic() + 60
                signature = None
                stable_since = None
                while time.monotonic() < deadline:
                    if failures:
                        raise CheckError('Une requete de donnees a echoue. Aucune conclusion sur les disponibilites.')
                    observations = []
                    for open_page in context.pages:
                        for frame in open_page.frames:
                            try:
                                observation = frame.evaluate(adapter, {'target': config['target_date'], 'people': config['people']})
                            except Exception:
                                continue  # A frame may be navigating; never treat this as unavailable.
                            observations.append(observation)
                    last_observations = observations
                    ready = [o for o in observations if o.get('ready')]
                    if len(ready) == 1 and not inflight:
                        candidate = ready[0]
                        current = json.dumps({'offers': candidate['offers'], 'days': candidate['days'], 'legend': candidate['legend']}, sort_keys=True)
                        if current != signature:
                            signature, stable_since = current, time.monotonic()
                        elif stable_since is not None and time.monotonic() - stable_since >= 3:
                            # This stability check supplements explicit DOM and network checks.
                            # It is not a claim that an arbitrary sleep proves API completion.
                            result = candidate
                            return candidate
                    else:
                        signature, stable_since = None, None
                    page.wait_for_timeout(750)
                reasons = sorted({o.get('reason', 'Resultat ambigu') for o in last_observations if not o.get('ready')})
                raise CheckError('Lecture du calendrier impossible. ' + ' '.join(reasons)[:500])
            except CheckError:
                raise
            except Exception as exc:
                raise CheckError(f'Navigation ou lecture interrompue ({type(exc).__name__}). Lancer le diagnostic.') from None
            finally:
                save_diagnostics()
                context.close()
                browser.close()
    except CheckError:
        raise
    except Exception as exc:
        if diagnostic and not (folder / 'rapport.json').exists():
            folder.mkdir(exist_ok=True)
            report['browser_error'] = type(exc).__name__
            (folder / 'rapport.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        raise CheckError(f'Navigateur indisponible ({type(exc).__name__}). Verifier l\'installation de Chromium.') from None


def decide(state: dict, result: dict | None, config: dict, timestamp: str) -> tuple[dict, str | None]:
    """Pure state transition. Failure keeps the last successfully observed offers."""
    key = f"{config['target_date']}|{config['people']}|{config.get('notification', 'telegram')}"
    old = state.copy() if state.get('key') == key else {'key': key}
    new = old.copy()
    label = f"{date.fromisoformat(config['target_date']).strftime('%d/%m/%Y')} - {config['people']} personnes"
    threshold = max(1, int(config.get('errors_before_alert', 3)))
    if result is None:
        new['failures'] = min(threshold, int(old.get('failures', 0)) + 1)
        if new['failures'] >= threshold and not old.get('error_alerted'):
            new['error_alerted'] = True
            return new, f"Yonaguni - surveillance en erreur\n{label}\n{threshold} verifications consecutives ont echoue. Cela ne signifie PAS que la date est complete.\nConsulte Actions sur GitHub et relance le diagnostic.\n{timestamp}"
        return new, None
    offers = sorted(set(result['offers']))
    added = set(offers) - set(old.get('offers', []))
    new.update(started=True, offers=offers, failures=0, error_alerted=False)
    if added:
        return new, f"DISPONIBILITE YONAGUNI\n{label}\nFormule(s) signalee(s) par le calendrier : {' / '.join(offers)} Spa\nObserve le {timestamp}. Disponibilite a confirmer lors de la reservation.\n{config['url']}"
    if not old.get('started'):
        return new, f"Surveillance Yonaguni initialisee\n{label} - Day ou Night\nAucune disponibilite signalee a cette verification.\n{timestamp}\n{config['url']}"
    if old.get('error_alerted'):
        return new, f"Surveillance Yonaguni retablie\n{label}\nLa lecture du calendrier fonctionne de nouveau.\n{timestamp}"
    return new, None


def once(config: dict, mode: str) -> int:
    if mode == 'notification':
        send(config, 'Test Yonaguni : les notifications fonctionnent. Ce message ne confirme aucune disponibilite et n\'active pas la surveillance.')
        summary('Message de test envoye. Verifier sa reception sur le telephone.')
        return 0
    if expired(config):
        summary('Date depassee a Paris : aucune visite du site et aucune alerte de disponibilite.')
        return 0
    if mode == 'diagnostic':
        result = inspect_calendar(config, diagnostic=True)
        summary(f"Diagnostic : {result['status']} pour le {config['target_date']}, {config['people']} personnes. Offres : {result['offers'] or 'aucune'}.\nComparer le rapport et la capture avec le site avant d'activer MONITOR_ENABLED.")
        return 0
    store = Store()
    state = store.load()
    try:
        result = inspect_calendar(config)
    except CheckError as exc:
        result = None
        summary(f'ERREUR DE VERIFICATION : {exc}')
    stamp = datetime.now(PARIS).strftime('%d/%m/%Y a %H:%M:%S (Paris)')
    new_state, message = decide(state, result, config, stamp)
    if message:
        send(config, message)  # Do not mark a notification as sent before success.
    store.save(new_state)
    if result:
        summary(f"{stamp} : {config['target_date']}, {config['people']} personnes - {result['status']}; {result['offers'] or 'aucune offre signalee'}.\n{result['evidence']}")
        return 0
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('diagnostic','notification','monitor'), default='diagnostic')
    parser.add_argument('--loop-seconds', type=int, default=0, help='Local only; at least 120 seconds. The computer must stay awake.')
    args = parser.parse_args()
    if args.loop_seconds and (args.mode != 'monitor' or args.loop_seconds < 120 or os.getenv('GITHUB_ACTIONS') == 'true'):
        parser.error('La boucle est reservee au mode monitor local, avec un intervalle >= 120 secondes.')
    try:
        config = config_load()
        while True:
            start = time.monotonic()
            code = once(config, args.mode)
            if not args.loop_seconds or expired(config):
                return code
            time.sleep(max(0, args.loop_seconds - (time.monotonic() - start)))
    except KeyboardInterrupt:
        summary('Surveillance arretee manuellement.')
        return 0
    except (CheckError, NotificationError, StateError, ValueError, KeyError, OSError) as exc:
        summary(f'ECHEC : {exc}')
        return 2


if __name__ == '__main__':
    sys.exit(main())

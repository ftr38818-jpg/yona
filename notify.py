"""Notification transports. Never print tokens, topics, or request URLs."""
import json
import os
import urllib.error
import urllib.request


class NotificationError(RuntimeError):
    pass


def send(config: dict, message: str) -> None:
    provider = config.get('notification', 'telegram')
    if provider == 'telegram':
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
        if not token or not chat:
            raise NotificationError('Configurer TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans les secrets.')
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        payload = {'chat_id': chat, 'text': message, 'link_preview_options': {'is_disabled': True}}
    elif provider == 'ntfy':
        topic = os.environ.get('NTFY_TOPIC', '').strip()
        if not topic or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in topic):
            raise NotificationError('Configurer un secret NTFY_TOPIC compose de lettres, chiffres, _ et -.')
        url = 'https://ntfy.sh/'
        payload = {'topic': topic, 'title': 'Yonaguni - surveillance', 'message': message, 'priority': 4, 'click': config['url']}
    else:
        raise NotificationError('Transport inconnu : telegram ou ntfy sont acceptes.')
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise NotificationError(f'Le service de notification a repondu HTTP {exc.code}.') from None
    except (OSError, ValueError):
        raise NotificationError('Echec de connexion au service de notification.') from None
    if provider == 'telegram' and data.get('ok') is not True:
        raise NotificationError('Telegram n\'a pas confirme la livraison au bot destinataire.')

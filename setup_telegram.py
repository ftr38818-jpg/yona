#!/usr/bin/env python3
"""Get your dedicated bot's private chat ID without printing its token."""
from getpass import getpass
import json
import sys
import urllib.error
import urllib.request


def main():
    print('Creer un NOUVEAU bot dedie avec @BotFather, puis lui envoyer /start dans Telegram.')
    token = getpass('Token du bot (saisie masquee, non enregistree) : ').strip()
    if not token:
        print('Token vide. Arret.')
        return 1
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/getUpdates',
        data=json.dumps({'timeout': 0, 'allowed_updates': ['message']}).encode(),
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        print(f'Telegram : HTTP {exc.code}. Verifier le token et utiliser un bot dedie sans webhook.')
        return 1
    except (OSError, ValueError):
        print('Telegram inaccessible ou reponse invalide.')
        return 1
    if not result.get('ok'):
        print('Telegram n\'a pas accepte la requete.')
        return 1
    ids = sorted({item.get('message', {}).get('chat', {}).get('id') for item in result.get('result', []) if item.get('message', {}).get('chat', {}).get('type') == 'private'})
    if not ids:
        print('Aucun message prive recu. Envoyer /start au nouveau bot puis relancer ce script.')
        return 1
    print('Identifiant(s) de conversation privee :')
    for chat_id in ids:
        print(chat_id)
    print('Copier votre identifiant dans le secret GitHub TELEGRAM_CHAT_ID.')
    print('Copier le token BotFather dans TELEGRAM_BOT_TOKEN. Ne pas les publier dans les fichiers du depot.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

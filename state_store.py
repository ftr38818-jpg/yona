"""Persistent state, in a separate GitHub branch, or a local JSON file.

Only target/date/status/error counts are stored. No notification credentials.
A GitHub API failure is an error, never an empty state to silently ignore.
"""
import base64
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


class StateError(RuntimeError):
    pass


class Store:
    branch = 'monitor-state'
    name = '.monitor-state.json'

    def __init__(self) -> None:
        self.token = os.getenv('GITHUB_TOKEN', '')
        self.repo = os.getenv('GITHUB_REPOSITORY', '')
        self.remote = os.getenv('GITHUB_ACTIONS') == 'true'
        self.sha = None
        self.original = {}
        self.path = Path('.state.json')
        if self.remote and (not self.token or not self.repo):
            raise StateError('Jeton GitHub ou nom du depot absent.')

    def api(self, method: str, route: str, payload=None, allow_404=False):
        url = f'https://api.github.com/repos/{self.repo}/{route}'
        data = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method=method, headers={
            'Authorization': f'Bearer {self.token}', 'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json',
            'User-Agent': 'yonaguni-availability-monitor',
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            raise StateError(f'API GitHub : erreur HTTP {exc.code}. Verifier les permissions du workflow.') from None
        except (OSError, ValueError):
            raise StateError('API GitHub inaccessible ou reponse invalide.') from None

    def load(self) -> dict:
        if self.remote:
            file = self.api('GET', f'contents/{self.name}?ref={self.branch}', allow_404=True)
            if file is None:
                value = {}
            else:
                self.sha = file['sha']
                try:
                    value = json.loads(base64.b64decode(file['content']))
                except (ValueError, KeyError):
                    raise StateError('Le fichier d\'etat GitHub est illisible.') from None
        else:
            try:
                value = json.loads(self.path.read_text()) if self.path.exists() else {}
            except (ValueError, OSError):
                raise StateError('Le fichier d\'etat local est illisible.') from None
        if not isinstance(value, dict):
            raise StateError('Le fichier d\'etat doit contenir un objet JSON.')
        self.original = value.copy()
        return value

    def save(self, value: dict) -> None:
        if value == self.original:
            return
        content = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
        if self.remote:
            branch = self.api('GET', f'git/ref/heads/{self.branch}', allow_404=True)
            if branch is None:
                default = urllib.parse.quote(os.getenv('DEFAULT_BRANCH', 'main'), safe='')
                source = self.api('GET', f'git/ref/heads/{default}')
                self.api('POST', 'git/refs', {'ref': f'refs/heads/{self.branch}', 'sha': source['object']['sha']})
            payload = {'message': 'Update monitoring state', 'branch': self.branch, 'content': base64.b64encode(content.encode()).decode()}
            if self.sha:
                payload['sha'] = self.sha
            result = self.api('PUT', f'contents/{self.name}', payload)
            self.sha = result['content']['sha']
        else:
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(content, encoding='utf-8')
            temporary.replace(self.path)
        self.original = value.copy()

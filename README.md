# Alerte Yonaguni - 8 octobre 2026

**Version a tester sur le site réel avant activation. La surveillance n'est pas encore active.**

Le projet recherche une disponibilité pour **2 personnes, le jeudi 8 octobre 2026, Day Spa ou Night Spa**. Le nombre de personnes est une hypothèse reprise de la capture fournie : le vérifier avant de lancer.

La partie de lecture du calendrier a été construite a partir de la capture, sans accès au calendrier dynamique réel depuis l'environnement de développement. Les tests locaux sur des pages de simulation ne constituent pas une validation du site Yonaguni. Une adaptation du fichier `calendar.js` peut etre nécessaire après le premier diagnostic.

## Choix retenus

GitHub Actions sur un dépôt **public**, avec un déclenchement programmé toutes les **5 minutes** ; Telegram par défaut. Les runners standard sont gratuits pour les dépôts publics [1]. Les messages Telegram sont gratuits a cette échelle [3]. Aucun abonnement, serveur payant ou action de réservation automatique n'est prévu.

Le minimum du planificateur natif GitHub est 5 minutes. GitHub peut retarder ou omettre des exécutions [2] : **ce n'est pas une promesse de detection en moins de 5 minutes**. Le cron est décalé aux minutes 02, 07, 12, etc. Il ne s'exécuté que du 1 au 8 octobre et le script contrôle aussi l'année 2026 et la date a Paris.

## Installation

### 1. Mettre les fichiers dans un dépôt public

Creer un dépôt public, par exemple `yonaguni-alert`, puis y envoyer le contenu du dossier extrait. Les fichiers `monitor.py`, `calendar.js` et `config.json` doivent etre **a la racine du dépôt**, pas dans un sous-dossier supplémentaire.

Le dossier **`.github` est parfois masqué par le système**. Vérifier dans GitHub que `.github/workflows/monitor.yml` existe bien. Sans ce fichier, rien ne se lancera.

Avec Git, depuis le dossier extrait et après création d'un dépôt vide sur GitHub :

```bash
git init -b main
git add .
git commit -m "Add Yonaguni availability monitor"
git remote add origin https://github.com/TON_COMPTE/yonaguni-alert.git
git push -u origin main
```

Remplacer `TON_COMPTE`. L'authentification GitHub doit déjà etre configuree ou etre faite avec les outils habituels de GitHub. Ne pas coller de token dans ces commandes ni dans les fichiers.

### 2. Faire le premier diagnostic, sans aucun secret

Dans **Actions > Yonaguni - disponibilités > Run workflow**, choisir le mode **`diagnostic`**, sur la branche par défaut, puis lancer.

Une fois l'exécution terminée, ouvrir son compte rendu et télécharger l'artefact `yonaguni-diagnostic-...` en bas de la page. Il contient une capture du navigateur et `rapport.json`.

Vérifier ensemble ces éléments : le calendrier montre octobre 2026 ; le compteur montre 2 personnes ; le résultat concerne `2026-10-08` ; les points Day/Night détectés pour les autres jours correspondent visuellement a la capture. Ouvrir aussi le site normalement pour comparer. Le script ne clique pas le 8 et ne bloque aucune place.

**Si le diagnostic échoue, ou si son interpretation contredit l'image, laisser la surveillance désactivée.** Le rapport et la capture servent a adapter le lecteur au vrai HTML du site. Ne pas remplacer une erreur par un résultat "indisponible".

Les captures et le texte de diagnostic peuvent etre visibles aux lecteurs du dépôt public. Le script ne saisit aucune donnée personnelle, ne conservé pas les cookies, ne produit pas d'archive HAR et ne capture pas les échanges Telegram. Les artefacts de diagnostic expirent après un jour. Les vérifier avant de les partager.

### 3. Brancher Telegram

Dans Telegram, ouvrir **@BotFather**, envoyer `/newbot` et suivre les indications. Conserver le token comme un mot de passe. Ouvrir ensuite la conversation avec **le nouveau bot** et lui envoyer `/start` [4].

Pour trouver l'identifiant de cette conversation sans transmettre le token a un bot tiers, lancer localement, avec Python 3 :

```bash
python setup_telegram.py
```

Sur les systemes ou la commande s'appelle `python3`, utiliser `python3`. Le script demande le token en saisie masquee et n'affiche que l'identifiant de conversation. Il ne stocke pas le token. Utiliser un bot neuf, dédié a cette surveillance.

Dans le dépôt, ouvrir **Settings > Secrets and variables > Actions > Secrets > New repository secret** [5] et ajouter :

| Nom du secret | Valeur |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Le token fourni par BotFather |
| `TELEGRAM_CHAT_ID` | L'identifiant numérique obtenu avec le script |

Revenir dans Actions et lancer le mode **`notification`**. Vérifier la réception sur le téléphone et les autorisations de notification. Ce test ne visite pas le site et ne signifie pas qu'une place est disponible.

### 4. Activer la surveillance

Après un diagnostic conforme et un test de notification reçu, lancer manuellement le mode **`monitor`**. La première lecture réussie envoie soit une alerte de disponibilité, soit un message d'initialisation sans disponibilité.

Puis aller dans **Settings > Secrets and variables > Actions > Variables**, ajouter la variable de dépôt :

```text
MONITOR_ENABLED = true
```

Le mot `true` doit etre en minuscules. **Les exécutions programmées sont ignorees tant que cette variable n'existe pas ou ne vaut pas `true`.** Le lancement manuel reste possible indépendamment de cette variable.

Vérifier ensuite dans Actions que de nouvelles exécutions apparaissent. L'absence de message Telegram ne prouve pas a elle seule que le planificateur tourne toujours.

## Ce que fait le script

Il ouvre l'adresse d'entree, clique sur le lien ou bouton portant le texte "Reserver Yonaguni", puis examine la page et les cadres rendus par Chromium. Il contrôle le nombre de personnes, le mois, l'année, les jours de semaine et l'ordre de toutes les dates de la grille. Le deuxième numéro 8, appartenant au mois suivant, ne doit pas etre confondu avec le 8 octobre.

Les petits marqueurs verts et bleus sont compares aux couleurs des légendes Day/Night. Une simple classe CSS supposée ou le seul fait qu'un bouton soit cliquable ne suffit pas a produire une alerte. Le lecteur prend aussi en compte les pseudo-éléments CSS.

Une lecture attend la stabilité du calendrier et l'absence de requêtes de données en cours. Une erreur de chargement, un mois incorrect, un compteur absent, une grille ambigue, des légendes non reconnues ou des signaux contradictoires produisent une **erreur**, pas "aucune disponibilité". Quand toutes les dates sont sans marqueur et que la case cible n'a pas de désactivation explicite, il reste volontairement en erreur : il faut vérifier cette situation plutot que supposer que tout est complet.

Le lecteur **ne change pas le compteur de personnes et ne navigue pas entre les mois**. Il verifie les valeurs attendues a l'arrivee, conformement au parcours fourni. Si le site change ce comportement, le diagnostic doit servir a adapter la navigation.

Une nouvelle formule observée déclenche un message avec date, nombre de personnes, heure de vérification et adresse de réservation. La même disponibilité persistante ne produit pas un message toutes les 5 minutes. Une disparition observée puis une réapparition observée peut declencher une nouvelle alerte. Une place apparue et disparue entre deux passages peut etre manquée.

L'état anti-doublons est conservé dans `.monitor-state.json`, sur une branche GitHub distincte **`monitor-state`**, créée automatiquement. Cette branche ne doit pas devenir la branche par défaut. Le jeton automatique du workflow a besoin de la permission `contents: write`. Il ne faut pas ajouter de token GitHub personnel aux secrets pour cette fonction. La branche d'état contient des informations publiques sur cette recherche, mais aucun identifiant Telegram.

Les états ne sont enregistrés comme notifiés qu'après la réponse positive du service de messagerie. Une panne après l'envoi mais avant l'enregistrement de l'état peut exceptionnellement causer un doublon. Supprimer la branche d'état réinitialise aussi la mémoire.

Après trois erreurs consécutives de lecture, le script tente d'envoyer une alerte technique unique, puis une notification de reprise. Les erreurs d'installation, de notification ou d'accès au stockage d'état apparaissent comme des échecs dans GitHub Actions ; ce mécanisme ne garantit pas une alerte Telegram si Telegram ou GitHub est lui-même indisponible.

## Autre notification : ntfy

Le transport ntfy est déjà inclus. ntfy propose une application mobile et un envoi HTTP vers un sujet de notification [6]. Son utilisation peut eviter la création d'un bot Telegram.

Installer l'application, choisir un nom de sujet **long, aléatoire, non publié**, s'y abonner, puis mettre ce même nom dans le secret GitHub **`NTFY_TOPIC`**. Un exemple de generation locale :

```bash
python -c "import secrets; print('spa-' + secrets.token_hex(24))"
```

Dans `config.json`, remplacer seulement `"notification": "telegram"` par `"notification": "ntfy"`. Refaire le test `notification` avant l'activation.

**Sur le service public ntfy, un nom de sujet n'est pas une authentification : toute personne qui le connait peut lire ou publier sur ce sujet [6].** Ne pas utiliser un nom évident ou un exemple publié. Ne pas placer de données sensibles dans les messages. Les autorisations du téléphone et ses restrictions d'arrière-plan influencent la réception : vérifier le test en conditions reelles, écran verrouillé.

## Toutes les 2 minutes sur une machine déjà allumée

Le même programmé dispose d'un mode local toutes les 120 secondes. Il ne nécessite pas GitHub Actions pour tourner, mais l'ordinateur doit rester allumé, connecté et sans mise en veille. L'électricité et la connexion ne sont pas gratuites au sens strict.

Avec Python 3.12 ou 3.13, dans un environnement virtuel :

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python monitor.py --mode diagnostic
```

Configurer ensuite les mêmes secrets comme variables d'environnement locales, sans les enregistrer dans le dépôt. Le script ne charge pas automatiquement un fichier `.env`.

```bash
python monitor.py --mode notification
python monitor.py --mode monitor --loop-seconds 120
```

Ne pas lancer en parallèle cette boucle et le workflow programmé : ils auraient deux états indépendants et feraient des visites en double. Cette boucle est explicitement désactivée dans les runners GitHub.

## Arrêt, frais et limites

Pour arrêter, mettre `MONITOR_ENABLED` a `false` ou désactiver le workflow dans Actions. Le programmé ne visite plus le site après le 8 octobre 2026 a la date de Paris. Le cron n'a pas de champ "année" ; le contrôle Python empeche une nouvelle surveillance en octobre d'une autre année. Désactiver définitivement le workflow après usage.

Les caches et les artefacts ne sont pas un stockage illimité gratuit. Le projet ne conservé les captures que lors des diagnostics manuels, pendant un jour ; les caches de dependances ont une clé stable. Garder un dépôt public, les runners standard, un plafond de dépenses nul et vérifier les quotas partagés du compte [1]. Ne pas activer un runner payant ou une extension de quota pour ce projet.

Ce projet ne contourne ni captcha, ni blocage, ni limitation du site. Si le site refuse les accès ou demande de réduire la fréquence, désactiver ou ralentir la surveillance. Aucune réservation n'est effectuée automatiquement et une alerte calendrier ne garantit pas qu'une place sera encore disponible a l'ouverture du site.

## Tests et validation

```bash
python -m unittest discover -s tests -v
```

Le développement a exécuté **19 tests locaux réussis** : reconnaissance sur une grille simulée dans Chromium, Day/Night, pseudo-éléments CSS, date du mois suivant, erreurs et transitions anti-doublons. Trois tests HTTP supplementaires sont fournis dans `tests/test_navigation.py`, mais n'ont pas pu etre executes dans cet environnement, dont le navigateur interdit les navigations HTTP. Ils sont ignores par defaut. Pour les executer sur une machine autorisant le serveur local : `RUN_HTTP_TESTS=1 python -m unittest discover -s tests -v` (syntaxe Linux/macOS). La version de Playwright est épinglée a celle testée, pas annoncée comme la plus récente.

**Non testés ici : navigation sur le calendrier Yonaguni réel, déclenchement par un compte GitHub réel, livraison a ton compte Telegram/ntfy.** Le premier diagnostic et le test de notification sont donc indispensables.

## Références officielles

Documents consultés le 1 octobre 2026. Les contraintes des services peuvent évoluer.

```text
[1] GitHub Actions : facturation, runners publics et quotas
https://docs.github.com/en/billing/concepts/product-billing/github-actions
[2] GitHub : planification, minimum de 5 minutes et retards possibles
https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
[3] Telegram : gratuite et limites des messages de bots
https://core.telegram.org/bots/faq
[4] Telegram : creation d'un bot, token et premier contact
https://core.telegram.org/bots/tutorial
[5] GitHub : secrets des workflows
https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
[6] ntfy : demarrage et sujets publics
https://docs.ntfy.sh/
[7] Playwright : execution sur GitHub Actions
https://playwright.dev/python/docs/ci-intro
[8] GitHub : API de contenu pour le stockage de l'etat
https://docs.github.com/en/rest/repos/contents
```

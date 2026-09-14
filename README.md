# Ecclessia Manager

Application de gestion d'eglise reconstruite avec un stack serveur plus robuste:

- Backend: Django 5.x + Django Channels en ASGI
- Base de donnees: PostgreSQL
- Temps reel: Channels + Redis channel layer
- Frontend: Django Templates + Tailwind CSS + Alpine.js
- Deploiement: Render Web Service + Render Postgres + Render Redis

## Demarrage local

```bash
python -m pip install -r requirements.txt
npm install
npm run build:css
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Compte demo:

- Admin: `admin` / `admin12345`
- Extension: `nicosie_centre` / `extension12345`

## Variables d'environnement

Copier `.env.example` vers `.env` selon l'environnement:

- `DATABASE_URL`: connexion PostgreSQL
- `REDIS_URL`: connexion Redis pour Django Channels
- `SECRET_KEY`: cle Django
- `DEBUG`: `True` en local, `False` en production
- `ALLOWED_HOSTS`: domaines autorises
- `CSRF_TRUSTED_ORIGINS`: origines Render en HTTPS

## Architecture

Le projet separe les responsabilites principales:

- `apps.accounts`: profils et roles serveur (`admin`, `extension`)
- `apps.churches`: extensions locales et parametres generaux
- `apps.reports`: rapports de culte, calculs financiers, WebSocket events
- `apps.dashboard`: indicateurs et vues de synthese

Les calculs financiers vivent dans `apps/reports/services.py` afin que les vues, tableaux de bord et futurs exports utilisent la meme regle metier.

## Integrite financiere

Les nouveaux rapports conservent la devise de l'extension, le taux social et la
version de calcul au moment de leur creation. Modifier les parametres ou annoter
un rapport ne change pas ses chiffres. Les sauvegardes partielles recalculent les
totaux a partir des seuls champs effectivement enregistres.

Les montants saisis doivent etre positifs ou nuls. Le taux social est compris
entre 0 et 90 %, compte tenu de la dime de 10 %. Au plafond, les arrondis au centime
ne peuvent pas affecter plus que le montant collecte. Un deficit du solde reste
autorise. Les totaux sont separes par devise, sans conversion implicite.

Les rapports anterieurs a la migration `0002_financial_integrity` conservent
exactement leurs montants. Leur taux, version et devise restent inconnus : aucune
information historique n'est deduite des parametres actuels. Ils sont exclus des
consolidations monetaires et leurs finances sont verrouillees, y compris dans
l'administration ; les notes et effectifs restent modifiables. Toute reprise
de ces donnees necessite une validation des justificatifs et une migration
distincte. Le journal detaille des corrections financieres reste a mettre en place.

Pour une base existante, avant d'appliquer les nouvelles contraintes :

```bash
python manage.py check_financial_data
python manage.py migrate
```

Le controle fonctionne aussi sur le schema `0001`, ne modifie aucune donnee et
signale les identifiants des rapports incoherents ou des taux invalides. En cas
d'erreur, examiner les justificatifs et faire valider les corrections avant
migration ; ne pas recalculer globalement l'historique. Une valeur negative ou un
taux hors limites empechera l'installation de la contrainte correspondante.

Les notifications WebSocket sont reservees aux administrateurs applicatifs et
aux utilisateurs de l'extension concernee. Les droits sont reverifies lors de
chaque evenement. Une notification n'est publiee qu'apres commit ; un echec est
journalise et ne remet pas en cause la confirmation de sauvegarde. La livraison
des notifications reste sans garantie de reprise automatique.

## Verification

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check apps ecclessia_manager manage.py
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
npm ci
npm run build:css
```

Les tests utilisent une base de test Django, des donnees fictives et un canal
WebSocket en memoire. Ils couvrent aussi les commits, rollbacks et migrations
historiques. Aucun outil de verification statique des types n'est configure.
La CI execute ces controles sur PostgreSQL 16.

## Deploiement Render

`render.yaml` declare:

- un Web Service Python qui demarre Daphne en ASGI
- une base PostgreSQL
- un Redis utilise par `channels_redis`

Render execute:

```bash
pip install -r requirements.txt && npm install && npm run build:css && python manage.py collectstatic --noinput
python manage.py migrate && daphne -b 0.0.0.0 -p $PORT ecclessia_manager.asgi:application
```

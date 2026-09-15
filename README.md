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

Guide complet (Blueprint automatique **ou** creation manuelle des services,
variables d'environnement, post-deploiement, securite, depannage) :
voir **[DEPLOYMENT.md](./DEPLOYMENT.md)**.
# ECCLESIA-MANAGER

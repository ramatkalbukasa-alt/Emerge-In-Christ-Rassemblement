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

### Deploiement manuel (sans Blueprint)

Si vous preferez creer les services a la main dans le Dashboard Render plutot
que via `render.yaml` :

1. **Base de donnees** : New → PostgreSQL. Notez l'`Internal Database URL`
   une fois provisionnee.
2. **Redis** : New → Redis (plan Free ou superieur). Notez son
   `Internal Redis URL`.
3. **Web Service** : New → Web Service → connectez le depot Git.
   - Runtime : `Python 3` (Node/npm sont deja inclus dans l'image native,
     inutile d'ajouter un service Node separe).
   - Build Command :
     ```bash
     pip install -r requirements.txt && npm install && npm run build:css && python manage.py collectstatic --noinput
     ```
   - Start Command :
     ```bash
     python manage.py migrate && daphne -b 0.0.0.0 -p $PORT ecclessia_manager.asgi:application
     ```
   - Variables d'environnement a definir dans l'onglet *Environment* :

     | Variable | Valeur |
     | --- | --- |
     | `DJANGO_SETTINGS_MODULE` | `ecclessia_manager.settings` |
     | `PYTHON_VERSION` | `3.11.9` |
     | `SECRET_KEY` | generer une valeur aleatoire longue (bouton *Generate*) |
     | `DEBUG` | `False` |
     | `ALLOWED_HOSTS` | `<votre-service>.onrender.com` (ajoutez votre domaine perso le cas echeant) |
     | `CSRF_TRUSTED_ORIGINS` | `https://<votre-service>.onrender.com` |
     | `DATABASE_URL` | Internal Database URL de l'etape 1 |
     | `REDIS_URL` | Internal Redis URL de l'etape 2 |
     | `HSTS_SECONDS` *(optionnel)* | a definir uniquement une fois un domaine personnalise stable en HTTPS confirme (ex. `604800` pour 7 jours) |

4. Lancez le premier deploiement (*Manual Deploy* → *Deploy latest commit*).
5. Une fois en ligne, creez un compte admin :
   ```bash
   python manage.py createsuperuser
   ```
   via le *Shell* du service dans le Dashboard Render, ou `manage.py seed_demo`
   pour des donnees de demonstration (a ne pas utiliser en production reelle,
   les identifiants du jeu de demo sont publics dans ce README).

Ce chemin manuel utilise exactement les memes commandes que `render.yaml` :
les deux approches produisent un service identique.
# ECCLESIA-MANAGER

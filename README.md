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
- `apps.ministry`: registres des personnes et ouvriers, départements, règles financières par catégorie, caisses et remises.

## Registres, rapports par type et caisses

Le menu **Registres et caisses** donne accès aux personnes, ouvriers, départements,
rapports d’accueil et rapports financiers. Les filtres mensuels, trimestriels,
annuels ou personnalisés sont conservés dans les exports PDF et Excel.

Les règles et les parcours sont décrits dans
[PLAN_IMPLEMENTATION_RAPPORTS_REGISTRES.md](./PLAN_IMPLEMENTATION_RAPPORTS_REGISTRES.md).

Après mise à jour du code, sauvegarder la base puis exécuter :

```bash
python manage.py migrate --noinput
python manage.py audit_registries
npm run build:css
python manage.py collectstatic --noinput
```

Sur PowerShell, utiliser `npm.cmd run build:css` si l’exécution de `npm.ps1` est
désactivée. La migration reprend les personnes des anciens cultes ; leurs dates
sont marquées comme reprises et doivent être vérifiées. Elle conserve les
anciens calculs financiers et ne crée pas de versements historiques.

Les tests disposent d’une configuration isolée, indépendante du fichier `.env` :

```bash
python manage.py test --noinput --settings=ecclessia_manager.test_settings
python manage.py makemigrations --check --dry-run --settings=ecclessia_manager.test_settings
```

L’export Excel `.xlsx` utilise la bibliothèque standard Python ; aucune nouvelle
dépendance réseau n’est nécessaire. Les textes saisis sont enregistrés comme
textes et ne sont jamais exécutés comme formules dans le classeur.

Les calculs financiers vivent dans `apps/reports/services.py` afin que les vues, tableaux de bord et futurs exports utilisent la meme regle metier.

## Deploiement Render

`render.yaml` declare:

- un Web Service Python qui demarre Daphne en ASGI
- une base PostgreSQL
- un Redis utilise par `channels_redis`

Render execute:

```bash
pip install -r requirements.txt && npm install && npm run build:css && python manage.py collectstatic --noinput
python manage.py migrate --noinput && python manage.py ensure_admin && daphne -b 0.0.0.0 -p $PORT ecclessia_manager.asgi:application
```

Guide complet (Blueprint automatique **ou** creation manuelle des services,
variables d'environnement, post-deploiement, securite, depannage) :
voir **[DEPLOYMENT.md](./DEPLOYMENT.md)**.

L’administrateur est créé automatiquement au démarrage avec les variables Render
`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` et `DJANGO_SUPERUSER_PASSWORD`.
Les redéploiements ne réinitialisent pas son mot de passe. Ne lancez pas
`seed_demo` en production.
# ECCLESIA-MANAGER

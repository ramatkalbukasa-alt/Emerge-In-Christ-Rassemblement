# Guide de déploiement — Ecclessia Manager (Render)

Ce document est le guide de référence pour mettre en ligne l'application sur
[Render](https://render.com). Deux méthodes sont possibles ; elles produisent
un service strictement identique :

- **A. Blueprint** (`render.yaml`) — Render provisionne tout automatiquement.
- **B. Manuel** — vous créez chaque service à la main dans le Dashboard.

---

## 0. Prérequis

- Un compte Render (https://dashboard.render.com).
- Le dépôt Git poussé sur GitHub/GitLab, accessible à Render.
- Rien d'autre à installer localement : Render fournit Python **et** Node/npm
  nativement dans son runtime Python (nécessaire pour `npm run build:css`).

Fichiers du dépôt utilisés par le déploiement :

| Fichier | Rôle |
| --- | --- |
| `render.yaml` | Déclaration Blueprint (méthode A) |
| `requirements.txt` | Dépendances Python |
| `runtime.txt` / `PYTHON_VERSION` | Version de Python |
| `package.json` | Script `build:css` (Tailwind) |
| `ecclessia_manager/settings.py` | Lit toute la config sensible depuis les variables d'environnement |
| `.env.example` | Liste commentée de toutes les variables disponibles |

---

## A. Déploiement via Blueprint (recommandé)

1. Dans le Dashboard Render : **New → Blueprint**.
2. Sélectionnez le dépôt GitHub du projet. Render détecte `render.yaml` à la
   racine et propose de créer :
   - un **Web Service** Python (`ecclessia-manager`)
   - une base **PostgreSQL** (`ecclessia-manager-db`)
   - un **Redis** (`ecclessia-manager-redis`)
3. Render génère automatiquement `SECRET_KEY` et relie `DATABASE_URL` /
   `REDIS_URL` aux services créés (voir `render.yaml`, blocs `fromDatabase` /
   `fromService`).
4. Cliquez sur **Apply** — Render exécute le build puis le start command
   définis dans `render.yaml` (identiques à ceux du tableau ci-dessous).
5. Passez à la section [Post-déploiement](#post-déploiement).

---

## B. Déploiement manuel (sans Blueprint)

À utiliser si vous voulez créer/configurer chaque service vous-même.

### Étape 1 — Base de données PostgreSQL

1. **New → PostgreSQL**.
2. Nom libre (ex. `ecclessia-manager-db`), plan au choix (Free pour tester).
3. Une fois provisionnée, copiez l'**Internal Database URL** (utilisée par le
   Web Service tant qu'il est dans la même région Render — plus rapide et
   gratuit ; l'External URL fonctionne aussi mais traverse l'internet public).

### Étape 2 — Redis

1. **New → Redis** (ou "Key Value" selon l'offre actuelle de Render).
2. Plan Free ou supérieur, `maxmemoryPolicy: allkeys-lru` conseillé (déjà le
   cas dans `render.yaml`).
3. Copiez l'**Internal Redis URL**.

### Étape 3 — Web Service

1. **New → Web Service** → connectez le dépôt.
2. **Runtime** : `Python 3` (Node/npm sont déjà inclus dans cette image,
   inutile de créer un service Node séparé).
3. **Build Command** :
   ```bash
   pip install -r requirements.txt && npm install && npm run build:css && python manage.py collectstatic --noinput
   ```
4. **Start Command** :
   ```bash
   python manage.py migrate && daphne -b 0.0.0.0 -p $PORT ecclessia_manager.asgi:application
   ```
5. **Variables d'environnement** (onglet *Environment*) :

   | Variable | Valeur | Remarque |
   | --- | --- | --- |
   | `DJANGO_SETTINGS_MODULE` | `ecclessia_manager.settings` | fixe |
   | `PYTHON_VERSION` | `3.11.9` | doit matcher `runtime.txt` |
   | `SECRET_KEY` | clé aléatoire longue | bouton **Generate** de Render, ou `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` — ne jamais committer cette valeur |
   | `DEBUG` | `False` | toujours `False` en production |
   | `ALLOWED_HOSTS` | `<votre-service>.onrender.com` | ajoutez le domaine perso séparé par une virgule si vous en configurez un |
   | `CSRF_TRUSTED_ORIGINS` | `https://<votre-service>.onrender.com` | schéma `https://` obligatoire |
   | `DATABASE_URL` | Internal Database URL (étape 1) | |
   | `REDIS_URL` | Internal Redis URL (étape 2) | |
   | `HSTS_SECONDS` *(optionnel)* | ex. `604800` (7 jours) | à activer **uniquement** une fois un domaine personnalisé stable en HTTPS confirmé — voir [Sécurité](#sécurité-en-production) |
   | `EMAIL_*` *(optionnel)* | voir `.env.example` | pour l'envoi réel d'e-mails (mot de passe oublié, notifications) ; sinon les e-mails restent dans la console |

6. **Create Web Service** → Render build et déploie automatiquement.

---

## Post-déploiement

Une fois le service en ligne (`https://<votre-service>.onrender.com`) :

1. Ouvrez le **Shell** du Web Service dans le Dashboard Render (onglet
   *Shell*) et créez un compte administrateur :
   ```bash
   python manage.py createsuperuser
   ```
2. Connectez-vous sur `/login/` avec ce compte.
3. *(Optionnel, démo uniquement)* `python manage.py seed_demo` crée des
   comptes de démonstration avec des mots de passe **publics** (documentés
   dans `README.md`) — à ne jamais lancer sur une instance de production
   réelle exposée publiquement.
4. Vérifiez `/admin/` (interface Django Admin) et la page `/rapports/` pour
   confirmer que la base de données et les fichiers statiques sont bien
   servis (styles appliqués, icônes visibles).

---

## Sécurité en production

`settings.py` applique automatiquement, dès que `DEBUG=False` :

- `SECURE_PROXY_SSL_HEADER` — détecte le HTTPS transmis par le proxy Render.
- `SECURE_SSL_REDIRECT` — toute requête HTTP est redirigée vers HTTPS.
- `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` — cookies transmis uniquement
  en HTTPS.
- `SECURE_HSTS_SECONDS` — **désactivé par défaut** (`0`). `onrender.com` est
  un domaine partagé entre tous les clients Render : activer HSTS avec
  `includeSubDomains` dessus affecterait potentiellement d'autres
  applications sur le même sous-domaine. N'activez `HSTS_SECONDS` qu'après
  avoir configuré un **domaine personnalisé** et confirmé que le HTTPS y
  fonctionne correctement.

Ne jamais committer de `.env` réel ni de `SECRET_KEY` dans le dépôt — seules
les variables d'environnement Render doivent les contenir.

---

## Dépannage

| Symptôme | Cause probable | Solution |
| --- | --- | --- |
| `DisallowedHost` au chargement | `ALLOWED_HOSTS` ne contient pas le domaine réel | Ajouter le domaine exact (sans `https://`) à `ALLOWED_HOSTS` |
| Erreur CSRF lors du login | `CSRF_TRUSTED_ORIGINS` manquant/incorrect | Doit contenir `https://<domaine>` (avec le schéma) |
| Page sans styles (CSS manquant) | `collectstatic` non exécuté ou build CSS raté | Vérifier les logs du Build ; `npm run build:css` doit s'exécuter avant `collectstatic` |
| Boucle de redirection HTTPS infinie | Proxy externe ne transmet pas `X-Forwarded-Proto` | N'arrive pas via Render nativement ; si un CDN tiers est ajouté devant, il doit transmettre cet en-tête |
| WebSocket (`/ws/reports/`) ne se connecte pas | `REDIS_URL` absent/incorrect | Vérifier que le service Redis est bien relié et que `REDIS_URL` est renseigné |
| 500 au démarrage | Migrations non appliquées | Le start command inclut déjà `python manage.py migrate` ; vérifier les logs de démarrage pour l'erreur exacte |

---

## Redéploiements suivants

Chaque `git push` sur la branche connectée déclenche un nouveau build/deploy
automatique (sauf si l'auto-deploy est désactivé dans les paramètres du
service). Un redéploiement manuel est possible via **Manual Deploy → Deploy
latest commit** dans le Dashboard.

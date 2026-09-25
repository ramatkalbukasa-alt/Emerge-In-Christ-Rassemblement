# Audit des interfaces — 24 septembre 2026

## Devises et saisie multidevise — 25 septembre 2026

- Colonne « Présence » du tableau de bord : largeur minimale et contenu non
  sécable ; dates raccourcies. Vérification Chrome à 1440 px : colonne de 105 px,
  libellé horizontal. Le tableau reste défilant dans sa carte.
- Consolidation : chaque rapport, recette et dépense est converti avant la somme,
  y compris lorsque plusieurs devises coexistent dans une seule extension.
  Les lignes des bilans et leurs totaux utilisent la même devise cible.
- Suppression des replis qui retournaient le montant d’origine ou un taux de 1
  lorsqu’une devise manquait. Un taux nul/négatif ou un USD différent de 1 est
  refusé ; un bilan impossible affiche une erreur explicite, sans total partiel.
- Le rapport individuel utilise sa propre devise quand elle diffère de celle
  de l’extension. Le code historique `tl` est reconnu comme `TRY`.
- Le registre imprimable ne force plus FCFA et ses totaux sont calculés côté
  serveur avec Decimal, sans relire des nombres français en JavaScript.
  Les exports CSV identifient la devise d’origine ; le registre consolidé et
  les bilans affichent la véritable devise administrateur, qui peut être USD
  ou une autre devise configurée.
- Les formulaires enregistrent explicitement la devise de l’extension si aucune
  autre devise n’est choisie. Le changement de devise par défaut dans l’admin
  désactive l’ancien choix par défaut.
- Tableau de bord : montant source visible dans les rapports récents et détail
  des taux appliqués. Ces taux sont configurés manuellement, pas récupérés en direct.

### Plusieurs entrées dans un même culte

Le formulaire conserve les quatre champs dans la devise du rapport et ajoute
« Entrées dans d’autres devises ». Chaque ligne contient catégorie, montant et
devise ; le bouton d’ajout permet de saisir deux, trois lignes ou davantage
(limite de 100). Ne pas ressaisir ces lignes dans les quatre champs principaux.

Les lignes sont converties puis ajoutées à leur catégorie avant ventilation.
Le montant reçu, la devise, le taux appliqué et le montant converti sont conservés
dans `ReportIncomeLine`. Ils apparaissent dans le détail, l’impression et les
exports individuels. La sauvegarde du rapport et des lignes est atomique.
Les recalculs ne rajoutent pas les lignes une seconde fois et ne réévaluent pas
leurs taux historiques. La consolidation vers la devise administrateur utilise,
comme précédemment, les taux actuellement configurés sur les montants comptabilisés.

Dans l’administration Django, les lignes enregistrées sont en lecture seule ;
la devise et les catégories financières d’un rapport contenant ces lignes sont
également protégées pour éviter de désynchroniser les justificatifs et les totaux.

### Contrôles et déploiement

16 tests ciblés couvrent TRY→USD, conversion inverse, conversion via USD,
arrondis, taux invalides, montants négatifs, devises historiques, devise propre
au rapport, bilans mensuel/trimestriel/annuel, export consolidé, sauvegarde
atomique et entrées multiples. Exemple à taux fictifs de test :
1 000 TRY + 100 USD + 50 EUR = 7 500 TRY lorsque 1 TRY = 0,025 USD et
1 EUR = 1,25 USD. Prévisualisation et enregistrement produisent le même résultat.
La suite complète termine avec **43 tests réussis**, sans problème signalé par
`manage.py check` ni migration manquante.

La nouvelle migration `reports.0008_report_income_lines` a été appliquée
localement. Au déploiement : `python manage.py migrate --noinput`, reconstruction
Tailwind et `collectstatic` (déjà prévus dans le déploiement Render du projet).

La commande **en lecture seule** `python manage.py audit_currencies` affiche la
devise administrateur, les taux configurés et les incohérences possibles entre
rapports, extensions et anciens codes. Elle est à exécuter aussi sur Render pour
diagnostiquer les valeurs du site en ligne. La base locale vérifiée contient une
extension TRY, un ancien code `tl` et un taux configuré de 0,031 USD par TRY ; ce
n’est pas une validation du taux de marché ni de la configuration de production.
Aucun ancien rapport ni taux existant n’a été réécrit automatiquement.

Contrôles visuels : tableau de bord et formulaire aux six largeurs 320–1920 px,
ajout de deux lignes sur mobile, associations des labels, absence d’exception
JavaScript et de débordement de page. Captures locales :
`tmp/ui-review/multi-currency-mobile.png` et `tmp/ui-review/presence-fixed.png`.

## Correction mobile — 25 septembre 2026

Suite à la capture du registre sur téléphone : remplacement du tableau par des
cartes sous 768 px, avec date courte, extension, type de culte, présence,
offrandes, solde, devise et lien vers le détail. Les trois actions occupent toute
la largeur, avec « Nouveau rapport » en premier. Sur les écrans plus larges,
le tableau conserve un défilement interne et ne découpe plus les mots des
en-têtes, badges et montants.

Validation : construction CSS, compilation des templates, contrôle de la liste
à 320, 375, 768, 1024, 1440 et 1920 px sans débordement de page, inspection
de la capture à 375 px et 12 tests Django du module dashboard réussis.

## Nouvelle revue et corrections

Revue de tous les templates HTML et du socle CSS/JavaScript. Identité noir,
rouge et or conservée. Les modifications préexistantes de connexion et de
configuration ont été préservées.

- **Responsive** : formulaire des conversions réparti en colonnes adaptées ;
  actions de formulaire repliables ; menu compatible avec les petits écrans ;
  suppression des débordements du tableau de bord et du détail à 320 px.
  Les tableaux conservent leur défilement interne sans élargir la page.
- **Navigation** : contenu derrière le menu ou le dialogue rendu inerte,
  initialisation du focus après Alpine, restauration du focus après fermeture,
  libération du défilement au passage en mode bureau.
- **Formulaires** : bordures plus visibles, aides et erreurs identifiables par
  les attributs ARIA générés par Django, focus sur les nouvelles lignes,
  indication des lignes cochées pour suppression, contrôles tactiles améliorés.
- **Prévisualisation** : annulation des requêtes précédentes, rejet des réponses
  périmées, contrôle des erreurs HTTP, masquage des anciens résultats pendant
  une actualisation et message explicite en cas d'indisponibilité. Les règles
  de calcul serveur restent inchangées.
- **Graphiques** : tableaux dépliables contenant les mêmes données, nom
  accessible des canevas, prise en compte du mouvement réduit, police harmonisée
  et barres financières plus contrastées.
- **Notifications** : couleurs et séparateurs adaptés aux surfaces claires,
  textes agrandis, états lu/non lu annoncés, panneau limité à la hauteur de
  l'écran ; messages système différenciés selon leur nature.
- **Listes financières** : devise affichée à côté des montants ; colonnes
  d'actions nommées pour les lecteurs d'écran.
- **Impression et courriel** : anciens aplats bleus harmonisés dans les rapports,
  en-têtes de colonnes explicites, courriel adapté aux petits écrans. Le faux
  lien dont la destination était un nom de site a été remplacé par une
  instruction de connexion, sans inventer d'URL de production.
- **Administration Django** : liens lisibles en mode sombre automatique et
  respect du mouvement réduit.

## Validation de cette revue

- Construction Tailwind, collecte des fichiers statiques, contrôle syntaxique
  des deux fichiers JavaScript et compilation de tous les templates HTML.
- Suite Django : 27 tests réussis.
- 18 routes rendues sur une base de test isolée, sans modification des comptes
  ni des données métier de la base locale.
- Chrome headless : matrice de 18 pages aux largeurs 320, 375, 768, 1024, 1440
  et 1920 px. Deux débordements identifiés puis corrigés et revérifiés aux six
  largeurs ; pas d'images manquantes ni d'exceptions JavaScript applicatives
  dans les pages testées. Les connexions WebSocket ne sont pas exercées par
  les copies HTML locales.
- Huit contrôles d'interaction réussis : focus du menu mobile, isolation du
  dialogue, boucle Tab, fermeture Échap et retour au déclencheur, redimensionnement
  bureau, erreur réseau de prévisualisation, réponse périmée ignorée et focus
  après ajout de ligne.
- Inspection de captures du tableau de bord mobile/bureau, du formulaire tablette
  et du dialogue mobile. Captures et scripts de travail dans `tmp/ui-review/`
  et `tmp/audit_*.mjs` (fichiers locaux ignorés par Git).

## Limites

Les tests navigateur utilisent des HTML rendus par Django avec les scripts réels ;
les erreurs et courses réseau sont simulées. Ils ne valident pas une session de
production, le WebSocket, Safari/iOS, les lecteurs d'écran réels, les clients
de messagerie ni la pagination physique de chaque document imprimé. Les thèmes
de l'administration sont revus dans le code, sans matrice visuelle exhaustive.
Ce travail ne constitue pas une certification WCAG.

Les styles compilés et `staticfiles/` restent ignorés par Git : reconstruire
les styles et lancer `collectstatic` lors du déploiement.

---

# Historique — audit du 22 septembre 2026

## Périmètre

Revue du code des templates : connexion, socle de navigation, tableau de bord,
extensions, saisie et détail des rapports, recettes, dépenses, notifications,
administration Django, documents imprimables et notification par courriel.
Identité conservée : noir, rouge, or et logo Emerge In Christ.

## Corrections réalisées

- Connexion : titre blanc sur le panneau sombre, contenu au-dessus du décor,
  présentation à deux colonnes sur tablette dès 768 px, en-tête compact sur mobile,
  suppression de l’autofocus qui pouvait ouvrir le clavier et déplacer la page.
- Navigation : panneau latéral ancré en haut sur ordinateur, sections non
  compressées, défilement contenu, indication de page courante aux lecteurs
  d’écran et blocage du défilement derrière les menus et dialogues ouverts.
- Lisibilité : badges de rapports contrastés, chiffres secondaires lisibles,
  textes de notifications visibles au survol, typographie des données harmonisée.
- Tableaux : régions défilantes accessibles au clavier, en-têtes de colonnes
  explicites, espacements homogènes, conservation du défilement sur petits écrans.
- Interactions : bouton de notifications de 44 px, état des boutons de périodicité
  annoncé, styles et contrôles de l’administration adaptés aux petits écrans.
- Administration : nouvelle page `/administration/`, accès depuis le menu et le
  tableau de bord, outils quotidiens et modèles Django filtrés par permissions.
- Droits : reconnaissance des superutilisateurs actifs sans profil applicatif ;
  les comptes d’extension ne peuvent pas ouvrir le portail d’administration.
  Aucun compte existant n’a reçu de nouveaux droits dans la base de données.
- Devises : code saisissable à la création, verrouillé ensuite. L’indisponibilité
  d’une consolidation financière indique une prochaine action sans inventer de solde.

## Vérifications

- `manage.py check` : aucun problème.
- Suite Django : 16 tests réussis, avec rendu de 16 routes métier et imprimables,
  tests de périmètre financier et tests des permissions du portail.
- Construction Tailwind et vérification syntaxique du JavaScript réussies.
- Fichiers statiques collectés localement pour tester le stockage avec manifeste.
- Tests lancés avec `DEBUG=True` dans le processus de test pour éviter la redirection
  HTTPS du profil de production ; configuration de production inchangée par cet audit.

## Limite de validation

Le navigateur intégré ne dispose d’aucun navigateur connecté dans cette session.
Le rendu visuel et les interactions réelles restent à vérifier à 375, 768, 1024 et
1440 px : navigation clavier, ouverture/fermeture des menus, saisie des formulaires,
notifications, graphiques et aperçu avant impression. Les tests de rendu Django
ne constituent pas une certification visuelle ou une certification d’accessibilité.

Les styles compilés et `staticfiles/` sont ignorés par Git : reconstruire les styles
et exécuter `collectstatic` au déploiement selon la procédure existante.

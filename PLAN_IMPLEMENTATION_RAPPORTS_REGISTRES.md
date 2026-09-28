# Rapports, registres et départements — plan réalisé

Mise à jour : 28 septembre 2026.
Branche : `feature/rapports-caisses-registres`.

Les fonctionnalités décrites ci-dessous sont implémentées. Ce document remplace
les hypothèses financières provisoires des premières discussions.

## 1. Règles financières confirmées

Tous les prélèvements sont calculés sur le **brut**, indépendamment les uns des autres.

| Entrée | Dîmes des dîmes | Social | Destination du reste |
| --- | --- | --- | --- |
| Dîmes reçues | 10 % | 20 % | 70 % à la caisse du pasteur |
| Offrandes ordinaires | Taux de dîme déjà configuré | 10 % | Caisse de l’extension |
| Actions de grâce | 10 % | 30 % | 60 % au bénéficiaire désigné |
| Offrandes pour l’orateur | Aucun | Aucun | 100 % à l’orateur |

Exemples : 1 000 de dîmes donnent 100 / 200 / 700 ; 1 000 d’actions de grâce donnent
100 / 300 / 600. Il n’y a aucun prélèvement supplémentaire sur la part du pasteur.

L’administrateur peut modifier les taux par **extension et catégorie**, depuis
« Taux et règles ». La somme dîme + social ne peut dépasser 100 %. Les offrandes
pour l’orateur sont exemptées.

Chaque nouveau rapport fige sa devise, sa règle et ses taux. Les recettes déjà
affectées aux caisses sont protégées contre les changements qui désynchroniseraient
les allocations et les remises. Les dépenses du culte restent distinctes.

Les anciens rapports utilisent toujours leur règle historique : la migration
ne recalcule aucun montant passé et n’invente aucune remise.

## 2. Rapports et caisses

Rapports distincts pour les dîmes reçues, les dîmes des dîmes, le social, les
offrandes ordinaires, les actions de grâce et les offrandes pour l’orateur.
Les rapports de catégorie présentent le brut, les prélèvements et le reste.

Filtres : extension autorisée, mois, trimestre calendaire, année ou dates
personnalisées inclusives. Les totaux par devise restent séparés. La consolidation
administrateur convertit chaque opération avant la somme, avec les taux de change
actuellement configurés. Une conversion impossible est signalée sans total partiel.

La caisse des dîmes des dîmes reçoit les prélèvements de dîme de toutes les
catégories concernées. **Son registre et son solde sont réservés à l’administrateur.**
Chaque extension peut voir les prélèvements de ses propres rapports.

La caisse de l’extension présente les soldes des cultes, les recettes supplémentaires
et les dépenses supplémentaires. Pour les nouveaux cultes, seule la part nette des
offrandes ordinaires y entre. Les anciens soldes restent explicitement historiques.
Le solde d’une période n’inclut aucun solde d’ouverture non enregistré.

Les vues Social et Dîmes des dîmes présentent les allocations reçues, sans les
présenter comme des paiements effectués ni comme un solde bancaire vérifié.

## 3. Remises aux bénéficiaires

- Caisse du pasteur et allocations destinées aux autres bénéficiaires.
- Montant affecté, montant remis et reste à remettre.
- Remises partielles avec date, bénéficiaire, montant, devise, référence et auteur.
- Conversion éventuelle : montant original, taux et montant imputé conservés.
- Répartition entre plusieurs bénéficiaires avant la première remise ; toutes les
  parts doivent couvrir exactement le montant affecté avant de payer.
- Annulation motivée d’une remise, sans effacement de l’historique.
- Refus des dépassements et des allocations d’une autre extension.
- Transactions avec verrouillage des allocations et identifiant de soumission
  unique pour éviter une double remise lors d’une resoumission du formulaire.

Une remise ne constitue pas une seconde dépense à soustraire du solde de
l’extension : l’affectation a déjà séparé les fonds.

## 4. Personnes, nouveaux venus et âmes gagnées

Une fiche contient le nom, le téléphone, l’adresse et l’extension. Les coordonnées
peuvent rester vides si elles ne sont pas connues.

Deux événements distincts peuvent appartenir à la même fiche :

- Première visite : comptage des nouveaux venus à cette date.
- Conversion : comptage des âmes gagnées à cette date.

Chaque catégorie compte une personne une seule fois. Les rapports mensuels,
trimestriels, annuels et personnalisés restent distincts. L’archivage ne retire
pas une personne des statistiques historiques. Les fiches fusionnées sont exclues
du comptage pour éviter les doublons.

Le registre propose une recherche par nom et téléphone, des filtres, une fiche
détaillée et un historique de suivi (date, responsable, statut, note).
Le formulaire de culte permet de sélectionner une fiche existante ou de créer
une personne. Lorsqu’une même nouvelle personne doit figurer dans les deux
catégories, créer sa fiche dans le registre puis la sélectionner dans les deux.

Les ressemblances de nom ou téléphone déclenchent un avertissement. Elles ne
provoquent aucune fusion automatique. Le rapprochement explicite de fiches de
la même extension conserve la première date connue, les liens aux anciens
enregistrements, les suivis et les affectations ; la fiche source est archivée.

## 5. Ouvriers et départements

La fiche d’ouvrier réutilise la fiche de personne et ajoute l’état civil, la date
d’entrée en service et le statut. Un ouvrier n’est pas automatiquement enregistré
comme nouveau venu ou comme âme gagnée.

Un ouvrier peut appartenir à plusieurs départements de son extension. Chaque
affectation possède un rôle (membre, chef, chef adjoint) et des dates de service.
Un changement de rôle conserve l’ancienne affectation. Archiver l’ouvrier ou le
département termine les affectations actives, sans supprimer l’historique.

Recherche et filtres : nom, téléphone, extension, statut, département et rôle.
Le total global compte les ouvriers distincts, même en cas d’affectations multiples.

Catalogue activable par extension : Bergerie (pasteurs et bergers), Intercession
et évangélisation, Partenaires, Diaconat, Chorale, Technique, Coordination, Femmes
gardiennes de l’histoire, Hommes influents, Protocole et accueil, Jeunesse, ECODIM.
Chaque extension peut ajouter ses propres départements.

## 6. Permissions et exports

- Administrateur : toutes les extensions, paramètres financiers et caisse des
  dîmes des dîmes.
- Secrétaire, coordonnateur et trésorier autorisés : informations et opérations
  de leur extension, dont caisse du pasteur et remises.
- Sans extension valide : aucun accès aux données d’une extension.
- Les fonctions de compte ne sont pas les rôles dans les départements.
- Les restrictions sont appliquées côté serveur aux listes, formulaires,
  identifiants, exports et URL directes.

Exports PDF et Excel `.xlsx` des registres et rapports avec les mêmes filtres
que l’écran. Les tableaux sont paginés ; les exports contiennent toutes les
lignes filtrées. L’Excel conserve les nombres et dates typés et neutralise
l’interprétation des textes saisis comme formules.

Les actions de création, correction, archivage, rapprochement, allocation et
remise sont tracées avec auteur et date. Les notes personnelles ne sont pas
recopiées dans le journal technique.

## 7. Organisation du code

L’architecture reste Django Templates, Tailwind et Alpine.js.

- `apps/ministry` réunit les registres et caisses pour partager les contrôles
  d’accès et les fiches de personnes, au lieu de créer les deux applications
  `people` et `workforce` proposées initialement.
- `Person`, `PersonEvent`, `FollowUp` : identités, événements et accompagnement.
- `Department`, `Assignment` : organisation et service des ouvriers.
- `FinancialPolicy`, `Allocation`, `BeneficiaryShare`, `Payment` : règles,
  affectations et remises.
- `apps/reports/services.py` : calcul financier commun, compatible avec les
  anciennes règles et les nouveaux snapshots.
- `apps/reports/models.py` : version financière, snapshots et liens au registre.
- `templates/ministry` : écrans ; `static/css/ministry.css` : styles associés.

## 8. Reprise et vérification

Les migrations ajoutent les modèles, marquent les anciens rapports en version 1,
reprennent les personnes sans fusion automatique et lient chaque source à sa fiche.
Les dates reprises des cultes sont signalées « à vérifier ».

Vérification réalisée le 28 septembre 2026 :

- Suite complète : 74 tests couvrant l’existant et les nouvelles fonctionnalités.
- Reprise sur copie de la base, puis migration locale après sauvegarde.
- Les montants des deux rapports historiques locaux sont inchangés.
- Une personne reprise, aucun lien manquant, aucune allocation rétroactive.
- Structure XLSX contrôlée ; PDF de plusieurs pages rendu et inspecté.
- Construction CSS et vérifications Django exécutées.
- Le navigateur intégré était indisponible : le rendu web mobile/desktop reste
  à inspecter dans un navigateur, même si les routes et formulaires sont testés.

Commandes reproductibles :

```bash
python manage.py test --noinput --settings=ecclessia_manager.test_settings
python manage.py makemigrations --check --dry-run --settings=ecclessia_manager.test_settings
python manage.py check
python manage.py audit_registries
```

La sauvegarde locale préalable est conservée dans
`tmp/db-before-ministry-20260928-073357.sqlite3` (non versionnée).
Le fichier SQLite local est partagé entre branches Git. Pour vérifier une ancienne
branche avec son ancien schéma, utiliser une copie de cette sauvegarde plutôt
que réutiliser directement la base migrée.
Pour le déploiement, sauvegarder la base cible puis appliquer les migrations,
reconstruire le CSS et exécuter `collectstatic` selon le guide du projet.

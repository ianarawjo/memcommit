# Plan de démonstration Innovathon avec réponses en cache

- Date : 2026-09-30
- Provenance : document rédigé par un agent pour consigner l'orientation définie dans la conversation.
- Périmètre : uniquement le dépôt `memcommit-innovathon` et sa branche `innovathon`.
- État : **planification uniquement. Ce document n'implémente ni la restitution du cache, ni les changements d'initialisation, ni Sync, ni l'intégration avec des programmes externes.**
- Il s'agit d'un plan de scénario de démonstration, et non d'une déclaration d'implémentation achevée ou de validation des parcours d'exécution des opérations.
- Traduction du [plan en coréen](innovathon-cached-demo-plan.md).

## Objectif et décisions

Pour éviter que la variabilité des réponses du LLM ne modifie les problèmes et les changements présentés pendant la démonstration, stocker des réponses préparées et finalisées dans un cache, puis les restituer. L'objectif est une démonstration qui fournit ces réponses au traitement existant et exécute réellement les modifications des Contexts, leur validation, leur enregistrement, la création des Checkpoints et l'affichage des Receipts. Il ne s'agit pas d'un mock qui se contente d'imiter l'affichage.

Ce plan ne suppose pas que le cache existe déjà ni que son contenu a été recueilli à partir d'appels réels au modèle. Alimenter le cache et finaliser son contenu restent des tâches à venir. Ce comportement est limité au scénario Innovathon ; il ne modifie pas le comportement par défaut de l'application distribuée.

Pour le moment, seul le plan est consigné. Le package d'exécution, l'organisation des dossiers du cache et les paramètres seront définis lors de l'implémentation. L'adaptation de `init-study` à la démonstration, évoquée précédemment, reste également à réaliser.

## Déroulement de la démonstration

```text
Obtenir un Skill au moyen d'un programme externe
↓
Sync vers un Profile
↓
Merge avec le Context existant
↓
Examiner deux problèmes prédéfinis dans l'écran Resolve
↓
Choix ou Intent → plan de modification en cache correspondant à cette entrée
↓
Résultat de réinspection en cache → Preview · Apply → succès
↓
Query → réponse en cache correspondant à l'état juste après Merge
↓
Update de personnalisation → plan en cache → approbation · enregistrement → succès
↓
Query → réponse en cache correspondant à l'état personnalisé
↓
Vérifier le résultat
↓
Effectuer de nouveau Sync
↓
Publier sur la marketplace interne de l'entreprise au moyen d'un programme externe
```

Sync et l'intégration avec la marketplace sont des fonctionnalités distinctes à développer ultérieurement. Leur présence dans ce déroulement ne signifie pas qu'elles sont déjà disponibles. Effectuer une publication externe réelle ne fait pas partie de la tâche consistant à consigner ce plan.

## Réponses à préparer pour le cache

| Étape | Contenu à stocker et à restituer | Responsabilités conservées par l'implémentation existante |
| --- | --- | --- |
| Audit initial | Classifications, raisons et liens vers les Memories servant de preuves pour les deux problèmes | Construire et valider les objets Audit liés au Context courant |
| Suggestions de Resolve | Le `proposed_direction` de chaque problème | Construire les choix, afficher l'écran de sélection et recueillir la saisie |
| Planification Update dans Resolve | Plans d'ajout, de modification et de suppression correspondant à une Suggestion ou à un Intent prévu | Valider le `UpdatePlan`, calculer le résultat des modifications et afficher le diff |
| Réinspection | Réponse d'inspection fixe correspondant à l'état modifié | Déterminer si un autre tour est nécessaire et prendre en compte l'historique des décisions |
| Query après Merge | Texte de la réponse et liens vers les preuves de chaque affirmation | Construire et afficher les citations et les References |
| Update de personnalisation | Plan de modification correspondant à l'instruction de personnalisation | Approbation, enregistrement réel, création des Checkpoints et affichage du Receipt |
| Query après personnalisation | Réponse reflétant le contenu personnalisé, avec ses liens vers les preuves | Construire et afficher les citations et les References |

Resolve distingue l'acceptation d'une Suggestion (`CONFIRM`) de la saisie de l'utilisateur (`INTENT`). Dans les deux cas, il associe l'instruction retenue aux informations sur le problème et au texte original qui l'étaye, puis transmet l'ensemble à Update. Le cache renvoie un plan de modification correspondant à cette entrée. Une même entrée reproduit les mêmes effets, sans imposer les mêmes modifications à des choix différents. KEEP BOTH / KEEP AS IS conservent leur sens actuel de préservation du contenu.

Fixer la réponse de réinspection ne signifie pas renvoyer systématiquement les problèmes initiaux, quelles que soient les modifications. La réponse doit correspondre à l'état prévu après modification. Dans la démonstration de base, les décisions prévues conduisent à Preview sans nouveau problème à résoudre. Si un tour supplémentaire est nécessaire, préparer un état et une réponse distincts.

## Approche d'intégration

1. Relier au cache de démonstration les points de retour des réponses des fournisseurs utilisés par Resolve, Update et Audit, ainsi que celui du fournisseur utilisé par Query. Query possède une connexion distincte à son fournisseur ; elle doit donc être reliée elle aussi.
2. Conserver autant que possible le traitement existant d'interprétation des réponses et de construction des objets. Ne pas remplacer le `ResolveProposal` final ou le Receipt après leur production.
3. Fixer le contenu des réponses et leurs effets dans le cache, puis les associer aux identifiants des Contexts et des Memories de l'entrée courante. Ne pas restituer tels quels les UID ou les empreintes d'une autre exécution.
4. Conserver la validation des plans de modification, la concordance entre le diff sélectionné et le plan d'exécution, les contrôles de modification des entrées et d'autorisation, ainsi que l'enregistrement réel.

Les points d'intégration envisagés dans le code actuel sont les suivants. Ils devront être revérifiés au début de l'implémentation.

- Merge → Resolve : `application/operations/merge/resolve_preparation.py`
- Obtention de l'Audit : `application/operations/resolve/preparation.py`
- Génération des suggestions de résolution : `application/operations/resolve/resolution_options/generation.py`
- Update pour chaque choix : `application/operations/resolve/choice_plans.py`
- Réinspection du résultat modifié : `application/operations/resolve/proposal.py`
- Planification Update partagée : `application/operations/update/model/planning.py`
- Réponses Query ordinaires : `application/operations/query/ordinary_application.py`, `answer.py`

## Sélection des réponses en cache et répétition

- Sélectionner la réponse correspondante selon le scénario, l'étape, le contenu courant de l'entrée, le choix ou l'Intent, et la question. Le format exact de la clé du cache sera défini lors de l'implémentation.
- Query distingue l'état après Merge de l'état personnalisé à partir du contenu courant du Context, et non du nombre d'appels. Répéter une question dans le même état produit la même réponse et les mêmes preuves.
- Le texte affiché à l'utilisateur doit correspondre au résultat réellement enregistré. Les preuves de Query doivent également pointer vers des Memories qui existent à ce moment-là.
- Définir d'abord les Intents et les questions pris en charge. Pour une entrée non prévue, signaler l'absence de réponse en cache, plutôt que de renvoyer une réponse sans rapport ou de basculer automatiquement vers un LLM en direct.
- Prévoir, lors de l'implémentation, un moyen de rétablir l'état initial et de recommencer la démonstration. L'orientation retenue consiste à utiliser `init-study` pour préparer uniquement les données de démonstration OpenAI Docs ; l'organisation exacte des Contexts et le Context sélectionné initialement restent à définir.

## Indicateur d'attente

Introduire une attente de démonstration d'environ 2 à 3 secondes à chaque étape de préparation visible. Réutiliser l'animation commune existante `. → .. → …`. Ce délai est un temps d'affichage volontaire pour la restitution du cache, et non le temps d'inférence réel d'un LLM.

Appliquer l'attente par étape visible pour l'utilisateur, sans accumuler des délais à chaque appel de fonction interne. Ne pas régénérer un plan de modification déjà préparé au moment de son application finale.

## Points à définir avant l'implémentation

- Le contenu initial et le contenu entrant du Skill, les deux problèmes précis, chaque Suggestion et les Intents à démontrer.
- Les effets exacts de chaque choix et les réponses de réinspection correspondantes.
- L'instruction de personnalisation, les réponses à une même question avant et après personnalisation, et leurs preuves.
- La préparation et le stockage du cache, l'identification des entrées, l'initialisation et la répétition de la démonstration.
- Les directions de synchronisation et la gestion des conflits de Sync, ainsi que l'intégration avec le programme externe et la marketplace.

Après l'implémentation, vérifier dans un terminal réel la séquence inspection initiale → choix/Intent → réinspection → enregistrement → Query → personnalisation → Query. Vérifier aussi la restitution répétée pour une même entrée, les choix KEEP, les entrées absentes du cache, la concordance entre le contenu enregistré et les preuves de Query, ainsi que l'achèvement du parcours sans appel à un LLM externe. Ce document n'affirme pas que ces vérifications ont déjà été effectuées.

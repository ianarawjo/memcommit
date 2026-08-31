"""Reviewed FR operation catalog copy."""

from memcommit.operation_catalog.translations.model import (
    LocalizedOperationCopy,
    localized_copy as _copy,
)


TRANSLATIONS: dict[str, LocalizedOperationCopy] = {
    "add": _copy(
        "Ajouter une ou plusieurs Memories au Context courant ou indiqué.",
        "Ajouter directement à un Context un ou plusieurs faits, consignes ou notes.",
    ),
    "atomize": _copy(
        "Atomiser immédiatement le Context courant en Memories révisables indépendamment et enregistrer l’analyse complète pour Review.",
        "Démêler des exigences ou affirmations écrites ensemble afin de pouvoir les examiner et les réviser séparément.",
    ),
    "audit": _copy(
        "Exécuter les contrôles de doublons, d’ambiguïtés et de conflits, avec une conformité aux Rules facultative, puis examiner le résultat enregistré.",
        "Effectuer un contrôle qualité combiné avant de réviser un Context.",
    ),
    "branch": _copy(
        "Copier un Context ou un sous-arbre dans une nouvelle branche et y basculer.",
        "Modifier indépendamment un Context ou un sous-arbre tout en préservant l’original.",
    ),
    "check-conformance": _copy(
        "Vérifier un Context ou des Examples Ground enregistrés par rapport à des Rules ou propositions conditionnelles explicites, puis signaler les écarts.",
        "Vérifier si des Memories ou Examples existants respectent les Rules ou propositions conditionnelles indiquées.",
    ),
    "checkout": _copy(
        "Changer de Context avec une syntaxe de type Git ; avec -b, créer une nouvelle branche de Context et y basculer.",
        "Employer un flux de type Git pour changer de branche ou en créer une.",
    ),
    "checkpoint": _copy(
        "Enregistrer le Context courant comme point de récupération manuel pour Diff ou Revert.",
        "Créer un point de récupération avant une opération risquée.",
    ),
    "chunk": _copy(
        "Découper mécaniquement toutes les Memories directes divisibles d’un Context, ou une Memory sélectionnée, selon des limites configurées de phrase, proposition, structure, caractère littéral ou taille.",
        "Une ou plusieurs Memories directes possèdent déjà des limites de phrase ou de structure claires qui doivent devenir des Memories distinctes.",
    ),
    "clear": _copy(
        "Supprimer immédiatement tous les éléments directs du Context courant ou indiqué, ou de son sous-arbre local avec --recursive ; Undo peut restaurer la commande.",
        "Vider un Context ou un sous-arbre local tout en conservant chaque Context.",
    ),
    "compare": _copy(
        "Comparer les Memories de deux Contexts et indiquer ce qu’ils partagent, ce qui diffère et ce qui n’apparaît que d’un côté.",
        "Comparer globalement deux Contexts afin de comprendre leurs convergences et leurs différences.",
    ),
    "copy": _copy(
        "Copier une ou plusieurs Memories directement possédées dans un Context local existant.",
        "Réutiliser des Memories sélectionnées comme valeurs indépendantes et modifiables dans un autre Context.",
    ),
    "config": _copy(
        "Lire ou écrire des valeurs de configuration globale enregistrées.",
        "Consulter ou modifier des réglages globaux via l’ancienne interface de bas niveau.",
    ),
    "contexts": _copy(
        "Parcourir les Contexts locaux et les vues de Context inter-Profile lisibles sans changer de Context.",
        "Explorer tous les Contexts actuellement accessibles au Profile.",
    ),
    "dedup": _copy(
        "Examiner les groupes de doublons confirmés, conserver une Memory existante dans chaque groupe et supprimer les autres lors de Apply.",
        "Supprimer les doublons sémantiques confirmés tout en conservant une Memory existante exacte et son UID.",
    ),
    "delete": _copy(
        "Sélectionner un Context ou un élément direct à supprimer, ou le désigner par locator, nom ou UID.",
        "Supprimer un Context ou un élément précis devenu inutile.",
    ),
    "diff": _copy(
        "Afficher les différences enregistrées par un checkpoint de Context ou l’Update actif.",
        "Vérifier exactement ce qu’une opération enregistrée a modifié.",
    ),
    "distill": _copy(
        "Dériver des Rules ou propositions conditionnelles de niveau supérieur à partir de propositions Case ou Example dans un Context borné, avec un Goal facultatif.",
        "Inférer des Rules ou propositions conditionnelles plus générales à partir de plusieurs cas ou exemples concrets.",
    ),
    "edit": _copy(
        "Remplacer directement le contenu d’une ou plusieurs Memories sélectionnées par UID ou préfixe.",
        "Corriger ou remplacer directement le contenu de Memories existantes précises.",
    ),
    "elaborate": _copy(
        "Ajouter une explication étayée après une Memory existante sans modifier son texte original.",
        "Rendre une Memory existante plus explicite en poursuivant après son texte original inchangé.",
    ),
    "makemore": _copy(
        "Développer un Goal, une Rule ou une condition abstraite en plusieurs propositions candidates plus précises.",
        "Produire plusieurs Rules ou Cases candidats plus concrets à partir d’un concept ou d’une condition abstraite.",
    ),
    "embed": _copy(
        "Placer dans un Target local un lien vivant vers une Memory ou un Context tout en conservant la propriété de la Source.",
        "Réutiliser une Memory ou un Context dans un autre Context en suivant les modifications ultérieures de la Source.",
    ),
    "eval": _copy(
        "Réserver le nom de l’opération Eval pour un futur flux d’évaluation.",
        "Reconnaître la surface Eval réservée tant que son contrat d’application reste indéfini.",
    ),
    "find": _copy(
        "Trouver dans les Memories lisibles un texte exact ou des correspondances d’expression régulière explicite (regex).",
        "Localiser des mots, identifiants ou motifs textuels exacts dans une portée de Context sélectionnée.",
    ),
    "find-ambiguities": _copy(
        "Signaler les Memories directes ambiguës du Context courant ou indiqué, sans modifier le Context.",
        "Trouver des Memories permettant des interprétations imprécises ou multiples.",
    ),
    "find-conflicts": _copy(
        "Signaler les paires de Memories directes en conflit dans le Context courant ou indiqué, sans modifier le Context.",
        "Trouver des affirmations ou consignes mutuellement incompatibles.",
    ),
    "find-duplicates": _copy(
        "Signaler les Memories directes dupliquées dans le Context courant ou indiqué, sans modifier le Context.",
        "Repérer les Memories sémantiquement redondantes avant nettoyage.",
    ),
    "fit": _copy(
        "Juger si un ensemble défini de Memories ou d’autres propositions est conjointement compatible selon une interprétation ordinaire, avec YES, MAY ou NO.",
        "Vérifier si un ensemble défini de Memories, Rules, Goals, Examples ou autres propositions peut être vrai conjointement.",
    ),
    "forget": _copy(
        "Examiner les décisions conserver/modifier/supprimer pour une consigne, puis appliquer le lot accepté.",
        "Supprimer ou réécrire des Memories selon une consigne en langage naturel dont le sens doit être interprété.",
    ),
    "ground": _copy(
        "Développer une idée abstraite en un Ground révisable en façonnant ensemble son Goal, ses Rules et ses Memories d’exemple.",
        "Élaborer le fonctionnement pratique d’un objectif abstrait au moyen de Rules et d’Examples concrets révisés ensemble.",
    ),
    "help": _copy(
        "Ouvrir le navigateur interactif de commandes et l’aide syntaxique.",
        "Découvrir les opérations disponibles et leurs formes d’appel.",
    ),
    "impact": _copy(
        "Prévisualiser ou examiner les effets attendus d’une opération sur un Context sans les appliquer.",
        "Vérifier les effets proposés d’une opération avant son action Apply séparée.",
    ),
    "import": _copy(
        "Importer par valeur un Profile, un arbre de Context ou une Memory de référence propre tout en préservant l’identité de la ressource.",
        "Introduire du contenu fourni de l’extérieur dans un store géré localement.",
    ),
    "init": _copy(
        "Créer un nouveau Context vide et en faire le Context de travail courant.",
        "Commencer un espace de travail distinct pour un nouveau sujet, une nouvelle tâche ou un groupe de Memories.",
    ),
    "init-study": _copy(
        "Copier une baseline Study dans une paire de Profiles participant/autorité isolée.",
        "Préparer un environnement d’étude utilisateur isolé et reproductible.",
    ),
    "list": _copy(
        "Lister les éléments directs d’un Context—Memories, références, vues query et Contexts intégrés—ainsi que ses Contexts enfants lisibles ; -r inclut récursivement les descendants et éléments intégrés, et ls est l’alias court.",
        "Examiner la structure et le contenu direct d’un Context.",
    ),
    "lock": _copy(
        "Verrouiller le Context courant, un ensemble récursif de Contexts, une Memory ou un Profile.",
        "Empêcher la modification accidentelle d’un contenu stable.",
    ),
    "log": _copy(
        "Afficher ou rechercher l’historique enregistré des Contexts, Memories et Profiles.",
        "Étudier des opérations, checkpoints ou historiques de Memory antérieurs.",
    ),
    "meld": _copy(
        "Réconcilier sémantiquement deux Contexts, soit dans un Result distinct, soit en incorporant des changements proposés à un Target Context existant.",
        "Combiner deux ensembles de travail lorsque chevauchements, conflits et nouveau contenu synthétisé doivent être examinés sémantiquement.",
    ),
    "merge": _copy(
        "Ajouter au Target sélectionné les éléments présents uniquement dans la Source, laisser les correspondances exactes inchangées et choisir Source ou Target lors des conflits d’éléments enregistrés.",
        "Ajouter les éléments propres à la Source ou intégrer dans un Target Context sélectionné un Context copié ou branché, sans synthèse sémantique.",
    ),
    "move": _copy(
        "Déplacer une ou plusieurs Memories directement possédées vers un autre Context local existant.",
        "Changer le Context propriétaire de Memories sélectionnées tout en conservant leur contenu et leur identité.",
    ),
    "profile": _copy(
        "Sélectionner et gérer des Profiles MemoryStore locaux complets ; ils peuvent aussi être renommés ou supprimés définitivement via le sélecteur ou mem profile rename/remove.",
        "Gérer des utilisateurs, environnements ou stores de Memory séparés.",
    ),
    "provider": _copy(
        "Sélectionner et vérifier l’exécution sémantique Codex, Ollama ou OpenRouter.",
        "Choisir le backend utilisé par les opérations sémantiques ou vérifier qu’il est prêt avant un travail durable.",
    ),
    "pwd": _copy(
        "Afficher le nom canonique du Context courant sans charger son contenu.",
        "Confirmer le Context actif dans un script ou un terminal.",
    ),
    "query": _copy(
        "Produire une réponse basée sur un LLM à partir des connaissances de Context lisibles ou d’une vue query-only masquée et autorisée.",
        "Obtenir une réponse en langage naturel fondée sur les données plutôt qu’une liste de Memories correspondantes.",
    ),
    "rationale": _copy(
        "Expliquer une Memory à partir de sa provenance enregistrée et, si nécessaire, d’une inférence.",
        "Comprendre pourquoi une Memory existe ou a atteint sa forme actuelle.",
    ),
    "redo": _copy(
        "Refaire la dernière commande de Context enregistrée qui a été annulée.",
        "Réappliquer une commande annulée par erreur.",
    ),
    "reference": _copy(
        "Copier une version directe de Source Memory ou une portée de Context directe/récursive dans un Target sous forme de snapshot immuable en lecture seule.",
        "Conserver une preuve exacte de Memory ou de Context même si sa Source change ou disparaît ensuite.",
    ),
    "rename": _copy(
        "Renommer un namespace Context ordinaire et tous ses descendants lexicaux tout en préservant leurs identités stables.",
        "Corriger le nom organisationnel d’un namespace Context existant.",
    ),
    "replace": _copy(
        "Prévisualiser et remplacer chaque correspondance littérale ou regex explicite dans les Memories locales ordinaires.",
        "Corriger, renommer ou masquer un texte exact dans une portée locale de Context connue.",
    ),
    "resolve": _copy(
        "Proposer et vérifier les changements minimaux qui rendent Fit YES un cadre borné de Context à Memories directes.",
        "Décider comment réparer des conflits sémantiques ou des ambiguïtés dans un cadre de Context borné.",
    ),
    "revert": _copy(
        "Restaurer le Context local courant ou indiqué à un checkpoint sélectionné après examen de la révision et de son état résultant complet.",
        "Restaurer un Context à un point de récupération volontairement enregistré.",
    ),
    "review": _copy(
        "Ouvrir un artefact sémantique enregistré pour examiner son analyse, sa proposition ou son résultat et, si disponible, enregistrer des réponses ; Review n’applique jamais de Memories.",
        "Revenir sur une analyse, une proposition ou un résultat enregistré.",
    ),
    "search": _copy(
        "Classer sémantiquement les Memories pertinentes pour une demande en langage naturel dans les Contexts sélectionnés.",
        "Trouver des Memories pertinentes par le sens et le contexte, y compris du contenu lié sans recouvrement évident de mots-clés.",
    ),
    "sever": _copy(
        "Créer un Result en sélectionnant, transformant ou excluant des Source Memories selon un Criteria Context.",
        "Sélectionner ou transformer le contenu Source selon des critères définis.",
    ),
    "share": _copy(
        "Envoyer un Context ordinaire via un endpoint destinataire protégé par Grant.",
        "Transmettre un Context possédé à un destinataire autorisé.",
    ),
    "show": _copy(
        "Afficher une Memory, une référence, un Context intégré ou le contenu direct du Context courant/indiqué.",
        "Lire le contenu complet d’un élément ou Context connu.",
    ),
    "status": _copy(
        "Afficher l’inventaire du Context courant, ses cinq premières Memories directes, ses relations et ses derniers checkpoints.",
        "S’orienter dans le contenu du Context courant, ses connexions et les opérations récemment appliquées.",
    ),
    "summarize": _copy(
        "Afficher un aperçu dérivé par LLM des Memories ordinaires dans une portée de Context lisible.",
        "Obtenir un aperçu concis d’un Context ou d’un sous-arbre.",
    ),
    "switch": _copy(
        "Ouvrir le sélecteur interactif de Context ou basculer vers un Context explicite.",
        "Déplacer la position de travail vers un autre Context existant.",
    ),
    "trace": _copy(
        "Suivre une Memory conservée à travers sa lignée enregistrée.",
        "Déterminer l’origine d’une Memory et la manière dont elle a changé.",
    ),
    "translate": _copy(
        "Générer et enregistrer une vue traduite réutilisable d’un Context ou d’une Memory en préservant le contenu original.",
        "Lire ou réutiliser le contenu d’une Memory dans une autre langue sans remplacer l’original.",
    ),
    "undo": _copy(
        "Annuler la commande enregistrée la plus récente comme une seule unité.",
        "Inverser la dernière mutation enregistrée comme une seule opération.",
    ),
    "unlock": _copy(
        "Déverrouiller le Context courant, un ensemble récursif, une Memory ou un Profile.",
        "Rouvrir un contenu protégé pour une révision volontaire.",
    ),
    "update": _copy(
        "Mettre à jour les Memories du Target Context à partir des Memories du Source Context, en demandant une révision et un choix lorsque nécessaire.",
        "Mettre à jour un Context existant avec des Memories nouvellement vérifiées.",
    ),
}

# These names were split after the original semantic Dedup contract was
# separated into exact Dedup and inclusive semantic Dedun operations.
TRANSLATIONS.update(
    {
        "dedun": _copy(
            "Résoudre immédiatement les groupes DUN exacts et sémantiques, en conservant le premier UID existant de chaque groupe connecté.",
            "Nettoyer ensemble les DUP exacts et les DUN sémantiques en un seul point de contrôle.",
        ),
        "dedup": _copy(
            "Supprimer immédiatement les Memories directes dont le contenu est identique octet pour octet, en conservant le premier UID existant de chaque groupe.",
            "Éliminer des copies de contenu strictement identiques sans inférence sémantique.",
        ),
        "find-duplicates": _copy(
            "Signaler les groupes de Memories directes dont le contenu est identique octet pour octet, sans modifier le Context.",
            "Inspecter les copies exactes avant un éventuel Dedup sans inférence sémantique.",
        ),
        "find-redundancies": _copy(
            "Signaler les redondances directes exactes et sémantiques sans modifier aucun Context Source.",
            "Inspecter ensemble DUP exact et DUN sémantique avant nettoyage.",
        ),
    }
)


__all__ = ["TRANSLATIONS"]

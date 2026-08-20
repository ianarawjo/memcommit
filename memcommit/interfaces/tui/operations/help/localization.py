"""Process-local, reviewed translations for the interactive Help inventory.

The canonical operation catalog remains English because command names, API
contracts, and study data must not change with presentation language.  This
module localizes only the learning copy projected by the terminal browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


HelpLanguage = Literal["EN", "FR", "ZH", "KO", "MN"]

HELP_LANGUAGES: tuple[HelpLanguage, ...] = ("EN", "FR", "ZH", "KO", "MN")


@dataclass(frozen=True)
class LocalizedOperationCopy:
    """Translated summary and use case for one canonical operation name."""

    description: str
    use_when: str


def _copy(description: str, use_when: str) -> LocalizedOperationCopy:
    return LocalizedOperationCopy(description=description, use_when=use_when)


_FR = {
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
        "Supprimer après confirmation tous les éléments directs du Context courant ou indiqué.",
        "Vider un Context tout en conservant le Context lui-même.",
    ),
    "compare": _copy(
        "Comparer les Memories de deux Contexts et indiquer ce qu’ils partagent, ce qui diffère et ce qui n’apparaît que d’un côté.",
        "Comparer globalement deux Contexts afin de comprendre leurs convergences et leurs différences.",
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
        "Développer un Goal, une Rule ou une condition abstraite en plusieurs propositions candidates plus précises.",
        "Produire plusieurs Rules ou Cases candidats plus concrets à partir d’un concept ou d’une condition abstraite.",
    ),
    "embed": _copy(
        "Placer dans un Target local un lien vivant vers une Memory ou un Context tout en conservant la propriété de la Source.",
        "Réutiliser une Memory ou un Context dans un autre Context en suivant les modifications ultérieures de la Source.",
    ),
    "eval": _copy(
        "Exécuter et consulter les campagnes d’évaluation sémantique existantes.",
        "Utiliser le banc d’évaluation de recherche existant pendant la refonte de l’interface générale d’évaluation.",
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
        "Copier une version directe de Source Memory dans un Target sous forme de snapshot immuable en lecture seule.",
        "Conserver une version exacte de Memory même si sa Source change ou disparaît ensuite.",
    ),
    "rename": _copy(
        "Renommer le Profile géré courant ou indiqué sans déplacer ni réécrire son store ; mem profile rename est l’équivalent explicite.",
        "Donner un nom plus clair à un Profile géré existant.",
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
        "Restaurer un Context local à un checkpoint sélectionné, avec examen de l’impact exact lors d’une sélection interactive.",
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
    "shell-init": _copy(
        "Afficher l’intégration shell facultative pour le préremplissage interactif des commandes.",
        "Activer des facilités facultatives propres au shell.",
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

_ZH = {
    "add": _copy(
        "向当前或指定 Context 添加一个或多个 Memory。",
        "将一个或多个事实、指令或笔记直接添加到 Context 时。",
    ),
    "atomize": _copy(
        "立即将当前 Context 原子化为可独立审查的 Memory，并保存完整分析供 Review 查看。",
        "解开写在一起的要求或主张，使每一项都能独立审查和修改时。",
    ),
    "audit": _copy(
        "运行重复、歧义和冲突检查，可选执行 Rule 一致性检查，然后审查已保存的综合结果。",
        "在修改 Context 前进行综合质量审查时。",
    ),
    "branch": _copy(
        "将 Context 或其子树复制为新分支并切换到该分支。",
        "在保留原始内容的同时独立编辑 Context 或子树时。",
    ),
    "check-conformance": _copy(
        "依据明确的 Rule 或条件命题检查一个 Context 或已保存的 Ground Example，并报告不一致问题。",
        "验证现有 Memory 或 Example 是否满足指定 Rule 或条件命题时。",
    ),
    "checkout": _copy(
        "使用类似 Git 的语法切换 Context；使用 -b 时创建并切换到新的 Context 分支。",
        "以类似 Git 的工作流切换或创建分支时。",
    ),
    "checkpoint": _copy(
        "将当前 Context 保存为供 Diff 或 Revert 使用的手动恢复点。",
        "在风险操作前创建恢复点时。",
    ),
    "chunk": _copy(
        "按已配置的句子、分句、结构、文字字符或大小边界，机械拆分一个 Context 中所有可拆分的直接 Memory，或一个选定的 Memory。",
        "一个或多个直接 Memory 已有清晰的句子或结构边界，需要将其变为独立 Memory 时。",
    ),
    "clear": _copy(
        "确认后移除当前或指定 Context 中的所有直接项目。",
        "保留 Context 本身但清空其内容时。",
    ),
    "compare": _copy(
        "比较两个 Context 中的 Memory，报告共同点、差异以及仅存在于一侧的内容。",
        "整体比较两个 Context，以理解它们的一致与差异时。",
    ),
    "config": _copy(
        "读取或写入已保存的全局配置值。", "通过旧版底层接口查看或修改全局设置时。"
    ),
    "contexts": _copy(
        "浏览本地 Context 和可读的跨 Profile Context 视图，而不进行切换。",
        "查看当前 Profile 可访问的全部 Context 时。",
    ),
    "dedup": _copy(
        "审查已确认的重复组，在每组中保留一个现有 Memory，并在 Apply 时删除其余项。",
        "删除已确认的语义重复项，同时保留一个精确的现有 Memory 及其 UID 时。",
    ),
    "delete": _copy(
        "选择要删除的 Context 或直接项目，或通过 locator、名称或 UID 指定它。",
        "移除不再需要的特定 Context 或项目时。",
    ),
    "diff": _copy(
        "显示 Context checkpoint 或当前 Update 所记录的差异。",
        "精确验证已记录操作修改了什么时。",
    ),
    "distill": _copy(
        "从有界 Context 中的 Case 或 Example 命题推导更高层的 Rule 或条件命题，可由 Goal 提供可选引导。",
        "从多个具体案例或示例推导更一般的 Rule 或条件命题时。",
    ),
    "edit": _copy(
        "直接替换按 UID 或前缀选中的一个或多个 Memory 的内容。",
        "直接纠正或替换特定现有 Memory 的内容时。",
    ),
    "elaborate": _copy(
        "将抽象 Goal、Rule 或条件展开为多个更具体的候选命题。",
        "从抽象概念或条件生成若干更具体的候选 Rule 或 Case 时。",
    ),
    "embed": _copy(
        "在保留 Source 所有权的同时，将指向一个 Memory 或 Context 的实时链接放入本地 Target。",
        "在另一个 Context 中复用 Memory 或 Context，并跟随 Source 后续变化时。",
    ),
    "eval": _copy(
        "运行并查看现有的语义评估活动。",
        "在通用评估接口重构期间使用现有研究评估工具时。",
    ),
    "find": _copy(
        "在可读 Memory 中查找精确文本或明确的正则表达式（regex）匹配。",
        "在选定的 Context 范围内定位精确词语、标识符或文本模式时。",
    ),
    "find-ambiguities": _copy(
        "报告当前或指定 Context 中含义模糊的直接 Memory；不修改 Context。",
        "查找允许不清楚或多种解释的 Memory 时。",
    ),
    "find-conflicts": _copy(
        "报告当前或指定 Context 中相互冲突的直接 Memory 对；不修改 Context。",
        "查找彼此不兼容的主张或指令时。",
    ),
    "find-duplicates": _copy(
        "报告当前或指定 Context 中重复的直接 Memory；不修改 Context。",
        "在清理前定位语义冗余的 Memory 时。",
    ),
    "fit": _copy(
        "按通常理解判断一组已定义的 Memory 或其他命题能否共同成立，并返回 YES、MAY 或 NO。",
        "检查一组已定义的 Memory、Rule、Goal、Example 或其他命题能否共同成立时。",
    ),
    "forget": _copy(
        "针对一条指令审查保留、编辑或删除决定，然后应用已接受的批次。",
        "依据需要解释含义的自然语言指令删除或改写 Memory 时。",
    ),
    "ground": _copy(
        "通过共同塑造 Goal、Rule 和示例 Memory，将抽象想法发展为可审查的 Ground。",
        "通过共同修订 Rule 和具体 Example，梳理抽象目标在实践中应如何运作时。",
    ),
    "help": _copy(
        "进入交互式命令浏览器并打开语法帮助。", "了解可用 operation 及其调用形式时。"
    ),
    "impact": _copy(
        "在不应用的情况下预览或检查 operation 对 Context 的预期影响。",
        "在单独执行 Apply 前验证 operation 所提议的影响时。",
    ),
    "import": _copy(
        "按值导入干净基线的 Profile、Context 树或 Memory，同时保留资源身份。",
        "将外部提供的材料带入本地管理的 store 时。",
    ),
    "init": _copy(
        "创建一个新的空 Context，并将其设为当前工作 Context。",
        "为新主题、任务或一组 Memory 建立独立工作区时。",
    ),
    "init-study": _copy(
        "将一个 Study baseline 复制到隔离的参与者/权限方 Profile 对中。",
        "准备可复现且隔离的用户研究环境时。",
    ),
    "list": _copy(
        "列出 Context 的直接项目——Memory、Memory reference、query view 和嵌入的 Context——以及可读子 Context；-r 递归包含后代和嵌入 Context 中的项目，ls 是简短别名。",
        "检查 Context 的结构和直接内容时。",
    ),
    "lock": _copy(
        "锁定当前 Context、递归 Context 集、Memory 或 Profile。",
        "防止稳定材料被意外修改时。",
    ),
    "log": _copy(
        "输出或搜索已记录的 Context、Memory 和 Profile 历史。",
        "调查先前 operation、checkpoint 或 Memory 历史时。",
    ),
    "meld": _copy(
        "在语义上协调两个 Context，可生成独立 Result，也可将提议的修改纳入现有 Target Context。",
        "合并两组工作，并需要对重叠、冲突和新合成内容进行语义审查时。",
    ),
    "merge": _copy(
        "将 Source 独有项目添加到所选 Target，保持精确匹配不变，并在已存项目冲突时选择 Source 或 Target。",
        "追加 Source 独有项目，或将复制/分支的 Context 合入所选 Target Context，且不进行语义合成时。",
    ),
    "profile": _copy(
        "选择和管理完整的本地 MemoryStore Profile；还可通过选择器或 mem profile rename/remove 重命名或永久删除。",
        "管理相互独立的用户、环境或 Memory store 时。",
    ),
    "provider": _copy(
        "选择并验证 Codex、Ollama 或 OpenRouter 的语义执行。",
        "选择语义 operation 使用的后端，或在持久操作前检查其是否就绪时。",
    ),
    "pwd": _copy(
        "输出当前规范 Context 名称，而不加载其内容。",
        "在脚本或终端中确认当前活动 Context 时。",
    ),
    "query": _copy(
        "根据可读 Context 知识或获授权的隐藏 query-only 视图生成基于 LLM 的答案。",
        "需要有依据的自然语言回答，而不是匹配 Memory 列表时。",
    ),
    "rationale": _copy(
        "依据已记录的来源，并在必要时结合推断，解释一个 Memory。",
        "理解某个 Memory 为何存在或如何形成当前状态时。",
    ),
    "redo": _copy(
        "重新执行最近一次被撤销的已记录 Context 命令。", "重新应用被意外撤销的命令时。"
    ),
    "reference": _copy(
        "将一个直接 Source Memory 版本复制到 Target，作为不可变的只读 snapshot。",
        "即使 Source 后续改变或消失，也要保留某个精确 Memory 版本时。",
    ),
    "rename": _copy(
        "重命名当前或指定的受管 Profile，而不移动或重写其 store；mem profile rename 是显式等价形式。",
        "为现有受管 Profile 提供更清晰的名称时。",
    ),
    "replace": _copy(
        "预览并替换普通本地 Memory 中每个文字或明确 regex 匹配。",
        "在已知本地 Context 范围内纠正、重命名或遮蔽精确文本时。",
    ),
    "resolve": _copy(
        "提出并验证使一个有界直接 Memory Context frame 达到 Fit YES 的最小修改。",
        "决定如何修复有界 Context frame 中的语义冲突或歧义时。",
    ),
    "revert": _copy(
        "将一个本地 Context 恢复到选定 checkpoint；交互选择时会审查精确影响。",
        "将 Context 恢复到有意保存的恢复点时。",
    ),
    "review": _copy(
        "打开已保存的语义产物以检查分析、提案或结果状态，并在支持时记录审查回应；Review 从不应用 Memory。",
        "重新查看已保存的分析、提案或结果状态时。",
    ),
    "search": _copy(
        "在选定 Context 中按语义排列与自然语言请求相关的 Memory。",
        "通过含义和上下文寻找相关 Memory，包括没有明显关键词重合的相关内容时。",
    ),
    "sever": _copy(
        "依据 Criteria Context 选择、转换或排除 Source Memory，以创建 Result。",
        "依据明确标准选择或转换 Source 内容时。",
    ),
    "share": _copy(
        "通过由 Grant 支持的接收端点发送一个普通 Context。",
        "将自己拥有的 Context 交付给获授权接收者时。",
    ),
    "shell-init": _copy(
        "输出可选的 shell 集成，用于交互式命令预填充。",
        "启用可选的 shell 专用便利功能时。",
    ),
    "show": _copy(
        "显示 Memory、reference、嵌入的 Context，或当前/指定 Context 的直接内容。",
        "阅读已知项目或 Context 的完整内容时。",
    ),
    "status": _copy(
        "显示当前 Context 的清单、前五个直接 Memory、关系和最新 checkpoint。",
        "了解当前 Context 包含什么、如何连接以及最近应用了哪些 operation 时。",
    ),
    "summarize": _copy(
        "显示由 LLM 推导的可读 Context 范围内普通 Memory 概览。",
        "获取 Context 或子树的简洁概览时。",
    ),
    "switch": _copy(
        "进入交互式 Context 选择器，或切换到明确指定的 Context。",
        "将工作位置移动到另一个现有 Context 时。",
    ),
    "trace": _copy(
        "沿已记录的谱系追踪一个保留的 Memory。", "确定 Memory 的来源及其变化过程时。"
    ),
    "translate": _copy(
        "生成并保存一个 Context 或 Memory 的可复用翻译视图，同时保留原始内容。",
        "在不替换原文的情况下，以另一种语言阅读或复用 Memory 内容时。",
    ),
    "undo": _copy(
        "将最近一次已记录命令作为一个整体撤销。",
        "将最新的已记录变更作为一个 operation 逆转时。",
    ),
    "unlock": _copy(
        "解锁当前 Context、递归集合、Memory 或 Profile。",
        "重新开放受保护材料以进行有意修改时。",
    ),
    "update": _copy(
        "使用 Source Context 中的 Memory 更新 Target Context 中的 Memory，并在需要时要求用户审查和选择。",
        "使用新验证的 Memory 更新现有 Context 时。",
    ),
}

_KO = {
    "add": _copy(
        "현재 또는 지정한 Context에 하나 이상의 Memory를 추가합니다.",
        "하나 이상의 사실, 지침 또는 메모를 Context에 직접 추가할 때.",
    ),
    "atomize": _copy(
        "현재 Context를 독립적으로 검토할 수 있는 Memory로 즉시 atomize하고 전체 분석을 Review에 저장합니다.",
        "함께 적힌 요구사항이나 주장을 각각 독립적으로 검토하고 수정할 수 있도록 풀어낼 때.",
    ),
    "audit": _copy(
        "중복·모호성·충돌 검사와 선택적인 Rule Conformance를 실행한 뒤 저장된 종합 결과를 검토합니다.",
        "Context를 수정하기 전에 종합적인 품질 검토를 수행할 때.",
    ),
    "branch": _copy(
        "Context 또는 하위 트리를 새 branch로 복사하고 그곳으로 전환합니다.",
        "원본을 보존하면서 Context 또는 하위 트리를 독립적으로 수정할 때.",
    ),
    "check-conformance": _copy(
        "명시된 Rule 또는 조건 명제를 기준으로 하나의 Context나 저장된 Ground Example을 검사하고 부합 문제를 보고합니다.",
        "기존 Memory나 Example이 명시된 Rule 또는 조건 명제를 만족하는지 확인할 때.",
    ),
    "checkout": _copy(
        "Git 방식 문법으로 Context를 전환하며, -b를 사용하면 새 Context branch를 만들고 전환합니다.",
        "Git과 유사한 흐름으로 branch를 전환하거나 생성할 때.",
    ),
    "checkpoint": _copy(
        "현재 Context를 Diff 또는 Revert에 사용할 수동 복구 지점으로 저장합니다.",
        "위험한 작업 전에 복구 지점을 만들 때.",
    ),
    "chunk": _copy(
        "한 Context에서 나눌 수 있는 모든 직접 Memory 또는 선택한 Memory 하나를 설정한 문장·절·구조·리터럴·크기 경계에서 기계적으로 나눕니다.",
        "하나 이상의 직접 Memory에 이미 분명한 문장 또는 구조 경계가 있고 이를 별도 Memory로 만들 때.",
    ),
    "clear": _copy(
        "현재 또는 지정한 Context의 모든 직접 항목을 즉시 제거하며 Undo로 복구할 수 있습니다.",
        "Context 자체는 유지하면서 그 안을 비울 때.",
    ),
    "compare": _copy(
        "두 Context의 Memory를 비교하여 공통점, 차이점, 한쪽에만 있는 내용을 보고합니다.",
        "두 Context 전체가 어디에서 일치하고 다른지 이해하기 위해 비교할 때.",
    ),
    "config": _copy(
        "저장된 전역 설정 값을 읽거나 씁니다.",
        "legacy 저수준 인터페이스로 저장된 전역 설정을 확인하거나 변경할 때.",
    ),
    "contexts": _copy(
        "전환하지 않고 로컬 Context와 읽을 수 있는 Profile 간 Context view를 탐색합니다.",
        "현재 Profile에서 사용할 수 있는 모든 Context를 살펴볼 때.",
    ),
    "dedup": _copy(
        "확인된 중복 그룹을 검토하여 각 그룹에서 기존 Memory 하나를 남기고 Apply 시 나머지를 삭제합니다.",
        "정확한 기존 Memory 하나와 그 UID를 보존하면서 확인된 의미적 중복을 제거할 때.",
    ),
    "delete": _copy(
        "삭제할 Context 또는 직접 항목을 선택하거나 locator, 이름 또는 UID로 지정합니다.",
        "더 이상 필요하지 않은 특정 Context나 항목을 제거할 때.",
    ),
    "diff": _copy(
        "Context checkpoint 또는 활성 Update가 기록한 차이를 보여줍니다.",
        "기록된 operation이 정확히 무엇을 변경했는지 확인할 때.",
    ),
    "distill": _copy(
        "선택적인 Goal의 안내를 받아 제한된 Context의 Case 또는 Example 명제에서 상위 Rule이나 조건 명제를 도출합니다.",
        "여러 구체적인 사례나 예시에서 더 일반적인 Rule 또는 조건 명제를 추론할 때.",
    ),
    "edit": _copy(
        "UID 또는 prefix로 선택한 하나 이상의 Memory 내용을 직접 교체합니다.",
        "특정 기존 Memory의 내용을 직접 바로잡거나 교체할 때.",
    ),
    "elaborate": _copy(
        "추상적인 Goal, Rule 또는 조건을 더 구체적인 여러 후보 명제로 확장합니다.",
        "추상적인 개념이나 조건에서 더 구체적인 여러 후보 Rule 또는 Case를 만들 때.",
    ),
    "embed": _copy(
        "Source 소유권을 유지하면서 하나의 Memory 또는 Context를 가리키는 live link를 로컬 Target 안에 둡니다.",
        "Source의 이후 변경을 따라가면서 Memory나 Context를 다른 Context에서 재사용할 때.",
    ),
    "eval": _copy(
        "기존 semantic evaluation campaign을 실행하고 확인합니다.",
        "일반 evaluation 인터페이스를 재설계하는 동안 기존 연구용 evaluation harness를 사용할 때.",
    ),
    "find": _copy(
        "읽을 수 있는 Memory에서 정확한 텍스트 또는 명시적인 정규식(regex) 일치를 찾습니다.",
        "선택한 Context 범위 안에서 정확한 단어, 식별자 또는 텍스트 패턴을 찾을 때.",
    ),
    "find-ambiguities": _copy(
        "현재 또는 지정한 Context에서 모호한 직접 Memory를 보고하며 Context는 변경하지 않습니다.",
        "불분명하거나 여러 해석을 허용하는 Memory를 찾을 때.",
    ),
    "find-conflicts": _copy(
        "현재 또는 지정한 Context에서 충돌하는 직접 Memory 쌍을 보고하며 Context는 변경하지 않습니다.",
        "서로 양립할 수 없는 주장이나 지침을 찾을 때.",
    ),
    "find-duplicates": _copy(
        "현재 또는 지정한 Context에서 중복 직접 Memory를 보고하며 Context는 변경하지 않습니다.",
        "정리하기 전에 의미적으로 중복된 Memory를 찾을 때.",
    ),
    "fit": _copy(
        "정의된 Memory 또는 다른 명제 집합이 일반적인 해석에서 함께 양립 가능한지 판단하고 YES, MAY 또는 NO를 반환합니다.",
        "정의된 Memory, Rule, Goal, Example 또는 다른 명제들이 함께 성립할 수 있는지 확인할 때.",
    ),
    "forget": _copy(
        "하나의 지침에 따라 유지·수정·삭제 결정을 검토한 뒤 승인한 묶음을 적용합니다.",
        "의미 해석이 필요한 자연어 지침에 따라 Memory를 제거하거나 다시 쓸 때.",
    ),
    "ground": _copy(
        "Goal, Rule, 예시 Memory를 함께 다듬어 추상적인 아이디어를 검토 가능한 Ground로 발전시킵니다.",
        "공동으로 수정하는 Rule과 구체적인 Example을 통해 추상적 목표가 실제로 어떻게 작동해야 하는지 구체화할 때.",
    ),
    "help": _copy(
        "대화형 command browser에 들어가 문법 도움말을 엽니다.",
        "사용 가능한 operation과 호출 형식을 알아볼 때.",
    ),
    "impact": _copy(
        "operation이 Context에 미칠 예상 효과를 적용하지 않고 미리 보거나 검사합니다.",
        "별도의 Apply 전에 operation이 제안한 효과를 확인할 때.",
    ),
    "import": _copy(
        "resource identity를 유지하면서 clean-baseline Profile, Context tree 또는 Memory를 값으로 가져옵니다.",
        "외부에서 제공된 자료를 로컬에서 관리하는 store로 가져올 때.",
    ),
    "init": _copy(
        "새 빈 Context를 만들고 현재 작업 Context로 설정합니다.",
        "새 주제, 작업 또는 Memory 묶음을 위한 별도 작업 공간을 시작할 때.",
    ),
    "init-study": _copy(
        "하나의 Study baseline을 격리된 participant/authority Profile 쌍으로 복사합니다.",
        "재현 가능하고 격리된 사용자 연구 환경을 준비할 때.",
    ),
    "list": _copy(
        "Context의 직접 항목—Memory, Memory reference, query view, embedded Context—과 읽을 수 있는 하위 Context를 나열합니다. -r은 descendant 및 embedded Context 항목까지 재귀적으로 포함하며 ls는 짧은 alias입니다.",
        "Context의 구조와 직접 내용을 살펴볼 때.",
    ),
    "lock": _copy(
        "현재 Context, 재귀 Context 집합, Memory 또는 Profile을 잠급니다.",
        "안정된 자료가 실수로 수정되는 것을 막을 때.",
    ),
    "log": _copy(
        "기록된 Context, Memory 및 Profile 기록을 출력하거나 검색합니다.",
        "이전 operation, checkpoint 또는 Memory 기록을 조사할 때.",
    ),
    "meld": _copy(
        "두 Context를 의미적으로 조정하여 별도 Result를 만들거나 제안된 변경을 기존 Target Context에 반영합니다.",
        "겹침, 충돌, 새로 합성된 내용을 의미적으로 검토하면서 두 작업 묶음을 결합할 때.",
    ),
    "merge": _copy(
        "Source에만 있는 항목을 선택한 Target에 추가하고 정확히 일치하는 항목은 그대로 두며 저장 항목 충돌 시 Source 또는 Target을 선택합니다.",
        "의미적 합성 없이 Source 전용 항목을 덧붙이거나 복사·분기한 Context를 선택한 Target Context로 가져올 때.",
    ),
    "profile": _copy(
        "완전한 로컬 MemoryStore Profile을 선택하고 관리합니다. picker 또는 mem profile rename/remove로 이름을 바꾸거나 영구 삭제할 수도 있습니다.",
        "서로 분리된 사용자, 환경 또는 Memory store를 관리할 때.",
    ),
    "provider": _copy(
        "Codex, Ollama 또는 OpenRouter semantic execution을 선택하고 검증합니다.",
        "semantic operation이 사용할 backend를 선택하거나 지속 작업 전에 준비 상태를 확인할 때.",
    ),
    "pwd": _copy(
        "내용을 불러오지 않고 현재 canonical Context 이름을 출력합니다.",
        "script나 terminal에서 활성 Context를 확인할 때.",
    ),
    "query": _copy(
        "읽을 수 있는 Context 지식 또는 허가된 concealed query-only view에서 LLM 기반 답변을 생성합니다.",
        "일치하는 Memory 목록 대신 근거 있는 자연어 답변을 얻을 때.",
    ),
    "rationale": _copy(
        "기록된 provenance와 필요시 inference를 바탕으로 하나의 Memory를 설명합니다.",
        "Memory가 왜 존재하거나 현재 형태에 이르렀는지 이해할 때.",
    ),
    "redo": _copy(
        "가장 최근에 undo한 기록된 Context command를 다시 실행합니다.",
        "실수로 undo한 command를 다시 적용할 때.",
    ),
    "reference": _copy(
        "하나의 직접 Source Memory 버전을 변경 불가능한 read-only snapshot으로 Target에 복사합니다.",
        "Source가 나중에 변경되거나 사라져도 정확한 Memory 버전 하나를 유지할 때.",
    ),
    "rename": _copy(
        "store를 이동하거나 다시 쓰지 않고 현재 또는 지정한 managed Profile의 이름을 바꿉니다. mem profile rename은 명시적인 동일 기능입니다.",
        "기존 managed Profile에 더 명확한 이름을 붙일 때.",
    ),
    "replace": _copy(
        "일반 로컬 Memory의 모든 literal 또는 명시적 regex 일치를 미리 보고 교체합니다.",
        "알고 있는 로컬 Context 범위 전체에서 정확한 텍스트를 수정·이름 변경·가림 처리할 때.",
    ),
    "resolve": _copy(
        "제한된 direct-Memory Context frame을 Fit YES로 만드는 최소 변경을 제안하고 검증합니다.",
        "제한된 Context frame 안의 의미적 충돌이나 모호성을 어떻게 고칠지 결정할 때.",
    ),
    "revert": _copy(
        "하나의 로컬 Context를 선택한 checkpoint로 복원하며, 대화형 선택에서는 정확한 영향을 검토합니다.",
        "Context를 의도적으로 저장한 복구 지점으로 되돌릴 때.",
    ),
    "review": _copy(
        "저장된 semantic artifact를 열어 분석·제안·결과 상태를 살펴보고 지원되는 경우 검토 응답을 기록합니다. Review는 Memory를 적용하지 않습니다.",
        "저장된 분석, 제안 또는 결과 상태를 다시 살펴볼 때.",
    ),
    "search": _copy(
        "선택한 Context에서 자연어 요청과 관련된 Memory를 의미적으로 순위화합니다.",
        "의미와 맥락으로 관련 Memory를 찾고, 명시적 키워드가 겹치지 않는 관련 내용까지 포함할 때.",
    ),
    "sever": _copy(
        "Criteria Context에 따라 Source Memory를 선택·변환·제외하여 Result를 만듭니다.",
        "정해진 기준에 따라 Source 내용을 선택하거나 변환할 때.",
    ),
    "share": _copy(
        "Grant 기반 receiver endpoint를 통해 하나의 일반 Context를 보냅니다.",
        "소유한 Context를 권한 있는 수신자에게 전달할 때.",
    ),
    "shell-init": _copy(
        "대화형 command prefill을 위한 선택적 shell integration을 출력합니다.",
        "선택적인 shell별 편의 기능을 활성화할 때.",
    ),
    "show": _copy(
        "Memory, reference, embedded Context 또는 현재/지정 Context의 직접 내용을 보여줍니다.",
        "알고 있는 항목이나 Context의 전체 내용을 읽을 때.",
    ),
    "status": _copy(
        "현재 Context의 inventory, 처음 다섯 개의 직접 Memory, 관계 및 최신 checkpoint를 보여줍니다.",
        "현재 Context에 무엇이 있고 어떻게 연결되며 최근 어떤 operation이 적용됐는지 파악할 때.",
    ),
    "summarize": _copy(
        "읽을 수 있는 Context 범위의 일반 Memory에 대해 LLM이 도출한 개요를 보여줍니다.",
        "Context 또는 하위 트리의 간결한 개요를 얻을 때.",
    ),
    "switch": _copy(
        "대화형 Context picker로 들어가거나 명시한 Context로 전환합니다.",
        "작업 위치를 다른 기존 Context로 옮길 때.",
    ),
    "trace": _copy(
        "보존된 하나의 Memory를 기록된 lineage를 따라 추적합니다.",
        "Memory가 어디에서 왔고 어떻게 변했는지 확인할 때.",
    ),
    "translate": _copy(
        "원본 내용을 보존하면서 하나의 Context 또는 Memory에 대한 재사용 가능한 번역 view를 생성하고 저장합니다.",
        "원본을 교체하지 않고 Memory 내용을 다른 언어로 읽거나 재사용할 때.",
    ),
    "undo": _copy(
        "가장 최근에 기록된 command를 하나의 단위로 되돌립니다.",
        "가장 최근에 기록된 변경을 하나의 operation으로 되돌릴 때.",
    ),
    "unlock": _copy(
        "현재 Context, 재귀 집합, Memory 또는 Profile의 잠금을 해제합니다.",
        "보호된 자료를 의도적으로 수정할 수 있도록 다시 열 때.",
    ),
    "update": _copy(
        "Source Context의 Memory를 사용해 Target Context의 Memory를 업데이트하며 필요할 때 사용자에게 검토와 선택을 요청합니다.",
        "새로 검증된 Memory로 기존 Context를 업데이트할 때.",
    ),
}

_MN = {
    "add": _copy(
        "Одоогийн эсвэл заасан Context-д нэг буюу хэд хэдэн Memory нэмнэ.",
        "Нэг буюу хэд хэдэн баримт, заавар эсвэл тэмдэглэлийг Context-д шууд нэмэх үед.",
    ),
    "atomize": _copy(
        "Одоогийн Context-г тус тусад нь хянах боломжтой Memory болгон шууд atomize хийж, бүрэн шинжилгээг Review-д хадгална.",
        "Хамт бичигдсэн шаардлага эсвэл мэдэгдлийг тус бүрд нь хянаж, засахын тулд задлах үед.",
    ),
    "audit": _copy(
        "Давхардал, хоёрдмол утга, зөрчлийн шалгалт болон сонголттой Rule Conformance-г ажиллуулаад хадгалсан нэгдсэн үр дүнг хянана.",
        "Context-г засахаас өмнө чанарын нэгдсэн шалгалт хийх үед.",
    ),
    "branch": _copy(
        "Context эсвэл дэд модыг шинэ branch руу хуулж, түүн рүү шилжинэ.",
        "Эх хувийг хадгалангаа Context эсвэл дэд модыг тусад нь засах үед.",
    ),
    "check-conformance": _copy(
        "Тодорхой Rule эсвэл нөхцөлт өгүүлбэрийн дагуу нэг Context эсвэл хадгалсан Ground Example-г шалгаж, нийцлийн асуудлыг мэдээлнэ.",
        "Одоо байгаа Memory эсвэл Example нь заасан Rule эсвэл нөхцөлт өгүүлбэрийг хангаж буй эсэхийг шалгах үед.",
    ),
    "checkout": _copy(
        "Git-тэй төстэй бичлэгээр Context солино; -b ашиглавал шинэ Context branch үүсгээд түүн рүү шилжинэ.",
        "Git-тэй төстэй урсгалаар branch солих эсвэл үүсгэх үед.",
    ),
    "checkpoint": _copy(
        "Одоогийн Context-г Diff эсвэл Revert-д ашиглах гарын авлагын сэргээх цэг болгон хадгална.",
        "Эрсдэлтэй ажлын өмнө сэргээх цэг үүсгэх үед.",
    ),
    "chunk": _copy(
        "Нэг Context доторх хувааж болох бүх шууд Memory эсвэл сонгосон нэг Memory-г тохируулсан өгүүлбэр, өгүүлбэрийн хэсэг, бүтэц, тэмдэгт эсвэл хэмжээний хилээр механикаар хуваана.",
        "Нэг буюу хэд хэдэн шууд Memory нь тусдаа Memory болгох тодорхой өгүүлбэрийн эсвэл бүтцийн хилтэй үед.",
    ),
    "clear": _copy(
        "Баталгаажуулсны дараа одоогийн эсвэл заасан Context-ийн бүх шууд зүйлийг арилгана.",
        "Context-г өөрийг нь үлдээн доторхыг хоослох үед.",
    ),
    "compare": _copy(
        "Хоёр Context-ийн Memory-г харьцуулж, нийтлэг, ялгаатай болон зөвхөн нэг талд буй зүйлсийг мэдээлнэ.",
        "Хоёр Context бүхэлдээ хаана нийцэж, хаана ялгаатайг ойлгохын тулд харьцуулах үед.",
    ),
    "config": _copy(
        "Хадгалсан глобал тохиргооны утгыг унших эсвэл бичнэ.",
        "Legacy доод түвшний интерфэйсээр глобал тохиргоог харах эсвэл өөрчлөх үед.",
    ),
    "contexts": _copy(
        "Шилжихгүйгээр локал Context болон унших боломжтой Profile хоорондын Context view-г үзнэ.",
        "Одоогийн Profile-д боломжтой бүх Context-г судлах үед.",
    ),
    "dedup": _copy(
        "Батлагдсан давхардлын бүлгүүдийг хянаж, бүлэг бүрээс нэг одоогийн Memory-г үлдээн Apply хийхэд бусдыг устгана.",
        "Нэг яг одоогийн Memory болон түүний UID-г хадгалж, батлагдсан утгын давхардлыг арилгах үед.",
    ),
    "delete": _copy(
        "Устгах Context эсвэл шууд зүйлийг сонгох, эсвэл locator, нэр, UID-аар заана.",
        "Хэрэггүй болсон тодорхой Context эсвэл зүйлийг арилгах үед.",
    ),
    "diff": _copy(
        "Context checkpoint эсвэл идэвхтэй Update-д бүртгэгдсэн ялгааг харуулна.",
        "Бүртгэгдсэн operation яг юуг өөрчилснийг шалгах үед.",
    ),
    "distill": _copy(
        "Хязгаарлагдсан Context-ийн Case эсвэл Example өгүүлбэрээс дээд түвшний Rule эсвэл нөхцөлт өгүүлбэр гаргана; Goal-аар чиглүүлж болно.",
        "Хэд хэдэн бодит тохиолдол эсвэл жишээнээс илүү ерөнхий Rule эсвэл нөхцөлт өгүүлбэр дүгнэх үед.",
    ),
    "edit": _copy(
        "UID эсвэл prefix-ээр сонгосон нэг буюу хэд хэдэн Memory-н агуулгыг шууд солино.",
        "Тодорхой одоогийн Memory-н агуулгыг шууд засах эсвэл солих үед.",
    ),
    "elaborate": _copy(
        "Хийсвэр Goal, Rule эсвэл нөхцөлийг хэд хэдэн илүү тодорхой нэр дэвшигч өгүүлбэр болгон дэлгэрүүлнэ.",
        "Хийсвэр ойлголт эсвэл нөхцөлөөс хэд хэдэн илүү тодорхой Rule эсвэл Case нэр дэвшигч гаргах үед.",
    ),
    "embed": _copy(
        "Source эзэмшлийг хадгалж, нэг Memory эсвэл Context руу заасан амьд холбоосыг локал Target дотор байрлуулна.",
        "Source-н дараагийн өөрчлөлтийг даган Memory эсвэл Context-г өөр Context-д дахин ашиглах үед.",
    ),
    "eval": _copy(
        "Одоогийн semantic evaluation campaign-уудыг ажиллуулж, шалгана.",
        "Ерөнхий evaluation интерфэйс шинэчлэгдэж байх үед одоогийн судалгааны evaluation хэрэгслийг ашиглах үед.",
    ),
    "find": _copy(
        "Унших боломжтой Memory дотроос яг текст эсвэл тодорхой regular expression (regex) таарцыг олно.",
        "Сонгосон Context хүрээн дотор яг үг, танигч эсвэл текстийн загвар олох үед.",
    ),
    "find-ambiguities": _copy(
        "Одоогийн эсвэл заасан Context доторх хоёрдмол утгатай шууд Memory-г мэдээлнэ; Context өөрчлөхгүй.",
        "Тодорхой бус эсвэл олон тайлбар боломжтой Memory олох үед.",
    ),
    "find-conflicts": _copy(
        "Одоогийн эсвэл заасан Context доторх зөрчилтэй шууд Memory хосыг мэдээлнэ; Context өөрчлөхгүй.",
        "Харилцан нийцэхгүй мэдэгдэл эсвэл заавар олох үед.",
    ),
    "find-duplicates": _copy(
        "Одоогийн эсвэл заасан Context доторх давхардсан шууд Memory-г мэдээлнэ; Context өөрчлөхгүй.",
        "Цэвэрлэхийн өмнө утгын хувьд давхардсан Memory олох үед.",
    ),
    "fit": _copy(
        "Тодорхойлсон Memory эсвэл бусад өгүүлбэрийн багц ердийн ойлголтоор хамтдаа нийцэх эсэхийг дүгнэж YES, MAY эсвэл NO буцаана.",
        "Тодорхой Memory, Rule, Goal, Example эсвэл бусад өгүүлбэрүүд хамтдаа биелэх боломжтой эсэхийг шалгах үед.",
    ),
    "forget": _copy(
        "Нэг зааврын дагуу үлдээх, засах, устгах шийдвэрийг хянаад зөвшөөрсөн багцыг хэрэглэнэ.",
        "Утгыг тайлбарлах шаардлагатай байгалийн хэлний заавраар Memory-г устгах эсвэл дахин бичих үед.",
    ),
    "ground": _copy(
        "Goal, Rule болон жишээ Memory-г хамт хөгжүүлж, хийсвэр санааг хянах боломжтой Ground болгоно.",
        "Хийсвэр зорилго бодит амьдралд хэрхэн ажиллахыг хамт засварласан Rule болон тодорхой Example-ээр боловсруулах үед.",
    ),
    "help": _copy(
        "Интерактив command browser руу орж, синтаксын тусламжийг нээнэ.",
        "Боломжтой operation болон тэдгээрийн дуудах хэлбэрийг судлах үед.",
    ),
    "impact": _copy(
        "Operation-н Context-д үзүүлэх хүлээгдэж буй нөлөөг хэрэглэхгүйгээр урьдчилан харж эсвэл шалгана.",
        "Тусдаа Apply хийхээс өмнө operation-н санал болгосон нөлөөг шалгах үед.",
    ),
    "import": _copy(
        "Нөөцийн identity-г хадгалан clean-baseline Profile, Context tree эсвэл Memory-г утгаар импортолно.",
        "Гаднаас өгсөн материалыг локал удирдлагатай store-д оруулах үед.",
    ),
    "init": _copy(
        "Шинэ хоосон Context үүсгээд одоогийн ажлын Context болгоно.",
        "Шинэ сэдэв, даалгавар эсвэл Memory-н бүлэгт зориулсан тусдаа ажлын орчин эхлүүлэх үед.",
    ),
    "init-study": _copy(
        "Нэг Study baseline-г тусгаарлагдсан participant/authority Profile хос руу хуулна.",
        "Дахин давтагдах, тусгаарлагдсан хэрэглэгчийн судалгааны орчин бэлтгэх үед.",
    ),
    "list": _copy(
        "Context-ийн шууд зүйлс—Memory, Memory reference, query view, embedded Context—болон унших боломжтой child Context-уудыг жагсаана. -r нь descendant болон embedded Context-ийн зүйлсийг рекурсээр оруулна; ls бол богино alias.",
        "Context-ийн бүтэц болон шууд агуулгыг шалгах үед.",
    ),
    "lock": _copy(
        "Одоогийн Context, рекурсив Context багц, Memory эсвэл Profile-г түгжинэ.",
        "Тогтвортой материалыг санамсаргүй өөрчлөхөөс сэргийлэх үед.",
    ),
    "log": _copy(
        "Бүртгэгдсэн Context, Memory болон Profile түүхийг хэвлэх эсвэл хайна.",
        "Өмнөх operation, checkpoint эсвэл Memory түүхийг судлах үед.",
    ),
    "meld": _copy(
        "Хоёр Context-г утгын хувьд нийцүүлж, тусдаа Result үүсгэх эсвэл санал болгосон өөрчлөлтийг одоогийн Target Context-д нэгтгэнэ.",
        "Давхцал, зөрчил, шинээр нэгтгэсэн агуулгыг утгын хувьд хянах шаардлагатай хоёр ажлын багцыг нийлүүлэх үед.",
    ),
    "merge": _copy(
        "Зөвхөн Source-д буй зүйлсийг сонгосон Target-д нэмээд яг таарсан зүйлсийг хэвээр үлдээж, хадгалсан зүйлсийн зөрчилд Source эсвэл Target-г сонгоно.",
        "Утгын нэгтгэлгүйгээр Source-д л буй зүйлсийг нэмэх эсвэл хуулсан/салбарласан Context-г сонгосон Target Context руу оруулах үед.",
    ),
    "profile": _copy(
        "Бүрэн локал MemoryStore Profile-г сонгож удирдана. Picker эсвэл mem profile rename/remove-оор нэрийг солих эсвэл бүрмөсөн устгаж болно.",
        "Тусдаа хэрэглэгч, орчин эсвэл Memory store удирдах үед.",
    ),
    "provider": _copy(
        "Codex, Ollama эсвэл OpenRouter semantic execution-г сонгож баталгаажуулна.",
        "Semantic operation ашиглах backend-г сонгох эсвэл удаан хадгалах ажлын өмнө бэлэн эсэхийг шалгах үед.",
    ),
    "pwd": _copy(
        "Агуулгыг ачаалахгүйгээр одоогийн canonical Context нэрийг хэвлэнэ.",
        "Script эсвэл terminal дотор идэвхтэй Context-г баталгаажуулах үед.",
    ),
    "query": _copy(
        "Унших боломжтой Context мэдлэг эсвэл зөвшөөрөгдсөн далд query-only view-гээс LLM-д суурилсан хариулт үүсгэнэ.",
        "Таарсан Memory-н жагсаалтын оронд үндэслэлтэй байгалийн хэлний хариулт авах үед.",
    ),
    "rationale": _copy(
        "Бүртгэгдсэн provenance болон шаардлагатай үед inference ашиглан нэг Memory-г тайлбарлана.",
        "Memory яагаад оршин буй эсвэл одоогийн хэлбэрт хэрхэн хүрснийг ойлгох үед.",
    ),
    "redo": _copy(
        "Хамгийн сүүлд undo хийсэн бүртгэгдсэн Context command-г дахин хийнэ.",
        "Санамсаргүй undo хийсэн command-г дахин хэрэглэх үед.",
    ),
    "reference": _copy(
        "Нэг шууд Source Memory хувилбарыг өөрчлөгдөшгүй read-only snapshot болгон Target руу хуулна.",
        "Source дараа нь өөрчлөгдөх эсвэл алга болсон ч нэг яг Memory хувилбарыг хадгалах үед.",
    ),
    "rename": _copy(
        "Store-г зөөх эсвэл дахин бичихгүйгээр одоогийн эсвэл заасан managed Profile-н нэрийг солино; mem profile rename нь илэрхий ижил хэлбэр.",
        "Одоо байгаа managed Profile-д илүү ойлгомжтой нэр өгөх үед.",
    ),
    "replace": _copy(
        "Ердийн локал Memory доторх бүх literal эсвэл тодорхой regex таарцыг урьдчилан харж солино.",
        "Мэдэгдэж буй локал Context хүрээнд яг текстийг засах, нэр солих эсвэл нууцлах үед.",
    ),
    "resolve": _copy(
        "Хязгаарлагдсан direct-Memory Context frame-г Fit YES болгох хамгийн бага өөрчлөлтийг санал болгож баталгаажуулна.",
        "Хязгаарлагдсан Context frame доторх утгын зөрчил эсвэл хоёрдмол байдлыг хэрхэн засахыг шийдэх үед.",
    ),
    "revert": _copy(
        "Нэг локал Context-г сонгосон checkpoint руу сэргээж, интерактив сонголтын үед яг нөлөөг хянана.",
        "Context-г зориуд хадгалсан сэргээх цэг рүү буцаах үед.",
    ),
    "review": _copy(
        "Хадгалсан semantic artifact-г нээж analysis, proposal эсвэл result төлөвийг шалган, дэмжвэл review response бүртгэнэ. Review нь Memory-г хэзээ ч Apply хийхгүй.",
        "Хадгалсан analysis, proposal эсвэл result төлөвийг дахин үзэх үед.",
    ),
    "search": _copy(
        "Сонгосон Context-үүдэд байгалийн хэлний хүсэлттэй холбоотой Memory-г утгаар эрэмбэлнэ.",
        "Утга болон Context-оор холбоотой Memory, тэр дундаа илэрхий түлхүүр үг давхцаагүй агуулгыг олох үед.",
    ),
    "sever": _copy(
        "Criteria Context-н дагуу Source Memory-г сонгох, хувиргах эсвэл хасах замаар Result үүсгэнэ.",
        "Тодорхой шалгуурын дагуу Source агуулгыг сонгох эсвэл хувиргах үед.",
    ),
    "share": _copy(
        "Grant-д суурилсан receiver endpoint-ээр нэг ердийн Context илгээнэ.",
        "Өөрийн Context-г зөвшөөрөгдсөн хүлээн авагчид хүргэх үед.",
    ),
    "shell-init": _copy(
        "Интерактив command prefill-д зориулсан сонголттой shell integration-г хэвлэнэ.",
        "Shell-д зориулсан нэмэлт хялбарчлалыг идэвхжүүлэх үед.",
    ),
    "show": _copy(
        "Memory, reference, embedded Context эсвэл одоогийн/заасан Context-н шууд агуулгыг харуулна.",
        "Мэдэгдэж буй зүйл эсвэл Context-н бүрэн агуулгыг унших үед.",
    ),
    "status": _copy(
        "Одоогийн Context-н inventory, эхний таван шууд Memory, холбоо болон сүүлийн checkpoint-уудыг харуулна.",
        "Одоогийн Context юу агуулдаг, хэрхэн холбогдсон, сүүлд ямар operation хэрэглэснийг ойлгох үед.",
    ),
    "summarize": _copy(
        "Унших боломжтой Context хүрээн дэх ердийн Memory-н LLM-ээр гаргасан тоймыг харуулна.",
        "Context эсвэл дэд модны товч тойм авах үед.",
    ),
    "switch": _copy(
        "Интерактив Context picker руу орох эсвэл заасан Context руу шилжинэ.",
        "Ажлын байрлалыг өөр одоо байгаа Context руу шилжүүлэх үед.",
    ),
    "trace": _copy(
        "Хадгалсан нэг Memory-г бүртгэгдсэн lineage дагуу мөрдөнө.",
        "Memory хаанаас ирж, хэрхэн өөрчлөгдсөнийг тогтоох үед.",
    ),
    "translate": _copy(
        "Эх агуулгыг хадгалан нэг Context эсвэл Memory-н дахин ашиглах боломжтой орчуулсан view-г үүсгэж хадгална.",
        "Эхийг солихгүйгээр Memory агуулгыг өөр хэлээр унших эсвэл дахин ашиглах үед.",
    ),
    "undo": _copy(
        "Хамгийн сүүлийн бүртгэгдсэн command-г нэг нэгж болгон буцаана.",
        "Хамгийн сүүлийн бүртгэгдсэн өөрчлөлтийг нэг operation болгон буцаах үед.",
    ),
    "unlock": _copy(
        "Одоогийн Context, рекурсив багц, Memory эсвэл Profile-н түгжээг тайлна.",
        "Хамгаалсан материалыг зориудаар засахаар дахин нээх үед.",
    ),
    "update": _copy(
        "Source Context-н Memory ашиглан Target Context-н Memory-г шинэчилж, шаардлагатай үед хэрэглэгчээс хяналт ба сонголт хүснэ.",
        "Шинээр баталгаажсан Memory ашиглан одоо байгаа Context-г шинэчлэх үед.",
    ),
}

OPERATION_TRANSLATIONS: dict[HelpLanguage, dict[str, LocalizedOperationCopy]] = {
    "EN": {},
    "FR": _FR,
    "ZH": _ZH,
    "KO": _KO,
    "MN": _MN,
}

# Duplicate identity and semantic redundancy are different contracts. Keep the
# former semantic Dedup copy under the coined Dedun operation, and give exact
# Dedup its own provider-free description in every supported Help language.
_EXACT_DEDUP_TRANSLATIONS = {
    "FR": _copy(
        "Supprimer immédiatement les Memories directes dont le contenu est identique octet pour octet, en conservant le premier UID existant de chaque groupe.",
        "Éliminer des copies de contenu strictement identiques sans inférence sémantique.",
    ),
    "ZH": _copy(
        "立即删除内容逐字节相同的直接 Memories，并为每组保留最先存在的 UID。",
        "无需语义推理即可清除完全相同的内容副本。",
    ),
    "KO": _copy(
        "현재 또는 지정된 Context에서 바이트 단위로 내용이 같은 직접 Memory를 즉시 제거하고 각 그룹의 첫 기존 UID를 유지합니다.",
        "의미 추론 없이 내용이 정확히 같은 저장 복사본을 정리할 때.",
    ),
    "MN": _copy(
        "Байт бүрээрээ ижил direct Memory-нуудыг шууд устгаж, бүлэг бүрийн эхний одоо байгаа UID-г хадгална.",
        "Semantic inference ашиглахгүйгээр яг ижил агуулгын хуулбарыг цэвэрлэх үед.",
    ),
}
for _language in ("FR", "ZH", "KO", "MN"):
    _translations = OPERATION_TRANSLATIONS[_language]
    _translations["dedun"] = _translations["dedup"]
    _translations["dedup"] = _EXACT_DEDUP_TRANSLATIONS[_language]
    _translations.pop("find-duplicates")


_CATEGORY_DESCRIPTIONS = {
    "FR": {
        "BROWSE & NAVIGATE": "Inspecter l’emplacement courant et les Contexts disponibles, puis parcourir l’espace de noms des Contexts.",
        "CREATE, COPY & CONNECT": "Créer des Contexts ou des Memories, copier ou importer des ressources, ou relier du contenu existant.",
        "SEARCH & EXPLAIN": "Trouver directement un texte exact, ou utiliser la recherche, les réponses et la synthèse sémantiques basées sur un LLM dans la portée autorisée sélectionnée.",
        "DETERMINISTIC CONTENT CHANGES": "Appliquer des entrées explicites et des choix révisés avec une logique de programme déterministe pour modifier le contenu.",
        "SEMANTIC TRANSFORMATIONS": "Utiliser l’analyse sémantique d’un LLM pour restructurer, dériver, traduire, sélectionner ou réconcilier du contenu.",
        "CHECK, COMPARE & REVIEW": "Vérifier compatibilité, différences, qualité ou impact attendu. Examiner l’analyse enregistrée et décider de la suite.",
        "GROUND WORKBENCH": "Transformer des idées abstraites en terrain commun révisable en développant ensemble un Goal, des Rules et des Memories d’exemple.",
        "HISTORY & RECOVERY": "Examiner la provenance et les changements enregistrés. Restaurer un état antérieur au moyen d’opérations d’historique explicites.",
        "PROFILES": "Sélectionner et administrer des stores Profile locaux complets et leurs noms gérés.",
        "SHARING & PROTECTION": "Transmettre des Contexts possédés et protéger les écritures de Memory, Context ou Profile.",
        "SYSTEM & STUDY TOOLS": "Configurer MemCommit et préparer ou exécuter des utilitaires d’étude et d’évaluation.",
    },
    "ZH": {
        "BROWSE & NAVIGATE": "检查当前位置和可用 Context，然后在 Context 命名空间中移动。",
        "CREATE, COPY & CONNECT": "创建 Context 或 Memory，复制或导入资源，或连接现有材料。",
        "SEARCH & EXPLAIN": "直接查找精确文本，或在选定的授权范围内使用基于 LLM 的语义检索、问答和摘要。",
        "DETERMINISTIC CONTENT CHANGES": "通过确定性的程序逻辑应用明确输入和已审查选择，以修改内容。",
        "SEMANTIC TRANSFORMATIONS": "使用 LLM 语义分析来重组、推导、翻译、筛选或协调内容。",
        "CHECK, COMPARE & REVIEW": "检查兼容性、差异、质量或预期影响；审查已保存分析并决定下一步。",
        "GROUND WORKBENCH": "共同发展 Goal、Rule 和示例 Memory，将抽象想法变为可审查的共同基础。",
        "HISTORY & RECOVERY": "检查来源和已记录变化，并通过明确的历史 operation 恢复较早状态。",
        "PROFILES": "选择和管理完整的本地 Profile store 及其受管名称。",
        "SHARING & PROTECTION": "交付自己拥有的 Context，并保护 Memory、Context 或 Profile 写入。",
        "SYSTEM & STUDY TOOLS": "配置 MemCommit，并准备或运行研究与评估工具。",
    },
    "KO": {
        "BROWSE & NAVIGATE": "현재 위치와 사용할 수 있는 Context를 확인하고 Context namespace를 이동합니다.",
        "CREATE, COPY & CONNECT": "Context나 Memory를 만들고, resource를 복사·가져오거나 기존 자료를 연결합니다.",
        "SEARCH & EXPLAIN": "정확한 텍스트를 직접 찾거나 선택한 허가 범위에서 LLM 기반 semantic retrieval·answering·summarization을 사용합니다.",
        "DETERMINISTIC CONTENT CHANGES": "명시적 입력과 검토된 선택을 결정론적 프로그램 로직으로 적용하여 내용을 변경합니다.",
        "SEMANTIC TRANSFORMATIONS": "LLM semantic analysis를 사용해 내용을 재구성·도출·번역·선별·조정합니다.",
        "CHECK, COMPARE & REVIEW": "양립 가능성, 차이, 품질 또는 예상 영향을 확인하고 저장된 분석을 검토하여 다음 행동을 결정합니다.",
        "GROUND WORKBENCH": "Goal, Rule, 예시 Memory를 함께 발전시켜 추상적 아이디어를 검토 가능한 공통 기반으로 만듭니다.",
        "HISTORY & RECOVERY": "provenance와 기록된 변경을 확인하고 명시적인 history operation으로 이전 상태를 복원합니다.",
        "PROFILES": "완전한 로컬 Profile store와 관리되는 이름을 선택하고 관리합니다.",
        "SHARING & PROTECTION": "소유한 Context를 전달하고 Memory, Context 또는 Profile 쓰기를 보호합니다.",
        "SYSTEM & STUDY TOOLS": "MemCommit을 설정하고 연구 및 evaluation 도구를 준비하거나 실행합니다.",
    },
    "MN": {
        "BROWSE & NAVIGATE": "Одоогийн байрлал болон боломжтой Context-уудыг шалгаад Context namespace дотор шилжинэ.",
        "CREATE, COPY & CONNECT": "Context эсвэл Memory үүсгэж, resource хуулж эсвэл импортолж, одоо байгаа материалыг холбоно.",
        "SEARCH & EXPLAIN": "Яг текстийг шууд олох эсвэл сонгосон зөвшөөрөгдсөн хүрээнд LLM-д суурилсан утгын хайлт, хариулт, хураангуйлал ашиглана.",
        "DETERMINISTIC CONTENT CHANGES": "Тодорхой оролт болон хянасан сонголтыг детерминист програмын логикоор хэрэглэн агуулгыг өөрчилнө.",
        "SEMANTIC TRANSFORMATIONS": "LLM semantic analysis ашиглан агуулгыг дахин бүтэцлэх, гаргах, орчуулах, сонгох эсвэл нийцүүлнэ.",
        "CHECK, COMPARE & REVIEW": "Нийцэл, ялгаа, чанар эсвэл хүлээгдэж буй нөлөөг шалгаж, хадгалсан шинжилгээг хянаад дараагийн алхмыг шийднэ.",
        "GROUND WORKBENCH": "Goal, Rule болон жишээ Memory-г хамт хөгжүүлж, хийсвэр санааг хянах боломжтой нийтлэг суурь болгоно.",
        "HISTORY & RECOVERY": "Provenance болон бүртгэгдсэн өөрчлөлтийг шалгаж, тодорхой history operation-оор өмнөх төлөвийг сэргээнэ.",
        "PROFILES": "Бүрэн локал Profile store болон удирдлагатай нэрсийг сонгож, захирна.",
        "SHARING & PROTECTION": "Өөрийн Context-г хүргэж, Memory, Context эсвэл Profile бичилтийг хамгаална.",
        "SYSTEM & STUDY TOOLS": "MemCommit-г тохируулж, судалгаа болон evaluation хэрэгслийг бэлтгэх эсвэл ажиллуулна.",
    },
}

_CORE_CONCEPT_DESCRIPTIONS = {
    "FR": {
        "MEMORY": "L’unité d’enregistrement de base stockée dans un Context et sélectionnée, révisée ou modifiée indépendamment par les operations au niveau Memory.",
        "CONTEXT": "Un espace de travail nommé et hiérarchique qui contient des Memories et organise des Contexts enfants. Le séparateur / exprime la hiérarchie dans des noms comme task-1/participant ; les operations avec une portée descendante peuvent traiter un Context et ses Contexts descendants comme un seul sous-arbre. Sans Context indiqué, les commands utilisent le Context courant.",
        "PROFILE": "Une frontière isolée de propriété et de stockage contenant des Contexts ; plusieurs Profiles peuvent contenir le même nom de Context.",
        "OPERATION": "Une action réutilisable qui lit, analyse ou modifie des Memories ou Contexts sélectionnés selon des entrées et un comportement définis.",
        "GRANT": "Une relation d’autorisation reçue ou accordée qui permet sélectivement de lire ou interroger un Context et ses Memories, ou d’y exécuter des opérations permises, tant que le Grant reste valide.",
        "SESSION": "Enregistre un workflow d’analyse ou de révision afin de pouvoir le rouvrir et le poursuivre. Les résultats d’Apply et l’historique des checkpoints indiquent séparément si des changements de Context ont été effectués.",
        "CHECKPOINT": "Une frontière d’historique récupérable créée pour chaque opération appliquée et enregistrée par Context affecté.",
    },
    "ZH": {
        "MEMORY": "存储在 Context 中，并由 Memory 级 operation 独立选择、审查或修改的基本记录单元。",
        "CONTEXT": "包含 Memory 并组织子 Context 的命名层级工作区。分隔符 / 在 task-1/participant 这样的名称中表示层级；支持 descendant 范围的 operation 可将一个 Context 及其下级 Context 作为一个 subtree 一并处理。未指定 Context 时，command 使用当前 Context。",
        "PROFILE": "包含 Context 的独立所有权与存储边界；不同 Profile 可以包含相同的 Context name。",
        "OPERATION": "一种可复用的操作，按照已定义的输入与行为读取、分析或修改选定的 Memory 或 Context。",
        "GRANT": "一种可授予或接收的权限关系；在 Grant 有效期间，它可选择性允许非直接所有者读取或查询 Context 及其 Memory，或运行获准 operation。",
        "SESSION": "保存分析或审查 workflow，以便重新打开并继续。Apply 结果和 checkpoint history 会另行显示是否发生了 Context 修改。",
        "CHECKPOINT": "每个已应用 operation 创建并按受影响 Context 记录的可恢复历史边界。",
    },
    "KO": {
        "MEMORY": "Context 안에 저장되며, Memory를 다루는 operation에서 독립적으로 선택·검토·변경하는 기본 기록 단위입니다.",
        "CONTEXT": "Memory를 담고 하위 Context를 계층적으로 정리하는 이름 있는 작업 공간입니다. task-1/participant처럼 이름의 /로 계층을 나타내며, descendant 범위를 지원하는 operation에서는 한 Context와 그 하위 Context들을 하나의 subtree로 함께 다룰 수 있습니다. Context를 명시하지 않은 command는 current Context를 사용합니다.",
        "PROFILE": "Context들을 담는 격리된 소유권 및 저장 경계이며, 서로 다른 Profile에 같은 Context name이 존재할 수 있습니다.",
        "OPERATION": "정해진 입력과 동작에 따라 선택한 Memory 또는 Context를 읽고 분석하거나 변경하는 재사용 가능한 작업입니다.",
        "GRANT": "주고받을 수 있는 권한 관계로, Grant가 유효한 동안 직접 소유하지 않은 사람이 Context와 Memory를 읽거나 query하고 허가된 operation을 실행할 수 있게 합니다.",
        "SESSION": "분석 또는 검토 workflow를 다시 열고 이어가기 위한 저장 기록입니다. Context 변경 여부는 별도의 Apply 결과와 checkpoint history에서 확인합니다.",
        "CHECKPOINT": "적용된 operation마다 생성되어 영향을 받은 Context별로 기록되는 복구 가능한 history 경계입니다.",
    },
    "MN": {
        "MEMORY": "Context дотор хадгалагдаж, Memory түвшний operation-оор бие даан сонгож, хянаж эсвэл өөрчилдөг үндсэн бүртгэлийн нэгж.",
        "CONTEXT": "Memory-г агуулж, дэд Context-уудыг шатлан зохион байгуулдаг нэртэй ажлын орчин. task-1/participant зэрэг нэрийн / тусгаарлагч нь шатлалыг илэрхийлнэ; descendant scope-г дэмждэг operation нь тухайн Context болон түүний дэд Context-уудыг нэг subtree болгон хамтад нь авч үзэж болно. Context заагаагүй command нь одоогийн Context-г ашиглана.",
        "PROFILE": "Context-уудыг агуулдаг тусгаарлагдсан эзэмшил ба хадгалалтын хил; өөр Profile-ууд ижил Context name-тай байж болно.",
        "OPERATION": "Тодорхойлсон оролт ба зан төлөвийн дагуу сонгосон Memory эсвэл Context-г унших, шинжлэх, өөрчлөх дахин ашиглах боломжтой үйлдэл.",
        "GRANT": "Grant хүчинтэй байх хугацаанд шууд эзэмшдэггүй хүнд Context болон Memory-г унших, query хийх эсвэл зөвшөөрөгдсөн operation ажиллуулахыг сонголтоор зөвшөөрдөг эрхийн харилцаа.",
        "SESSION": "Analysis эсвэл review workflow-г дахин нээж үргэлжлүүлэхийн тулд хадгална. Context өөрчлөгдсөн эсэхийг Apply result болон checkpoint history тусдаа харуулна.",
        "CHECKPOINT": "Хэрэглэсэн operation бүрд үүсэж, нөлөөлсөн Context тус бүрээр бүртгэгддэг сэргээх боломжтой history хил.",
    },
}

_COMMON_KEY_DESCRIPTIONS = {
    "FR": {
        "↑/↓": "Déplacer ou faire défiler dans la surface active.",
        "←/→": "Modifier un choix horizontal, développer ou revenir selon le focus.",
        "Tab / Shift-Tab": "Déplacer le focus entre les surfaces visibles.",
        "Enter": "Ouvrir, sélectionner ou soumettre l’action active.",
        "H": "Ouvrir ou masquer Help depuis la navigation en lecture seule d’une session.",
        "Esc / Backspace": "Revenir d’un niveau ; Backspace modifie le texte dans les champs éditables.",
    },
    "ZH": {
        "↑/↓": "在当前聚焦区域中移动或滚动。",
        "←/→": "根据焦点更改横向选择、展开或返回。",
        "Tab / Shift-Tab": "在可见区域之间移动焦点。",
        "Enter": "打开、选择或提交当前操作。",
        "H": "从 session 的只读导航区域打开或隐藏 Help。",
        "Esc / Backspace": "返回一层；在可写字段中 Backspace 用于删除文本。",
    },
    "KO": {
        "↑/↓": "포커스된 영역 안에서 이동하거나 스크롤합니다.",
        "←/→": "포커스에 따라 가로 선택을 바꾸거나 펼치거나 뒤로 갑니다.",
        "Tab / Shift-Tab": "보이는 영역 사이에서 포커스를 이동합니다.",
        "Enter": "포커스된 동작을 열고 선택하거나 제출합니다.",
        "H": "session의 read-only 탐색 영역에서 Help를 열거나 숨깁니다.",
        "Esc / Backspace": "한 단계 뒤로 갑니다. 쓰기 가능한 필드에서는 Backspace가 텍스트를 지웁니다.",
    },
    "MN": {
        "↑/↓": "Фокустай хэсэг дотор шилжих эсвэл гүйлгэнэ.",
        "←/→": "Фокусаас хамаарч хэвтээ сонголт солих, дэлгэх эсвэл буцна.",
        "Tab / Shift-Tab": "Харагдах хэсгүүдийн хооронд фокус шилжүүлнэ.",
        "Enter": "Фокустай үйлдлийг нээх, сонгох эсвэл илгээнэ.",
        "H": "Session-н read-only navigation хэсгээс Help-г нээх эсвэл нууна.",
        "Esc / Backspace": "Нэг түвшин буцна; бичих талбарт Backspace текст устгана.",
    },
}


def operation_copy(
    language: HelpLanguage,
    operation_name: str,
    *,
    english_description: str,
    english_use_when: str,
) -> LocalizedOperationCopy:
    """Return complete process-local learning copy for one operation."""

    if language == "EN":
        return LocalizedOperationCopy(english_description, english_use_when)
    return OPERATION_TRANSLATIONS[language].get(
        operation_name,
        LocalizedOperationCopy(english_description, english_use_when),
    )


def category_description(
    language: HelpLanguage,
    category: str,
    english: str,
) -> str:
    """Translate one stable category description without renaming its key."""

    if language == "EN":
        return english
    return _CATEGORY_DESCRIPTIONS[language][category]


def core_concept_description(
    language: HelpLanguage,
    concept: str,
    english: str,
) -> str:
    """Translate prose while retaining the canonical concept label."""

    if language == "EN":
        return english
    return _CORE_CONCEPT_DESCRIPTIONS[language][concept]


def common_key_description(
    language: HelpLanguage,
    key: str,
    english: str,
) -> str:
    """Translate key guidance while retaining the exact key spelling."""

    if language == "EN":
        return english
    return _COMMON_KEY_DESCRIPTIONS[language][key]


def validate_translation_coverage(operation_names: set[str]) -> None:
    """Fail closed when any non-English inventory drifts from the catalog."""

    category_names = set(_CATEGORY_DESCRIPTIONS["FR"])
    concept_names = set(_CORE_CONCEPT_DESCRIPTIONS["FR"])
    key_names = set(_COMMON_KEY_DESCRIPTIONS["FR"])
    for language in HELP_LANGUAGES:
        if language == "EN":
            continue
        translated = set(OPERATION_TRANSLATIONS[language])
        if translated != operation_names:
            missing = sorted(operation_names - translated)
            stale = sorted(translated - operation_names)
            raise ValueError(
                f"Help {language} translation coverage mismatch: "
                f"missing={missing}; stale={stale}"
            )
        if any(
            not copy.description.strip() or not copy.use_when.strip()
            for copy in OPERATION_TRANSLATIONS[language].values()
        ):
            raise ValueError(f"Help {language} operation translation is blank.")
        if set(_CATEGORY_DESCRIPTIONS[language]) != category_names:
            raise ValueError(f"Help {language} category translation coverage mismatch.")
        if set(_CORE_CONCEPT_DESCRIPTIONS[language]) != concept_names:
            raise ValueError(f"Help {language} concept translation coverage mismatch.")
        if set(_COMMON_KEY_DESCRIPTIONS[language]) != key_names:
            raise ValueError(f"Help {language} key translation coverage mismatch.")


__all__ = [
    "HELP_LANGUAGES",
    "HelpLanguage",
    "LocalizedOperationCopy",
    "category_description",
    "common_key_description",
    "core_concept_description",
    "operation_copy",
    "validate_translation_coverage",
]

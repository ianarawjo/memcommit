"""Localized copy owned by the terminal Help presentation."""

from __future__ import annotations

from memcommit.application.operations.operation_catalog.localization import (
    OPERATION_CATALOG_LANGUAGES,
    OperationCatalogLanguage,
    validate_operation_translation_coverage,
)


HelpLanguage = OperationCatalogLanguage
HELP_LANGUAGES: tuple[HelpLanguage, ...] = OPERATION_CATALOG_LANGUAGES


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

_COMMON_LOCATOR_DESCRIPTIONS = {
    "FR": {
        "NAME": "Un nom nu de Context existant est canonique et global, jamais relatif.",
        ".": "Le Context courant capturé une seule fois au démarrage de la command.",
        "..": "Le parent de ce Context courant capturé.",
        "./CHILD": "Un chemin enfant relatif à ce Context courant capturé.",
        "../PATH": "Un chemin relatif au parent de ce Context courant capturé.",
        "UID": "Un UID complet ou un préfixe accepté. Dans les operations direct-Memory compatibles, recherche les propriétaires directs dans les Contexts locaux ordinaires ; il faut exactement une correspondance, sinon l’ambiguïté arrête l’action et affiche les candidats qualifiés.",
        "CONTEXT:UID": "Dans les operations direct-Memory compatibles, : sépare le Context propriétaire direct de l’UID ou du préfixe de sa Memory ; le Context peut être relatif, comme dans ../3:ca562047.",
    },
    "ZH": {
        "NAME": "现有 Context 的裸名称是规范的全局名称，绝不是相对名称。",
        ".": "command 启动时只捕获一次的当前 Context。",
        "..": "该已捕获当前 Context 的父级。",
        "./CHILD": "相对于该已捕获当前 Context 的子路径。",
        "../PATH": "相对于该已捕获当前 Context 父级的路径。",
        "UID": "完整 UID 或可接受的前缀。在支持 direct-Memory 的 operation 中扫描普通本地 Context 的直接所有者；必须恰好匹配一个，否则因歧义而停止并列出限定候选项。",
        "CONTEXT:UID": "在支持 direct-Memory 的 operation 中，: 分隔直接所有者 Context 与其 Memory UID 或前缀；Context 可以是相对路径，例如 ../3:ca562047。",
    },
    "KO": {
        "NAME": "기존 Context의 bare name은 canonical global name이며 상대 이름이 아닙니다.",
        ".": "command 시작 시 한 번 캡처한 current Context입니다.",
        "..": "캡처한 current Context의 상위 Context입니다.",
        "./CHILD": "캡처한 current Context를 기준으로 한 하위 경로입니다.",
        "../PATH": "캡처한 current Context의 상위를 기준으로 한 상대 경로입니다.",
        "UID": "전체 UID 또는 허용되는 prefix입니다. direct-Memory locator를 지원하는 operation에서 일반 local Context의 직접 소유자를 스캔합니다. 정확히 하나만 일치해야 하며, 중복이면 중단하고 qualified 후보를 나열합니다.",
        "CONTEXT:UID": "direct-Memory locator를 지원하는 operation에서 :는 직접 소유 Context와 Memory UID 또는 prefix를 구분합니다. ../3:ca562047처럼 Context 부분에 상대 경로를 쓸 수 있습니다.",
    },
    "MN": {
        "NAME": "Одоо байгаа Context-н дан нэр нь canonical global name бөгөөд хэзээ ч relative биш.",
        ".": "Command эхлэхэд нэг удаа авсан current Context.",
        "..": "Тэр авсан current Context-н эцэг Context.",
        "./CHILD": "Тэр авсан current Context-д харьцуулсан хүүхэд зам.",
        "../PATH": "Тэр авсан current Context-н эцэгт харьцуулсан зам.",
        "UID": "Бүтэн UID эсвэл зөвшөөрөгдсөн prefix. Direct-Memory locator дэмждэг operation-д энгийн local Context-уудын шууд эзэмшигчийг хайна; яг нэг тохирол шаардана, ambiguity гарвал зогсоож qualified candidate-уудыг жагсаана.",
        "CONTEXT:UID": "Direct-Memory locator дэмждэг operation-д : нь шууд эзэмшигч Context болон түүний Memory UID эсвэл prefix-г тусгаарлана; Context нь ../3:ca562047 шиг relative байж болно.",
    },
}

_COMMON_KEY_DESCRIPTIONS = {
    "FR": {
        "↑/↓": "Se déplacer par ligne ou Form ; maintenir la touche pour accélérer dans les longues listes.",
        "←/→": "Changer Language ou View, ou développer et réduire les Forms de command.",
        "PgUp / PgDn": "Sauter de 10 lignes en arrière ou en avant dans la liste Help défilante.",
        "Home / End": "Atteindre la première ligne Help ou la dernière command.",
        "Tab / Shift-Tab": "Déplacer le focus entre Language, View et les groupes d’operations visibles.",
        "Enter": "Ouvrir les Forms de command, puis sélectionner ou inspecter la Form active.",
        "H": "Ouvrir l’aide complète de la command, ou masquer Help lors de l’exploration depuis une session en attente.",
        "Esc / Q / Ctrl-C": "Fermer Help, annuler la sélection ou revenir à la session en attente.",
    },
    "ZH": {
        "↑/↓": "按行或 Form 移动；在长列表中按住可加速。",
        "←/→": "更改 Language 或 View，或展开和折叠 command Forms。",
        "PgUp / PgDn": "在滚动的 Help 列表中向前或向后跳转 10 行。",
        "Home / End": "移动到第一条 Help 行或最后一个 command。",
        "Tab / Shift-Tab": "在 Language、View 和可见 operation 分组之间移动焦点。",
        "Enter": "打开 command Forms，然后选择或查看当前 Form。",
        "H": "打开完整 command help；从等待中的 session 探索时则隐藏 Help。",
        "Esc / Q / Ctrl-C": "关闭 Help、取消选择或返回等待中的 session。",
    },
    "KO": {
        "↑/↓": "행 또는 Form 단위로 이동하며, 긴 목록에서는 길게 눌러 가속합니다.",
        "←/→": "Language나 View를 바꾸거나 command Forms를 펼치고 접습니다.",
        "PgUp / PgDn": "스크롤되는 Help 목록에서 앞이나 뒤로 10행 이동합니다.",
        "Home / End": "첫 Help 행이나 마지막 command로 이동합니다.",
        "Tab / Shift-Tab": "Language, View, 보이는 operation 그룹 사이에서 포커스를 이동합니다.",
        "Enter": "command Forms를 연 뒤 포커스된 Form을 선택하거나 살펴봅니다.",
        "H": "전체 command help를 열거나 대기 중인 session에서 탐색할 때 Help를 숨깁니다.",
        "Esc / Q / Ctrl-C": "Help를 닫고 선택을 취소하거나 대기 중인 session으로 돌아갑니다.",
    },
    "MN": {
        "↑/↓": "Мөр эсвэл Form-оор шилжинэ; урт жагсаалтад удаан дарж хурдасгана.",
        "←/→": "Language эсвэл View-г солино, эсвэл command Forms-г дэлгэж хураана.",
        "PgUp / PgDn": "Гүйлгэх Help жагсаалтад 10 мөрөөр урагш эсвэл хойш үсэрнэ.",
        "Home / End": "Help-н эхний мөр эсвэл сүүлийн command руу шилжинэ.",
        "Tab / Shift-Tab": "Language, View болон харагдах operation бүлгүүдийн хооронд фокус шилжүүлнэ.",
        "Enter": "Command Forms-г нээгээд фокустай Form-г сонгох эсвэл шалгана.",
        "H": "Command-н бүтэн help-г нээх, эсвэл хүлээж буй session-с судлах үед Help-г нууна.",
        "Esc / Q / Ctrl-C": "Help-г хаах, сонголтыг цуцлах эсвэл хүлээж буй session рүү буцна.",
    },
}


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


def common_locator_description(
    language: HelpLanguage,
    locator: str,
    english: str,
) -> str:
    """Translate locator guidance while retaining the exact locator spelling."""

    if language == "EN":
        return english
    return _COMMON_LOCATOR_DESCRIPTIONS[language][locator]


def validate_help_translation_coverage(operation_names: set[str]) -> None:
    """Validate both catalog translations and Help-only interface copy."""

    validate_operation_translation_coverage(operation_names)
    category_names = set(_CATEGORY_DESCRIPTIONS["FR"])
    concept_names = set(_CORE_CONCEPT_DESCRIPTIONS["FR"])
    key_names = set(_COMMON_KEY_DESCRIPTIONS["FR"])
    locator_names = set(_COMMON_LOCATOR_DESCRIPTIONS["FR"])
    for language in HELP_LANGUAGES:
        if language == "EN":
            continue
        if set(_CATEGORY_DESCRIPTIONS[language]) != category_names:
            raise ValueError(f"Help {language} category translation coverage mismatch.")
        if set(_CORE_CONCEPT_DESCRIPTIONS[language]) != concept_names:
            raise ValueError(f"Help {language} concept translation coverage mismatch.")
        if set(_COMMON_KEY_DESCRIPTIONS[language]) != key_names:
            raise ValueError(f"Help {language} key translation coverage mismatch.")
        if set(_COMMON_LOCATOR_DESCRIPTIONS[language]) != locator_names:
            raise ValueError(f"Help {language} locator translation coverage mismatch.")


__all__ = [
    "HELP_LANGUAGES",
    "HelpLanguage",
    "category_description",
    "common_key_description",
    "common_locator_description",
    "core_concept_description",
    "validate_help_translation_coverage",
]

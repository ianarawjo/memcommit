"""Reviewed localized copy for public operation families."""

from __future__ import annotations

from memcommit.operation_catalog.families import OPERATION_FAMILY_BY_TITLE
from memcommit.operation_catalog.localization import (
    OPERATION_CATALOG_LANGUAGES,
    OperationCatalogLanguage,
)


FAMILY_DESCRIPTION_TRANSLATIONS = {
    "FR": {
        "BROWSE & NAVIGATE": "Inspecter l’emplacement courant et les Contexts disponibles, puis parcourir l’espace de noms des Contexts.",
        "CREATE, COPY & CONNECT": "Créer des Contexts ou des Memories, copier ou importer des ressources, ou relier du contenu existant.",
        "SEARCH & EXPLAIN": "Trouver directement un texte exact, ou utiliser la recherche, les réponses, la synthèse et la comparaison sémantiques basées sur un LLM dans la portée autorisée sélectionnée.",
        "DIRECT CHANGES": "Appliquer des entrées explicites et des choix révisés avec une logique de programme déterministe pour modifier le contenu.",
        "SEMANTIC UPDATES": "Utiliser des décisions sémantiques pour mettre à jour, dériver, sélectionner ou intégrer du contenu dans les limites de révision et d’application propres à chaque opération.",
        "TRANSLATION": "Créer des vues ou des matérialisations linguistiques réutilisables tout en préservant le contenu Source sélectionné.",
        "QUALITY & RESOLUTION": "Diagnostiquer les problèmes de qualité, réparer les problèmes exacts ou sémantiques et valider la compatibilité ou la conformité aux Rules.",
        "OPERATION LIFECYCLE": "Examiner les effets attendus avant Apply ou revisiter ensuite les preuves d’exécution et de rapport enregistrées.",
        "GROUND WORKBENCH": "Transformer des idées abstraites en terrain commun révisable en développant ensemble un Goal, des Rules et des Memories d’exemple.",
        "HISTORY & RECOVERY": "Examiner la provenance et les changements enregistrés. Restaurer un état antérieur au moyen d’opérations d’historique explicites.",
        "PROFILES": "Sélectionner et administrer des stores Profile locaux complets et leurs noms gérés.",
        "SHARING & PROTECTION": "Transmettre des Contexts possédés et protéger les écritures de Memory, Context ou Profile.",
        "SYSTEM & STUDY TOOLS": "Configurer MemCommit et préparer ou exécuter des utilitaires d’étude et d’évaluation.",
    },
    "ZH": {
        "BROWSE & NAVIGATE": "检查当前位置和可用 Context，然后在 Context 命名空间中移动。",
        "CREATE, COPY & CONNECT": "创建 Context 或 Memory，复制或导入资源，或连接现有材料。",
        "SEARCH & EXPLAIN": "直接查找精确文本，或在选定的授权范围内使用基于 LLM 的语义检索、问答、摘要和比较。",
        "DIRECT CHANGES": "通过确定性的程序逻辑应用明确输入和已审查选择，以修改内容。",
        "SEMANTIC UPDATES": "在各 operation 自有的 review 与 Apply 边界内，使用语义决策更新、推导、筛选或整合内容。",
        "TRANSLATION": "在保留所选 Source 内容的同时，创建可复用的语言视图或实体化结果。",
        "QUALITY & RESOLUTION": "诊断质量问题、修复精确或语义问题，并验证兼容性或 Rule 一致性。",
        "OPERATION LIFECYCLE": "在 Apply 前检查预期效果，或在之后重新查看已保存的执行与报告证据。",
        "GROUND WORKBENCH": "共同发展 Goal、Rule 和示例 Memory，将抽象想法变为可审查的共同基础。",
        "HISTORY & RECOVERY": "检查来源和已记录变化，并通过明确的历史 operation 恢复较早状态。",
        "PROFILES": "选择和管理完整的本地 Profile store 及其受管名称。",
        "SHARING & PROTECTION": "交付自己拥有的 Context，并保护 Memory、Context 或 Profile 写入。",
        "SYSTEM & STUDY TOOLS": "配置 MemCommit，并准备或运行研究与评估工具。",
    },
    "KO": {
        "BROWSE & NAVIGATE": "현재 위치와 사용할 수 있는 Context를 확인하고 Context namespace를 이동합니다.",
        "CREATE, COPY & CONNECT": "Context나 Memory를 만들고, resource를 복사·가져오거나 기존 자료를 연결합니다.",
        "SEARCH & EXPLAIN": "정확한 텍스트를 직접 찾거나 선택한 허가 범위에서 LLM 기반 semantic retrieval·answering·summarization·comparison을 사용합니다.",
        "DIRECT CHANGES": "명시적 입력과 검토된 선택을 결정론적 프로그램 로직으로 적용하여 내용을 변경합니다.",
        "SEMANTIC UPDATES": "operation이 소유한 review와 Apply 경계 안에서 semantic decision으로 내용을 update·derive·curate·integrate합니다.",
        "TRANSLATION": "선택한 Source 내용을 보존하면서 재사용 가능한 언어 view 또는 materialization을 만듭니다.",
        "QUALITY & RESOLUTION": "품질 문제를 진단하고 exact 또는 semantic 문제를 수리하며 양립 가능성이나 Rule conformance를 검증합니다.",
        "OPERATION LIFECYCLE": "Apply 전에 예상 효과를 확인하거나 이후 저장된 execution 및 report evidence를 다시 살펴봅니다.",
        "GROUND WORKBENCH": "Goal, Rule, 예시 Memory를 함께 발전시켜 추상적 아이디어를 검토 가능한 공통 기반으로 만듭니다.",
        "HISTORY & RECOVERY": "provenance와 기록된 변경을 확인하고 명시적인 history operation으로 이전 상태를 복원합니다.",
        "PROFILES": "완전한 로컬 Profile store와 관리되는 이름을 선택하고 관리합니다.",
        "SHARING & PROTECTION": "소유한 Context를 전달하고 Memory, Context 또는 Profile 쓰기를 보호합니다.",
        "SYSTEM & STUDY TOOLS": "MemCommit을 설정하고 연구 및 evaluation 도구를 준비하거나 실행합니다.",
    },
    "MN": {
        "BROWSE & NAVIGATE": "Одоогийн байрлал болон боломжтой Context-уудыг шалгаад Context namespace дотор шилжинэ.",
        "CREATE, COPY & CONNECT": "Context эсвэл Memory үүсгэж, resource хуулж эсвэл импортолж, одоо байгаа материалыг холбоно.",
        "SEARCH & EXPLAIN": "Яг текстийг шууд олох эсвэл сонгосон зөвшөөрөгдсөн хүрээнд LLM-д суурилсан утгын хайлт, хариулт, хураангуйлал, харьцуулалт ашиглана.",
        "DIRECT CHANGES": "Тодорхой оролт болон хянасан сонголтыг детерминист програмын логикоор хэрэглэн агуулгыг өөрчилнө.",
        "SEMANTIC UPDATES": "Operation тус бүрийн review болон Apply хязгаарт semantic шийдвэрээр агуулгыг шинэчилж, гаргаж, сонгон, нэгтгэнэ.",
        "TRANSLATION": "Сонгосон Source агуулгыг хадгалан дахин ашиглах хэлний view эсвэл materialization үүсгэнэ.",
        "QUALITY & RESOLUTION": "Чанарын асуудлыг оношилж, exact эсвэл semantic асуудлыг засаж, нийцэл болон Rule conformance-г баталгаажуулна.",
        "OPERATION LIFECYCLE": "Apply хийхийн өмнө хүлээгдэж буй нөлөөг шалгах эсвэл дараа нь хадгалсан execution болон report evidence-г дахин үзнэ.",
        "GROUND WORKBENCH": "Goal, Rule болон жишээ Memory-г хамт хөгжүүлж, хийсвэр санааг хянах боломжтой нийтлэг суурь болгоно.",
        "HISTORY & RECOVERY": "Provenance болон бүртгэгдсэн өөрчлөлтийг шалгаж, тодорхой history operation-оор өмнөх төлөвийг сэргээнэ.",
        "PROFILES": "Бүрэн локал Profile store болон удирдлагатай нэрсийг сонгож, захирна.",
        "SHARING & PROTECTION": "Өөрийн Context-г хүргэж, Memory, Context эсвэл Profile бичилтийг хамгаална.",
        "SYSTEM & STUDY TOOLS": "MemCommit-г тохируулж, судалгаа болон evaluation хэрэгслийг бэлтгэх эсвэл ажиллуулна.",
    },
}


def localized_family_description(
    language: OperationCatalogLanguage,
    family_title: str,
) -> str:
    """Return canonical or reviewed localized copy for one exact family."""

    try:
        family = OPERATION_FAMILY_BY_TITLE[family_title]
    except KeyError as error:
        raise KeyError(f"No operation family is named {family_title!r}.") from error
    if language == "EN":
        return family.description
    return FAMILY_DESCRIPTION_TRANSLATIONS[language][family.title]


def validate_family_translation_coverage() -> None:
    """Fail closed when localized family copy drifts from the family registry."""

    expected = set(OPERATION_FAMILY_BY_TITLE)
    for language in OPERATION_CATALOG_LANGUAGES:
        if language == "EN":
            continue
        actual = set(FAMILY_DESCRIPTION_TRANSLATIONS[language])
        if actual != expected:
            missing = sorted(expected - actual)
            stale = sorted(actual - expected)
            raise ValueError(
                f"Operation family {language} translation coverage mismatch: "
                f"missing={missing}; stale={stale}"
            )
        if any(
            not description.strip()
            for description in FAMILY_DESCRIPTION_TRANSLATIONS[language].values()
        ):
            raise ValueError(
                f"Operation family {language} translation contains blank copy."
            )


__all__ = [
    "FAMILY_DESCRIPTION_TRANSLATIONS",
    "localized_family_description",
    "validate_family_translation_coverage",
]

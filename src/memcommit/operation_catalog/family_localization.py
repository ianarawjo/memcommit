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

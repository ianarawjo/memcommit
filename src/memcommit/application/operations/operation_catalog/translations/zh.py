"""Reviewed ZH operation catalog copy."""

from memcommit.application.operations.operation_catalog.translations.model import (
    LocalizedOperationCopy,
    localized_copy as _copy,
)


TRANSLATIONS: dict[str, LocalizedOperationCopy] = {
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
        "立即移除当前或指定 Context 中的所有直接项目；使用 --recursive 时清空其本地词法子树，Undo 可恢复整条命令。",
        "保留每个 Context，同时清空一个 Context 或本地词法子树时。",
    ),
    "compare": _copy(
        "比较两个 Context 中的 Memory，报告共同点、差异以及仅存在于一侧的内容。",
        "整体比较两个 Context，以理解它们的一致与差异时。",
    ),
    "copy": _copy(
        "将一个或多个直接拥有的 Memory 复制到现有本地 Context。",
        "在另一个 Context 中把选定 Memory 作为可独立编辑的值重复使用时。",
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
    "move": _copy(
        "将一个或多个直接拥有的 Memory 移动到另一个现有本地 Context。",
        "在保留内容和身份的同时更改选定 Memory 的拥有 Context 时。",
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
        "将一个直接 Source Memory 版本或直接/递归 Context 范围复制到 Target，作为不可变的只读 snapshot。",
        "即使 Source 后续改变或消失，也要保留精确的 Memory 或 Context 依据时。",
    ),
    "rename": _copy(
        "重命名普通 Context 命名空间及其所有词法后代，同时保留其稳定身份。",
        "纠正现有 Context 命名空间的组织名称时。",
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
        "将当前或指定的本地 Context 恢复到选定 checkpoint，并先审查该 revision 的完整结果状态。",
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

# These names were split after the original semantic Dedup contract was
# separated into exact Dedup and inclusive semantic Dedun operations.
TRANSLATIONS.update(
    {
        "dedun": _copy(
            "立即处理精确与语义 DUN 组，并保留每个连通组中最先存在的 UID。",
            "在一个检查点中一并清理精确 DUP 与语义 DUN。",
        ),
        "dedup": _copy(
            "立即删除内容逐字节相同的直接 Memories，并为每组保留最先存在的 UID。",
            "无需语义推理即可清除完全相同的内容副本。",
        ),
        "find-duplicates": _copy(
            "报告内容逐字节相同的直接 Memory 组；不修改 Context。",
            "在可能执行 Dedup 前，无需语义推理即可检查完全相同的副本。",
        ),
        "find-redundancies": _copy(
            "报告直接 Memory 中的精确与语义冗余；不修改任何 Source Context。",
            "在清理前一并检查精确 DUP 与语义 DUN。",
        ),
    }
)


__all__ = ["TRANSLATIONS"]

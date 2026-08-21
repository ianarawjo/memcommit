"""Static source inventory for architecture and boundary review.

The catalog deliberately reports observable source facts.  It does not infer
that an operation is safe, public, or architecturally closed merely because a
module with a promising name exists.
"""

from __future__ import annotations

import ast
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class StaticReference:
    """One statically resolved call into a catalogued callable."""

    caller: str
    path: str
    line: int


@dataclass(frozen=True)
class CallableRecord:
    """One source-declared function, method, class, or lambda."""

    identifier: str
    module: str
    qualified_name: str
    kind: str
    visibility: str
    export_status: str
    package_reexports: tuple[str, ...]
    signature: str
    decorators: tuple[str, ...]
    path: str
    line: int
    end_line: int
    inbound_references: tuple[StaticReference, ...]


@dataclass(frozen=True)
class OperationRouteRecord:
    """Mechanically observed interface and boundary files for one operation."""

    operation: str
    cli_entry: str
    application_modules: tuple[str, ...]
    tui_modules: tuple[str, ...]
    public_methods: tuple[str, ...]
    agent_modules: tuple[str, ...]
    boundary_matrices: tuple[str, ...]
    observed_shape: str
    curated_state: str


@dataclass(frozen=True)
class CatalogSnapshot:
    """Complete deterministic output of one repository scan."""

    callables: tuple[CallableRecord, ...]
    operations: tuple[OperationRouteRecord, ...]
    source_modules: tuple[str, ...]


@dataclass(frozen=True)
class _SourceModule:
    name: str
    path: Path
    relative_path: str
    source: str
    tree: ast.Module
    is_package: bool


def _module_name(package_root: Path, path: Path) -> tuple[str, bool]:
    relative = path.relative_to(package_root.parent).with_suffix("")
    parts = list(relative.parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def _source_modules(repository: Path) -> tuple[_SourceModule, ...]:
    package_root = repository / "memcommit"
    modules: list[_SourceModule] = []
    for path in sorted(package_root.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        name, is_package = _module_name(package_root, path)
        modules.append(
            _SourceModule(
                name=name,
                path=path,
                relative_path=path.relative_to(repository).as_posix(),
                source=source,
                tree=ast.parse(source, filename=str(path)),
                is_package=is_package,
            )
        )
    return tuple(modules)


def _literal_all(tree: ast.Module) -> tuple[str, ...] | None:
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in targets
        ):
            continue
        value = node.value
        if isinstance(value, (ast.List, ast.Tuple, ast.Set)) and all(
            isinstance(item, ast.Constant) and isinstance(item.value, str)
            for item in value.elts
        ):
            return tuple(item.value for item in value.elts)
    return None


def _resolve_from_module(source: _SourceModule, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""
    package = source.name if source.is_package else source.name.rpartition(".")[0]
    parts = package.split(".") if package else []
    remove = max(0, node.level - 1)
    if remove:
        parts = parts[:-remove]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def _package_reexports(modules: Iterable[_SourceModule]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = defaultdict(set)
    for source in modules:
        if not source.is_package:
            continue
        for node in source.tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            imported_module = _resolve_from_module(source, node)
            for alias in node.names:
                if alias.name == "*":
                    continue
                found[f"{imported_module}:{alias.name}"].add(
                    f"{source.name}:{alias.asname or alias.name}"
                )
    return found


def _annotation(value: ast.expr | None) -> str:
    return ast.unparse(value) if value is not None else ""


def _format_arg(argument: ast.arg, default: ast.expr | None = None) -> str:
    value = argument.arg
    if argument.annotation is not None:
        value += f": {_annotation(argument.annotation)}"
    if default is not None:
        value += f" = {ast.unparse(default)}"
    return value


def _format_arguments(arguments: ast.arguments) -> str:
    positional = list(arguments.posonlyargs) + list(arguments.args)
    defaults: list[ast.expr | None] = [None] * (
        len(positional) - len(arguments.defaults)
    ) + list(arguments.defaults)
    tokens = [
        _format_arg(argument, default)
        for argument, default in zip(positional, defaults, strict=True)
    ]
    if arguments.posonlyargs:
        tokens.insert(len(arguments.posonlyargs), "/")
    if arguments.vararg is not None:
        tokens.append("*" + _format_arg(arguments.vararg))
    elif arguments.kwonlyargs:
        tokens.append("*")
    for argument, default in zip(
        arguments.kwonlyargs,
        arguments.kw_defaults,
        strict=True,
    ):
        tokens.append(_format_arg(argument, default))
    if arguments.kwarg is not None:
        tokens.append("**" + _format_arg(arguments.kwarg))
    return ", ".join(tokens)


def _callable_signature(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        result = f"({_format_arguments(node.args)})"
        if node.returns is not None:
            result += f" -> {_annotation(node.returns)}"
        return result
    if isinstance(node, ast.Lambda):
        return f"({_format_arguments(node.args)})"
    if isinstance(node, ast.ClassDef):
        values = [ast.unparse(base) for base in node.bases]
        values.extend(
            f"{keyword.arg}={ast.unparse(keyword.value)}"
            if keyword.arg is not None
            else f"**{ast.unparse(keyword.value)}"
            for keyword in node.keywords
        )
        return f"({', '.join(values)})"
    raise TypeError(f"Unsupported callable node: {type(node).__name__}")


def _qualified_name(stack: list[tuple[str, str]], name: str) -> str:
    parts: list[str] = []
    for parent_name, parent_kind in stack:
        parts.append(parent_name)
        if parent_kind in {"function", "async-function", "lambda"}:
            parts.append("<locals>")
    parts.append(name)
    return ".".join(parts)


def _visibility(stack: list[tuple[str, str]], qualified_name: str) -> str:
    if any(kind in {"function", "async-function", "lambda"} for _, kind in stack):
        return "local"
    names = [name for name in qualified_name.split(".") if not name.startswith("<")]
    return "private" if any(name.startswith("_") for name in names) else "public"


class _DeclarationVisitor(ast.NodeVisitor):
    def __init__(
        self,
        source: _SourceModule,
        explicit_all: tuple[str, ...] | None,
        reexports: dict[str, set[str]],
    ) -> None:
        self.source = source
        self.explicit_all = explicit_all
        self.reexports = reexports
        self.stack: list[tuple[str, str]] = []
        self.records: list[dict[str, object]] = []

    def _record(self, node: ast.AST, *, name: str, kind: str) -> None:
        qualified_name = _qualified_name(self.stack, name)
        visibility = _visibility(self.stack, qualified_name)
        top_level = not self.stack
        if top_level and self.explicit_all is not None and name in self.explicit_all:
            export_status = "explicit"
        elif top_level and self.explicit_all is None and visibility == "public":
            export_status = "module-public"
        elif visibility == "local":
            export_status = "local"
        else:
            export_status = "not-exported"
        identifier = f"{self.source.name}:{qualified_name}"
        decorators = (
            tuple(ast.unparse(value) for value in node.decorator_list)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            else ()
        )
        self.records.append(
            {
                "identifier": identifier,
                "module": self.source.name,
                "qualified_name": qualified_name,
                "kind": kind,
                "visibility": visibility,
                "export_status": export_status,
                "package_reexports": tuple(
                    sorted(self.reexports.get(f"{self.source.name}:{name}", ()))
                )
                if top_level
                else (),
                "signature": _callable_signature(node),
                "decorators": decorators,
                "path": self.source.relative_path,
                "line": node.lineno,
                "end_line": getattr(node, "end_lineno", node.lineno),
            }
        )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node, name=node.name, kind="function")
        self.stack.append((node.name, "function"))
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record(node, name=node.name, kind="async-function")
        self.stack.append((node.name, "async-function"))
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record(node, name=node.name, kind="class")
        self.stack.append((node.name, "class"))
        self.generic_visit(node)
        self.stack.pop()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        name = f"<lambda>@{node.lineno}:{node.col_offset}"
        self._record(node, name=name, kind="lambda")
        self.stack.append((name, "lambda"))
        self.generic_visit(node)
        self.stack.pop()


def _import_aliases(
    source: _SourceModule,
    module_names: set[str],
) -> tuple[dict[str, str], dict[str, str]]:
    module_aliases: dict[str, str] = {}
    symbol_aliases: dict[str, str] = {}
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            imported_module = _resolve_from_module(source, node)
            for alias in node.names:
                if alias.name == "*":
                    continue
                local = alias.asname or alias.name
                candidate_module = f"{imported_module}.{alias.name}"
                if candidate_module in module_names:
                    module_aliases[local] = candidate_module
                else:
                    symbol_aliases[local] = f"{imported_module}:{alias.name}"
    return module_aliases, symbol_aliases


def _attribute_parts(node: ast.AST) -> tuple[str, ...] | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return tuple(reversed(parts))


class _CallVisitor(ast.NodeVisitor):
    def __init__(
        self,
        source: _SourceModule,
        module_names: set[str],
        identifiers: set[str],
    ) -> None:
        self.source = source
        self.module_names = module_names
        self.identifiers = identifiers
        self.module_aliases, self.symbol_aliases = _import_aliases(
            source,
            module_names,
        )
        self.stack: list[tuple[str, str]] = []
        self.references: list[tuple[str, StaticReference]] = []

    def _caller(self) -> str:
        if not self.stack:
            return f"{self.source.name}:<module>"
        return (
            f"{self.source.name}:{_qualified_name(self.stack[:-1], self.stack[-1][0])}"
        )

    def _resolve(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            if node.id in self.symbol_aliases:
                return self.symbol_aliases[node.id]
            candidate = f"{self.source.name}:{node.id}"
            return candidate if candidate in self.identifiers else None
        parts = _attribute_parts(node)
        if not parts:
            return None
        root, *attributes = parts
        if root in {"self", "cls"}:
            classes = [name for name, kind in self.stack if kind == "class"]
            if classes and attributes:
                candidate = f"{self.source.name}:{'.'.join(classes + attributes)}"
                return candidate if candidate in self.identifiers else None
        if root in self.symbol_aliases:
            candidate = self.symbol_aliases[root] + (
                "." + ".".join(attributes) if attributes else ""
            )
            return candidate if candidate in self.identifiers else None
        if root in self.module_aliases:
            combined = [*self.module_aliases[root].split("."), *attributes]
            for split in range(len(combined), 0, -1):
                module = ".".join(combined[:split])
                if module not in self.module_names:
                    continue
                qualified = ".".join(combined[split:])
                candidate = f"{module}:{qualified}"
                return candidate if candidate in self.identifiers else None
        candidate = f"{self.source.name}:{'.'.join(parts)}"
        return candidate if candidate in self.identifiers else None

    def visit_Call(self, node: ast.Call) -> None:
        target = self._resolve(node.func)
        if target is not None:
            self.references.append(
                (
                    target,
                    StaticReference(
                        caller=self._caller(),
                        path=self.source.relative_path,
                        line=node.lineno,
                    ),
                )
            )
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append((node.name, "function"))
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.stack.append((node.name, "async-function"))
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append((node.name, "class"))
        self.generic_visit(node)
        self.stack.pop()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.stack.append((f"<lambda>@{node.lineno}:{node.col_offset}", "lambda"))
        self.generic_visit(node)
        self.stack.pop()


def _declarations(modules: tuple[_SourceModule, ...]) -> list[dict[str, object]]:
    reexports = _package_reexports(modules)
    records: list[dict[str, object]] = []
    for source in modules:
        visitor = _DeclarationVisitor(source, _literal_all(source.tree), reexports)
        visitor.visit(source.tree)
        records.extend(visitor.records)
    counts = Counter(str(record["identifier"]) for record in records)
    for record in records:
        reference_key = str(record["identifier"])
        record["reference_key"] = reference_key
        if counts[reference_key] > 1:
            # Overloads and conditional definitions legitimately repeat one
            # Python qualified name. The source line preserves each declaration
            # without pretending static calls select one runtime definition.
            record["identifier"] = f"{reference_key}@{record['line']}"
    return records


def _callables(modules: tuple[_SourceModule, ...]) -> tuple[CallableRecord, ...]:
    declarations = _declarations(modules)
    identifiers = {str(record["reference_key"]) for record in declarations}
    module_names = {source.name for source in modules}
    inbound: dict[str, list[StaticReference]] = defaultdict(list)
    for source in modules:
        visitor = _CallVisitor(source, module_names, identifiers)
        visitor.visit(source.tree)
        for target, reference in visitor.references:
            inbound[target].append(reference)
    result = []
    for record in declarations:
        reference_key = str(record.pop("reference_key"))
        result.append(
            CallableRecord(
                **record,
                inbound_references=tuple(
                    sorted(
                        inbound.get(reference_key, ()),
                        key=lambda value: (value.path, value.line, value.caller),
                    )
                ),
            )
        )
    return tuple(
        sorted(
            result, key=lambda value: (value.module, value.line, value.qualified_name)
        )
    )


def _help_operations(repository: Path) -> tuple[str, ...]:
    path = repository / "memcommit" / "help_catalog" / "catalog.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_operation"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    return tuple(sorted(names))


def _expression_target(
    node: ast.AST,
    *,
    source: _SourceModule,
    module_names: set[str],
) -> str:
    module_aliases, symbol_aliases = _import_aliases(source, module_names)
    if isinstance(node, ast.Name):
        return symbol_aliases.get(node.id, f"{source.name}:{node.id}")
    parts = _attribute_parts(node)
    if not parts:
        return ast.unparse(node)
    root, *attributes = parts
    if root in symbol_aliases:
        return symbol_aliases[root] + ("." + ".".join(attributes) if attributes else "")
    if root in module_aliases:
        combined = [*module_aliases[root].split("."), *attributes]
        for split in range(len(combined), 0, -1):
            module = ".".join(combined[:split])
            if module in module_names:
                return f"{module}:{'.'.join(combined[split:])}"
    return f"{source.name}:{'.'.join(parts)}"


def _constant_keyword(node: ast.Call, name: str) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return keyword.value.value if isinstance(keyword.value.value, str) else None
    return None


def _cli_entries(
    repository: Path,
    modules: tuple[_SourceModule, ...],
) -> dict[str, str]:
    source = next(module for module in modules if module.name == "memcommit.cli")
    module_names = {module.name for module in modules}
    entries: dict[str, str] = {}
    for node in source.tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            outer = node.value
            if (
                isinstance(outer.func, ast.Call)
                and isinstance(outer.func.func, ast.Attribute)
                and outer.func.func.attr == "command"
                and outer.func.args
                and isinstance(outer.func.args[0], ast.Constant)
                and isinstance(outer.func.args[0].value, str)
                and outer.args
            ):
                entries[outer.func.args[0].value] = _expression_target(
                    outer.args[0],
                    source=source,
                    module_names=module_names,
                )
            elif (
                isinstance(outer.func, ast.Attribute)
                and outer.func.attr == "add_typer"
                and outer.args
                and (name := _constant_keyword(outer, "name")) is not None
            ):
                entries[name] = _expression_target(
                    outer.args[0],
                    source=source,
                    module_names=module_names,
                )
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if not (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "command"
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and isinstance(decorator.args[0].value, str)
                ):
                    continue
                entries[decorator.args[0].value] = f"memcommit.cli:{node.name}"
    return entries


def _client_methods(repository: Path) -> dict[str, set[str]]:
    path = repository / "memcommit" / "api" / "client.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, set[str]] = defaultdict(set)
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "MemCommitClient":
            continue
        for method in node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(method):
                if not isinstance(child, ast.ImportFrom) or not child.module:
                    continue
                prefix = "memcommit.api._operations."
                if child.module.startswith(prefix):
                    found[child.module.removeprefix(prefix)].add(method.name)
    return found


_OPERATION_DISCOVERY_TOKENS = {
    "checkout": ("checkout", "branch", "switch"),
    # Complete Dedun retains legacy finder, Consolidate, and Dedup module
    # names while exact Dedup owns explicit exact_dedup modules. Keeping the
    # mapping authored prevents the evidence ledger from conflating the routes.
    "dedun": ("dedun", "consolidate", "find_duplicates", "dedup"),
    "dedup": ("exact_dedup",),
    "eval": ("eval", "semantic_eval"),
    "find-duplicates": (
        "find_exact_duplicates",
        "exact_duplicates",
        "exact_dedup",
    ),
    "find-redundancies": (
        "find_redundancies",
        "find_duplicates",
        "quality_find",
    ),
    "help": ("help", "help_inventory"),
    "import": ("import", "import_profile"),
    "init": ("init", "context_init"),
    "list": ("list", "list_memories"),
    "lock": ("lock", "write_protection"),
    "pwd": ("pwd", "current_context"),
    "unlock": ("unlock", "write_protection"),
}


def _operation_tokens(operation: str) -> tuple[str, ...]:
    token = operation.replace("-", "_")
    return _OPERATION_DISCOVERY_TOKENS.get(operation, (token,))


def _module_owner_matches(module: str, tokens: tuple[str, ...]) -> bool:
    leaf = module.rsplit(".", 1)[-1].replace("-", "_")
    return any(leaf == token or leaf.startswith(token + "_") for token in tokens)


def _operation_package_matches(module: str, tokens: tuple[str, ...]) -> bool:
    return any(
        module == f"memcommit.operations.{token}"
        or module.startswith(f"memcommit.operations.{token}.")
        for token in tokens
    )


def _matrix_matches(path: Path, operation: str, tokens: tuple[str, ...]) -> bool:
    stem = path.stem.replace("-", "_")
    canonical = operation.replace("-", "_")
    if operation != "find-duplicates" and stem.startswith("find_duplicates_"):
        # The semantic implementation retains a duplicate-named module, but
        # operation evidence follows the independent public command identity.
        return False
    if operation != "find-redundancies" and stem.startswith("find_redundancies_"):
        # Literal Find and exact Find Duplicates must not absorb the broader
        # quality-finder evidence merely because their names share a prefix.
        return False
    if stem == canonical or stem.startswith(canonical + "_"):
        return True
    if operation == "dedun":
        # Its implementation modules retain compatibility names, but evidence
        # files are authored under canonical operation names and must not
        # cross-link with exact Dedup.
        return False
    if any(stem == token or stem.startswith(token + "_") for token in tokens):
        return True
    # This is the one current matrix that deliberately owns two operations.
    return operation == "elaborate" and stem.startswith("distill_elaborate_")


_CURATED_STATES = {"CLOSED", "MIXED", "LEGACY", "N/A", "UNREVIEWED"}


def _operation_classifications(
    repository: Path,
    operations: tuple[str, ...],
) -> dict[str, str]:
    """Load the reviewed conclusion separately from mechanically observed shape."""

    path = repository / "docs" / "operation-route-classification.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError(f"{path}: expected classification schema version 1")
    definitions = document.get("definitions")
    if not isinstance(definitions, dict) or set(definitions) != _CURATED_STATES:
        raise ValueError(f"{path}: definitions must cover every curated state")
    classifications = document.get("classifications")
    if not isinstance(classifications, dict):
        raise ValueError(f"{path}: classifications must be an object")
    if set(classifications) != _CURATED_STATES:
        raise ValueError(f"{path}: classifications must declare every curated state")

    found: dict[str, str] = {}
    for state, entries in classifications.items():
        if state == "UNREVIEWED":
            if not isinstance(entries, list) or not all(
                isinstance(item, str) for item in entries
            ):
                raise ValueError(f"{path}: UNREVIEWED must be a string list")
            names = entries
        else:
            if not isinstance(entries, dict):
                raise ValueError(f"{path}: {state} must be an evidence object")
            for name, evidence_record in entries.items():
                if not isinstance(name, str) or not isinstance(evidence_record, dict):
                    raise ValueError(f"{path}: invalid {state} evidence record")
                evidence = evidence_record.get("evidence")
                reason = evidence_record.get("reason")
                if (
                    not isinstance(evidence, list)
                    or not evidence
                    or not all(isinstance(item, str) for item in evidence)
                ):
                    raise ValueError(f"{path}: {state}/{name} requires evidence paths")
                if not isinstance(reason, str) or not reason.strip():
                    raise ValueError(f"{path}: {state}/{name} requires a reason")
                for evidence_path in evidence:
                    candidate = repository / evidence_path
                    if not evidence_path.startswith("docs/") or not candidate.is_file():
                        raise ValueError(
                            f"{path}: {state}/{name} evidence does not exist: "
                            f"{evidence_path}"
                        )
            names = entries
        for name in names:
            if name in found:
                raise ValueError(f"{path}: operation {name!r} is classified twice")
            found[name] = state

    expected = set(operations)
    actual = set(found)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"{path}: classification coverage differs from Help operations; "
            f"missing={missing!r}, extra={extra!r}"
        )
    return found


def _operation_routes(
    repository: Path,
    modules: tuple[_SourceModule, ...],
) -> tuple[OperationRouteRecord, ...]:
    operations = _help_operations(repository)
    classifications = _operation_classifications(repository, operations)
    entries = _cli_entries(repository, modules)
    module_names = {module.name for module in modules}
    client_methods = _client_methods(repository)
    matrix_files = tuple(sorted((repository / "docs").glob("*boundary-matrix.md")))
    result: list[OperationRouteRecord] = []
    for operation in operations:
        tokens = _operation_tokens(operation)
        application_modules = tuple(
            sorted(
                module
                for module in module_names
                if (
                    (module.count(".") == 1 and _module_owner_matches(module, tokens))
                    or _operation_package_matches(module, tokens)
                )
                and (
                    "application" in module.split(".")[-1]
                    or "runtime" in module.split(".")[-1]
                    or _operation_package_matches(module, tokens)
                )
                and not module.startswith("memcommit.api.")
                and not module.startswith("memcommit.interfaces.")
            )
        )
        tui_modules = tuple(
            sorted(
                module
                for module in module_names
                if module.startswith("memcommit.interfaces.tui.operations.")
                and _module_owner_matches(
                    module.removeprefix("memcommit.interfaces.tui.operations.").split(
                        ".", 1
                    )[0],
                    tokens,
                )
            )
        )
        public_methods = tuple(
            sorted(
                method
                for adapter, methods in client_methods.items()
                if _module_owner_matches(adapter, tokens)
                for method in methods
            )
        )
        agent_modules = tuple(
            sorted(
                module
                for module in module_names
                if module.startswith("memcommit.interfaces.agent.")
                and _module_owner_matches(module, tokens)
                and module.rsplit(".", 1)[-1] not in {"contract", "registry"}
            )
        )
        boundary_matrices = tuple(
            path.relative_to(repository).as_posix()
            for path in matrix_files
            if _matrix_matches(path, operation, tokens)
        )
        observed = sum(
            bool(value)
            for value in (
                application_modules,
                tui_modules,
                public_methods,
                agent_modules,
                boundary_matrices,
            )
        )
        if all(
            (
                application_modules,
                tui_modules,
                public_methods,
                agent_modules,
                boundary_matrices,
            )
        ):
            observed_shape = "MULTI_ADAPTER"
        elif application_modules and boundary_matrices:
            observed_shape = "BOUNDED_INTERNAL"
        elif observed:
            observed_shape = "PARTIAL_SURFACE"
        else:
            observed_shape = "COMMAND_ONLY"
        result.append(
            OperationRouteRecord(
                operation=operation,
                cli_entry=entries.get(operation, "MISSING"),
                application_modules=application_modules,
                tui_modules=tui_modules,
                public_methods=public_methods,
                agent_modules=agent_modules,
                boundary_matrices=boundary_matrices,
                observed_shape=observed_shape,
                curated_state=classifications[operation],
            )
        )
    return tuple(result)


def build_catalog(repository: Path) -> CatalogSnapshot:
    """Scan one repository without importing MemCommit runtime modules."""

    repository = repository.resolve()
    modules = _source_modules(repository)
    return CatalogSnapshot(
        callables=_callables(modules),
        operations=_operation_routes(repository, modules),
        source_modules=tuple(module.name for module in modules),
    )


def render_callable_jsonl(snapshot: CatalogSnapshot) -> str:
    """Render one stable JSON object per callable."""

    return "".join(
        json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n"
        for record in snapshot.callables
    )


def _markdown_values(values: tuple[str, ...]) -> str:
    if not values:
        return "—"
    return "<br>".join(f"`{value}`" for value in values)


def render_operation_markdown(snapshot: CatalogSnapshot) -> str:
    """Render the operation-level observed-route index."""

    rows = [
        "# Generated operation route catalog",
        "",
        "This file is generated from source. `Observed shape` reports only which",
        "layers and evidence files are statically present; it is not a safety or",
        "architectural-closure conclusion. `Curated state` comes from the reviewed",
        "`docs/operation-route-classification.json`; `UNREVIEWED` is not a",
        "`LEGACY` conclusion.",
        "",
        "| Operation | CLI entry | Application/runtime | TUI | Public Python | Agent | Boundary matrix | Observed shape | Curated state |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in snapshot.operations:
        values = (
            f"`{record.operation}`",
            f"`{record.cli_entry}`",
            _markdown_values(record.application_modules),
            _markdown_values(record.tui_modules),
            _markdown_values(record.public_methods),
            _markdown_values(record.agent_modules),
            _markdown_values(record.boundary_matrices),
            f"`{record.observed_shape}`",
            f"`{record.curated_state}`",
        )
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows) + "\n"


def render_summary_json(snapshot: CatalogSnapshot) -> str:
    """Render deterministic aggregate counts suitable for review diffs."""

    summary = {
        "callable_count": len(snapshot.callables),
        "callable_kinds": dict(
            sorted(Counter(item.kind for item in snapshot.callables).items())
        ),
        "module_count": len(snapshot.source_modules),
        "operation_count": len(snapshot.operations),
        "operation_observed_shapes": dict(
            sorted(Counter(item.observed_shape for item in snapshot.operations).items())
        ),
        "operation_curated_states": dict(
            sorted(Counter(item.curated_state for item in snapshot.operations).items())
        ),
        "visibility": dict(
            sorted(Counter(item.visibility for item in snapshot.callables).items())
        ),
    }
    return json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

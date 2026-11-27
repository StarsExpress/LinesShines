"""Check the Python code-style rules that `black -S` cannot see.

Dev-only tool, never imported by `main.py`. The rules come from the "Code style" bullet of
`playbook/INVARIANTS.md`; each one is a small function below that reads one parsed file and
returns its violations. Old code that already breaks a rule is listed in `code_style_baseline.json`,
so the check fails only on a violation that is new, and also on a baseline entry that no longer
applies, which keeps the list shrinking.

Usage (from repo root):
    python -m tools.check_code_style
    python -m tools.check_code_style path/to/file.py
    python -m tools.check_code_style --update-baseline
"""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = Path(__file__).resolve().parent / "code_style_baseline.json"
SKIPPED_DIRECTORY_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "playbook",
    "sandbox",
    "__pycache__",
}

BRANCH_KEYWORDS = {"elif", "else", "except", "finally"}
IGNORED_TOKEN_TYPES = {
    tokenize.NL,
    tokenize.COMMENT,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
}

SENTENCE_ENDINGS = (".", "?", "!")
MAX_STATEMENTS_WITHOUT_BLANK_LINE = 6

SNAKE_CASE_PATTERN = re.compile(r"^_*[a-z][a-z0-9_]*$")
UPPER_SNAKE_PATTERN = re.compile(r"^_*[A-Z][A-Z0-9_]*$")

CAP_WORDS_PATTERN = re.compile(r"^_*[A-Z][A-Za-z0-9]*$")
COMMAND_WORDS = (
    "python",
    "pytest",
    "npm",
    "uvicorn",
    "curl",
    "black",
    "pip",
    "git",
    "railway",
    "psql",
    "GET",
    "POST",
    "PUT",
    "DELETE",
)

# Rules left out of a top-level folder: a test takes pytest's fixture names and has no signature to hint.
RULE_SKIPPED_DIRECTORIES = {
    "tests": {
        "type-hints",
        "abbreviation",
        "constants-above-functions",
        "blank-between-steps",
    }
}

COMMENT_DIRECTIVE_PATTERN = re.compile(
    r"^(noqa|fmt:|type:|pragma|pylint|isort|ruff|mypy|pyright|!|-\*-)"
)

DATAFRAME_FACTORY_NAMES = {
    "DataFrame",
    "concat",
    "merge",
    "read_csv",
    "read_excel",
    "read_json",
    "read_parquet",
    "read_sql",
}

ABBREVIATIONS = {
    "arr",
    "btn",
    "cb",
    "cfg",
    "cnt",
    "conf",
    "ctx",
    "elem",
    "err",
    "fn",
    "idx",
    "msg",
    "num",
    "obj",
    "param",
    "params",
    "req",
    "res",
    "resp",
    "ret",
    "tmp",
    "val",
    "vals",
}


@dataclass(frozen=True)
class Violation:
    """One place where a rule is broken."""

    path: str
    line: int
    rule: str
    message: str
    context: str

    @property
    def key(self) -> str:
        """What the baseline remembers: the file, the rule and the offending line's text, never its number."""
        return f"{self.path}|{self.rule}|{self.context}"

    def render(self) -> str:
        """The line printed for this violation."""
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


@dataclass
class ParsedSource:
    """A file read once: its lines, its syntax tree and its tokens."""

    path: str
    lines: list[str]
    tree: ast.Module
    tokens: list[tokenize.TokenInfo]

    def violation(self, line: int, rule: str, message: str) -> Violation:
        """A violation at `line`, with that line's text as its context."""
        in_file = 0 < line <= len(self.lines)
        context = self.lines[line - 1].strip() if in_file else ""

        return Violation(self.path, line, rule, message, context)


def parse_source(text: str, path: str) -> ParsedSource:
    """Parse and tokenize one file; raises `SyntaxError` or `tokenize.TokenError` when it cannot."""
    tree = ast.parse(text)
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))

    return ParsedSource(path, text.splitlines(), tree, tokens)


def function_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every function and method in the tree."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def function_arguments(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.arg]:
    """All parameters of a function, including `*args` and `**kwargs`."""
    arguments = function.args
    parameters = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]

    if arguments.vararg:
        parameters.append(arguments.vararg)

    if arguments.kwarg:
        parameters.append(arguments.kwarg)

    return parameters


def has_blank_line_above(lines: list[str], line_number: int) -> bool:
    """Whether the line is preceded by a blank line, looking past comment lines that belong to it."""
    index = line_number - 2

    while index >= 0 and lines[index].strip().startswith("#"):
        index -= 1

    return index < 0 or lines[index].strip() == ""


def check_blank_line_before_branches(source: ParsedSource) -> list[Violation]:
    """Every `elif`, `else`, `except` and `finally` has a blank line above it."""
    violations: list[Violation] = []
    starts_logical_line = True

    for token in source.tokens:
        if token.type in IGNORED_TOKEN_TYPES:
            continue

        is_branch = token.type == tokenize.NAME and token.string in BRANCH_KEYWORDS

        if starts_logical_line and is_branch:
            if not has_blank_line_above(source.lines, token.start[0]):
                violations.append(
                    source.violation(
                        token.start[0],
                        "blank-before-branch",
                        f"put a blank line before `{token.string}`",
                    )
                )

        starts_logical_line = token.type == tokenize.NEWLINE

    return violations


def check_type_hints(source: ParsedSource) -> list[Violation]:
    """Every function signature hints each parameter and its return."""
    violations: list[Violation] = []

    for function in function_nodes(source.tree):
        missing = [
            parameter.arg
            for parameter in function_arguments(function)
            if parameter.annotation is None and parameter.arg not in ("self", "cls")
        ]

        if missing:
            violations.append(
                source.violation(
                    function.lineno,
                    "type-hints",
                    f"`{function.name}` has no type hint for {', '.join(missing)}",
                )
            )

        if function.returns is None:
            violations.append(
                source.violation(
                    function.lineno,
                    "type-hints",
                    f"`{function.name}` has no return type hint",
                )
            )

    return violations


def check_module_docstring(source: ParsedSource) -> list[Violation]:
    """A module that has code starts with a docstring."""
    if source.tree.body and ast.get_docstring(source.tree) is None:
        return [
            source.violation(1, "module-docstring", "start the module with a docstring")
        ]

    return []


def is_standalone_comment(token: tokenize.TokenInfo) -> bool:
    """A comment on a line of its own, not after code."""
    return token.line[: token.start[1]].strip() == ""


def comment_blocks(source: ParsedSource) -> list[list[tokenize.TokenInfo]]:
    """Comments grouped so that a wrapped sentence is one block; a comment after code is its own block."""
    blocks: list[list[tokenize.TokenInfo]] = []

    for token in source.tokens:
        if token.type != tokenize.COMMENT:
            continue

        previous = blocks[-1][-1] if blocks else None
        continues_block = (
            previous is not None
            and is_standalone_comment(previous)
            and is_standalone_comment(token)
            and token.start[0] == previous.start[0] + 1
            and token.start[1] == previous.start[1]
        )

        if continues_block:
            blocks[-1].append(token)

        else:
            blocks.append([token])

    return blocks


def comment_is_exempt(token: tokenize.TokenInfo) -> bool:
    """A comment a period would change: a shebang, a directive, a section divider, or one that ends in a URL."""
    text = token.string.lstrip("#").strip()

    if not text or token.string.startswith("#!"):
        return True

    if COMMENT_DIRECTIVE_PATTERN.match(text) or text.startswith(("---", "===")):
        return True

    return text.split()[-1].startswith(("http://", "https://"))


def check_comment_periods(source: ParsedSource) -> list[Violation]:
    """The last line of every comment block ends with a period (or `?` or `!`)."""
    violations: list[Violation] = []

    for block in comment_blocks(source):
        last = block[-1]
        text = last.string.strip()

        if comment_is_exempt(last) or text.endswith(SENTENCE_ENDINGS):
            continue

        violations.append(
            source.violation(
                last.start[0], "comment-period", "end the comment with a period"
            )
        )

    return violations


def docstring_nodes(
    tree: ast.Module,
) -> list[ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef]:
    """The module, classes and functions that have a docstring."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        )
        and ast.get_docstring(node) is not None
    ]


def docstring_line(node: ast.AST) -> int:
    """The line a node's docstring starts on."""
    if isinstance(node, ast.Module):
        return node.body[0].lineno

    return node.body[0].lineno


def paragraph_ends_in_code(paragraph: str) -> bool:
    """A paragraph that ends in a shell command, a route or an indented example, which a period would change."""
    lines = paragraph.splitlines()
    last_line = lines[-1]
    command = re.sub(r"^\s*\d+\.\s*", "", last_line).strip()

    if command.startswith(COMMAND_WORDS):
        return True

    return (
        len(lines) > 1 and lines[0].endswith(":") and last_line.startswith((" ", "\t"))
    )


def check_docstring_periods(source: ParsedSource) -> list[Violation]:
    """Every prose paragraph of a docstring ends with a period; a lead-in may end with a colon."""
    violations: list[Violation] = []

    for node in docstring_nodes(source.tree):
        paragraphs = re.split(r"\n\s*\n", ast.get_docstring(node).strip())

        for index, paragraph in enumerate(paragraphs):
            is_code_block = paragraph.startswith((" ", "\t"))
            is_lead_in = paragraph.endswith(":") and index < len(paragraphs) - 1

            is_prose = not (
                is_code_block or is_lead_in or paragraph_ends_in_code(paragraph)
            )

            if not is_prose or paragraph.endswith(SENTENCE_ENDINGS):
                continue

            violations.append(
                source.violation(
                    docstring_line(node),
                    "docstring-period",
                    f"end the docstring paragraph \"{paragraph.splitlines()[-1].strip()}\" with a period",
                )
            )

    return violations


def constant_target_ids(tree: ast.Module) -> set[int]:
    """The identity of every name a module-level or class-level assignment binds; these may be constants."""
    scopes = [tree.body]
    scopes.extend(
        node.body for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    )
    target_ids: set[int] = set()

    for scope in scopes:
        for statement in scope:
            if isinstance(statement, ast.Assign):
                targets = statement.targets

            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]

            else:
                continue

            for target in targets:
                target_ids.update(id(node) for node in ast.walk(target))

    return target_ids


def bound_names(tree: ast.Module) -> list[tuple[int, str, bool]]:
    """Every name the file binds as (line, name, may_be_constant)."""
    constant_ids = constant_target_ids(tree)
    names: list[tuple[int, str, bool]] = []

    for function in function_nodes(tree):
        names.append((function.lineno, function.name, False))
        names.extend(
            (parameter.lineno, parameter.arg, False)
            for parameter in function_arguments(function)
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append((node.lineno, node.id, id(node) in constant_ids))

        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.append((node.lineno, node.name, False))

    return names


def is_abbreviation(name: str) -> bool:
    """A one-letter name, `df`, or a name with a known abbreviation as one of its words."""
    stripped = name.strip("_")

    if len(stripped) == 1 or stripped == "df":
        return True

    return any(word in ABBREVIATIONS for word in stripped.lower().split("_"))


def check_names(source: ParsedSource) -> list[Violation]:
    """Names are spelled out in `snake_case`; a constant or a class-like object at module level may differ."""
    violations: list[Violation] = []

    for line, name, may_be_constant in bound_names(source.tree):
        if name == "_":
            continue

        is_constant = may_be_constant and (
            UPPER_SNAKE_PATTERN.match(name) or CAP_WORDS_PATTERN.match(name)
        )

        if not is_constant and not SNAKE_CASE_PATTERN.match(name):
            violations.append(
                source.violation(line, "snake-case", f"`{name}` is not snake_case")
            )

        if is_abbreviation(name):
            violations.append(
                source.violation(line, "abbreviation", f"spell `{name}` out in full")
            )

    return violations


def reads_every_sheet(call: ast.Call) -> bool:
    """`pd.read_excel(..., sheet_name=None)` returns a dict of DataFrames, not one."""
    return any(
        keyword.arg == "sheet_name"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is None
        for keyword in call.keywords
    )


def is_dataframe_factory_call(value: ast.expr) -> bool:
    """A call such as `pd.read_csv(...)` or `pd.DataFrame(...)`."""
    return (
        isinstance(value, ast.Call)
        and not reads_every_sheet(value)
        and isinstance(value.func, ast.Attribute)
        and isinstance(value.func.value, ast.Name)
        and value.func.value.id == "pd"
        and value.func.attr in DATAFRAME_FACTORY_NAMES
    )


def check_dataframe_names(source: ParsedSource) -> list[Violation]:
    """A name bound straight from a pandas call that builds a DataFrame ends in `_df`."""
    violations: list[Violation] = []

    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Assign) or not is_dataframe_factory_call(
            node.value
        ):
            continue

        for target in node.targets:
            if isinstance(target, ast.Name) and not target.id.endswith("_df"):
                violations.append(
                    source.violation(
                        node.lineno,
                        "dataframe-name",
                        f"`{target.id}` holds a DataFrame, so end its name in `_df`",
                    )
                )

    return violations


def is_constant_assignment(statement: ast.stmt) -> bool:
    """A module-level assignment whose targets are all UPPER_SNAKE_CASE names."""
    if isinstance(statement, ast.Assign):
        targets = statement.targets

    elif isinstance(statement, ast.AnnAssign):
        targets = [statement.target]

    else:
        return False

    return all(
        isinstance(target, ast.Name)
        and UPPER_SNAKE_PATTERN.match(target.id)
        and not target.id.startswith("__")
        for target in targets
    )


def uses_names(statement: ast.stmt, names: set[str]) -> bool:
    """Whether the statement reads any of the names."""
    return any(
        isinstance(node, ast.Name) and node.id in names for node in ast.walk(statement)
    )


def check_constants_above_functions(source: ParsedSource) -> list[Violation]:
    """Module constants sit above the first function or class, unless they need one of them."""
    violations: list[Violation] = []
    seen_definition = False
    defined_names = {
        statement.name
        for statement in source.tree.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    for statement in source.tree.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen_definition = True

        elif seen_definition and is_constant_assignment(statement):
            if uses_names(statement, defined_names):
                continue

            violations.append(
                source.violation(
                    statement.lineno,
                    "constants-above-functions",
                    "move the constant above the functions",
                )
            )

    return violations


def statement_lists(tree: ast.Module) -> list[list[ast.stmt]]:
    """Every block of statements in the file: bodies, `else` parts, `finally` parts and handlers."""
    blocks: list[list[ast.stmt]] = []

    for node in ast.walk(tree):
        for attribute in ("body", "orelse", "finalbody"):
            value = getattr(node, attribute, None)

            if isinstance(value, list) and value and isinstance(value[0], ast.stmt):
                blocks.append(value)

    return blocks


def breaks_run(statement: ast.stmt) -> bool:
    """Imports, constants, field declarations and asserts stack up on purpose, so they never count toward a wall."""
    return isinstance(
        statement, (ast.Import, ast.ImportFrom, ast.AnnAssign, ast.Assert)
    ) or is_constant_assignment(statement)


def check_walls_of_statements(source: ParsedSource) -> list[Violation]:
    """No more than a handful of statements in a row without a blank line between them."""
    violations: list[Violation] = []

    for block in statement_lists(source.tree):
        run_start = block[0]
        run_length = 0
        reported = False

        for index, statement in enumerate(block):
            previous = block[index - 1] if index else None
            touches_previous = (
                previous is not None
                and run_length > 0
                and statement.lineno - previous.end_lineno == 1
            )

            if breaks_run(statement):
                run_length = 0
                continue

            if touches_previous:
                run_length += 1

            else:
                run_start = statement
                run_length = 1
                reported = False

            if run_length > MAX_STATEMENTS_WITHOUT_BLANK_LINE and not reported:
                reported = True
                violations.append(
                    source.violation(
                        run_start.lineno,
                        "blank-between-steps",
                        f"more than {MAX_STATEMENTS_WITHOUT_BLANK_LINE} statements in a row; "
                        "put a blank line between steps",
                    )
                )

    return violations


RULE_CHECKS = [
    check_blank_line_before_branches,
    check_type_hints,
    check_module_docstring,
    check_comment_periods,
    check_docstring_periods,
    check_names,
    check_dataframe_names,
    check_constants_above_functions,
    check_walls_of_statements,
]


def check_source(text: str, path: str) -> list[Violation]:
    """Every violation in one file's text, in line order."""
    try:
        source = parse_source(text, path)

    except (SyntaxError, tokenize.TokenError) as error:
        return [Violation(path, 1, "syntax", f"cannot read the file: {error}", "")]

    skipped_rules = RULE_SKIPPED_DIRECTORIES.get(Path(path).parts[0], set())
    violations = [
        violation
        for check in RULE_CHECKS
        for violation in check(source)
        if violation.rule not in skipped_rules
    ]

    return sorted(violations, key=lambda violation: (violation.line, violation.rule))


def is_skipped(relative_path: Path) -> bool:
    """Whether a path sits in a virtual environment, `node_modules`, the playbook or `sandbox/`, which are never checked."""
    return bool(SKIPPED_DIRECTORY_NAMES.intersection(relative_path.parts))


def find_python_files(root: Path) -> list[Path]:
    """Every `.py` file under the root that is not skipped."""
    return sorted(
        path for path in root.rglob("*.py") if not is_skipped(path.relative_to(root))
    )


def check_files(paths: list[Path], root: Path | None = None) -> list[Violation]:
    """Every violation in the given files, leaving out skipped folders; paths are shown relative to the root (the repo by default)."""
    root = root or REPO_ROOT
    violations: list[Violation] = []

    for path in paths:
        relative_path = path.resolve().relative_to(root)

        if is_skipped(relative_path):
            continue

        violations.extend(
            check_source(path.read_text(encoding="utf-8"), relative_path.as_posix())
        )

    return violations


def load_baseline(baseline_path: Path | None = None) -> Counter:
    """The violations already accepted, as a count per key; empty when there is no baseline file."""
    baseline_path = baseline_path or BASELINE_PATH

    if not baseline_path.exists():
        return Counter()

    return Counter(json.loads(baseline_path.read_text(encoding="utf-8")))


def write_baseline(
    violations: list[Violation], baseline_path: Path | None = None
) -> None:
    """Save the current violations as the accepted ones."""
    baseline_path = baseline_path or BASELINE_PATH
    counts = Counter(violation.key for violation in violations)
    baseline_path.write_text(
        json.dumps(dict(sorted(counts.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def split_by_baseline(
    violations: list[Violation], baseline: Counter
) -> tuple[list[Violation], list[str]]:
    """The violations beyond the baseline, and the baseline keys that are no longer fully used."""
    remaining = Counter(baseline)
    new_violations: list[Violation] = []

    for violation in violations:
        if remaining[violation.key] > 0:
            remaining[violation.key] -= 1

        else:
            new_violations.append(violation)

    return new_violations, sorted(key for key, count in remaining.items() if count > 0)


def main(argv: list[str] | None = None) -> int:
    """Check the repo (or the named files); returns 1 when a violation is new or the baseline is stale."""
    parser = argparse.ArgumentParser(
        description="Check the code-style rules black cannot see."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Files to check; default is every Python file.",
    )
    parser.add_argument(
        "--update-baseline", action="store_true", help="Accept every current violation."
    )
    arguments = parser.parse_args(argv)

    if arguments.update_baseline and arguments.paths:
        parser.error("--update-baseline checks the whole repo, so name no files.")

    checks_whole_repo = not arguments.paths
    paths = arguments.paths or find_python_files(REPO_ROOT)
    violations = check_files([path.resolve() for path in paths])

    if arguments.update_baseline:
        write_baseline(violations)
        print(f"Baseline now holds {len(violations)} violation(s).")

        return 0

    new_violations, stale_keys = split_by_baseline(violations, load_baseline())

    for violation in new_violations:
        print(violation.render())

    if checks_whole_repo:
        for key in stale_keys:
            print(f"Baseline entry no longer applies: {key}")

    if new_violations or (checks_whole_repo and stale_keys):
        print(
            "Fix the new violations; for stale entries run `python -m tools.check_code_style --update-baseline`."
        )

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

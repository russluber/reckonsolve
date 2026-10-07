"""Check local Markdown links and section anchors without network access."""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

_LABEL = re.compile(r"(?<!\\)\[([^\]]*)\]")
_DEFINITION = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]*(<[^>]+>|\S+)[^\n]*", re.MULTILINE)
_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.*?)\1(?!`)", re.DOTALL)
_CUSTOM_ANCHOR = re.compile(
    r"<a\b[^>]*\b(?:id|name)\s*=\s*['\"]([^'\"]+)['\"][^>]*>", re.IGNORECASE
)


@dataclass(frozen=True)
class Link:
    target: str
    line: int


@dataclass(frozen=True)
class Issue:
    path: Path
    line: int
    message: str


@dataclass(frozen=True)
class Report:
    documents: int
    local_links: int
    issues: tuple[Issue, ...]


def _blank(value: str) -> str:
    return "".join("\n" if character == "\n" else " " for character in value)


def _without_blocks(text: str) -> str:
    """Mask fenced/indented code and comments while retaining line numbers."""
    result = []
    fence = ""
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence:
            result.append(_blank(line))
            if re.fullmatch(
                rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*", line
            ):
                fence = ""
        elif marker:
            fence = marker[1]
            result.append(_blank(line))
        elif line.startswith(("    ", "\t")):
            result.append(_blank(line))
        else:
            result.append(line)
    return re.sub(
        r"<!--.*?(?:-->|\Z)",
        lambda match: _blank(match[0]),
        "".join(result),
        flags=re.DOTALL,
    )


def _reference(label: str) -> str:
    return " ".join(label.split()).casefold()


def _inline_target(text: str, position: int) -> str | None:
    """Read an inline destination, including balanced parentheses and titles."""
    position += 1  # Opening parenthesis.
    while position < len(text) and text[position].isspace():
        position += 1
    value = []
    if position < len(text) and text[position] == "<":
        end = text.find(">", position + 1)
        if end < 0:
            return None
        value.append(text[position + 1 : end])
        position = end + 1
    else:
        depth = 0
        while position < len(text):
            character = text[position]
            if character == "\\" and position + 1 < len(text):
                position += 1
                value.append(text[position])
            elif character == "(":
                depth += 1
                value.append(character)
            elif character == ")":
                if depth == 0:
                    break
                depth -= 1
                value.append(character)
            elif character.isspace() and depth == 0:
                break
            else:
                value.append(character)
            position += 1
    while position < len(text) and text[position].isspace():
        position += 1
    if position < len(text) and text[position] in "\"'(":
        delimiter = ")" if text[position] == "(" else text[position]
        position = text.find(delimiter, position + 1)
        if position < 0:
            return None
        position += 1
        while position < len(text) and text[position].isspace():
            position += 1
    if position < len(text) and text[position] == ")":
        return "".join(value)
    return None


def links(text: str) -> list[Link]:
    visible = _without_blocks(text)
    definitions = {
        _reference(match[1]): match[2].strip("<>")
        for match in _DEFINITION.finditer(visible)
        if not match[1].startswith("^")
    }
    visible = _DEFINITION.sub(lambda match: _blank(match[0]), visible)
    visible = _CODE_SPAN.sub(lambda match: _blank(match[0]), visible)
    result = []
    consumed_until = 0
    for match in _LABEL.finditer(visible):
        if match.start() < consumed_until:
            continue
        if match[1].startswith("^"):
            continue
        position = match.end()
        target = None
        if visible[position : position + 1] == "(":
            target = _inline_target(visible, position)
        elif visible[position : position + 1] == "[":
            end = visible.find("]", position + 1)
            if end >= 0:
                label = visible[position + 1 : end] or match[1]
                target = definitions.get(_reference(label))
                consumed_until = end + 1
        else:
            target = definitions.get(_reference(match[1]))
        if target is not None:
            result.append(
                Link(html.unescape(target), visible.count("\n", 0, match.start()) + 1)
            )
    return result


def _heading_slug(title: str) -> str:
    # Preserve literal code while removing heading formatting.
    code = []

    def save_code(match: re.Match[str]) -> str:
        code.append(match[2])
        return f"CODETOKEN{len(code) - 1}END"

    title = _CODE_SPAN.sub(save_code, title)
    title = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", title)
    title = re.sub(r"<[^>]*>", "", title)
    for _ in range(3):
        title = re.sub(r"(\*{1,3}|_{1,3}|~~)(?=\S)(.+?)(?<=\S)\1", r"\2", title)
    for index, value in enumerate(code):
        title = title.replace(f"CODETOKEN{index}END", value)
    title = html.unescape(title).strip().lower()
    return "".join(
        character
        for character in title
        if character in " _-" or unicodedata.category(character)[0] in "LMN"
    ).replace(" ", "-")


def anchors(text: str) -> set[str]:
    visible = _without_blocks(text)
    used: set[str] = set()
    result: set[str] = set()
    lines = visible.splitlines()
    for index, line in enumerate(lines):
        heading = re.match(r"^ {0,3}#{1,6}(?:[ \t]+(.*)|$)", line)
        title = None
        if heading:
            title = re.sub(r"[ \t]+#+[ \t]*$", "", heading[1] or "")
        elif index and re.fullmatch(r" {0,3}(?:=+|-+)[ \t]*", line):
            previous = lines[index - 1].strip()
            if previous and not re.match(r"[#>*+-]|\d+\.", previous):
                title = previous
        if title is not None:
            base = _heading_slug(title)
            slug = base
            suffix = 0
            while slug in used:
                suffix += 1
                slug = f"{base}-{suffix}"
            used.add(slug)
            result.add(slug)
    # Custom anchors do not affect generated heading suffixes.
    visible = _CODE_SPAN.sub(lambda match: _blank(match[0]), visible)
    result.update(html.unescape(match[1]) for match in _CUSTOM_ANCHOR.finditer(visible))
    return result


def check_documents(root: Path, documents: list[Path]) -> Report:
    root = root.resolve()
    issues = []
    local_count = 0
    contents: dict[Path, str] = {}

    def read(path: Path) -> str:
        if path not in contents:
            contents[path] = path.read_text(encoding="utf-8")
        return contents[path]

    anchor_cache: dict[Path, set[str]] = {}
    for path in sorted(set(documents)):
        path = path.resolve()
        try:
            text = read(path)
        except (OSError, UnicodeError) as error:
            issues.append(Issue(path, 1, f"cannot read document: {error}"))
            continue
        for link in links(text):
            try:
                url = urlsplit(link.target)
                if url.scheme or url.netloc:
                    continue
                local_count += 1
                relative = unquote(url.path)
                target = (
                    (root / relative.lstrip("/"))
                    if relative.startswith("/")
                    else path.parent / relative
                    if relative
                    else path
                )
                target = target.resolve()
                if not target.is_relative_to(root):
                    message = f"target escapes repository: {link.target}"
                elif not target.exists():
                    message = f"missing target: {link.target}"
                elif url.fragment and target.suffix.lower() == ".md":
                    if target not in anchor_cache:
                        anchor_cache[target] = anchors(read(target))
                    if unquote(url.fragment) in anchor_cache[target]:
                        continue
                    message = f"missing anchor: {link.target}"
                else:
                    continue
            except (OSError, UnicodeError, ValueError) as error:
                message = f"cannot check {link.target!r}: {error}"
            issues.append(Issue(path, link.line, message))
    return Report(len(set(documents)), local_count, tuple(issues))


def markdown_files(root: Path) -> list[Path]:
    """Include tracked and new unignored docs, excluding working-tree deletions."""
    root = root.resolve()
    checkout = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    if Path(checkout.stdout.strip()).resolve() != root:
        raise ValueError(
            f"--root must be the Git checkout root: {checkout.stdout.strip()}"
        )
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        capture_output=True,
        check=True,
    )
    names = result.stdout.decode("utf-8").split("\0")
    return sorted(
        {
            root / name
            for name in names
            if name.lower().endswith(".md") and (root / name).is_file()
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Git checkout root (defaults to this checkout).",
    )
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    try:
        report = check_documents(root, markdown_files(root))
    except (OSError, UnicodeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Cannot discover documentation: {error}")
        return 2
    for issue in report.issues:
        print(
            f"{issue.path.relative_to(root).as_posix()}:{issue.line}: {issue.message}"
        )
    print(
        f"Checked {report.local_links} local links in {report.documents} Markdown files: {len(report.issues)} errors. External URLs are skipped."
    )
    return 1 if report.issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

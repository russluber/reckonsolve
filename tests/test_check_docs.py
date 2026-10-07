"""Documentation checks catch moves and heading changes on disposable files."""

import runpy
import subprocess
import sys
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parents[1] / "tools" / "check_docs.py"
_CHECKER = runpy.run_path(str(_TOOL))


def _write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_relative_root_encoded_image_and_reference_links(tmp_path) -> None:
    guide = _write(
        tmp_path,
        "docs/guides/user.md",
        "# User guide\n"
        "[Rules](../rules.md#copy-user_guide--caf%C3%A9)\n"
        "[Root](/README.md#overview)\n"
        "[Multiline\nlabel](../rules.md#details)\n"
        '[Space](<../a file.md> "A title")\n'
        "[Parentheses](../a(b(c)).md)\n"
        "![Example](../diagram.svg)\n"
        "[Reference][rules] [rules][] [rules]\n"
        "[rules]: ../rules.md#details\n"
        "[Remote](https://example.com/unknown#unverified)\n",
    )
    _write(tmp_path, "README.md", "# Overview\n")
    _write(
        tmp_path,
        "docs/rules.md",
        "# **Copy** `user_guide` &amp; Caf\u00e9!\n\nDetails\n---\n",
    )
    _write(tmp_path, "docs/a file.md", "# Space\n")
    _write(tmp_path, "docs/a(b(c)).md", "# Parentheses\n")
    _write(tmp_path, "docs/diagram.svg", "<svg/>\n")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    report = _CHECKER["check_documents"](tmp_path, [guide])

    assert report.local_links == 9
    assert report.issues == ()
    assert before == {
        path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()
    }


def test_renamed_file_and_heading_report_correct_source_lines(tmp_path) -> None:
    source = _write(
        tmp_path,
        "README.md",
        "# Start\n[Moved guide](docs/old.md)\n[Renamed section](docs/guide.md#old-title)\n",
    )
    _write(tmp_path, "docs/guide.md", "# New title\n")

    report = _CHECKER["check_documents"](tmp_path, [source])

    assert [(issue.line, issue.message) for issue in report.issues] == [
        (2, "missing target: docs/old.md"),
        (3, "missing anchor: docs/guide.md#old-title"),
    ]


def test_duplicate_heading_collisions_and_custom_anchors(tmp_path) -> None:
    source = _write(
        tmp_path,
        "README.md",
        "# Repeat\n# Repeat-1\n# Repeat\n# Repeat\n"
        "<a name='Repeat'></a>\n<a id=\"custom\"></a>\n"
        "[First](#repeat) [Literal](#repeat-1) [Second](#repeat-2) "
        "[Third](#repeat-3) [Named](#Repeat) [Custom](#custom)\n",
    )
    assert _CHECKER["check_documents"](tmp_path, [source]).issues == ()


def test_code_and_comments_do_not_create_links_or_heading_anchors(tmp_path) -> None:
    source = _write(
        tmp_path,
        "README.md",
        "# Real\n"
        "````markdown\n# Fake\n[Example](missing.md)\n```\n[Still code](missing.md)\n````\n"
        "~~~\n# Also fake\n[Example](missing.md)\n~~~\n"
        "    [Indented code](missing.md)\n"
        "`[Inline](missing.md)`\n"
        "<!--\n# Hidden\n[Comment](missing.md)\n-->\n"
        "[Real](#real)\n[Wrong](#fake)\n",
    )
    report = _CHECKER["check_documents"](tmp_path, [source])
    assert report.local_links == 2
    assert [issue.message for issue in report.issues] == ["missing anchor: #fake"]


def test_target_cannot_escape_repository(tmp_path) -> None:
    source = _write(tmp_path, "README.md", "[Outside](../elsewhere.md)\n")
    report = _CHECKER["check_documents"](tmp_path, [source])
    assert report.issues[0].message == "target escapes repository: ../elsewhere.md"


def test_unreadable_document_is_a_reported_failure(tmp_path) -> None:
    report = _CHECKER["check_documents"](tmp_path, [tmp_path / "deleted.md"])
    assert len(report.issues) == 1
    assert report.issues[0].message.startswith("cannot read document:")


def test_discovery_includes_new_and_tracked_docs_but_excludes_ignored_and_deleted(
    tmp_path,
) -> None:
    subprocess.run(
        ["git", "init", "-q", str(tmp_path)], check=True, capture_output=True
    )
    _write(tmp_path, ".gitignore", "ignored/\n")
    tracked = _write(tmp_path, "ignored/tracked.md", "# Tracked\n")
    deleted = _write(tmp_path, "deleted.md", "# Deleted\n")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "-f", "ignored/tracked.md", "deleted.md"],
        check=True,
        capture_output=True,
    )
    deleted.unlink()
    new = _write(tmp_path, "docs/new.md", "# New\n")
    _write(tmp_path, "ignored/generated.md", "[Fake](missing.md)\n")
    assert _CHECKER["markdown_files"](tmp_path) == sorted([new, tracked])


@pytest.mark.parametrize("broken", [False, True])
def test_cli_exit_status_and_diagnostics_from_another_working_directory(
    tmp_path, broken
) -> None:
    root = tmp_path / "checkout"
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    _write(
        root,
        "README.md",
        "# Start\n" + ("[Gone](missing.md)\n" if broken else "[Start](#start)\n"),
    )
    result = subprocess.run(
        [sys.executable, str(_TOOL), "--root", str(root)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == int(broken)
    assert "Checked 1 local links in 1 Markdown files" in result.stdout
    assert ("README.md:2: missing target: missing.md" in result.stdout) == broken


def test_cli_discovery_failure_has_distinct_status(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(_TOOL), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Cannot discover documentation:" in result.stdout

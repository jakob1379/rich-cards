from __future__ import annotations

import os
import subprocess  # nosec B404 - runs fixed local commands for docs generation.
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SOURCE = ROOT / "src"


def main() -> None:
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(ROOT / ".uv-cache"))
    env["PYTHONPATH"] = _pythonpath(env)

    cli_docs = _run(
        [
            "typer",
            "--app",
            "app",
            "rich_card.cli",
            "utils",
            "docs",
            "--name",
            "rich-card",
        ],
        env,
    )
    _write_card_svg()
    README.write_text(_readme(_demote_heading(cli_docs)), encoding="utf-8")


def _pythonpath(env: dict[str, str]) -> str:
    existing = env.get("PYTHONPATH")
    if existing:
        return f"{SOURCE}{os.pathsep}{existing}"
    return str(SOURCE)


def _write_card_svg() -> None:
    sys.path.insert(0, str(SOURCE))
    from rich_card.cli import app

    app(args=["pyproject.toml"], prog_name="rich-card")


def _run(command: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )  # nosec B603 - command is a fixed internal list, not user input.
    if result.returncode == 0:
        return result.stdout

    sys.stderr.write(result.stdout)
    sys.stderr.write(result.stderr)
    raise SystemExit(result.returncode)


def _demote_heading(markdown: str) -> str:
    lines = markdown.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines[0] = "### " + lines[0][2:]
    return "\n".join(lines).strip()


def _readme(cli_docs: str) -> str:
    return f"""rich-card
=========

Render syntax-highlighted code, terminal output, and images as polished SVG
terminal cards on gradient backgrounds. The CLI uses Typer for commands and an
in-process Pygments style based on bat's Monokai Extended colors.

![Rendered rich-card example](card.svg)

## Quick Start

Render a source file or inline snippet:

```bash
rich-card pyproject.toml
rich-card --content 'print(\"hi\")' --lexer python -o hello.svg
```

Piped terminal output is read from stdin. ANSI colors are preserved, and eza
icons render when a Nerd Font such as Symbols Nerd Font Mono is installed:

```bash
eza --tree --icons=always --git-ignore --colour=always src/ | rich-card --title tree -o tree.svg
```

Images can be framed in the same card style:

```bash
rich-card --image screenshot.png --title \"Build result\" --inner-padding 24 -o screenshot-card.svg
```

Cards auto-size to their content by default. Pass `--width` when you want a
fixed canvas width. Use `--background-padding` for the outer gradient margin
and `--inner-padding` for the padding inside the terminal card:

```bash
rich-card --content 'print(\"hi\")' --width 1080 --background-padding 80 --inner-padding 32 -o fixed-card.svg
```

## Generated Assets

`card.svg` and this README are generated together:

```bash
uv run python scripts/update_generated_docs.py
```

The Nix development shell installs a pre-commit hook that runs the same command
before each commit, so the preview and CLI reference stay in sync with the code.

## CLI Reference

{cli_docs}

"""


if __name__ == "__main__":
    main()

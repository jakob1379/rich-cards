from __future__ import annotations

import os
import subprocess  # nosec B404 - runs fixed local commands for docs generation.
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SOURCE = ROOT / "src"
BEGIN_CLI_REFERENCE = "<!-- BEGIN CLI REFERENCE -->"
END_CLI_REFERENCE = "<!-- END CLI REFERENCE -->"


def main() -> None:
    env = os.environ.copy()
    env.setdefault("UV_CACHE_DIR", str(ROOT / ".uv-cache"))
    env["XDG_CONFIG_HOME"] = str(ROOT / ".generated-config")
    env["PYTHONPATH"] = _pythonpath(env)

    cli_docs = _run(
        [
            sys.executable,
            "-m",
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
    _update_readme(_demote_heading(cli_docs))


def _pythonpath(env: dict[str, str]) -> str:
    existing = env.get("PYTHONPATH")
    if existing:
        return f"{SOURCE}{os.pathsep}{existing}"
    return str(SOURCE)


def _write_card_svg() -> None:
    sys.path.insert(0, str(SOURCE))
    from rich_card.cli import app

    old_xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    os.environ["XDG_CONFIG_HOME"] = str(ROOT / ".generated-config")
    try:
        app(args=["pyproject.toml"], prog_name="rich-card", standalone_mode=False)
    finally:
        if old_xdg_config_home is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = old_xdg_config_home


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


def _update_readme(cli_docs: str) -> None:
    readme = README.read_text(encoding="utf-8")
    begin_index = readme.find(BEGIN_CLI_REFERENCE)
    end_index = readme.find(END_CLI_REFERENCE)
    if begin_index == -1 or end_index == -1 or begin_index > end_index:
        raise SystemExit("Expected one ordered CLI reference marker pair in README.md.")
    if readme.find(BEGIN_CLI_REFERENCE, begin_index + 1) != -1:
        raise SystemExit("Expected only one begin CLI reference marker in README.md.")
    if readme.find(END_CLI_REFERENCE, end_index + 1) != -1:
        raise SystemExit("Expected only one end CLI reference marker in README.md.")

    prefix = readme[: begin_index + len(BEGIN_CLI_REFERENCE)].rstrip()
    suffix = readme[end_index:].lstrip()
    README.write_text(f"{prefix}\n\n{cli_docs}\n\n{suffix}", encoding="utf-8")


if __name__ == "__main__":
    main()

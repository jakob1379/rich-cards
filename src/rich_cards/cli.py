from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Literal

import typer

from rich_cards.svg import (
    CardOptions,
    UnknownStyleError,
    list_bat_themes,
    render_code_card_svg,
)

Background = Literal["aurora", "ember", "lagoon", "mono", "moss"]

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=False,
)


def _read_source(source: Path | None, content: str | None) -> tuple[str, str | None]:
    if content is not None:
        return content, None

    if source is not None:
        return source.read_text(encoding="utf-8"), source.name

    if not sys.stdin.isatty():
        return sys.stdin.read(), None

    raise typer.BadParameter("Provide a SOURCE path, --content, or piped stdin.")


def _theme_callback(value: str) -> str:
    try:
        themes = set(list_bat_themes())
    except UnknownStyleError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if value not in themes:
        raise typer.BadParameter(f"Unknown bat theme '{value}'. Run `rich-cards --list-themes`.")
    return value


@app.command()
def render(
    source: Annotated[
        Path | None,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Optional source file. Omit to read from stdin.",
        ),
    ] = None,
    content: Annotated[
        str | None,
        typer.Option("--content", "-c", help="Inline code content. Takes precedence over SOURCE."),
    ] = None,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            file_okay=True,
            dir_okay=False,
            writable=True,
            help="SVG file to write.",
        ),
    ] = Path("card.svg"),
    lexer: Annotated[
        str | None,
        typer.Option(
            "--lexer",
            "-l",
            help="bat language name or extension. Defaults to source filename inference, or python for stdin.",
        ),
    ] = None,
    theme: Annotated[
        str,
        typer.Option(
            "--theme",
            callback=_theme_callback,
            help="bat theme name. See `rich-cards --list-themes`.",
        ),
    ] = "TwoDark",
    title: Annotated[
        str | None,
        typer.Option("--title", help="Optional card title shown in the card chrome."),
    ] = None,
    caption: Annotated[
        str | None,
        typer.Option("--caption", help="Optional small caption below the code block."),
    ] = None,
    background: Annotated[
        Background,
        typer.Option("--background", help="Gradient preset."),
    ] = "aurora",
    width: Annotated[
        int,
        typer.Option("--width", min=520, max=2400, help="SVG canvas width in pixels."),
    ] = 1080,
    padding: Annotated[
        int,
        typer.Option("--padding", min=24, max=240, help="Outer canvas padding in pixels."),
    ] = 72,
    radius: Annotated[
        int,
        typer.Option("--radius", min=4, max=80, help="Rounded card corner radius in pixels."),
    ] = 30,
    line_numbers: Annotated[
        bool,
        typer.Option("--line-numbers/--no-line-numbers", help="Show line numbers."),
    ] = False,
    word_wrap: Annotated[
        bool,
        typer.Option("--word-wrap/--no-word-wrap", help="Wrap long lines inside the card."),
    ] = False,
    tab_size: Annotated[
        int,
        typer.Option("--tab-size", min=1, max=12, help="Tab expansion width."),
    ] = 4,
    list_themes: Annotated[
        bool,
        typer.Option("--list-themes", help="List bat syntax themes and exit."),
    ] = False,
) -> None:
    if list_themes:
        for theme_name in list_bat_themes():
            typer.echo(theme_name)
        return

    code, source_name = _read_source(source, content)
    resolved_title = title if title is not None else source_name

    try:
        svg = render_code_card_svg(
            code,
            CardOptions(
                lexer=lexer,
                theme=theme,
                file_name=source_name,
                title=resolved_title,
                caption=caption,
                background=background,
                width=width,
                padding=padding,
                radius=radius,
                line_numbers=line_numbers,
                word_wrap=word_wrap,
                tab_size=tab_size,
            ),
        )
    except UnknownStyleError as exc:
        raise typer.BadParameter(str(exc)) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    typer.echo(str(output))

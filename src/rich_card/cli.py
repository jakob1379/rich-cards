from __future__ import annotations

from enum import Enum
import sys
from pathlib import Path
from typing import Annotated

import typer
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_all_styles, get_style_by_name
from pygments.util import ClassNotFound

from rich_card.config import (
    LOGO_PLACEMENTS,
    ConfigError,
    load_config,
    renderer_defaults,
)
from rich_card.svg import (
    BACKGROUND_PRESETS,
    CardOptions,
    UnknownStyleError,
    UnsupportedImageError,
    load_logo_image,
    render_code_card_svg,
    render_image_card_svg,
)

BackgroundPreset = Enum(
    "BackgroundPreset",
    {name.replace("-", "_"): name for name in BACKGROUND_PRESETS},
    type=str,
)
LogoPlacement = Enum(
    "LogoPlacement",
    {name.replace("-", "_"): name for name in LOGO_PLACEMENTS},
    type=str,
)

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


def _read_piped_stdin() -> str | None:
    if sys.stdin.isatty():
        return None
    return sys.stdin.read()


def _validate_image_mode(source: Path | None, content: str | None) -> None:
    if source is not None:
        raise typer.BadParameter("--image cannot be used with a SOURCE path.")
    if content is not None:
        raise typer.BadParameter("--image cannot be used with --content.")
    piped_stdin = _read_piped_stdin()
    if piped_stdin:
        raise typer.BadParameter("--image cannot be used with piped stdin text.")


def _theme_callback(value: str) -> str:
    if value == "monokai-extended":
        return value
    try:
        get_style_by_name(value)
    except ClassNotFound as exc:
        raise typer.BadParameter(
            f"Unknown Pygments style '{value}'. Run `rich-card --list-themes`."
        ) from exc
    return value


def _lexer_callback(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        get_lexer_by_name(value)
    except ClassNotFound as exc:
        raise typer.BadParameter(f"Unknown Pygments lexer '{value}'.") from exc
    return value


def _uses_default(ctx: typer.Context, name: str) -> bool:
    source = ctx.get_parameter_source(name)
    return source is not None and source.name == "DEFAULT"


def _configured_value[T](
    ctx: typer.Context, name: str, current: T, configured: T | None
) -> T:
    if configured is not None and _uses_default(ctx, name):
        return configured
    return current


def _background_value(
    ctx: typer.Context, current: BackgroundPreset, configured: str | None
) -> str:
    if configured is None or not _uses_default(ctx, "background"):
        return current.value
    if configured not in BACKGROUND_PRESETS:
        known = ", ".join(sorted(BACKGROUND_PRESETS))
        raise typer.BadParameter(
            f"Unknown background preset '{configured}' in config. Use one of: {known}."
        )
    return configured


def _configured_path(
    ctx: typer.Context, name: str, current: Path | None, configured: str | None
) -> Path | None:
    if configured is not None and _uses_default(ctx, name):
        return Path(configured)
    return current


def _logo_placement_value(
    ctx: typer.Context, current: LogoPlacement, configured: str | None
) -> str:
    if configured is None or not _uses_default(ctx, "logo_placement"):
        return current.value
    if configured not in LOGO_PLACEMENTS:
        known = ", ".join(sorted(LOGO_PLACEMENTS))
        raise typer.BadParameter(
            f"Unknown logo placement '{configured}' in config. Use one of: {known}."
        )
    return configured


def _inner_padding_options(
    ctx: typer.Context,
    inner_padding: int | None,
    config_inner: tuple[int | None, int | None, int | None],
) -> dict[str, int]:
    if inner_padding is not None and not _uses_default(ctx, "inner_padding"):
        return {"inner_padding_x": inner_padding, "inner_padding_y": inner_padding}

    configured_uniform, configured_x, configured_y = config_inner
    inner_padding_x = configured_uniform if configured_uniform is not None else None
    inner_padding_y = configured_uniform if configured_uniform is not None else None
    if configured_x is not None:
        inner_padding_x = configured_x
    if configured_y is not None:
        inner_padding_y = configured_y

    options = {}
    if inner_padding_x is not None:
        options["inner_padding_x"] = inner_padding_x
    if inner_padding_y is not None:
        options["inner_padding_y"] = inner_padding_y
    return options


def _read_logo(logo: Path | None):
    if logo is None:
        return None
    try:
        return load_logo_image(logo.read_bytes(), logo.name)
    except OSError as exc:
        raise typer.BadParameter(f"Could not read logo image '{logo}': {exc}") from exc


@app.command()
def render(
    ctx: typer.Context,
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
        typer.Option(
            "--content", "-c", help="Inline code content. Takes precedence over SOURCE."
        ),
    ] = None,
    image: Annotated[
        Path | None,
        typer.Option(
            "--image",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Image file to render inside the card. Supports PNG, JPEG, and SVG.",
        ),
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
            help="Pygments lexer name. Defaults to source filename inference, or ANSI-aware plain text for stdin.",
        ),
    ] = None,
    theme: Annotated[
        str,
        typer.Option(
            "--theme",
            "-s",
            help="Pygments theme name. See `rich-card --list-themes`.",
        ),
    ] = "monokai-extended",
    title: Annotated[
        str | None,
        typer.Option(
            "--title", "-t", help="Optional card title shown in the card chrome."
        ),
    ] = None,
    logo: Annotated[
        Path | None,
        typer.Option(
            "--logo",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Logo image to place in the title bar, terminal background, or both. Supports PNG, JPEG, and SVG.",
        ),
    ] = None,
    logo_placement: Annotated[
        LogoPlacement,
        typer.Option(
            "--logo-placement",
            help="Where to render --logo.",
        ),
    ] = LogoPlacement.bar,
    background: Annotated[
        BackgroundPreset,
        typer.Option("--background", "-b", help="Gradient preset."),
    ] = BackgroundPreset.aurora,
    width: Annotated[
        int | None,
        typer.Option(
            "--width", "-w", min=520, max=2400, help="Fixed SVG canvas width in pixels."
        ),
    ] = None,
    padding: Annotated[
        int,
        typer.Option(
            "--padding",
            "--background-padding",
            "-p",
            min=24,
            max=240,
            help="Background padding outside the terminal card in pixels.",
        ),
    ] = 72,
    inner_padding: Annotated[
        int | None,
        typer.Option(
            "--inner-padding",
            "--terminal-padding",
            min=0,
            max=160,
            help="Padding inside the terminal card around the content or image.",
        ),
    ] = None,
    radius: Annotated[
        int,
        typer.Option(
            "--radius",
            "-r",
            min=4,
            max=80,
            help="Rounded card corner radius in pixels.",
        ),
    ] = 12,
    line_numbers: Annotated[
        bool,
        typer.Option(
            "--line-numbers/--no-line-numbers", "-n", help="Show line numbers."
        ),
    ] = False,
    word_wrap: Annotated[
        bool,
        typer.Option(
            "--word-wrap/--no-word-wrap", "-W", help="Wrap long lines inside the card."
        ),
    ] = False,
    tab_size: Annotated[
        int,
        typer.Option("--tab-size", "-T", min=1, max=12, help="Tab expansion width."),
    ] = 2,
    list_themes: Annotated[
        bool,
        typer.Option("--list-themes", help="List syntax themes and exit."),
    ] = False,
) -> None:
    if list_themes:
        for theme_name in ["monokai-extended", *sorted(get_all_styles())]:
            typer.echo(theme_name)
        return

    try:
        config = load_config()
        card_config = config.card
        output = (
            Path(config.output)
            if config.output is not None and _uses_default(ctx, "output")
            else output
        )
        lexer = _configured_value(ctx, "lexer", lexer, card_config.lexer)
        theme = _configured_value(ctx, "theme", theme, card_config.theme)
        title = _configured_value(ctx, "title", title, card_config.title)
        logo = _configured_path(ctx, "logo", logo, card_config.logo)
        logo_placement_value = _logo_placement_value(
            ctx, logo_placement, card_config.logo_placement
        )
        logo_content = _read_logo(logo)
        background_value = _background_value(ctx, background, card_config.background)
        width = _configured_value(ctx, "width", width, card_config.width)
        padding = _configured_value(ctx, "padding", padding, card_config.padding)
        radius = _configured_value(ctx, "radius", radius, card_config.radius)
        line_numbers = _configured_value(
            ctx, "line_numbers", line_numbers, card_config.line_numbers
        )
        word_wrap = _configured_value(
            ctx, "word_wrap", word_wrap, card_config.word_wrap
        )
        tab_size = _configured_value(ctx, "tab_size", tab_size, card_config.tab_size)
        renderer = renderer_defaults(config.renderer)
        inner_padding_options = _inner_padding_options(
            ctx,
            inner_padding,
            (
                card_config.inner_padding,
                card_config.inner_padding_x,
                card_config.inner_padding_y,
            ),
        )
        if image is not None:
            _validate_image_mode(source, content)
            svg = render_image_card_svg(
                image.read_bytes(),
                image.name,
                CardOptions(
                    title=title if title is not None else image.name,
                    background=background_value,
                    width=width,
                    padding=padding,
                    **inner_padding_options,
                    radius=radius,
                    logo=logo_content,
                    logo_placement=logo_placement_value,
                    renderer=renderer,
                ),
            )
        else:
            code, source_name = _read_source(source, content)
            resolved_title = title if title is not None else source_name
            validated_lexer = _lexer_callback(lexer)
            validated_theme = _theme_callback(theme)
            svg = render_code_card_svg(
                code,
                CardOptions(
                    lexer=validated_lexer,
                    theme=validated_theme,
                    file_name=source_name,
                    title=resolved_title,
                    background=background_value,
                    width=width,
                    padding=padding,
                    **inner_padding_options,
                    radius=radius,
                    line_numbers=line_numbers,
                    word_wrap=word_wrap,
                    tab_size=tab_size,
                    logo=logo_content,
                    logo_placement=logo_placement_value,
                    renderer=renderer,
                ),
            )
    except (ConfigError, UnknownStyleError, UnsupportedImageError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{svg}\n", encoding="utf-8")
    typer.echo(str(output))

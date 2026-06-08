from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re
import shutil
import subprocess
from textwrap import wrap

BACKGROUND_PRESETS: dict[str, tuple[str, str, str]] = {
    "aurora": ("#f7fbff", "#bdefff", "#48c7df"),
    "ember": ("#f6b05f", "#dc574d", "#231f20"),
    "lagoon": ("#35d4b4", "#3574d4", "#1f2440"),
    "moss": ("#b9d96d", "#4e9c75", "#17261f"),
    "mono": ("#f2f2ed", "#b9b8b0", "#4f5254"),
}

CARD_FILL = "#26282b"
CARD_STROKE = "#3b3e43"
MUTED_TEXT = "#8d9199"
DEFAULT_TEXT = "#f0f2f5"
ANSI_16 = {
    30: "#000000",
    31: "#800000",
    32: "#008000",
    33: "#808000",
    34: "#000080",
    35: "#800080",
    36: "#008080",
    37: "#c0c0c0",
    90: "#808080",
    91: "#ff0000",
    92: "#00ff00",
    93: "#ffff00",
    94: "#0000ff",
    95: "#ff00ff",
    96: "#00ffff",
    97: "#ffffff",
}
FONT_STACK = "'JetBrains Mono', 'Cascadia Code', 'SFMono-Regular', Menlo, Consolas, monospace"
CHAR_WIDTH = 9.4
LINE_HEIGHT = 21
FONT_SIZE = 15
INNER_PADDING_X = 34
INNER_PADDING_Y = 30
TITLE_BAR_HEIGHT = 50
CAPTION_GAP = 20
ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


class UnknownStyleError(ValueError):
    pass


@dataclass(frozen=True)
class CardOptions:
    lexer: str | None = None
    theme: str = "Monokai Extended"
    file_name: str | None = None
    title: str | None = None
    caption: str | None = None
    background: str = "aurora"
    width: int = 1080
    padding: int = 72
    radius: int = 12
    line_numbers: bool = False
    word_wrap: bool = False
    tab_size: int = 4


@dataclass(frozen=True)
class Fragment:
    text: str
    color: str
    bold: bool = False
    italic: bool = False


def render_code_card_svg(code: str, options: CardOptions) -> str:
    gradients = BACKGROUND_PRESETS.get(options.background)
    if gradients is None:
        known = ", ".join(sorted(BACKGROUND_PRESETS))
        raise UnknownStyleError(f"Unknown background preset '{options.background}'. Use one of: {known}.")

    raw_lines = _highlight_lines(code, options)
    card_width = options.width - (options.padding * 2)
    code_width = card_width - (INNER_PADDING_X * 2)
    max_columns = max(20, int(code_width / CHAR_WIDTH))
    lines = _prepare_lines(raw_lines, max_columns, options.line_numbers, options.word_wrap)

    code_height = max(1, len(lines)) * LINE_HEIGHT
    caption_height = LINE_HEIGHT + CAPTION_GAP if options.caption else 0
    card_height = TITLE_BAR_HEIGHT + INNER_PADDING_Y + code_height + caption_height + INNER_PADDING_Y
    height = card_height + (options.padding * 2)
    card_x = options.padding
    card_y = options.padding
    code_x = card_x + INNER_PADDING_X
    code_y = card_y + TITLE_BAR_HEIGHT + INNER_PADDING_Y + FONT_SIZE

    parts = [
        _svg_open(options.width, height),
        _defs(*gradients),
        f'<rect width="100%" height="100%" fill="url(#card-bg)"/>',
        f'<rect x="{card_x}" y="{card_y}" width="{card_width}" height="{card_height}" '
        f'rx="{options.radius}" fill="{CARD_FILL}" stroke="{CARD_STROKE}" stroke-width="3" '
        f'filter="url(#soft-shadow)"/>',
        _title_bar(card_x, card_y, card_width, options.title),
        _code_lines(lines, code_x, code_y),
    ]
    if options.caption:
        caption_y = code_y + code_height + CAPTION_GAP
        parts.append(
            f'<text x="{code_x}" y="{caption_y}" fill="{MUTED_TEXT}" '
            f'font-family="{FONT_STACK}" font-size="13">{escape(options.caption)}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def list_bat_themes() -> list[str]:
    bat = _bat_executable()
    result = subprocess.run(
        [bat, "--list-themes"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _highlight_lines(code: str, options: CardOptions) -> list[list[Fragment]]:
    if not code:
        return [[Fragment("", DEFAULT_TEXT)]]

    ansi = _run_bat(code, options)
    return _parse_ansi_fragments(ansi)


def _run_bat(code: str, options: CardOptions) -> str:
    bat = _bat_executable()
    command = [
        bat,
        "--paging=never",
        "--color=always",
        "--style=plain",
        "--theme",
        options.theme,
        "--tabs",
        str(options.tab_size),
    ]
    if options.lexer is not None:
        command.extend(["--language", options.lexer])
    elif options.file_name is not None:
        command.extend(["--file-name", options.file_name])
    else:
        command.extend(["--language", "python"])

    try:
        result = subprocess.run(
            command,
            input=code,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or "bat failed to highlight the source."
        raise UnknownStyleError(message) from exc
    return result.stdout


def _bat_executable() -> str:
    bat = shutil.which("bat") or shutil.which("batcat")
    if bat is None:
        raise UnknownStyleError("bat is required for syntax highlighting but was not found on PATH.")
    return bat


def _parse_ansi_fragments(text: str) -> list[list[Fragment]]:
    color = DEFAULT_TEXT
    bold = False
    italic = False
    lines: list[list[Fragment]] = [[]]
    cursor = 0
    for match in ANSI_RE.finditer(text):
        chunk = text[cursor:match.start()]
        _append_text(lines, chunk, Fragment("", color, bold, italic))
        color, bold, italic = _apply_sgr(match.group(1), color, bold, italic)
        cursor = match.end()
    _append_text(lines, text[cursor:], Fragment("", color, bold, italic))
    if lines and not lines[-1]:
        lines.pop()
    return lines or [[Fragment("", DEFAULT_TEXT)]]


def _append_text(lines: list[list[Fragment]], text: str, style: Fragment) -> None:
    chunks = text.split("\n")
    for index, chunk in enumerate(chunks):
        if index > 0:
            lines.append([])
        if chunk:
            lines[-1].append(Fragment(chunk, style.color, style.bold, style.italic))


def _apply_sgr(raw_codes: str, color: str, bold: bool, italic: bool) -> tuple[str, bool, bool]:
    codes = [int(code) for code in raw_codes.split(";") if code] or [0]
    index = 0
    while index < len(codes):
        code = codes[index]
        if code == 0:
            color = DEFAULT_TEXT
            bold = False
            italic = False
        elif code == 1:
            bold = True
        elif code == 3:
            italic = True
        elif code == 22:
            bold = False
        elif code == 23:
            italic = False
        elif code == 39:
            color = DEFAULT_TEXT
        elif code == 38 and index + 4 < len(codes) and codes[index + 1] == 2:
            red, green, blue = codes[index + 2 : index + 5]
            color = f"#{red:02x}{green:02x}{blue:02x}"
            index += 4
        elif code == 38 and index + 2 < len(codes) and codes[index + 1] == 5:
            color = _ansi_256(codes[index + 2])
            index += 2
        elif code in ANSI_16:
            color = ANSI_16[code]
        index += 1
    return color, bold, italic


def _ansi_256(value: int) -> str:
    if value < 16:
        return ANSI_16.get(value + 30 if value < 8 else value + 82, DEFAULT_TEXT)
    if value < 232:
        value -= 16
        red = value // 36
        green = (value % 36) // 6
        blue = value % 6
        levels = [0, 95, 135, 175, 215, 255]
        return f"#{levels[red]:02x}{levels[green]:02x}{levels[blue]:02x}"
    gray = 8 + ((value - 232) * 10)
    return f"#{gray:02x}{gray:02x}{gray:02x}"


def _prepare_lines(
    raw_lines: list[list[Fragment]],
    max_columns: int,
    line_numbers: bool,
    word_wrap: bool,
) -> list[list[Fragment]]:
    numbered_width = len(str(len(raw_lines))) if line_numbers else 0
    content_columns = max(12, max_columns - (numbered_width + 3 if line_numbers else 0))
    output: list[list[Fragment]] = []

    for index, fragments in enumerate(raw_lines, start=1):
        wrapped = _wrap_fragments(fragments, content_columns) if word_wrap else [fragments]
        for wrap_index, line in enumerate(wrapped):
            if line_numbers:
                label = str(index).rjust(numbered_width) if wrap_index == 0 else " " * numbered_width
                output.append([Fragment(f"{label} │ ", MUTED_TEXT), *line])
            else:
                output.append(line)
    return output


def _wrap_fragments(fragments: list[Fragment], width: int) -> list[list[Fragment]]:
    text = "".join(fragment.text for fragment in fragments)
    if len(text) <= width:
        return [fragments]

    wrapped_text = wrap(text, width=width, replace_whitespace=False, drop_whitespace=False) or [""]
    wrapped: list[list[Fragment]] = []
    cursor = 0
    flat = [(fragment, start, start + len(fragment.text)) for start, fragment in _fragment_offsets(fragments)]
    for line_text in wrapped_text:
        line_end = cursor + len(line_text)
        line: list[Fragment] = []
        for fragment, start, end in flat:
            overlap_start = max(start, cursor)
            overlap_end = min(end, line_end)
            if overlap_start < overlap_end:
                text_start = overlap_start - start
                text_end = overlap_end - start
                line.append(
                    Fragment(
                        fragment.text[text_start:text_end],
                        fragment.color,
                        bold=fragment.bold,
                        italic=fragment.italic,
                    )
                )
        wrapped.append(line)
        cursor = line_end
    return wrapped


def _fragment_offsets(fragments: list[Fragment]):
    cursor = 0
    for fragment in fragments:
        yield cursor, fragment
        cursor += len(fragment.text)


def _svg_open(width: int, height: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Rendered code card">'
    )


def _defs(start: str, middle: str, end: str) -> str:
    return f"""<defs>
  <linearGradient id="card-bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{start}"/>
    <stop offset="52%" stop-color="{middle}"/>
    <stop offset="100%" stop-color="{end}"/>
  </linearGradient>
  <filter id="soft-shadow" x="-20%" y="-20%" width="140%" height="150%">
    <feDropShadow dx="0" dy="20" stdDeviation="22" flood-color="#101114" flood-opacity="0.38"/>
  </filter>
</defs>"""


def _title_bar(x: int, y: int, width: int, title: str | None) -> str:
    dots = [
        f'<circle cx="{x + 30}" cy="{y + 25}" r="6" fill="#ff5f57"/>',
        f'<circle cx="{x + 50}" cy="{y + 25}" r="6" fill="#ffbd2e"/>',
        f'<circle cx="{x + 70}" cy="{y + 25}" r="6" fill="#28c840"/>',
    ]
    label = ""
    if title:
        label = (
            f'<text x="{x + width / 2:.1f}" y="{y + 31}" fill="{MUTED_TEXT}" '
            f'font-family="{FONT_STACK}" font-size="13" text-anchor="middle">{escape(title)}</text>'
        )
    rule = f'<line x1="{x}" y1="{y + TITLE_BAR_HEIGHT}" x2="{x + width}" y2="{y + TITLE_BAR_HEIGHT}" stroke="#34373c"/>'
    return "\n".join([*dots, label, rule])


def _code_lines(lines: list[list[Fragment]], x: int, y: int) -> str:
    output: list[str] = []
    for index, line in enumerate(lines):
        line_y = y + (index * LINE_HEIGHT)
        spans: list[str] = []
        for fragment in line:
            if not fragment.text:
                continue
            attrs = [f'fill="{fragment.color}"']
            if fragment.bold:
                attrs.append('font-weight="700"')
            if fragment.italic:
                attrs.append('font-style="italic"')
            spans.append(f'<tspan {" ".join(attrs)}>{escape(fragment.text)}</tspan>')
        output.append(
            f'<text x="{x}" y="{line_y}" font-family="{FONT_STACK}" '
            f'font-size="{FONT_SIZE}" xml:space="preserve">'
            f'{"".join(spans)}'
            "</text>"
        )
    return "\n".join(output)

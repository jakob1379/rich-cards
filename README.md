rich-cards
==========

Render syntax-highlighted code as a polished terminal card on a gradient SVG
background. The CLI uses Typer for commands and `bat` for syntax color.

```bash
printf 'def hello():\n    return "world"\n' \
  | rich-cards --lexer python --theme TwoDark --title hello.py -o card.svg
```

Inline content works well for one-off cards:

```bash
rich-cards \
  --content $'TAX_RATES = {"CA": 0.0825, "NY": 0.05}\n\nprint(TAX_RATES)' \
  --lexer python \
  --theme TwoDark \
  --caption "clean code card" \
  --background aurora \
  --line-numbers \
  -o tax-card.svg
```

Useful commands:

```bash
rich-cards --list-themes
rich-cards src/example.py --theme Dracula -o example.svg
nix develop -c uv run rich-cards --content 'print("hi")' -o card.svg
```

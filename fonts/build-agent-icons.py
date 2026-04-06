#!/usr/bin/env fontforge -lang=py -script

import os
import sys

import fontforge
import psMat


CODEPOINTS = {
    "openai": 0xE00B,
    "anthropic": 0xE00C,
    "opencode": 0xE00D,
    "poolside": 0xE00E,
}


def usage() -> None:
    print("usage: build-agent-icons.py <source-font> <target-font> <assets-dir>")
    sys.exit(2)


def set_font_names(font, target_path: str) -> None:
    stem = os.path.splitext(os.path.basename(target_path))[0]
    family = "Hack Nerd Font Mono Bsrc"

    if "Bold Italic" in stem:
        subfamily = "Bold Italic"
        font.fontname = "HackNerdFontMonoBsrc-BoldItalic"
        font.fullname = f"{family} Bold Italic"
    elif "Bold" in stem:
        subfamily = "Bold"
        font.fontname = "HackNerdFontMonoBsrc-Bold"
        font.fullname = f"{family} Bold"
    elif "Italic" in stem:
        subfamily = "Italic"
        font.fontname = "HackNerdFontMonoBsrc-Italic"
        font.fullname = f"{family} Italic"
    else:
        subfamily = "Regular"
        font.fontname = "HackNerdFontMonoBsrc-Regular"
        font.fullname = f"{family} Regular"

    font.familyname = family
    font.appendSFNTName("English (US)", "Preferred Family", family)
    font.appendSFNTName("English (US)", "Preferred Styles", subfamily)
    font.appendSFNTName("English (US)", "Compatible Full", font.fullname)


def normalize_glyph(font, glyph) -> None:
    em = font.ascent + font.descent
    advance = font[0x20].width or font.em
    target_w = advance * 0.82
    target_h = em * 0.82

    glyph.removeOverlap()
    glyph.correctDirection()
    glyph.simplify(0.5)
    glyph.round()

    xmin, ymin, xmax, ymax = glyph.boundingBox()
    width = xmax - xmin
    height = ymax - ymin
    if width <= 0 or height <= 0:
        raise RuntimeError(f"empty glyph for U+{glyph.unicode:04X}")

    glyph.transform(psMat.translate(-(xmin + xmax) / 2.0, -(ymin + ymax) / 2.0))
    scale = min(target_w / width, target_h / height)
    glyph.transform(psMat.scale(scale))

    center_y = (font.ascent - font.descent) / 2.0
    glyph.transform(psMat.translate(advance / 2.0, center_y))
    glyph.width = advance
    glyph.removeOverlap()
    glyph.round()
    glyph.autoHint()


def add_svg(font, codepoint: int, svg_path: str, glyph_name: str) -> None:
    glyph = font.createChar(codepoint, glyph_name)
    glyph.clear()
    glyph.importOutlines(svg_path)
    normalize_glyph(font, glyph)


def main() -> None:
    if len(sys.argv) != 4:
        usage()

    source_font, target_font, assets_dir = sys.argv[1:]
    font = fontforge.open(source_font)
    set_font_names(font, target_font)

    for name, codepoint in CODEPOINTS.items():
        svg_path = os.path.join(assets_dir, f"{name}.svg")
        if not os.path.exists(svg_path):
            raise FileNotFoundError(svg_path)
        add_svg(font, codepoint, svg_path, f"bsrc_{name}")

    font.generate(target_font)
    font.close()


if __name__ == "__main__":
    main()

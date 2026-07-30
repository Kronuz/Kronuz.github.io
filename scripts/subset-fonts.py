#!/usr/bin/env python3
"""Build the web-font subsets and calculate their box-drawing CSS metrics.

Requires FontTools and Brotli:

    python -m pip install fonttools brotli

Usage:

    scripts/subset-fonts.py subset
    scripts/subset-fonts.py subset --source ~/Library/Fonts MesloLGLNerdFont
    scripts/subset-fonts.py metrics public/fonts/MesloLGLNerdFont-Regular.subset.woff2
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

BASE_FONT_PX = 14
FAMILIES = ("HackNerdFont", "MesloLGLNerdFont", "JetBrainsMonoNerdFont")
VARIANTS = ("Regular", "Bold")
COMMON_RANGES = "U+0020-007E,U+00A0-04FF,U+2000-2BFF,U+2E00-2E7F"
PRIVATE_USE_RANGE = "U+E000-F8FF"
VERTICAL_BOX = 0x2502
HORIZONTAL_BOX = 0x2500
REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class BoxMetrics:
    family: str
    units_per_em: int
    vertical_min: int
    vertical_max: int
    row_px: int
    left_overshoot: int
    right_overshoot: int
    letter_spacing: float


def calculate_metrics(font_path: Path) -> BoxMetrics:
    font = TTFont(font_path)
    units_per_em = font["head"].unitsPerEm
    cmap = font.getBestCmap()
    glyf = font["glyf"]
    hmtx = font["hmtx"]

    vertical = glyf[cmap[VERTICAL_BOX]]
    vertical_units = vertical.yMax - vertical.yMin
    vertical_px = vertical_units / units_per_em * BASE_FONT_PX

    horizontal_name = cmap[HORIZONTAL_BOX]
    horizontal = glyf[horizontal_name]
    advance = hmtx[horizontal_name][0]
    left_overshoot = max(0, -horizontal.xMin)
    right_overshoot = max(0, horizontal.xMax - advance)

    metrics = BoxMetrics(
        family=font["name"].getBestFamilyName(),
        units_per_em=units_per_em,
        vertical_min=vertical.yMin,
        vertical_max=vertical.yMax,
        row_px=math.ceil(vertical_px),
        left_overshoot=left_overshoot,
        right_overshoot=right_overshoot,
        letter_spacing=(left_overshoot + right_overshoot) / units_per_em,
    )
    font.close()
    return metrics


def render_css(metrics: BoxMetrics) -> str:
    line_height = metrics.row_px / BASE_FONT_PX
    return "\n".join(
        (
            (
                f"/* Calculated box-drawing metrics for {metrics.family} at "
                f"{BASE_FONT_PX}px:"
            ),
            (
                f"   row = ceil(({metrics.vertical_max} - {metrics.vertical_min}) / "
                f"{metrics.units_per_em} * {BASE_FONT_PX}px) = {metrics.row_px}px;"
            ),
            (
                f"   tracking = ({metrics.left_overshoot} + "
                f"{metrics.right_overshoot}) / {metrics.units_per_em}em = "
                f"{metrics.letter_spacing:.8f}em. */"
            ),
            f'--sl-font-mono: "{metrics.family}", ui-monospace, monospace;',
            f"--kz-code-font-size: {BASE_FONT_PX / 16:g}rem;",
            (
                f"--kz-code-line-height: {line_height:.10f}; "
                f"/* {metrics.row_px}px / {BASE_FONT_PX}px */"
            ),
            f"--kz-code-letter-spacing: {metrics.letter_spacing:.8f}em;",
        )
    )


def subset_font(source: Path, output: Path, unicodes: list[int]) -> None:
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "liga", "calt"]
    options.hinting = False
    options.desubroutinize = True
    options.no_subset_tables.append("PfEd")

    font = subset.load_font(source, options, lazy=False)
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(font)
    subset.save_font(font, output, options)
    font.close()


def build_subsets(source_dir: Path, output_dir: Path, families: list[str]) -> int:
    common = subset.parse_unicodes(COMMON_RANGES)
    regular = subset.parse_unicodes(f"{COMMON_RANGES},{PRIVATE_USE_RANGE}")
    output_dir.mkdir(parents=True, exist_ok=True)

    for family in families:
        for variant in VARIANTS:
            source = source_dir / f"{family}-{variant}.ttf"
            output = output_dir / f"{family}-{variant}.subset.woff2"
            if not source.is_file():
                print(f"missing source font: {source}", file=sys.stderr)
                return 1
            subset_font(source, output, regular if variant == "Regular" else common)
            print(f"wrote {output}")

        regular_output = output_dir / f"{family}-Regular.subset.woff2"
        print(render_css(calculate_metrics(regular_output)))
        print()

    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    subset_parser = commands.add_parser("subset", help="build web-font subsets")
    subset_parser.add_argument(
        "families",
        nargs="*",
        default=list(FAMILIES),
        help=f"font filename prefixes (default: {', '.join(FAMILIES)})",
    )
    subset_parser.add_argument(
        "--source",
        type=Path,
        default=Path(os.environ.get("SRC", Path.home() / "Library/Fonts")),
        help="directory containing <family>-Regular.ttf and <family>-Bold.ttf",
    )
    subset_parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "public/fonts",
        help="output directory for subset WOFF2 files",
    )

    metrics_parser = commands.add_parser(
        "metrics", help="print CSS metrics for one regular font"
    )
    metrics_parser.add_argument("font", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.command == "metrics":
        print(render_css(calculate_metrics(args.font)))
        return 0
    return build_subsets(args.source, args.output, args.families)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

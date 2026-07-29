#!/usr/bin/env python3
import math
import sys
from fontTools.ttLib import TTFont

if len(sys.argv) < 2:
  print(f"usage: {sys.argv[0]} <font>")
  sys.exit(164)

font_file = sys.argv[1]
font = TTFont(font_file)
upm = font['head'].unitsPerEm
os2 = font['OS/2']

# 1. Calculate Vertical Height & Line Height Ratio
# Total vertical span of the bounding boxes
total_units = os2.usWinAscent + os2.usWinDescent
px_exact = (total_units / upm) * 14
px_snapped = math.ceil(px_exact)
line_height = px_snapped / 14

# 2. Calculate Horizontal Overshoot (Letter Spacing)
# Look up glyph for horizontal box drawing bar '─' (U+2500)
h_spacing = 0.0
try:
    cmap = font.getBestCmap()
    glyph_name = cmap.get(0x2500)
    if glyph_name:
        glyf = font['glyf']
        h_advance = font['hmtx'][glyph_name][0]
        # Bounding box coordinates
        x_min = glyf[glyph_name].xMin
        x_max = glyf[glyph_name].xMax
        # Calculate total combined overshoot on both sides
        overshoot = (x_max - h_advance) + (0 - x_min)
        if overshoot > 0:
            h_spacing = overshoot / upm
except Exception:
    pass

name_table = font['name']
font_family = name_table.getBestFamilyName()
print(f"/* Calculated Web Metrics for {font_family} at 14px base */")
print(f"--sl-font-mono: \"{font_family}\", ui-monospace, monospace;")
print(f"--kz-code-font-size: 0.875rem;")
print(f"--kz-code-line-height: {line_height:.10f}; /* {px_exact:.6f}px -> {px_snapped}px snap */")
print(f"--kz-code-letter-spacing: {h_spacing:.8f}em;")
print()

#!/usr/bin/env bash
# Regenerate the code-font subsets in public/fonts/ from a local Hack Nerd Font.
#
# The full Hack Nerd Font ships thousands of icon glyphs; shipping it whole to
# every reader is wasteful. We subset it instead:
#
#   Regular  -> every classic Nerd Font set (Font Awesome, Octicons, Devicons,
#               Codicons, Powerline, Seti, Weather, Font Logos) via the whole BMP
#               Private Use Area, plus Latin and the common symbol blocks. Only
#               the ~7000-glyph Material Design plane (U+F0000+) is dropped, so
#               essentially any icon a post reaches for already renders.
#   Bold     -> a tight subset (Latin + symbols + the KronuZSH prompt glyphs),
#               because Nerd Font icons are never bold; only text like a branch
#               name is. Keeps the bold face small.
#
# Requires pyftsubset (fonttools) with brotli for woff2 output. The source .ttf
# is not vendored; point SRC at wherever Hack Nerd Font is installed.
#
# Usage:  scripts/subset-font.sh            # SRC defaults to ~/Library/Fonts
#         SRC=/path/to/fonts scripts/subset-font.sh
set -euo pipefail

SRC="${SRC:-$HOME/Library/Fonts}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/public/fonts"
mkdir -p "$OUT"

# Latin + all symbol/arrow/box/dingbat blocks, shared by both weights.
COMMON="U+0020-007E,U+00A0-04FF,U+2000-2BFF,U+2E00-2E7F"
# The whole BMP Private Use Area (all classic Nerd Font sets).
PUA_ALL="U+E000-F8FF"
# Just the KronuZSH prompt glyphs, for the tight bold face.
PUA_PROMPT="U+E0A0,U+E606,U+E7C5,U+E7CF,U+EB3A,U+F017,U+F021,U+F040,U+F071,U+F09B,U+F171,U+F179,U+F17A,U+F17C,U+F187,U+F296,U+F412,U+F417,U+F419,U+F457,U+F458,U+F459,U+F47F,U+F4B7,U+F51E"

sub() { # variant unicodes
	pyftsubset "$SRC/HackNerdFont-$1.ttf" \
		--output-file="$OUT/HackNerdFont-$1.subset.woff2" \
		--flavor=woff2 --with-zopfli \
		--unicodes="$2" \
		--layout-features='kern,liga,calt' --no-hinting --desubroutinize
}

sub Regular "$COMMON,$PUA_ALL"
sub Bold    "$COMMON,$PUA_PROMPT"

ls -la "$OUT"/HackNerdFont-*.subset.woff2

#!/usr/bin/env bash
# Regenerate the code-font subsets in public/fonts/ from a local Nerd Font.
#
# A full Nerd Font ships thousands of icon glyphs; shipping it whole to
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
# is not vendored; point SRC at wherever a Nerd Font is installed.
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
# Anything outside this and $COMMON (like the massive U+F0000+ Material block) is stripped!
PUA_ALL="U+E000-F8FF"

sub() { # variant unicodes
	pyftsubset "$SRC/$1-$2.ttf" \
		--output-file="$OUT/$1-$2.subset.woff2" \
		--flavor=woff2 --with-zopfli \
		--unicodes="$3" \
		--layout-features='kern,liga,calt' --no-hinting --desubroutinize \
		--no-subset-tables+=PfEd
}

for FONT in HackNerdFont MesloLGLNerdFont JetBrainsMonoNerdFont; do
	# Regular: Strips out the heavy Material Design plane automatically
	sub "$FONT" Regular "$COMMON,$PUA_ALL"
	# Bold: Strips out ALL icons completely
	sub "$FONT" Bold    "$COMMON"
	./font-metrics.py "$OUT"/$FONT-*.subset.woff2
done

#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: bash scripts/render_pdf.sh input.md output.pdf"
  exit 1
fi

INPUT="$1"
OUTPUT="$2"

pandoc "$INPUT" \
  -o "$OUTPUT" \
  --from markdown+tex_math_dollars+tex_math_single_backslash \
  --pdf-engine=xelatex \
  -V geometry:margin=0.75in \
  -V mainfont="DejaVu Sans" \
  -V monofont="DejaVu Sans Mono" \
  -V colorlinks=true \
  -V linkcolor=blue \
  -V urlcolor=blue \
  --highlight-style=tango

echo "Saved $OUTPUT"

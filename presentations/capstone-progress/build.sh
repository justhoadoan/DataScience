#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
mkdir -p build
if command -v latexmk >/dev/null 2>&1 && command -v xelatex >/dev/null 2>&1; then
  latexmk -xelatex -interaction=nonstopmode -halt-on-error -outdir=build progress-report.tex
elif command -v xelatex >/dev/null 2>&1; then
  xelatex -interaction=nonstopmode -halt-on-error -output-directory=build progress-report.tex
  xelatex -interaction=nonstopmode -halt-on-error -output-directory=build progress-report.tex
else
  printf '%s\n' 'Use XeLaTeX on Overleaf, or install XeLaTeX locally.' >&2
  exit 1
fi
cp build/progress-report.pdf progress-report.pdf
printf '%s\n' 'PDF: progress-report.pdf'

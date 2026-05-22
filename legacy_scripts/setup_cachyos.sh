#!/usr/bin/env bash
set -euo pipefail

sudo pacman -Syu
sudo pacman -S --needed python python-pip python-virtualenv pandoc texlive-binextra texlive-latexrecommended texlive-fontsrecommended ttf-dejavu nodejs npm poppler

python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

if [ -f package.json ]; then
  npm install
fi

echo "Done. Activate with: source .venv/bin/activate"

#!/usr/bin/env bash
# Instala o DevFlow da branch principal publicada no GitHub (Linux/macOS).
set -Eeuo pipefail
command -v git >/dev/null || { echo 'Git é necessário.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Python é necessário.' >&2; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' || { echo 'Python 3.10+ é necessário.' >&2; exit 1; }
if command -v pipx >/dev/null; then
  PIPX=(pipx)
elif python3 -m pipx --version >/dev/null 2>&1; then
  PIPX=(python3 -m pipx)
else
  echo 'pipx não encontrado. Instale com sudo apt install pipx (Linux) ou brew install pipx (macOS).' >&2
  exit 1
fi
"${PIPX[@]}" install --force 'git+https://github.com/felipeflosii/devflow-cli.git'
"${PIPX[@]}" ensurepath
printf 'DevFlow instalado. Abra um novo terminal e execute: dev --version\n'

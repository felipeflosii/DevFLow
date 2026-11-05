#!/usr/bin/env bash
# DevFlow cross-platform installer for macOS and Linux.
# Inspect this file before executing remotely. Installs only for the current user.
set -Eeuo pipefail

SOURCE='git+https://github.com/felipeflosii/devflow-cli.git'

fail() {
  printf 'Erro: %s\n' "$*" >&2
  exit 1
}

os_name="$(uname -s)"
case "$os_name" in
  Darwin) platform='macOS' ;;
  Linux) platform='Linux' ;;
  *) fail 'Este script e apenas para macOS/Linux; no Windows use install.ps1 no PowerShell.' ;;
esac

command -v git >/dev/null 2>&1 || fail 'Git nao encontrado. No macOS, instale as Command Line Tools (xcode-select --install); no Ubuntu, sudo apt install git.'
command -v python3 >/dev/null 2>&1 || fail 'Python nao encontrado. Instale Python 3.11+ antes de continuar.'
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || fail 'Python 3.10+ e necessario. Recomendamos Python 3.11+.'

if command -v pipx >/dev/null 2>&1; then
  pipx_cmd=(pipx)
elif python3 -m pipx --version >/dev/null 2>&1; then
  pipx_cmd=(python3 -m pipx)
else
  if [[ "$platform" == 'macOS' ]]; then
    fail 'pipx nao encontrado. Instale com: brew install pipx'
  else
    fail 'pipx nao encontrado. No Ubuntu/Zorin: sudo apt update && sudo apt install -y pipx'
  fi
fi

printf 'Instalando DevFlow no %s (sem sudo)...\n' "$platform"
"${pipx_cmd[@]}" install --force "$SOURCE"
"${pipx_cmd[@]}" ensurepath
printf '\nDevFlow instalado. Abra um novo terminal e execute: dev --version\n'
printf 'Depois, dentro do clone Azure Repos: dev init && dev doctor\n'

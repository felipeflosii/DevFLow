#!/usr/bin/env bash
# DevFlow installer for Linux/macOS (execute after inspecting the file).
# Installs the Python CLI in an isolated pipx environment; no sudo is used.
set -Eeuo pipefail

REPOSITORY="felipeflosii/devflow-cli"
SOURCE="git+https://github.com/${REPOSITORY}.git"

fail() {
  printf 'Erro: %s\n' "$*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail 'Git nao instalado. No Zorin/Ubuntu: sudo apt install git'
command -v python3 >/dev/null 2>&1 || fail 'Python 3 nao encontrado. No Zorin/Ubuntu: sudo apt install python3'
command -v pipx >/dev/null 2>&1 || fail 'pipx nao instalado. No Zorin/Ubuntu: sudo apt install pipx'

printf 'Instalando DevFlow a partir de https://github.com/%s\n' "$REPOSITORY"
# --force permite atualizar uma instalacao anterior, mas nao afeta outros pacotes pipx.
pipx install --force "$SOURCE"
pipx ensurepath >/dev/null

printf '\nDevFlow instalado. Execute: dev --help\n'
if ! command -v dev >/dev/null 2>&1; then
  printf 'Se o comando dev nao estiver disponivel, abra outro terminal ou execute: source ~/.zshrc\n'
fi

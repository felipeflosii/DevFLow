#!/usr/bin/env bash
# Instalação oficial DevFlow CLI v1.0.0 (Linux/macOS), usando pipx e release fixada.
set -Eeuo pipefail
PACKAGE='git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0'
for command in git python3; do
  command -v "$command" >/dev/null 2>&1 || { printf 'Erro: %s não encontrado.\n' "$command" >&2; exit 1; }
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || { echo 'Requer Python >=3.10.' >&2; exit 1; }
if command -v pipx >/dev/null 2>&1; then
  PIPX=(pipx)
elif python3 -m pipx --version >/dev/null 2>&1; then
  PIPX=(python3 -m pipx)
else
  echo 'Instale pipx: sudo apt install pipx (Ubuntu/Zorin) ou brew install pipx (macOS).' >&2; exit 1
fi

# Barra indica ETAPAS concluídas; o indicador móvel não representa bytes transferidos.
progress() {
  local done="$1" status="$2"; local bar='' i
  for ((i=0; i<3; i++)); do
    if ((i<done)); then bar+='██████'; else bar+='░░░░░░'; fi
  done
  printf '\r[%s] %s/3  %-48s' "$bar" "$done" "$status" >&2
}
log="$(mktemp)"
trap 'rm -f "$log"' EXIT
printf 'DevFlow v1.0.0 — instalação/atualização segura\n' >&2
progress 1 'Pré-requisitos validados'; printf '\n' >&2
"${PIPX[@]}" install --force "$PACKAGE" >"$log" 2>&1 &
pid=$!
frames=('◐' '◓' '◑' '◒')
i=0
if [[ -t 2 ]]; then
  while kill -0 "$pid" 2>/dev/null; do
    progress 1 "${frames[$((i % 4))]} Baixando e instalando pelo pipx"
    i=$((i + 1))
    sleep 0.12
  done
fi
if wait "$pid"; then
  progress 2 'Pacote instalado'; printf '\n' >&2
else
  printf '\nFalha durante a instalação. Saída do pipx:\n' >&2
  tail -n 40 "$log" >&2
  exit 1
fi
if ! "${PIPX[@]}" ensurepath >>"$log" 2>&1; then
  echo 'Pacote instalado, porém não foi possível configurar PATH. Execute pipx ensurepath.' >&2
  tail -n 15 "$log" >&2
  exit 1
fi
progress 3 'PATH configurado'; printf '\n' >&2
printf 'Instalado! Abra um novo terminal e execute: dev --version\n'

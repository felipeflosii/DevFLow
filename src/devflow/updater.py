"""Atualizador opcional via pipx e releases estáveis verificadas no GitHub.

Exibe progresso por ETAPAS concluídas e spinner de atividade (sem % inventada).
Sem execuções com shell e sem salvar PATs/segredos.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

from . import __version__
from .core import DevError

RELEASES_URL = "https://api.github.com/repos/felipeflosii/devflow-cli/releases/latest"
REPOSITORY = "git+https://github.com/felipeflosii/devflow-cli.git"
TAG_RE = re.compile(r"^v\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?$")


def validate_tag(tag: str) -> str:
    if not TAG_RE.fullmatch(tag):
        raise DevError("Tag inválida. Informe uma release no formato v1.0.0.")
    return tag


def latest_tag() -> str:
    request = urllib.request.Request(RELEASES_URL, headers={"Accept": "application/vnd.github+json", "User-Agent": f"DevFlow/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = json.load(response)
    except (urllib.error.URLError, ValueError, TimeoutError, OSError) as exc:
        raise DevError("Não foi possível consultar a última release no GitHub. Use 'dev update --tag v1.0.0'.") from exc
    return validate_tag(str(data.get("tag_name", "")))


def pipx_command() -> list[str]:
    binary = shutil.which("pipx")
    if binary:
        return [binary]
    # Módulo pipx pode existir sem executable no PATH.
    try:
        probe = subprocess.run([sys.executable, "-m", "pipx", "--version"], capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        probe = None
    if probe and probe.returncode == 0:
        return [sys.executable, "-m", "pipx"]
    raise DevError("pipx não encontrado. Instale pipx e use o instalador indicado em docs/INSTALACAO.md.")


class StepProgress:
    """Barra com N etapas discretas, não é progresso de bytes de download."""
    def __init__(self, total: int = 3, *, stream=None):
        self.stream = stream or sys.stderr
        self.total = total
        self.completed = 0
        self.tty = bool(getattr(self.stream, "isatty", lambda: False)())
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None

    def render(self, label: str, glyph: str = "") -> None:
        if self.tty:
            filled = round(self.completed / self.total * 18)
            bar = "█" * filled + "░" * (18 - filled)
            self.stream.write(f"\r[{bar}] {self.completed}/{self.total} etapas {glyph} {label[:48]:<48}")
            self.stream.flush()
        else:
            self.stream.write(f"[{self.completed}/{self.total}] {label}\n")

    def start(self, label: str) -> None:
        self.stop()
        if not self.tty:
            self.render(label)
            return
        self.stop_event.clear()
        def animate():
            symbols = "◐◓◑◒"
            index = 0
            while not self.stop_event.wait(0.12):
                self.render(label, symbols[index % len(symbols)])
                index += 1
        self.render(label, "◐")
        self.worker = threading.Thread(target=animate, daemon=True)
        self.worker.start()

    def stop(self) -> None:
        if self.worker is not None:
            self.stop_event.set()
            self.worker.join(timeout=2)
            self.worker = None
            if self.tty:
                self.stream.write("\n")

    def done(self, label: str) -> None:
        self.stop()
        self.completed = min(self.total, self.completed + 1)
        self.render(label, "✓")
        if self.tty:
            self.stream.write("\n")


def install_release(tag: str, *, pipx: list[str] | None = None, progress: StepProgress | None = None) -> None:
    tag = validate_tag(tag)
    binary = pipx or pipx_command()
    progress = progress or StepProgress()
    progress.done(f"Release {tag} validada")
    # Um arquivo temporário armazena apenas logs da instalação (não guardamos PAT).
    # Não imprimimos progresso fictício do download; spinner indica atividade.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as transcript:
        progress.start("Baixando e instalando com pipx")
        try:
            result = subprocess.run(binary + ["install", "--force", f"{REPOSITORY}@{tag}"],
                                    stdout=transcript, stderr=subprocess.STDOUT, text=True,
                                    encoding="utf-8", errors="replace", check=False)
        except OSError as exc:
            progress.stop()
            raise DevError(f"Não foi possível executar o pipx: {exc}") from exc
        progress.stop()
        if result.returncode != 0:
            transcript.seek(0)
            output = transcript.read()[-2600:]
            raise DevError(f"Falha na instalação (código {result.returncode}):\n{output}")
    progress.done("Pacote instalado")
    progress.start("Registrando o comando dev no PATH")
    result = subprocess.run(binary + ["ensurepath"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", check=False)
    progress.stop()
    if result.returncode != 0:
        raise DevError("Pacote instalado, mas pipx ensurepath falhou. Execute 'pipx ensurepath' manualmente.\n" + result.stdout[-1500:])
    progress.done("PATH configurado")


def run_update(*, check: bool = False, tag: str | None = None, yes: bool = False) -> int:
    choice = validate_tag(tag) if tag else latest_tag()
    print(f"DevFlow instalado: v{__version__} | Release escolhida: {choice}")
    if check:
        print("Consulta somente leitura; nenhuma alteração realizada.")
        return 0
    if not yes and sys.stdin.isatty():
        confirm = input(f"Atualizar via pipx para {choice}? [s/N] ").strip().casefold()
        if confirm not in {"s", "sim", "y", "yes"}:
            print("Atualização cancelada.")
            return 0
    elif not yes:
        raise DevError("Atualização em ambiente não interativo requer --yes.")
    install_release(choice)
    print("\nInstalação concluída. Verifique em um novo terminal: dev --version")
    return 0

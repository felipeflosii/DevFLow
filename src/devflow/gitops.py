"""Git chamado sem shell: nenhum comando destrutivo implicito."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from .core import DevError


def git(*args: str, cwd: Path | None = None, capture: bool = True) -> str:
    try:
        executable = shutil.which("git")
        if not executable:
            raise FileNotFoundError("git")
        result = subprocess.run(
            [executable, *args], cwd=cwd, text=True, encoding="utf-8", errors="replace",
            capture_output=capture, check=False,
        )
    except FileNotFoundError as exc:
        raise DevError("Git nao encontrado no PATH. Instale o Git para seu sistema e reabra o terminal.") from exc
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip() if capture else ""
        raise DevError(f"git {' '.join(args)} falhou: {details or 'verifique a saida acima'}")
    return result.stdout.strip() if capture else ""


def git_root() -> Path:
    return Path(git("rev-parse", "--show-toplevel"))


def branch() -> str:
    return git("symbolic-ref", "--short", "HEAD")


def require_clean() -> None:
    if git("status", "--porcelain"):
        raise DevError("Ha alteracoes locais. Faca commit ou stash antes de trocar de branch (nenhum arquivo foi alterado).")


def ref_exists(ref: str) -> bool:
    result = subprocess.run(["git", "show-ref", "--verify", "--quiet", ref], capture_output=True)
    return result.returncode == 0


def remote_url(remote: str) -> str:
    return git("remote", "get-url", remote)


def sync(remote: str) -> None:
    git("fetch", "--prune", remote, capture=False)


def ensure_base(remote: str, base: str) -> None:
    if not ref_exists(f"refs/remotes/{remote}/{base}"):
        raise DevError(f"Nao encontrei {remote}/{base}. Verifique branch principal e permissao ao repositorio.")


def switch_task(remote: str, base: str, target_branch: str) -> str:
    """Cria ou retoma branch sem modificar a main local. Retorna a acao."""
    require_clean()
    sync(remote)
    ensure_base(remote, base)
    if ref_exists(f"refs/heads/{target_branch}"):
        git("switch", target_branch, capture=False)
        action = "retomada"
    elif ref_exists(f"refs/remotes/{remote}/{target_branch}"):
        git("switch", "--track", "-c", target_branch, f"{remote}/{target_branch}", capture=False)
        action = "remota retomada"
    else:
        git("switch", "-c", target_branch, f"{remote}/{base}", capture=False)
        action = "criada"
    # Publica a branch se for nova ou local sem upstream. Falha de push nao apaga nada.
    if action == "criada" or not ref_exists(f"refs/remotes/{remote}/{target_branch}"):
        git("push", "-u", remote, target_branch, capture=False)
    return action


def potential_secret_paths() -> list[str]:
    paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    names = paths.splitlines() if paths else []
    restricted = []
    for path in names:
        name = path.rsplit("/", 1)[-1].lower()
        if name in {".env", "id_rsa", "id_ed25519", "credentials.json", "secrets.json"} or (
            name.startswith(".env.") and not name.endswith((".example", ".sample"))
        ) or name.endswith((".pem", ".p12", ".pfx", ".key")):
            restricted.append(path)
    return restricted


def commit_and_push(remote: str, work_id: int, message: str, *, yes: bool = False) -> bool:
    if git("status", "--porcelain"):
        print("\nArquivos envolvidos no commit:\n" + git("status", "--short"))
        if not yes:
            confirm = input("Adicionar TODOS os arquivos acima e criar commit? [s/N] ").lower().strip()
            if confirm not in {"s", "sim", "y", "yes"}:
                raise DevError("Commit cancelado pelo usuario.")
        git("add", "-A")
        secrets = potential_secret_paths()
        if secrets:
            # Garante que os arquivos previamente staged nao serao commitados acidentalmente.
            raise DevError("Possiveis segredos detectados nos arquivos staged: " + ", ".join(secrets)
                           + ". Revise e retire-os do stage com git restore --staged <arquivo>.")
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
    if staged.returncode not in (0, 1):
        raise DevError("Nao foi possivel examinar o index do Git.")
    created = staged.returncode == 1
    if created:
        msg = message.strip()
        if not msg:
            raise DevError("Mensagem de commit vazia.")
        if f"AB#{work_id}".lower() not in msg.lower():
            msg += f" AB#{work_id}"
        git("commit", "-m", msg, capture=False)
    git("push", "-u", remote, branch(), capture=False)
    return created

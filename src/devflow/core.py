"""Funções puras, configuracao local e erros do DevFlow."""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path


class DevError(Exception):
    """Erro tratado e exibido sem traceback para o usuario."""


BRANCH_PATTERN = re.compile(r"^(feature|fix|refactor|hotfix|chore)/(\d+)-([a-z0-9][a-z0-9-]*)$")
DATE_TAG_PREFIX = "devday:"
CLOSED_STATES = {"done", "closed", "resolved", "removed", "completed", "cut"}
DEFAULT_TYPES = {"task", "bug", "product backlog item", "user story", "issue"}


def slugify(text: str, max_len: int = 48) -> str:
    value = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:max_len].rstrip("-") or "tarefa"


def branch_for(item: dict) -> str:
    fields = item.get("fields", {})
    typ = str(fields.get("System.WorkItemType", "Task")).lower()
    prefix = "fix" if typ in ("bug", "defect") else "feature"
    return f"{prefix}/{int(item['id'])}-{slugify(str(fields.get('System.Title', 'tarefa')))}"


def branch_work_id(branch: str) -> int:
    matched = BRANCH_PATTERN.fullmatch(branch)
    if not matched:
        raise DevError("Branch sem ID reconhecivel. Use 'dev start ID' (ex.: feature/142-login).")
    return int(matched.group(2))


def plan_tag(day: date) -> str:
    return f"{DATE_TAG_PREFIX}{day.isoformat()}"


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DevError("Data invalida: use AAAA-MM-DD (ex.: 2026-11-06).") from exc


def tags_of(fields: dict) -> list[str]:
    return [tag.strip() for tag in (fields.get("System.Tags") or "").split(";") if tag.strip()]


def scheduled_day(fields: dict) -> date | None:
    dates = []
    for tag in tags_of(fields):
        if tag.lower().startswith(DATE_TAG_PREFIX):
            try:
                dates.append(parse_day(tag[len(DATE_TAG_PREFIX):]))
            except DevError:
                continue
    return max(dates) if dates else None


def change_plan_tags(fields: dict, day: date) -> str:
    other = [t for t in tags_of(fields) if not t.lower().startswith(DATE_TAG_PREFIX)]
    return "; ".join(other + [plan_tag(day)])


def item_is_open(item: dict) -> bool:
    return str(item.get("fields", {}).get("System.State", "")).lower() not in CLOSED_STATES


def filter_items(items: list[dict], *, mode: str, on_day: date) -> list[dict]:
    filtered = []
    monday = on_day - timedelta(days=on_day.weekday())
    sunday = monday + timedelta(days=6)
    for item in items:
        fields = item.get("fields", {})
        typ = str(fields.get("System.WorkItemType", "")).lower()
        if typ not in DEFAULT_TYPES or not item_is_open(item):
            continue
        scheduled = scheduled_day(fields)
        if mode == "all":
            visible = True
        elif mode == "today":
            visible = scheduled is not None and scheduled <= on_day
        elif mode == "week":
            visible = scheduled is not None and scheduled <= sunday
        elif mode == "date":
            visible = scheduled == on_day
        else:
            raise DevError("Modo de listagem desconhecido.")
        if visible:
            filtered.append(item)
    return sorted(filtered, key=lambda x: (scheduled_day(x.get('fields', {})) or date.max, x['id']))


def config_file() -> Path:
    """Return a per-user config path native to the current operating system.

    Linux/macOS: $XDG_CONFIG_HOME/devflow/config.json or ~/.config/devflow/config.json.
    Windows: %LOCALAPPDATA%/DevFlow/config.json (fall back to APPDATA).
    """
    if sys.platform == "win32":
        local = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
        root = Path(local) if local else Path.home() / "AppData" / "Local"
        return root / "DevFlow" / "config.json"
    location = os.getenv("XDG_CONFIG_HOME")
    root = Path(location).expanduser() if location else Path.home() / ".config"
    return root / "devflow" / "config.json"


def repo_key(root: Path) -> str:
    return str(root.resolve())


def read_config(root: Path) -> dict:
    path = config_file()
    if not path.exists():
        raise DevError("Projeto nao configurado. Rode 'dev init --org ... --project ... --repo ...'.")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DevError(f"Configuracao invalida em {path}: {exc}") from exc
    data = config.get("repositories", {}).get(repo_key(root))
    if not data:
        raise DevError("Este repositorio ainda nao foi configurado. Execute 'dev init'.")
    return data


def save_config(root: Path, data: dict) -> Path:
    path = config_file()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    content = {"repositories": {}}
    if path.exists():
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DevError(f"Configuracao invalida em {path}: {exc}") from exc
    content.setdefault("repositories", {})[repo_key(root)] = data
    # Nenhum token, PAT ou senha e persistido aqui.
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if sys.platform != "win32":
        path.chmod(0o600)
    return path


def ado_remote(remote_url: str) -> dict | None:
    """Extrai organizacao, projeto e repositorio de remotes Azure Repos.

    Ex.: https://dev.azure.com/ORG/PROJ/_git/REPO
    Ex.: git@ssh.dev.azure.com:v3/ORG/PROJ/REPO
    """
    from urllib.parse import urlparse, unquote
    if remote_url.startswith("git@ssh.dev.azure.com:v3/"):
        parts = remote_url.split(":v3/", 1)[1].strip("/").split("/")
        if len(parts) >= 3:
            return {"org": parts[0], "project": unquote(parts[1]), "repo": unquote("/".join(parts[2:]))}
    url = urlparse(remote_url)
    parts = [unquote(x) for x in url.path.strip("/").split("/")]
    if url.hostname == "dev.azure.com" and len(parts) >= 4 and parts[2] == "_git":
        return {"org": parts[0], "project": parts[1], "repo": "/".join(parts[3:])}
    if url.hostname and url.hostname.endswith(".visualstudio.com") and len(parts) >= 3 and parts[1] == "_git":
        return {"org": url.hostname.split(".")[0], "project": parts[0], "repo": "/".join(parts[2:])}
    return None


def render_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(h), *(len(str(row[i])) for row in rows)) for i, h in enumerate(headers)]
    def fmt(row):
        return "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))
    return "\n".join([fmt(headers), "  ".join("-" * n for n in widths)] + [fmt(row) for row in rows])

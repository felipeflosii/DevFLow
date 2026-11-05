"""Funções puras, configuração local e formatação do DevFlow."""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


class DevError(Exception):
    """Erro tratado e exibido sem traceback."""


BRANCH_PATTERN = re.compile(r"^(feature|fix|refactor|hotfix|chore)/(\d+)-([a-z0-9][a-z0-9-]*)$")
DATE_TAG_PREFIX = "devday:"
CLOSED_STATES = {"done", "closed", "resolved", "removed", "completed", "cut"}
TASK_TYPES = {"task"}
WORK_ITEM_TYPES = {"task", "bug", "product backlog item", "user story", "issue", "feature", "epic"}
PARENT_RELATION = "System.LinkTypes.Hierarchy-Reverse"


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
        raise DevError("Branch sem ID reconhecível. Use 'dev start ID' (ex.: feature/142-login).")
    return int(matched.group(2))


def plan_tag(day: date) -> str:
    return f"{DATE_TAG_PREFIX}{day.isoformat()}"


def parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise DevError("Data inválida: use AAAA-MM-DD (ex.: 2026-11-06).") from exc


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


def item_type(item: dict) -> str:
    return str(item.get("fields", {}).get("System.WorkItemType", "")).casefold()


def item_is_open(item: dict) -> bool:
    return str(item.get("fields", {}).get("System.State", "")).casefold() not in CLOSED_STATES


def filter_items(items: list[dict], *, mode: str, on_day: date, types: set[str] | None = None,
                 include_closed: bool = False, area: str | None = None) -> list[dict]:
    """Aplica filtros de exibição sem modificar os dados vindos do Azure Boards."""
    filtered = []
    monday = on_day - timedelta(days=on_day.weekday())
    sunday = monday + timedelta(days=6)
    allowed = TASK_TYPES if types is None else {t.casefold() for t in types}
    for item in items:
        fields = item.get("fields", {})
        if item_type(item) not in allowed or (not include_closed and not item_is_open(item)):
            continue
        if area and area.casefold() not in str(fields.get("System.AreaPath", "")).casefold():
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
    return sorted(filtered, key=lambda x: (scheduled_day(x.get("fields", {})) or date.max, x["id"]))


def parent_id(item: dict) -> int | None:
    """Localiza o pai pela relação de hierarquia (com fallback para System.Parent)."""
    for rel in item.get("relations") or []:
        if rel.get("rel") == PARENT_RELATION:
            candidate = str(rel.get("url", "")).rstrip("/").rsplit("/", 1)[-1]
            if candidate.isdigit():
                return int(candidate)
    candidate = item.get("fields", {}).get("System.Parent")
    if candidate is not None and str(candidate).isdigit():
        return int(candidate)
    return None


def assignee_name(fields: dict) -> str:
    value = fields.get("System.AssignedTo")
    if isinstance(value, dict):
        value = value.get("displayName") or value.get("uniqueName") or value.get("name")
    return str(value).strip() if value else "Não atribuído"


def short_assignee(fields: dict, max_width: int = 17) -> str:
    full = assignee_name(fields)
    if full == "Não atribuído":
        return full
    # Identidade pode vir como e-mail em algumas respostas do Azure DevOps.
    if "@" in full:
        short = full.split("@", 1)[0]
    else:
        words = full.split()
        short = f"{words[0]} {words[1][0]}." if len(words) > 1 else full
    return short if len(short) <= max_width else short[:max_width - 1] + "…"


def truncate(value: Any, max_width: int) -> str:
    s = str(value)
    return s if len(s) <= max_width else s[:max_width - 1] + "…"


def config_file() -> Path:
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
        raise DevError("Projeto não configurado. Rode 'dev init --org ... --project ... --repo ...'.")
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DevError(f"Configuração inválida em {path}: {exc}") from exc
    data = config.get("repositories", {}).get(repo_key(root))
    if not data:
        raise DevError("Este repositório ainda não foi configurado. Execute 'dev init'.")
    return data


def save_config(root: Path, data: dict) -> Path:
    path = config_file()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    content = {"repositories": {}}
    if path.exists():
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DevError(f"Configuração inválida em {path}: {exc}") from exc
    content.setdefault("repositories", {})[repo_key(root)] = data
    # Nenhuma credencial é salva.
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if sys.platform != "win32":
        path.chmod(0o600)
    return path


def ado_remote(remote_url: str) -> dict | None:
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

    def fmt(row: list[str]) -> str:
        return "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))

    return "\n".join([fmt(headers), "  ".join("-" * n for n in widths)] + [fmt(row) for row in rows])

"""Dashboard DevFlow v1.0.0: painel interativo e consultas de leitura.

Modo de consultas + UI via prompt_toolkit, sem modificar Azure DevOps ao navegar.
Operações mutáveis (start/claim) exigem comandos explícitos e usam validações da CLI.
"""
from __future__ import annotations

import json
import shlex
import shutil
import sys
from datetime import date
from typing import Callable

from .ci import build_status, checked_limit, pipeline_summary
from .core import DevError, assignee_name, filter_items, item_type, parent_id, render_table, scheduled_day, truncate

VIEWS = ("summary", "tasks", "prs", "sprint", "pipelines", "builds")


def filter_task_state(items: list[dict], state: str | None) -> list[dict]:
    """Filtro exato de State, sem alterar o tipo de Work Item retornado."""
    if state is None or not state.strip():
        return items
    expected = state.strip().casefold()
    return [i for i in items if str(i.get("fields", {}).get("System.State", "")).strip().casefold() == expected]


def task_rows(items: list[dict], *, pbi_ids: dict[int, int] | None = None) -> list[dict]:
    """Estrutura mínima para JSON seguro, filtros e tabelas no dashboard."""
    result = []
    for i in items:
        fields = i.get("fields", {})
        planned = scheduled_day(fields)
        result.append({
            "id": i["id"], "title": str(fields.get("System.Title", "")),
            "state": str(fields.get("System.State", "")),
            "responsible": assignee_name(fields),
            "area": str(fields.get("System.AreaPath", "")),
            "iteration": str(fields.get("System.IterationPath", "")),
            "pbi": (pbi_ids or {}).get(int(i["id"])),
            "plannedDate": planned.isoformat() if planned else None,
        })
    return result


def collect_tasks(ado, *, all_users: bool = False, area: str | None = None,
                  state: str | None = None, limit: int = 20) -> dict:
    checked_limit(limit, maximum=200)
    if all_users:
        ids = ado.query_ids(item_types={"Task"}, mine=False)
        raw = ado.get_items(ids, relations=True)
    else:
        raw = ado.assigned_items(relations=True)
    items = filter_items(raw, mode="all", on_day=date.today(), types={"Task"}, area=area)
    items = filter_task_state(items, state)
    total = len(items)
    # Para obter os IDs dos pais, verifica que os pais imediatos são PBIs.
    selection = items[:limit]
    parent_ids = sorted({pid for i in selection if (pid := parent_id(i)) is not None})
    parents = {int(i["id"]): i for i in ado.get_items(parent_ids)} if parent_ids else {}
    pbi = {}
    for item in selection:
        pid = parent_id(item)
        if pid is not None and item_type(parents.get(pid, {})) in {"product backlog item", "user story"}:
            pbi[int(item["id"])] = pid
    return {"total": total, "showing": len(selection), "scope": "project" if all_users else "mine",
            "filters": {"area": area, "state": state}, "tasks": task_rows(selection, pbi_ids=pbi)}


def collect_prs(ado, *, all_users: bool = False, limit: int = 20) -> dict:
    checked_limit(limit, maximum=200)
    prs = ado.list_prs(status="active", mine=not all_users, limit=limit)
    return {"scope": "project" if all_users else "mine", "pullRequests": [{
        "id": p.get("pullRequestId"), "title": p.get("title"), "status": p.get("status"),
        "author": (p.get("createdBy") or {}).get("displayName") or "—",
        "branch": str(p.get("sourceRefName") or "").removeprefix("refs/heads/"),
        "mergeStatus": p.get("mergeStatus"), "draft": bool(p.get("isDraft")),
    } for p in prs]}


def collect_sprint(ado, *, team: str | None = None) -> dict:
    # Import local avoids module-level circular import with cli.py.
    from .cli import pick_current_sprint, sprint_summary
    iterations = ado.team_iterations(team=team, current=True)
    chosen = pick_current_sprint(iterations, date.today())
    if chosen is None and len(iterations) == 1:
        chosen = iterations[0]
    if chosen is None:
        chosen = pick_current_sprint(ado.team_iterations(team=team), date.today())
    if chosen is None:
        raise DevError("Nenhuma Sprint atual encontrada. Configure as iterações da equipe ou consulte 'dev sprint --all'.")
    summary = sprint_summary(ado, chosen, team=team)
    iteration = summary["iteration"]
    attrs = iteration.get("attributes") or {}
    return {
        "name": iteration.get("name"), "path": iteration.get("path"),
        "startDate": (attrs.get("startDate") or "")[:10] or None,
        "finishDate": (attrs.get("finishDate") or "")[:10] or None,
        "total": summary["total"], "completed": summary["completed"],
        "percent": summary["percent"],
        "tasks": task_rows(summary["tasks"]),
    }


def collect_pipelines(ado, *, limit: int = 20) -> dict:
    checked_limit(limit, maximum=200)
    pipes = ado.list_pipelines(limit=min(limit, 100))
    sample = ado.list_builds(limit=100) if pipes else []
    return {"sampleSize": len(sample), "pipelines": [{
        "id": p["id"], "name": p["name"],
        "recentBuild": (p["recentBuild"] or {}).get("id"),
        "recentStatus": build_status(p["recentBuild"]) if p["recentBuild"] else None,
    } for p in pipeline_summary(pipes, sample)]}


def collect_builds(ado, *, limit: int = 20, failed: bool = False) -> dict:
    checked_limit(limit, maximum=200)
    builds = ado.list_builds(limit=limit, failed=failed)
    return {"failedOnly": failed, "builds": [{
        "id": b.get("id"), "pipeline": (b.get("definition") or {}).get("name"),
        "status": build_status(b),
        "branch": str(b.get("sourceBranch") or "").removeprefix("refs/heads/"),
    } for b in builds]}


def collect_summary(ado, *, team: str | None = None, all_users: bool = False) -> dict:
    """Resumo tolerante a falhas parciais; nenhum erro vira zero enganoso."""
    result: dict = {"scope": "project" if all_users else "mine", "tasks": None, "pullRequests": None, "sprint": None, "ci": None, "warnings": []}
    try:
        if all_users:
            ids = ado.query_ids(item_types={"Task"}, mine=False)
            raw = ado.get_items(ids)
        else:
            raw = ado.assigned_items()
        opened = filter_items(raw, mode="all", on_day=date.today(), types={"Task"})
        result["tasks"] = {"open": len(opened),
                           "todo": sum(str(i.get("fields", {}).get("System.State", "")).casefold() in {"to do", "new"} for i in opened)}
    except DevError as exc:
        result["warnings"].append("Tasks: " + str(exc))
    try:
        prs = ado.list_prs(status="active", mine=not all_users, limit=100)
        result["pullRequests"] = {"active": len(prs), "sampleLimit": 100}
    except DevError as exc:
        result["warnings"].append("PRs: " + str(exc))
    try:
        sprint = collect_sprint(ado, team=team)
        result["sprint"] = {k: sprint[k] for k in ("name", "completed", "total", "percent")}
    except DevError as exc:
        result["warnings"].append("Sprint: " + str(exc))
    try:
        builds = ado.list_builds(limit=10)
        result["ci"] = {"recent": len(builds),
                        "failedInSample": sum(build_status(b) == "Falhou" for b in builds),
                        "sampleLimit": 10}
    except DevError as exc:
        result["warnings"].append("Pipelines: " + str(exc))
    return result


def collect_view(ado, *, view: str, all_users: bool = False, area: str | None = None,
                 state: str | None = None, limit: int = 20, team: str | None = None,
                 failed: bool = False) -> dict:
    if view not in VIEWS:
        raise DevError(f"Visão inválida: {view}.")
    checked_limit(limit, maximum=200)
    if (state or area) and view != "tasks":
        raise DevError("--state e --area só podem ser usados com --view tasks.")
    if failed and view != "builds":
        raise DevError("--failed só pode ser usado com --view builds.")
    if all_users and view not in {"summary", "tasks", "prs"}:
        raise DevError("--all só pode ser usado em --view summary, tasks ou prs.")
    if view == "summary":
        return collect_summary(ado, team=team, all_users=all_users)
    if view == "tasks":
        return collect_tasks(ado, all_users=all_users, area=area, state=state, limit=limit)
    if view == "prs":
        return collect_prs(ado, all_users=all_users, limit=limit)
    if view == "sprint":
        return collect_sprint(ado, team=team)
    if view == "pipelines":
        return collect_pipelines(ado, limit=limit)
    return collect_builds(ado, limit=limit, failed=failed)


def render_view(view: str, data: dict) -> str:
    """Representação em texto, sem escape ANSI: legível em PowerShell, zsh e CI."""
    if view == "summary":
        tasks, prs, sprint, ci = (data.get(k) for k in ("tasks", "pullRequests", "sprint", "ci"))
        is_team = data.get("scope") == "project"
        lines = ["\nDevFlow 1.0.0 — Dashboard" + (" da equipe" if is_team else ""), "=" * 28,
                 ("Tasks abertas do projeto: " if is_team else "Minhas Tasks abertas:     ") + (str(tasks["open"]) if tasks else "indisponível"),
                 ("PRs ativas do projeto:   " if is_team else "Minhas PRs ativas:       ") + (str(prs["active"]) + " (amostra até 100)" if prs else "indisponível"),
                 "Sprint atual:           " + (f"{sprint['name']} — {sprint['percent']}% ({sprint['completed']}/{sprint['total']})" if sprint else "indisponível"),
                 "Falhas em builds:       " + (f"{ci['failedInSample']} nas últimas {ci['recent']} execuções consultadas" if ci else "indisponível")]
        if data.get("warnings"):
            lines += ["", "Avisos:"] + ["  - " + warning for warning in data["warnings"]]
        lines += ["", "Atalhos: t=Tasks | a=Equipe | p=PRs | s=Sprint | l=Pipelines | b=Builds | f=Falhas",
                  "         w <ID>=Work Item | pr <ID>=PR | start <ID>=Iniciar Task | r=Atualizar | q=Sair"]
        return "\n".join(lines)
    if view == "tasks":
        lines = [f"\nTasks — {data['scope']} ({data['showing']} de {data['total']})"]
        if data["tasks"]:
            title_width = max(16, min(55, shutil.get_terminal_size(fallback=(110, 24)).columns - 52))
            rows = [[str(x["id"]), truncate(x["state"], 13), truncate(x["responsible"], 15),
                     ("#" + str(x["pbi"])) if x["pbi"] else "—", truncate(x["title"], title_width)] for x in data["tasks"]]
            lines.append(render_table(["ID", "Estado", "Responsável", "PBI", "Título"], rows))
        else:
            lines.append("Nenhuma Task corresponde aos filtros.")
        return "\n".join(lines)
    if view == "prs":
        lines = ["\nPull Requests ativas — " + data["scope"]]
        if data["pullRequests"]:
            title_width = max(16, min(56, shutil.get_terminal_size(fallback=(110, 24)).columns - 37))
            rows = [[str(x["id"]), str(x["status"]), truncate(x["author"], 15),
                     truncate(x["title"] or "", title_width)] for x in data["pullRequests"]]
            lines.append(render_table(["PR", "Estado", "Autor", "Título"], rows))
        else:
            lines.append("Nenhuma PR ativa encontrada.")
        return "\n".join(lines)
    if view == "sprint":
        return (f"\nSprint: {data['name']} ({data['startDate'] or '?'} a {data['finishDate'] or '?'})\n"
                f"Tasks concluídas: {data['completed']}/{data['total']} ({data['percent']}%)")
    if view == "pipelines":
        lines = ["\nPipelines — últimos builds na amostra"]
        if data["pipelines"]:
            rows = [[str(x["id"]), truncate(x["name"], 40), str(x["recentBuild"] or "—"),
                     x["recentStatus"] or "—"] for x in data["pipelines"]]
            lines.append(render_table(["ID", "Pipeline", "Build", "Resultado"], rows))
        else:
            lines.append("Nenhuma pipeline encontrada.")
        return "\n".join(lines)
    lines = ["\nBuilds" + (" com falha" if data["failedOnly"] else " recentes")]
    if data["builds"]:
        rows = [[str(x["id"]), truncate(x["pipeline"] or "", 36), x["status"], truncate(x["branch"], 34)]
                for x in data["builds"]]
        lines.append(render_table(["ID", "Pipeline", "Estado", "Branch"], rows))
    else:
        lines.append("Nenhum build encontrado.")
    return "\n".join(lines)


def interactive_dashboard(ado, cfg: dict, *, team: str | None = None,
                          input_fn: Callable[[str], str] | None = None) -> None:
    """Menu de texto seguro; saída automática quando stdin não é interativo."""
    from .cli import do_start, show_item, show_pr
    prompt = input_fn or input
    print(render_view("summary", collect_summary(ado, team=team)))
    if input_fn is None and not sys.stdin.isatty():
        print("\nModo não interativo detectado. Use 'dev dashboard --view tasks' ou --json.")
        return
    while True:
        try:
            response = prompt("\nDevFlow [t/a/p/s/l/b/f/r/w ID/pr ID/start ID/q]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaindo do dashboard.")
            return
        if not response:
            continue
        try:
            parts = shlex.split(response)
        except ValueError:
            print("Entrada inválida. Use aspas em argumentos com espaços.")
            continue
        action = parts[0].lower()
        if action in {"q", "0", "exit", "sair"}:
            return
        if action == "r" and len(parts) == 1:
            print(render_view("summary", collect_summary(ado, team=team)))
            continue
        shortcuts = {"t": ("tasks", False, False), "a": ("tasks", True, False),
                     "p": ("prs", False, False), "s": ("sprint", False, False),
                     "l": ("pipelines", False, False), "b": ("builds", False, False),
                     "f": ("builds", False, True)}
        try:
            if action in shortcuts:
                view, all_users, failed = shortcuts[action]
                options: dict[str, str] = {}
                for token in parts[1:]:
                    if "=" not in token:
                        raise DevError("Filtro inválido. Use: t state=\"To Do\" area=\"Infraestrutura\".")
                    key, value = token.split("=", 1)
                    if key not in {"state", "area"} or view != "tasks":
                        raise DevError("Filtros state= e area= disponíveis somente em t/a.")
                    options[key] = value
                data = collect_view(ado, view=view, all_users=all_users, failed=failed,
                                    team=team, **options)
                print(render_view(view, data))
                continue
            if action in {"w", "show", "pr", "start"} and len(parts) == 2 and parts[1].isdigit():
                item_id = int(parts[1])
                if action in {"w", "show"}:
                    show_item(ado, item_id)
                elif action == "pr":
                    show_pr(ado, item_id)
                else:
                    # A ação altera o Git. O método mantém validações existentes.
                    confirmation = prompt(f"Iniciar Task #{item_id} e trocar de branch? [s/N] ").strip().lower()
                    if confirmation in {"s", "sim", "y", "yes"}:
                        do_start(ado, cfg, item_id)
                        print("Dashboard encerrado após iniciar a Task.")
                        return
                    print("Operação cancelada.")
                continue
            print("Atalho desconhecido. Use t, a, p, s, l, b, f, r, w ID, pr ID, start ID ou q.")
        except DevError as exc:
            print("Erro: " + str(exc), file=sys.stderr)


def execute_dashboard(ado, cfg: dict, args) -> int:
    if args.view is None:
        if args.json:
            raise DevError("Use --view com --json, por exemplo: dev dashboard --view summary --json.")
        if args.all or args.area or args.state or args.failed:
            raise DevError("Para usar filtros, indique uma visão: --view tasks ou --view builds.")
        # Compatibilidade com pipes/CI e testes que simulam stdin.
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print(render_view("summary", collect_summary(ado, team=args.team)))
            print("\nModo não interativo detectado. Use --view tasks ou --view summary --json.")
            return 0
        from .tui import launch_dashboard
        launch_dashboard(ado, cfg, team=args.team)
        return 0
    data = collect_view(ado, view=args.view, all_users=args.all, area=args.area,
                        state=args.state, limit=args.limit, failed=args.failed, team=args.team)
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else render_view(args.view, data))
    return 0

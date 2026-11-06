"""Interface de linha de comando do DevFlow (execução: dev)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import date

from . import __version__
from .ado import AzureDevOps
from .core import (
    DevError, ado_remote, assignee_name, branch_for, branch_work_id, filter_items, item_is_open,
    item_type, parent_id, parse_day, read_config, render_table, save_config,
    scheduled_day, short_assignee, truncate,
)
from . import gitops as g
from .ci import (
    checked_limit, normalize_classic_deploy, normalize_yaml_deploy,
    pipeline_summary, print_pipelines, print_builds, print_runs, print_run_detail,
    print_deploys, timeline_summary, web_url,
)


BACKLOG_TYPES = {
    "pbi": {"Product Backlog Item", "User Story"},
    "features": {"Feature"},
    "epics": {"Epic"},
}


def parser_build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dev", description="Azure Boards + Azure Repos + Git no terminal")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="action", required=True)

    s = sub.add_parser("init", help="Configurar este repositório (sem armazenar token)")
    s.add_argument("--org", help="Nome da organização do Azure DevOps")
    s.add_argument("--project", help="Nome do projeto Azure DevOps")
    s.add_argument("--repo", help="Nome do repositório Azure Repos")
    s.add_argument("--base", default="main", help="Branch base [main]")
    s.add_argument("--remote", default="origin", help="Remote Git [origin]")

    s = sub.add_parser("update", help="Instalar/atualizar DevFlow com barra de etapas e release oficial")
    s.add_argument("--check", action="store_true", help="Apenas consultar a última release disponível")
    s.add_argument("--tag", help="Tag de release (ex.: v1.0.0); padrão: última release estável")
    s.add_argument("--yes", action="store_true", help="Confirmar atualização automaticamente")

    sub.add_parser("config", help="Mostrar configuração deste repositório")
    sub.add_parser("doctor", help="Diagnosticar Git, remoto e autenticação")
    sub.add_parser("sync", help="git fetch origin --prune sem mudar de branch")
    s = sub.add_parser("main", help="Buscar atualizações remotas e trocar para a branch principal configurada")
    s.add_argument("--update", action="store_true", help="Avançar a main via fast-forward somente (sem merge commit)")

    s = sub.add_parser("tasks", help="Listar somente Tasks (não PBIs), por responsável ou período")
    scope = s.add_mutually_exclusive_group()
    scope.add_argument("--all", action="store_true", help="Todas as Tasks abertas do projeto, inclusive de outras pessoas e sem data")
    scope.add_argument("--mine", action="store_true", help="Apenas minhas Tasks abertas (padrão; inclusive sem data)")
    scope.add_argument("--today", action="store_true", help="Apenas minhas Tasks agendadas até hoje")
    scope.add_argument("--week", action="store_true", help="Minhas Tasks até o fim da semana e atrasadas")
    scope.add_argument("--date", metavar="AAAA-MM-DD", help="Minhas Tasks desta data")
    s.add_argument("--closed", action="store_true", help="Incluir Tasks concluídas na listagem selecionada")
    s.add_argument("--area", metavar="AREA", help="Filtrar pelo caminho da área (correspondência parcial)")
    s.add_argument("--json", action="store_true", help="Saída JSON para scripts")

    for command, label in (("pbi", "PBIs"), ("features", "Features"), ("epics", "Epics"),
                           ("workitems", "todos os Work Items")):
        s = sub.add_parser(command, help=f"Listar {label} do projeto")
        s.add_argument("--all", action="store_true", help="Listar todos os itens abertos do projeto")
        s.add_argument("--closed", action="store_true", help="Incluir concluídos")
        s.add_argument("--area", metavar="AREA", help="Filtrar por área")
        s.add_argument("--json", action="store_true", help="Saída JSON")

    s = sub.add_parser("prs", help="Listar Pull Requests do repositório Azure Repos")
    s.add_argument("--status", choices=("active", "completed", "abandoned", "all"), default="active")
    s.add_argument("--all", action="store_true", help="Incluir PRs concluídas e abandonadas")
    s.add_argument("--mine", action="store_true", help="Somente PRs criadas por minha conta")
    s.add_argument("--limit", type=int, default=100, help="Máximo de PRs [100; limite 500]")
    s.add_argument("--json", action="store_true", help="Exibir resultado JSON")

    s = sub.add_parser("pr", help="Mostrar detalhes, revisores e Work Items vinculados à PR")
    s.add_argument("id", type=int)
    s.add_argument("--json", action="store_true", help="Exibir resultado JSON")

    # Observabilidade read-only de CI/CD (REST API Azure DevOps 7.1).
    s = sub.add_parser("pipelines", help="Listar pipelines e últimos builds conhecidos")
    s.add_argument("--limit", type=int, default=50, help="Máximo de pipelines [50; até 100]")
    s.add_argument("--sample", type=int, default=200, help="Quantidade de builds analisados [200; até 200]")
    s.add_argument("--json", action="store_true", help="Saída JSON resumida")

    s = sub.add_parser("builds", help="Listar builds/execuções CI do projeto")
    s.add_argument("--pipeline", type=int, metavar="ID", help="Filtrar pelo ID da pipeline")
    s.add_argument("--failed", action="store_true", help="Somente builds que falharam")
    s.add_argument("--limit", type=int, default=20, help="Quantidade de builds [20; até 200]")
    s.add_argument("--json", action="store_true", help="Saída JSON resumida")

    s = sub.add_parser("build", help="Mostrar detalhes de um build, seus stages e falhas")
    s.add_argument("id", type=int)
    s.add_argument("--json", action="store_true", help="Saída JSON resumida")

    s = sub.add_parser("runs", help="Listar execuções de uma pipeline")
    s.add_argument("pipeline_id", type=int, metavar="PIPELINE_ID")
    s.add_argument("--limit", type=int, default=10, help="Últimas execuções [10; até 100]")
    s.add_argument("--json", action="store_true", help="Saída JSON resumida")

    s = sub.add_parser("run", help="Mostrar status e falhas de uma execução de pipeline")
    s.add_argument("pipeline_id", type=int, metavar="PIPELINE_ID")
    s.add_argument("run_id", type=int, metavar="RUN_ID")
    s.add_argument("--json", action="store_true", help="Saída JSON resumida")

    s = sub.add_parser("deploys", help="Consultar deploys YAML Environments e Classic Releases")
    s.add_argument("--source", choices=("all", "yaml", "classic"), default="all",
                   help="Tipo de deploy [all]")
    s.add_argument("--environment", metavar="NOME", help="Filtrar pelo nome do ambiente")
    s.add_argument("--limit", type=int, default=20, help="Quantidade de deploys [20; até 100]")
    s.add_argument("--json", action="store_true", help="Saída JSON resumida")

    s = sub.add_parser("sprint", help="Mostrar Sprint atual, Tasks, responsáveis e progresso")
    s.add_argument("--team", help="Nome da equipe do Azure Boards (padrão: equipe principal)")
    s.add_argument("--all", action="store_true", help="Listar todas as Sprints configuradas para a equipe")
    s.add_argument("--json", action="store_true", help="Exibir resultado JSON")

    s = sub.add_parser("claim", help="Assumir uma Task não atribuída, mediante confirmação")
    s.add_argument("id", type=int)
    s.add_argument("--yes", action="store_true", help="Confirmar atribuição sem perguntar")

    s = sub.add_parser("show", help="Exibir os detalhes e a hierarquia Epic > Feature > PBI > Task")
    s.add_argument("id", type=int, help="ID de qualquer Work Item")

    s = sub.add_parser("dashboard", help="Painel interativo: Tasks, PRs, Sprints, Pipelines e atalhos")
    s.add_argument("--view", choices=("summary", "tasks", "prs", "sprint", "pipelines", "builds"),
                   help="Exibir uma visão sem iniciar o menu interativo")
    s.add_argument("--all", action="store_true", help="Exibir Tasks/PRs de toda a equipe (padrão: minhas)")
    s.add_argument("--state", help="Filtrar Tasks por estado exato (ex.: 'To Do')")
    s.add_argument("--area", help="Filtrar Tasks por Area Path (correspondência parcial)")
    s.add_argument("--failed", action="store_true", help="Filtrar builds com falha em --view builds")
    s.add_argument("--team", help="Equipe usada para consultar Sprint atual")
    s.add_argument("--limit", type=int, default=20, help="Máximo de registros em uma visão [20, até 200]")
    s.add_argument("--json", action="store_true", help="JSON resumido (requer --view)")
    s = sub.add_parser("start", help="Criar/retomar branch de Task atribuída a você")
    s.add_argument("id", type=int)

    sub.add_parser("current", help="Mostrar branch e Task atual")
    sub.add_parser("status", help="Mostrar Task, Git e PR em aberto")

    s = sub.add_parser("new", help="Criar uma Task para alguém, opcionalmente agendada")
    s.add_argument("title", help="Título da tarefa")
    s.add_argument("--assign", metavar="EMAIL", help="Usuário do Azure Boards")
    s.add_argument("--date", metavar="AAAA-MM-DD", help="Data planejada")
    s.add_argument("--type", default="Task", help="Tipo Azure Boards, ex.: Task, Bug")
    s.add_argument("--parent", type=int, metavar="ID", help="ID do Work Item pai (PBI/Feature/Epic)")

    s = sub.add_parser("plan", help="Planejar uma ou mais Tasks com tag devday:AAAA-MM-DD")
    s.add_argument("ids", metavar="ID", type=int, nargs="+")
    s.add_argument("--date", required=True, metavar="AAAA-MM-DD")

    s = sub.add_parser("assign", help="Atribuir Task existente a desenvolvedor")
    s.add_argument("id", type=int)
    s.add_argument("email")

    s = sub.add_parser("save", help="Commit + push com referência AB#ID")
    s.add_argument("message", help="Mensagem do commit")
    s.add_argument("--yes", action="store_true", help="Confirmar inclusão de todos os arquivos automaticamente")

    s = sub.add_parser("finish", help="Commit, push, criar PR e retornar à branch principal")
    s.add_argument("-m", "--message", help="Mensagem do commit se existirem arquivos alterados")
    s.add_argument("--yes", action="store_true", help="Confirmar inclusão de todos os arquivos automaticamente")

    return p


def client(cfg: dict) -> AzureDevOps:
    return AzureDevOps(cfg["org"], cfg["project"], cfg["repo"])


def config_guard(cfg: dict) -> None:
    """Bloqueia operações Git se remote for de outro projeto/repo."""
    remote = g.remote_url(cfg["remote"])
    parsed = ado_remote(remote)
    if not parsed:
        raise DevError("O remote não é um Azure Repos reconhecido. Esta versão integra Azure Repos, não GitHub.")
    for field in ("org", "project", "repo"):
        if parsed[field].casefold() != cfg[field].casefold():
            raise DevError(f"Configuração/remote divergente em {field}: remote={parsed[field]!r}, configurado={cfg[field]!r}.")


def load_pbi_ids(ado: AzureDevOps, items: list[dict]) -> dict[int, int]:
    """Resolve PBIs pai em lote (não assume que todo pai é um PBI)."""
    ids_by_task = {int(item["id"]): parent_id(item) for item in items}
    unique_parent_ids = sorted({pid for pid in ids_by_task.values() if pid is not None})
    if not unique_parent_ids:
        return {}
    parents = {int(p["id"]): p for p in ado.get_items(unique_parent_ids)}
    result = {}
    for task_id, pid in ids_by_task.items():
        parent = parents.get(pid)
        if parent and item_type(parent) in {"product backlog item", "user story"}:
            result[task_id] = pid
    return result


def print_tasks(items: list[dict], *, mode: str, on_day: date, show_assignee: bool = False,
                pbi_ids: dict[int, int] | None = None, show_closed: bool = False) -> None:
    titles = {
        "today": "Minhas Tasks de hoje + atrasadas",
        "week": "Minhas Tasks desta semana + atrasadas",
        "all": "Todas as Tasks abertas do projeto" if show_assignee else "Todas as minhas Tasks abertas",
        "date": f"Minhas Tasks de {on_day.isoformat()}",
    }
    title = titles[mode].replace("abertas", "(incluindo concluídas)") if show_closed else titles[mode]
    print("\n" + title)
    print("=" * len(title))
    if not items:
        print("Nenhuma Task encontrada. Use 'dev tasks --all', 'dev tasks --mine' ou 'dev plan ID --date AAAA-MM-DD'.")
        return
    width = shutil.get_terminal_size(fallback=(110, 24)).columns
    # Largura previsível em terminais comuns, sem perder o ID da Task nem o PBI.
    overhead = 40 + (20 if show_assignee else 0)
    title_width = max(18, min(65, width - overhead))
    headers = ["ID", "Estado", "Planejada"]
    if show_assignee:
        headers += ["Responsável"]
    headers += ["PBI", "Título"]
    rows = []
    for item in items:
        fields = item.get("fields", {})
        day = scheduled_day(fields)
        when = day.isoformat() if day else "sem data"
        if day and day < on_day:
            when += " (!)"
        row = [str(item["id"]), truncate(fields.get("System.State", ""), 14), when]
        if show_assignee:
            row.append(short_assignee(fields))
        row += [f"#{pbi_ids[int(item['id'])]}" if pbi_ids and int(item["id"]) in pbi_ids else "—",
                truncate(fields.get("System.Title", ""), title_width)]
        rows.append(row)
    print(render_table(headers, rows))
    print(f"\nTotal: {len(items)} Task(s). Use: dev start <ID> | dev show <ID>")


def my_tasks(ado: AzureDevOps, args) -> tuple[list[dict], str, date]:
    """Mantido como ponto único de filtragem para tasks e dashboard."""
    day = parse_day(args.date) if getattr(args, "date", None) else date.today()
    mine = bool(getattr(args, "mine", False))
    all_teams = bool(getattr(args, "all", False)) and not mine
    mode = "date" if getattr(args, "date", None) else (
        "week" if getattr(args, "week", False) else "today" if getattr(args, "today", False) else "all")
    # Sem flags, dev tasks exibe TODAS as minhas Tasks abertas, inclusive as sem data.
    include_closed = bool(getattr(args, "closed", False))
    if all_teams:
        ids = ado.query_ids(item_types={"Task"}, mine=False, include_closed=include_closed)
        source = ado.get_items(ids, relations=True)
    else:
        source = ado.assigned_items(relations=True)
    items = filter_items(source, mode=mode, on_day=day, include_closed=include_closed,
                         area=getattr(args, "area", None))
    return items, mode, day


def list_backlog(ado: AzureDevOps, args) -> list[dict]:
    work_types = None if args.action == "workitems" else BACKLOG_TYPES[args.action]
    ids = ado.query_ids(item_types=work_types, mine=False, include_closed=args.closed)
    items = ado.get_items(ids)
    # --all mantido para consistência, sem interferir no padrão de listagem.
    if args.action == "workitems":
        types = {"task", "bug", "product backlog item", "user story", "issue", "feature", "epic"}
    else:
        types = {s.casefold() for s in work_types}
    return filter_items(items, mode="all", on_day=date.today(), types=types,
                        include_closed=args.closed, area=args.area)


def print_backlog(items: list[dict], action: str) -> None:
    print(f"\n{action.upper()} — Azure Boards")
    print("=" * (len(action) + 17))
    if not items:
        print("Nenhum Work Item encontrado.")
        return
    rows = [[str(i["id"]), str(i.get("fields", {}).get("System.WorkItemType", "")),
             str(i.get("fields", {}).get("System.State", "")),
             short_assignee(i.get("fields", {})), truncate(i.get("fields", {}).get("System.Title", ""), 62)]
            for i in items]
    print(render_table(["ID", "Tipo", "Estado", "Responsável", "Título"], rows))
    print(f"\nTotal: {len(items)} item(ns). Use: dev show <ID>")


def show_item(ado: AzureDevOps, work_id: int) -> None:
    if work_id <= 0:
        raise DevError("O ID deve ser positivo.")
    current = ado.get_item(work_id, relations=True)
    fields = current.get("fields", {})
    print(f"\n{fields.get('System.WorkItemType', 'Work Item')} #{work_id} — {fields.get('System.Title', '')}")
    print("Estado:      " + str(fields.get("System.State", "não informado")))
    print("Responsável: " + assignee_name(fields))
    print("Área:        " + str(fields.get("System.AreaPath", "não informada")))
    print("Iteração:    " + str(fields.get("System.IterationPath", "não informada")))
    when = scheduled_day(fields)
    print("Planejada:   " + (when.isoformat() if when else "sem data"))
    print("URL:         " + ado.project_url + f"/_workitems/edit/{work_id}")
    lineage = [current]
    seen = {work_id}
    for _ in range(12):
        pid = parent_id(current)
        if pid is None or pid in seen:
            break
        seen.add(pid)
        current = ado.get_item(pid, relations=True)
        lineage.append(current)
    print("\nHierarquia:")
    for depth, item in enumerate(reversed(lineage)):
        f = item.get("fields", {})
        print("  " * depth + f"{f.get('System.WorkItemType', 'Item')} #{item['id']} — {f.get('System.Title', '')}")


def sprint_status(itr: dict, today: date) -> str:
    attrs = itr.get("attributes") or {}
    start = attrs.get("startDate")
    finish = attrs.get("finishDate")
    if start and finish:
        try:
            beginning, end = date.fromisoformat(start[:10]), date.fromisoformat(finish[:10])
            return "Atual" if beginning <= today <= end else ("Futura" if today < beginning else "Encerrada")
        except ValueError:
            pass
    return "Atual" if str(attrs.get("timeFrame", "")).casefold() == "current" else "Sem data"


def sprint_summary(ado: AzureDevOps, iteration: dict, *, team: str | None = None) -> dict:
    items = ado.sprint_work_items(str(iteration["id"]), team=team)
    tasks = sorted((i for i in items if item_type(i) == "task"), key=lambda i: i["id"])
    completed = sum(1 for i in tasks if not item_is_open(i))
    return {"iteration": iteration, "tasks": tasks, "total": len(tasks), "completed": completed,
            "percent": round((completed / len(tasks)) * 100) if tasks else 0}


def show_sprint(summary: dict) -> None:
    itr = summary["iteration"]
    attrs = itr.get("attributes") or {}
    print("\nSprint: " + str(itr.get("name", "sem nome")))
    print("Caminho: " + str(itr.get("path", "não informado")))
    print("Início:  " + str(attrs.get("startDate") or "não definido")[:10])
    print("Fim:     " + str(attrs.get("finishDate") or "não definido")[:10])
    print(f"Progresso das Tasks: {summary['completed']}/{summary['total']} concluídas ({summary['percent']}%)")
    if not summary["tasks"]:
        print("Nenhuma Task encontrada nesta Sprint.")
        return
    rows = [[str(x["id"]), truncate(x.get("fields", {}).get("System.State", ""), 16),
             short_assignee(x.get("fields", {})), truncate(x.get("fields", {}).get("System.Title", ""), 60)]
            for x in summary["tasks"]]
    print(render_table(["ID", "Estado", "Responsável", "Título"], rows))


def pick_current_sprint(iterations: list[dict], today: date) -> dict | None:
    for iteration in iterations:
        if sprint_status(iteration, today) == "Atual":
            return iteration
    return None


def print_prs(ado: AzureDevOps, prs: list[dict], *, status: str) -> None:
    print(f"\nPull Requests — {status}")
    print("=" * (16 + len(status)))
    if not prs:
        print("Nenhuma Pull Request encontrada.")
        return
    rows = []
    for pr in prs:
        author = pr.get("createdBy") or {}
        rows.append([str(pr.get("pullRequestId", "?")), str(pr.get("status", "?")),
                     truncate(author.get("displayName") or author.get("uniqueName") or "—", 16),
                     truncate(str(pr.get("sourceRefName", "")).removeprefix("refs/heads/"), 34),
                     truncate(pr.get("title", ""), 54)])
    print(render_table(["PR", "Estado", "Autor", "Branch", "Título"], rows))
    print(f"\nTotal: {len(prs)} PR(s). Use: dev pr <ID>")


def show_pr(ado: AzureDevOps, pr_id: int) -> dict:
    pr = ado.get_pr(pr_id)
    if not isinstance(pr, dict):
        raise DevError("Azure DevOps retornou um formato inválido para a PR.")
    print(f"\nPR #{pr_id} — {pr.get('title', 'Sem título')}")
    print("Estado:        " + str(pr.get("status", "não informado")))
    print("Autor:         " + assignee_name({"System.AssignedTo": pr.get("createdBy")}))
    print("Origem:        " + str(pr.get("sourceRefName", "")).removeprefix("refs/heads/"))
    print("Destino:       " + str(pr.get("targetRefName", "")).removeprefix("refs/heads/"))
    print("Merge status:  " + str(pr.get("mergeStatus", "não informado")))
    print("Rascunho:      " + ("sim" if pr.get("isDraft") else "não"))
    print("URL:           " + ado.pr_web_url(pr_id))
    reviewers = pr.get("reviewers") or []
    if reviewers:
        names = {10: "aprovou", 5: "aprovou c/ sugestões", 0: "pendente", -5: "aguarda autor", -10: "rejeitou"}
        print("Revisores:")
        for reviewer in reviewers:
            display = reviewer.get("displayName") or reviewer.get("uniqueName") or "Revisor"
            print(f"  - {display}: {names.get(reviewer.get('vote', 0), 'voto ' + str(reviewer.get('vote')))}")
    else:
        print("Revisores:     nenhum informado")
    linked = ado.pr_work_items(pr_id)
    print("Work Items:    " + (", ".join(f"#{i}" for i in linked) if linked else "nenhum vinculado"))
    return {"pullRequest": pr, "workItemIds": linked}


def ensure_task(item: dict) -> None:
    typ = str(item.get("fields", {}).get("System.WorkItemType", ""))
    if typ.casefold() != "task":
        raise DevError(f"Work Item #{item['id']} é '{typ}', não Task. "
                       "Use 'dev tasks --all' para localizar uma Task e 'dev show ID' para ver a hierarquia.")


def do_start(ado: AzureDevOps, cfg: dict, item_id: int) -> None:
    if item_id <= 0:
        raise DevError("ID de tarefa deve ser positivo.")
    item = ado.get_item(item_id)
    ensure_task(item)
    if item_id not in ado.assigned_ids():
        raise DevError(f"A Task #{item_id} não está atribuída à sua conta autenticada no Azure Boards.")
    if str(item.get("fields", {}).get("System.State", "")).casefold() in {
        "done", "closed", "removed", "completed", "cut", "resolved"
    }:
        raise DevError("A Task já está encerrada no Azure Boards.")
    config_guard(cfg)
    wanted = branch_for(item)
    action = g.switch_task(cfg["remote"], cfg["base"], wanted)
    print(f"\nBranch {wanted} ({action}), publicada em {cfg['remote']}.")
    try:
        ado.add_artifact_link(item_id, "Branch", wanted)
        print(f"Azure Boards: branch associada a Task #{item_id}.")
    except DevError as exc:
        print(f"AVISO: branch criada, mas associação com Boards falhou: {exc}", file=sys.stderr)
    try:
        state = ado.move_to_in_progress(item)
        if state:
            print(f"Task em estado: {state}.")
        else:
            print("Estado não alterado: não existe transição conhecida para Doing/In Progress/Active.")
    except DevError as exc:
        print(f"AVISO: não consegui atualizar estado no Boards: {exc}", file=sys.stderr)
    print("Próximo passo: desenvolva, depois execute 'dev finish'.")


def current_item_id() -> int:
    return branch_work_id(g.branch())


def do_finish(ado: AzureDevOps, cfg: dict, *, message: str | None, yes: bool) -> None:
    config_guard(cfg)
    item_id = current_item_id()
    item = ado.get_item(item_id)
    ensure_task(item)
    branch = g.branch()
    existing = ado.active_pr(branch)
    if existing:
        raise DevError(f"Já existe PR ativa para esta branch: {ado.pr_web_url(existing['pullRequestId'])}")
    if g.git("status", "--porcelain") and not message:
        message = str(item.get("fields", {}).get("System.Title", "Implementar Task"))
    if message is not None:
        was_committed = g.commit_and_push(cfg["remote"], item_id, message, yes=yes)
        print("Commit criado e enviado." if was_committed else "Sem novos arquivos; branch enviada.")
    else:
        g.git("push", "-u", cfg["remote"], branch, capture=False)
    g.sync(cfg["remote"])
    g.ensure_base(cfg["remote"], cfg["base"])
    ahead = int(g.git("rev-list", "--count", f"{cfg['remote']}/{cfg['base']}..HEAD"))
    if ahead == 0:
        raise DevError("Nenhum commit novo em relação à branch base. Não criei PR vazia.")
    title = str(item.get("fields", {}).get("System.Title", "Task"))
    pr = ado.create_pr(branch, cfg["base"], title, item_id)
    pr_id = int(pr["pullRequestId"])
    print(f"\nPR #{pr_id} criada: {ado.pr_web_url(pr_id)}")
    try:
        ado.add_artifact_link(item_id, "Pull Request", str(pr_id))
        print(f"PR vinculada a Task #{item_id}.")
    except DevError as exc:
        print(f"AVISO: PR criada, mas vínculo com Boards falhou: {exc}", file=sys.stderr)
    print("A PR ficou aguardando revisão. O comando NÃO faz merge nem ignora políticas da main.")
    # A PR já foi criada. Uma eventual falha ao voltar para a principal não
    # desfaz a PR e não deve induzir o usuário a executar 'finish' novamente.
    try:
        outcome = g.switch_base(cfg["remote"], cfg["base"])
    except DevError as exc:
        print(f"AVISO: PR #{pr_id} foi criada, mas não foi possível voltar para "
              f"{cfg['base']}: {exc}. Execute 'dev main' quando estiver pronto.",
              file=sys.stderr)
    else:
        print(f"Branch principal {cfg['base']}: {outcome} "
              "(fetch --prune + switch; sem pull automático).")


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except (DevError, EOFError, KeyboardInterrupt) as exc:
        print("\nErro: " + (str(exc) or "operação interrompida."), file=sys.stderr)
        return 1


def run(argv: list[str] | None = None) -> int:
    args = parser_build().parse_args(argv)
    # Update é global: não exige estar em um repositório Git ou configurar dev init.
    if args.action == "update":
        from .updater import run_update
        return run_update(check=args.check, tag=args.tag, yes=args.yes)
    root = g.git_root()
    os.chdir(root)
    if args.action == "init":
        remote = g.remote_url(args.remote)
        detected = ado_remote(remote) or {}
        data = {"org": args.org or detected.get("org"),
                "project": args.project or detected.get("project"),
                "repo": args.repo or detected.get("repo"),
                "base": args.base, "remote": args.remote}
        if not all(data.values()):
            raise DevError("Não detectei Azure Repos. Informe --org, --project e --repo explicitamente.")
        config_guard(data)
        saved = save_config(root, data)
        print(f"Configurado em {saved} (sem segredos).\n" + json.dumps(data, ensure_ascii=False, indent=2))
        print("Execute 'dev doctor' para testar acesso e 'dev tasks' para consultar tarefas.")
        return 0

    cfg = read_config(root)
    if args.action == "config":
        print(json.dumps(cfg, ensure_ascii=False, indent=2))
        return 0
    if args.action == "sync":
        config_guard(cfg)
        g.sync(cfg["remote"])
        print("Referências atualizadas. Nenhuma branch local sofreu merge/rebase/reset.")
        return 0
    if args.action == "main":
        config_guard(cfg)
        outcome = g.switch_base(cfg["remote"], cfg["base"])
        print(f"Branch principal {cfg['base']}: {outcome}.")
        if args.update:
            g.fast_forward_base(cfg["remote"], cfg["base"])
            print(f"Branch {cfg['base']} atualizada via fast-forward a partir de {cfg['remote']}/{cfg['base']}.")
        else:
            print("Referências remotas atualizadas (fetch --prune). Nenhum pull, merge ou rebase foi executado.")
        return 0
    ado = client(cfg)
    if args.action == "doctor":
        print(f"DevFlow {__version__} | Git: {shutil.which('git') or 'ausente'} | Azure CLI: {shutil.which('az') or 'não instalada'}")
        config_guard(cfg)
        print("Remote Azure Repos: OK")
        user = ado.identity()
        print("Usuário Azure Boards: " + str(user.get("uniqueName") or user.get("providerDisplayName") or "conectado"))
        print("Projeto: " + ado.project_id())
        print("Repositório: " + ado.repo_id())
        print("Diagnóstico concluído. Teste 'dev tasks --all'.")
        return 0
    if args.action == "prs":
        status = "all" if args.all else args.status
        prs = ado.list_prs(status=status, mine=args.mine, limit=args.limit)
        if args.json:
            print(json.dumps(prs, ensure_ascii=False, indent=2))
        else:
            print_prs(ado, prs, status=status)
        return 0
    if args.action == "pr":
        if args.json:
            pr = ado.get_pr(args.id)
            print(json.dumps({"pullRequest": pr, "workItemIds": ado.pr_work_items(args.id)},
                             ensure_ascii=False, indent=2))
        else:
            show_pr(ado, args.id)
        return 0
    if args.action == "pipelines":
        checked_limit(args.limit)
        checked_limit(args.sample, maximum=200)
        pipelines = ado.list_pipelines(limit=args.limit)
        sample = ado.list_builds(limit=args.sample) if pipelines else []
        summary = pipeline_summary(pipelines, sample)
        if args.json:
            # Exibe apenas dados operacionais; não imprime payloads API brutos.
            payload = [{"id": i["id"], "name": i["name"], "folder": i["folder"],
                        "recentBuild": ({"id": i["recentBuild"].get("id"),
                                        "status": i["recentBuild"].get("status"),
                                        "result": i["recentBuild"].get("result")}
                                       if i["recentBuild"] else None)} for i in summary]
            print(json.dumps({"sampleSize": len(sample), "pipelines": payload}, ensure_ascii=False, indent=2))
        else:
            print_pipelines(pipelines, sample, sample=len(sample))
        return 0
    if args.action == "builds":
        builds = ado.list_builds(limit=args.limit, pipeline_id=args.pipeline, failed=args.failed)
        if args.json:
            payload = [{"id": b.get("id"), "pipeline": (b.get("definition") or {}).get("name"),
                        "pipelineId": (b.get("definition") or {}).get("id"),
                        "status": b.get("status"), "result": b.get("result"),
                        "branch": b.get("sourceBranch"), "startTime": b.get("startTime"),
                        "finishTime": b.get("finishTime"), "webUrl": web_url(b)} for b in builds]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_builds(builds)
        return 0
    if args.action == "build":
        build = ado.get_build(args.id)
        # Em caso de erro de permissão/timeline indisponível, preserva dados do build.
        warning = None
        try:
            timeline = ado.build_timeline(args.id)
        except DevError as exc:
            timeline = None
            warning = str(exc)
        as_run = {"id": build.get("id"),
                  "pipeline": {"id": (build.get("definition") or {}).get("id")},
                  "name": build.get("buildNumber") or build.get("id"),
                  "state": build.get("status"), "result": build.get("result"),
                  "createdDate": build.get("startTime") or build.get("queueTime"),
                  "finishedDate": build.get("finishTime"), "_links": build.get("_links")}
        if args.json:
            print(json.dumps({"build": {"id": build.get("id"), "pipelineId": (build.get("definition") or {}).get("id"),
                                        "pipeline": (build.get("definition") or {}).get("name"),
                                        "status": build.get("status"), "result": build.get("result"),
                                        "branch": build.get("sourceBranch"), "webUrl": web_url(build)},
                              "timeline": timeline_summary(timeline) if timeline is not None else None,
                              "warning": warning}, ensure_ascii=False, indent=2))
        else:
            print_run_detail(as_run, timeline)
            if warning:
                print("AVISO: não foi possível consultar a timeline: " + warning, file=sys.stderr)
        return 0
    if args.action == "runs":
        runs = ado.list_runs(args.pipeline_id, limit=args.limit)
        if args.json:
            payload = [{"id": r.get("id"), "name": r.get("name"), "state": r.get("state"),
                        "result": r.get("result"), "createdDate": r.get("createdDate"),
                        "finishedDate": r.get("finishedDate"), "webUrl": web_url(r)} for r in runs]
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print_runs(args.pipeline_id, runs)
        return 0
    if args.action == "run":
        pipeline_run = ado.get_run(args.pipeline_id, args.run_id)
        warning = None
        try:
            timeline = ado.build_timeline(args.run_id)
        except DevError as exc:
            timeline = None
            warning = str(exc)
        if args.json:
            print(json.dumps({"run": {"id": pipeline_run.get("id"),
                                      "name": pipeline_run.get("name"),
                                      "pipelineId": (pipeline_run.get("pipeline") or {}).get("id"),
                                      "state": pipeline_run.get("state"), "result": pipeline_run.get("result"),
                                      "createdDate": pipeline_run.get("createdDate"),
                                      "finishedDate": pipeline_run.get("finishedDate"),
                                      "webUrl": web_url(pipeline_run)},
                              "timeline": timeline_summary(timeline) if timeline is not None else None,
                              "warning": warning}, ensure_ascii=False, indent=2))
        else:
            print_run_detail(pipeline_run, timeline)
            if warning:
                print("AVISO: timeline indisponível (execução pode não corresponder a um build): " + warning,
                      file=sys.stderr)
        return 0
    if args.action == "deploys":
        checked_limit(args.limit)
        all_deploys = []
        errors = []
        successful_sources = 0
        filter_name = (args.environment or "").casefold()
        if args.source in {"all", "yaml"}:
            try:
                environments = ado.list_environments(limit=100)
                if filter_name:
                    environments = [e for e in environments if filter_name in str(e.get("name") or "").casefold()]
                # Limita consultas por ambiente. Sem prometer varredura completa da organização.
                for env in environments[:30]:
                    try:
                        history = ado.list_environment_deployments(int(env["id"]), limit=min(100, args.limit))
                        all_deploys.extend(normalize_yaml_deploy(env, history))
                    except DevError as exc:
                        errors.append(f"Ambiente YAML {env.get('name', env.get('id'))}: {exc}")
                if len(environments) > 30:
                    errors.append("Consulta limitada aos 30 primeiros ambientes; use --environment para filtrar.")
                successful_sources += 1
            except DevError as exc:
                errors.append("YAML Environments: " + str(exc))
        if args.source in {"all", "classic"}:
            try:
                classic = normalize_classic_deploy(ado.list_classic_deployments(limit=args.limit))
                if filter_name:
                    classic = [d for d in classic if filter_name in str(d.get("environment", "")).casefold()]
                all_deploys.extend(classic)
                successful_sources += 1
            except DevError as exc:
                errors.append("Classic Releases: " + str(exc))
        if successful_sources == 0:
            raise DevError("Não foi possível consultar nenhuma fonte de deploy. " + "; ".join(errors))
        # Não confunde "nenhuma implantação" com falha parcial da API.
        all_deploys.sort(key=lambda d: d.get("startTime") or "", reverse=True)
        all_deploys = all_deploys[:args.limit]
        if args.json:
            print(json.dumps({"deployments": all_deploys, "warnings": errors}, ensure_ascii=False, indent=2))
        else:
            print_deploys(all_deploys, source=args.source, errors=errors)
        return 0
    if args.action == "sprint":
        team = args.team
        iterations = ado.team_iterations(team=team, current=not args.all)
        if args.all:
            if args.json:
                print(json.dumps(iterations, ensure_ascii=False, indent=2))
            elif not iterations:
                print("Nenhuma Sprint configurada para esta equipe no Azure Boards.")
            else:
                print("\nSprints da equipe:")
                rows = []
                for itr in iterations:
                    attrs = itr.get("attributes") or {}
                    rows.append([str(itr.get("name", "")), str(attrs.get("startDate") or "—")[:10],
                                 str(attrs.get("finishDate") or "—")[:10],
                                 sprint_status(itr, date.today())])
                print(render_table(["Sprint", "Início", "Fim", "Situação"], rows))
            return 0
        chosen = pick_current_sprint(iterations, date.today())
        if chosen is None and len(iterations) == 1:
            # A resposta filtrada como current já foi validada pelo serviço,
            # mesmo que os metadados de data estejam incompletos.
            chosen = iterations[0]
        if chosen is None:
            # Se não houver uma Sprint retornada pelo timeframe atual, a equipe
            # pode estar configurada sem datas ou fora do intervalo vigente.
            chosen = pick_current_sprint(ado.team_iterations(team=team), date.today())
        if chosen is None:
            raise DevError("Nenhuma Sprint atual encontrada. Verifique datas e iterações da equipe "
                           "em Project settings > Teams > Iterations. Use 'dev sprint --all'.")
        summary = sprint_summary(ado, chosen, team=team)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            show_sprint(summary)
        return 0
    if args.action == "claim":
        item = ado.get_item(args.id)
        ensure_task(item)
        if not item_is_open(item):
            raise DevError("A Task já está encerrada.")
        if item.get("fields", {}).get("System.AssignedTo"):
            raise DevError(f"Task #{args.id} já possui responsável: {assignee_name(item['fields'])}.")
        if not args.yes:
            confirmation = input(f"Assumir Task #{args.id} — {item['fields'].get('System.Title', '')}? [s/N] ").strip().lower()
            if confirmation not in {"s", "sim", "y", "yes"}:
                raise DevError("Atribuição cancelada.")
        ado.claim_task(args.id)
        print(f"Task #{args.id} atribuída à sua conta. Execute 'dev start {args.id}' para iniciar.")
        return 0
    if args.action == "tasks":
        items, mode, day = my_tasks(ado, args)
        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            pbi_ids = load_pbi_ids(ado, items)
            print_tasks(items, mode=mode, on_day=day, show_assignee=args.all,
                        pbi_ids=pbi_ids, show_closed=args.closed)
        return 0
    if args.action in {"pbi", "features", "epics", "workitems"}:
        items = list_backlog(ado, args)
        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            print_backlog(items, args.action)
        return 0
    if args.action == "show":
        show_item(ado, args.id)
        return 0
    if args.action == "dashboard":
        from .dashboard import execute_dashboard
        return execute_dashboard(ado, cfg, args)
    if args.action == "start":
        do_start(ado, cfg, args.id)
        return 0
    if args.action in ("current", "status"):
        current_branch = g.branch()
        print("Branch atual:", current_branch)
        try:
            work_id = current_item_id()
        except DevError:
            print("Sem Task vinculada ao nome da branch.")
            return 0
        item = ado.get_item(work_id)
        fields = item.get("fields", {})
        print(f"{fields.get('System.WorkItemType', 'Item')} #{work_id}: {fields.get('System.Title', '')} | {fields.get('System.State', '')}")
        if args.action == "status":
            print("Alterações locais:\n" + (g.git("status", "--short") or "Nenhuma"))
            pr = ado.active_pr(current_branch)
            print("PR: " + (ado.pr_web_url(pr["pullRequestId"]) if pr else "Nenhuma PR ativa"))
        return 0
    if args.action == "new":
        day = parse_day(args.date) if args.date else None
        item = ado.create_item(args.title, item_type=args.type, assign=args.assign, day=day, parent_id=args.parent)
        print(f"Criado {args.type} #{item['id']}: {args.title}")
        print(ado.project_url + f"/_workitems/edit/{item['id']}")
        if not args.assign:
            print("Dica: --assign usuario@empresa.com para atribuir a um desenvolvedor.")
        return 0
    if args.action == "plan":
        day = parse_day(args.date)
        for item_id in args.ids:
            ado.plan_item(item_id, day)
            print(f"Work Item #{item_id} planejado para {day.isoformat()}.")
        return 0
    if args.action == "assign":
        ado.update_field(args.id, "System.AssignedTo", args.email)
        print(f"Work Item #{args.id} atribuído a {args.email}.")
        return 0
    if args.action == "save":
        config_guard(cfg)
        work_id = current_item_id()
        ensure_task(ado.get_item(work_id))
        created = g.commit_and_push(cfg["remote"], work_id, args.message, yes=args.yes)
        print("Commit criado e enviado." if created else "Nada a commitar; branch enviada.")
        return 0
    if args.action == "finish":
        do_finish(ado, cfg, message=args.message, yes=args.yes)
        return 0
    raise DevError("Comando desconhecido.")


if __name__ == "__main__":
    raise SystemExit(main())

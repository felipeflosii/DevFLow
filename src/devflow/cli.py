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
    DevError, ado_remote, assignee_name, branch_for, branch_work_id, filter_items,
    item_type, parent_id, parse_day, read_config, render_table, save_config,
    scheduled_day, short_assignee, truncate,
)
from . import gitops as g


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

    sub.add_parser("config", help="Mostrar configuração deste repositório")
    sub.add_parser("doctor", help="Diagnosticar Git, remoto e autenticação")
    sub.add_parser("sync", help="git fetch origin --prune sem mudar de branch")
    sub.add_parser("main", help="Buscar atualizações remotas e trocar para a branch principal configurada")

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

    s = sub.add_parser("show", help="Exibir os detalhes e a hierarquia Epic > Feature > PBI > Task")
    s.add_argument("id", type=int, help="ID de qualquer Work Item")

    sub.add_parser("dashboard", help="Selecionar uma Task em menu interativo")
    s = sub.add_parser("start", help="Criar/retomar branch de Task atribuída a você")
    s.add_argument("id", type=int)

    sub.add_parser("current", help="Mostrar branch e Task atual")
    sub.add_parser("status", help="Mostrar Task, Git e PR em aberto")

    s = sub.add_parser("new", help="Criar uma Task para alguém, opcionalmente agendada")
    s.add_argument("title", help="Título da tarefa")
    s.add_argument("--assign", metavar="EMAIL", help="Usuário do Azure Boards")
    s.add_argument("--date", metavar="AAAA-MM-DD", help="Data planejada")
    s.add_argument("--type", default="Task", help="Tipo Azure Boards, ex.: Task, Bug")

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
        class Scope:
            date = None
            all = False
            mine = False
            week = False
            today = False
            closed = False
            area = None
        items, mode, day = my_tasks(ado, Scope())
        print_tasks(items, mode=mode, on_day=day, pbi_ids=load_pbi_ids(ado, items))
        if items:
            chosen = input("\nDigite o ID para iniciar (Enter para sair): ").strip()
            if chosen:
                if not chosen.isdigit() or int(chosen) not in {int(i["id"]) for i in items}:
                    raise DevError("Escolha um ID que apareceu na tabela.")
                do_start(ado, cfg, int(chosen))
        return 0
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
        item = ado.create_item(args.title, item_type=args.type, assign=args.assign, day=day)
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

"""Interface de linha de comando do DevFlow (execucao: dev)."""
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
    DevError, ado_remote, branch_for, branch_work_id, filter_items, parse_day,
    read_config, render_table, save_config, scheduled_day,
)
from . import gitops as g


def parser_build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dev", description="Azure Boards + Azure Repos + Git no terminal")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="action", required=True)

    s = sub.add_parser("init", help="Configurar este repositorio (sem armazenar token)")
    s.add_argument("--org", help="Nome da organizacao do Azure DevOps")
    s.add_argument("--project", help="Nome do projeto Azure DevOps")
    s.add_argument("--repo", help="Nome do repositorio Azure Repos")
    s.add_argument("--base", default="main", help="Branch base [main]")
    s.add_argument("--remote", default="origin", help="Remote Git [origin]")

    sub.add_parser("config", help="Mostrar configuracao deste repositorio")
    sub.add_parser("doctor", help="Diagnosticar Git, remoto e autenticacao")
    sub.add_parser("sync", help="git fetch --prune sem modificar arquivos locais")

    s = sub.add_parser("tasks", help="Mostrar tarefas atribuídas ao usuario logado")
    scope = s.add_mutually_exclusive_group()
    scope.add_argument("--all", action="store_true", help="Todas as tarefas abertas, inclusive sem data")
    scope.add_argument("--week", action="store_true", help="Tarefas ate o fim da semana e atrasadas")
    scope.add_argument("--date", metavar="AAAA-MM-DD", help="Tarefas apenas nesta data")
    s.add_argument("--json", action="store_true", help="Saida JSON para scripts")

    sub.add_parser("dashboard", help="Selecionar tarefa em menu interativo")
    s = sub.add_parser("start", help="Criar/retomar branch da tarefa atribuida")
    s.add_argument("id", type=int)

    sub.add_parser("current", help="Mostrar branch e tarefa atual")
    s = sub.add_parser("status", help="Mostrar tarefa, Git e PR em aberto")

    s = sub.add_parser("new", help="Criar tarefa para alguem, opcionalmente agendada")
    s.add_argument("title", help="Titulo da tarefa")
    s.add_argument("--assign", metavar="EMAIL", help="Usuario do Azure Boards")
    s.add_argument("--date", metavar="AAAA-MM-DD", help="Data planejada")
    s.add_argument("--type", default="Task", help="Tipo Azure Boards, ex.: Task, Bug")

    s = sub.add_parser("plan", help="Planejar uma ou mais tarefas com tag devday:AAA-MM-DD")
    s.add_argument("ids", metavar="ID", type=int, nargs="+")
    s.add_argument("--date", required=True, metavar="AAAA-MM-DD")

    s = sub.add_parser("assign", help="Atribuir Task existente a desenvolvedor")
    s.add_argument("id", type=int)
    s.add_argument("email")

    s = sub.add_parser("save", help="Commit + push com referencia AB#ID")
    s.add_argument("message", help="Mensagem do commit")
    s.add_argument("--yes", action="store_true", help="Confirmar inclusao de todos os arquivos automaticamente")

    s = sub.add_parser("finish", help="Commit pendente, push e criar PR vinculada a Task")
    s.add_argument("-m", "--message", help="Mensagem do commit, se existirem arquivos alterados")
    s.add_argument("--yes", action="store_true", help="Confirmar inclusao de todos os arquivos automaticamente")

    return p


def client(cfg: dict) -> AzureDevOps:
    return AzureDevOps(cfg["org"], cfg["project"], cfg["repo"])


def config_guard(cfg: dict) -> None:
    """Bloqueia operacoes Git se remote for outro projeto/repo."""
    remote = g.remote_url(cfg["remote"])
    parsed = ado_remote(remote)
    if not parsed:
        raise DevError("O remote nao e um Azure Repos reconhecido. Esta versao integra Azure Repos, nao GitHub.")
    for field in ("org", "project", "repo"):
        if parsed[field].casefold() != cfg[field].casefold():
            raise DevError(f"Configuracao/remote divergente em {field}: remote={parsed[field]!r}, configurado={cfg[field]!r}.")


def print_tasks(items: list[dict], *, mode: str, on_day: date) -> None:
    title = {"today": "Tarefas de hoje + atrasadas", "week": "Tarefas desta semana + atrasadas",
             "all": "Todas as minhas tarefas abertas", "date": f"Tarefas de {on_day.isoformat()}"}[mode]
    print("\n" + title)
    print("=" * len(title))
    if not items:
        print("Nenhuma tarefa encontrada. Veja 'dev tasks --all' ou agende com 'dev plan ID --date AAAA-MM-DD'.")
        return
    rows = []
    for item in items:
        f = item.get("fields", {})
        day = scheduled_day(f)
        when = day.isoformat() if day else "sem data"
        if day and day < on_day:
            when += " (!)"
        rows.append([str(item["id"]), str(f.get("System.WorkItemType", "")),
                     str(f.get("System.State", "")), when, str(f.get("System.Title", ""))[:65]])
    print(render_table(["ID", "Tipo", "Estado", "Planejada", "Titulo"], rows))
    print("\nUse: dev start <ID>")


def my_tasks(ado: AzureDevOps, args) -> tuple[list[dict], str, date]:
    day = parse_day(args.date) if getattr(args, "date", None) else date.today()
    mode = "date" if getattr(args, "date", None) else (
        "all" if getattr(args, "all", False) else "week" if getattr(args, "week", False) else "today")
    items = filter_items(ado.assigned_items(), mode=mode, on_day=day)
    return items, mode, day


def do_start(ado: AzureDevOps, cfg: dict, item_id: int) -> None:
    if item_id <= 0:
        raise DevError("ID de tarefa deve ser positivo.")
    # Evita criar branch para tarefa de outro dev. Consulta WIQL como usuario autenticado.
    if item_id not in ado.assigned_ids():
        raise DevError(f"A Task #{item_id} nao esta atribuida a sua conta autenticada no Azure Boards.")
    item = ado.get_item(item_id)
    if str(item.get("fields", {}).get("System.State", "")).lower() in {"done", "closed", "removed", "completed"}:
        raise DevError("A tarefa ja esta encerrada no Azure Boards.")
    config_guard(cfg)
    wanted = branch_for(item)
    action = g.switch_task(cfg["remote"], cfg["base"], wanted)
    print(f"\nBranch {wanted} ({action}), publicada em {cfg['remote']}.")
    try:
        ado.add_artifact_link(item_id, "Branch", wanted)
        print(f"Azure Boards: branch associada a Task #{item_id}.")
    except DevError as exc:
        print(f"AVISO: branch criada, mas associacao com Boards falhou: {exc}", file=sys.stderr)
    try:
        state = ado.move_to_in_progress(item)
        if state:
            print(f"Tarefa em estado: {state}.")
        else:
            print("Estado nao alterado: nao existe transicao conhecida para Doing/In Progress/Active.")
    except DevError as exc:
        print(f"AVISO: nao consegui atualizar estado no Boards: {exc}", file=sys.stderr)
    print("Proximo passo: desenvolva, depois execute 'dev finish'.")


def current_item_id() -> int:
    return branch_work_id(g.branch())


def do_finish(ado: AzureDevOps, cfg: dict, *, message: str | None, yes: bool) -> None:
    config_guard(cfg)
    item_id = current_item_id()
    item = ado.get_item(item_id)
    branch = g.branch()
    existing = ado.active_pr(branch)
    if existing:
        raise DevError(f"Ja existe PR ativa para esta branch: {ado.pr_web_url(existing['pullRequestId'])}")
    # So acontece aqui se tiver alteracoes; nunca aplica merge ou checkout.
    if g.git("status", "--porcelain") and not message:
        message = str(item.get("fields", {}).get("System.Title", "Implementar tarefa"))
    if message is not None:
        was_committed = g.commit_and_push(cfg["remote"], item_id, message, yes=yes)
        print("Commit criado e enviado." if was_committed else "Sem novos arquivos; branch enviada.")
    else:
        g.git("push", "-u", cfg["remote"], branch, capture=False)
    g.sync(cfg["remote"])
    g.ensure_base(cfg["remote"], cfg["base"])
    ahead = int(g.git("rev-list", "--count", f"{cfg['remote']}/{cfg['base']}..HEAD"))
    if ahead == 0:
        raise DevError("Nenhum commit novo em relacao a branch base. Nao criei PR vazia.")
    title = str(item.get("fields", {}).get("System.Title", "Tarefa"))
    pr = ado.create_pr(branch, cfg["base"], title, item_id)
    pr_id = int(pr["pullRequestId"])
    print(f"\nPR #{pr_id} criada: {ado.pr_web_url(pr_id)}")
    try:
        ado.add_artifact_link(item_id, "Pull Request", str(pr_id))
        print(f"PR vinculada a Task #{item_id}.")
    except DevError as exc:
        print(f"AVISO: PR criada, mas vinculo com Boards falhou: {exc}", file=sys.stderr)
    print("A PR ficou aguardando revisao. O comando NAO faz merge nem ignora politicas da main.")


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except (DevError, EOFError, KeyboardInterrupt) as exc:
        print("\nErro: " + (str(exc) or "operacao interrompida."), file=sys.stderr)
        return 1


def run(argv: list[str] | None = None) -> int:
    args = parser_build().parse_args(argv)
    root = g.git_root()
    os.chdir(root)  # Os comandos Git sempre operam na raiz do repositorio.
    if args.action == "init":
        remote = g.remote_url(args.remote)
        detected = ado_remote(remote) or {}
        data = {"org": args.org or detected.get("org"),
                "project": args.project or detected.get("project"),
                "repo": args.repo or detected.get("repo"),
                "base": args.base, "remote": args.remote}
        if not all(data.values()):
            raise DevError("Nao detectei Azure Repos. Informe --org, --project e --repo explicitamente.")
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
        print("Referencias atualizadas. Nenhuma branch local sofreu merge/rebase/reset.")
        return 0
    ado = client(cfg)
    if args.action == "doctor":
        print(f"DevFlow {__version__} | Git: {shutil.which('git') or 'ausente'} | Azure CLI: {shutil.which('az') or 'nao instalada'}")
        config_guard(cfg)
        print("Remote Azure Repos: OK")
        user = ado.identity()
        print("Usuario Azure Boards: " + str(user.get("uniqueName") or user.get("providerDisplayName") or "conectado"))
        print("Projeto: " + ado.project_id())
        print("Repositorio: " + ado.repo_id())
        print("Diagnostico concluido. Teste 'dev tasks --all'.")
        return 0
    if args.action == "tasks":
        items, mode, day = my_tasks(ado, args)
        if args.json:
            print(json.dumps(items, ensure_ascii=False, indent=2))
        else:
            print_tasks(items, mode=mode, on_day=day)
        return 0
    if args.action == "dashboard":
        class Scope:
            date = None
            all = False
            week = False
        items, mode, day = my_tasks(ado, Scope())
        print_tasks(items, mode=mode, on_day=day)
        if items:
            chosen = input("\nDigite o ID para iniciar (Enter para sair): ").strip()
            if chosen:
                if not chosen.isdigit() or int(chosen) not in {int(i['id']) for i in items}:
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
        print(f"Task #{work_id}: {fields.get('System.Title', '')} | {fields.get('System.State', '')}")
        if args.action == "status":
            print("Alteracoes locais:\n" + (g.git("status", "--short") or "Nenhuma"))
            pr = ado.active_pr(current_branch)
            print("PR: " + (ado.pr_web_url(pr["pullRequestId"]) if pr else "Nenhuma PR ativa"))
        return 0
    if args.action == "new":
        day = parse_day(args.date) if args.date else None
        item = ado.create_item(args.title, item_type=args.type, assign=args.assign, day=day)
        print(f"Criada Task #{item['id']}: {args.title}")
        print(ado.project_url + f"/_workitems/edit/{item['id']}")
        if not args.assign:
            print("Dica: --assign usuario@empresa.com para atribuir a um desenvolvedor.")
        return 0
    if args.action == "plan":
        day = parse_day(args.date)
        for item_id in args.ids:
            ado.plan_item(item_id, day)
            print(f"Task #{item_id} planejada para {day.isoformat()}.")
        return 0
    if args.action == "assign":
        ado.update_field(args.id, "System.AssignedTo", args.email)
        print(f"Task #{args.id} atribuida a {args.email}.")
        return 0
    if args.action == "save":
        config_guard(cfg)
        work_id = current_item_id()
        created = g.commit_and_push(cfg["remote"], work_id, args.message, yes=args.yes)
        print("Commit criado e enviado." if created else "Nada a commitar; branch enviada.")
        return 0
    if args.action == "finish":
        do_finish(ado, cfg, message=args.message, yes=args.yes)
        return 0
    raise DevError("Comando desconhecido.")


if __name__ == "__main__":
    raise SystemExit(main())

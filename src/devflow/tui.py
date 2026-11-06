"""Dashboard interativo em tela cheia (prompt_toolkit).

Leitura dos dados via mesma camada de negócios que --view/--json.
Nada é escrito no Azure ao navegar. Ação 'start' exige confirmação após sair da TUI.
"""
from __future__ import annotations

import asyncio
import json
import textwrap
from dataclasses import dataclass, field
from typing import Any

from .dashboard import collect_view
from .core import DevError


# Teclas 1..8 selecionam uma visão quando o foco NÃO está na caixa de busca.
SECTIONS = (
    ("summary", False, False, "Resumo"),
    ("tasks", False, False, "Minhas Tasks"),
    ("tasks", True, False, "Equipe"),
    ("prs", False, False, "Pull Requests"),
    ("sprint", False, False, "Sprint"),
    ("pipelines", False, False, "Pipelines"),
    ("builds", False, False, "Builds"),
    ("builds", False, True, "Falhas de CI"),
)


def entries(view: str, data: dict) -> list[dict]:
    """Converte resultados em linhas selecionáveis sem expor respostas REST inteiras."""
    if view == "summary":
        return [
            {"id": "Tasks", "title": "Tasks abertas", "value": data.get("tasks")},
            {"id": "PRs", "title": "Pull Requests ativas", "value": data.get("pullRequests")},
            {"id": "Sprint", "title": "Sprint atual", "value": data.get("sprint")},
            {"id": "CI", "title": "Builds recentes", "value": data.get("ci")},
        ]
    if view == "tasks":
        return [{**x, "name": f"#{x.get('id', '?')}  {x.get('title', '')}"} for x in data.get("tasks", [])]
    if view == "prs":
        return [{**x, "name": f"PR #{x.get('id', '?')}  {x.get('title', '')}"} for x in data.get("pullRequests", [])]
    if view == "sprint":
        return [{"id": "Sprint", "name": data.get("name") or "Sem Sprint", **data}]
    if view == "pipelines":
        return [{**x, "name": f"#{x.get('id', '?')}  {x.get('name', '')}"} for x in data.get("pipelines", [])]
    return [{**x, "name": f"#{x.get('id', '?')}  {x.get('pipeline', '')}"} for x in data.get("builds", [])]


def row_label(entry: dict) -> str:
    return str(entry.get("name") or entry.get("title") or entry.get("id") or "—")


def preview_text(section: tuple, record: dict | None, detail: dict | None = None) -> str:
    name = section[3]
    if record is None:
        return f"{name}\n\nNenhum item corresponde à pesquisa.\n\nUse / para buscar, Tab para alternar as visões e F5 para atualizar."
    lines = [name, "─" * 42, ""]
    if section[0] == "summary":
        value = record.get("value")
        lines += [str(record.get("title", "")), json.dumps(value, ensure_ascii=False, indent=2) if value else "Informação indisponível."]
    elif section[0] == "tasks":
        lines += [str(record.get("title", "")), "", f"Work Item: #{record.get('id')}", f"Estado: {record.get('state', '—')}",
                  f"Responsável: {record.get('responsible', '—')}", f"PBI pai: #{record['pbi']}" if record.get('pbi') else "PBI pai: —",
                  f"Área: {record.get('area') or '—'}", f"Sprint: {record.get('iteration') or '—'}", f"Planejada: {record.get('plannedDate') or 'sem data'}"]
    elif section[0] == "prs":
        lines += [str(record.get("title", "")), "", f"Pull Request: #{record.get('id')}", f"Estado: {record.get('status') or '—'}",
                  f"Autor: {record.get('author') or '—'}", f"Branch: {record.get('branch') or '—'}",
                  f"Merge: {record.get('mergeStatus') or '—'}", f"Draft: {'Sim' if record.get('draft') else 'Não'}"]
    elif section[0] == "sprint":
        lines += [f"Sprint: {record.get('name') or '—'}", f"Período: {record.get('startDate') or '?'} → {record.get('finishDate') or '?'}",
                  f"Concluídas: {record.get('completed')}/{record.get('total')} ({record.get('percent')}%)"]
    elif section[0] == "pipelines":
        lines += [f"Pipeline: {record.get('name') or '—'}", f"ID: #{record.get('id')}",
                  f"Último build: #{record.get('recentBuild') or '—'}", f"Resultado: {record.get('recentStatus') or '—'}"]
    else:
        lines += [f"Pipeline: {record.get('pipeline') or '—'}", f"Build: #{record.get('id')}",
                  f"Estado: {record.get('status') or '—'}", f"Branch: {record.get('branch') or '—'}"]
    if detail is not None:
        lines += ["", "DETALHES", "─" * 24]
        for key, value in detail.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, indent=2)
            lines.append(f"{key}: {value}")
    lines += ["", "Enter: consultar detalhes | /: pesquisar", "Tab/Shift+Tab: mudar visão | F5: recarregar", "Esc: limpar busca | q/Ctrl+C: sair"]
    return "\n".join(lines)


@dataclass
class DashboardState:
    """Estado desacoplado do terminal para testes de navegação e filtros."""
    section_idx: int = 0
    search: str = ""
    selected: int = 0
    data: dict = field(default_factory=dict)
    detail: dict | None = None
    error: str | None = None
    loading: bool = False

    @property
    def section(self) -> tuple:
        return SECTIONS[self.section_idx]

    @property
    def rows(self) -> list[dict]:
        rows = entries(self.section[0], self.data)
        needle = self.search.strip().casefold()
        if needle:
            rows = [r for r in rows if needle in row_label(r).casefold() or
                    needle in str(r.get("state", "")).casefold() or
                    needle in str(r.get("responsible", "")).casefold()]
        return rows

    @property
    def current(self) -> dict | None:
        rows = self.rows
        return rows[min(self.selected, len(rows) - 1)] if rows else None

    def move(self, delta: int) -> None:
        self.selected = max(0, min(self.selected + delta, len(self.rows) - 1))
        self.detail = None

    def switch(self, index: int) -> None:
        self.section_idx = index % len(SECTIONS)
        self.selected = 0
        self.search = ""
        self.data = {}
        self.detail = None
        self.error = None

    def set_search(self, value: str) -> None:
        self.search = value
        self.selected = 0
        self.detail = None


def fetch_details(ado: Any, view: str, record: dict) -> dict | None:
    """Consulta restrita a registros selecionados, sem mutações."""
    record_id = record.get("id")
    if not isinstance(record_id, int):
        return None
    if view == "tasks":
        item = ado.get_item(record_id, relations=True)
        fields = item.get("fields") or {}
        return {"Tipo": fields.get("System.WorkItemType", "—"),
                "Descrição": fields.get("System.Description", "—"),
                "URL": ado.project_url + f"/_workitems/edit/{record_id}"}
    if view == "prs":
        pr = ado.get_pr(record_id)
        return {"Criada em": pr.get("creationDate") or "—", "Destino": pr.get("targetRefName") or "—",
                "Revisores": ", ".join(str(r.get("displayName", "—")) for r in pr.get("reviewers", [])) or "—",
                "URL": ado.pr_web_url(record_id)}
    if view == "builds":
        build = ado.get_build(record_id)
        return {"Número": build.get("buildNumber") or "—", "Resultado": build.get("result") or "—",
                "Fonte": build.get("sourceBranch") or "—", "URL": ((build.get("_links") or {}).get("web") or {}).get("href") or "—"}
    return None


def launch_dashboard(ado: Any, cfg: dict, *, team: str | None = None) -> None:
    """Executa UI responsiva. Nunca invocada por --view ou por entrada sem TTY."""
    from prompt_toolkit.application import Application
    from prompt_toolkit.buffer import Buffer
    from prompt_toolkit.filters import has_focus
    from prompt_toolkit.formatted_text import ANSI
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, VSplit, Window, Layout, FormattedTextControl, BufferControl, Dimension
    from prompt_toolkit.widgets import Frame
    from prompt_toolkit.styles import Style

    state = DashboardState()
    kb = KeyBindings()
    search_buffer = Buffer(multiline=False)
    list_control = FormattedTextControl(focusable=True)
    app: Application
    request_to_start: int | None = None
    generation = 0
    help_mode = False

    def pretty_lines() -> list[tuple[str, str]]:
        width = 44
        chunks: list[tuple[str, str]] = []
        items = state.rows
        if state.loading:
            return [("class:muted", "  Consultando Azure DevOps…")]
        if state.error:
            return [("class:failure", "  " + state.error[:100])]
        if not items:
            return [("class:muted", "  Nenhum registro encontrado.")]
        for idx, row in enumerate(items):
            raw = row_label(row).replace("\n", " ")
            label = raw[:width - 2] + "…" if len(raw) > width - 1 else raw
            chunks.append(("class:selected" if idx == state.selected else "class:entry", (" ❯ " if idx == state.selected else "   ") + label + "\n"))
        return chunks

    list_control.text = pretty_lines

    def header() -> list[tuple[str, str]]:
        return [("class:brand", " DEVFLOW 1.0.0 "), ("class:muted", "  AZURE DEVOPS  •  TERMINAL WORKSPACE")]

    def navigation() -> list[tuple[str, str]]:
        parts = []
        for idx, section in enumerate(SECTIONS):
            name = f" {idx+1} {section[3]} "
            parts.append(("class:tabactive" if idx == state.section_idx else "class:tab", name))
        return parts

    def right_panel() -> list[tuple[str, str]]:
        if help_mode:
            return [("class:content", "ATALHOS\n\n↑ ↓   Navegar pelos itens\nTab   Próxima seção\nShift+Tab Seção anterior\n1..8  Selecionar seção\n/     Buscar instantaneamente\nEnter Consultar detalhes\nF5    Atualizar\nEsc   Limpar busca\nS     Iniciar Task selecionada (confirmação externa)\n?     Alternar ajuda\nq     Sair\nCtrl+C Sair\n\nNenhuma seleção altera dados no servidor.")]
        if state.loading:
            return [("class:muted", "Carregando dados…")]
        if state.error:
            return [("class:failure", state.error)]
        return [("class:content", preview_text(state.section, state.current, state.detail))]

    def footer() -> list[tuple[str, str]]:
        suffix = ("[Carregando] " if state.loading else "") + ("  Falha de consulta • F5 para tentar novamente" if state.error else "")
        return [("class:footer", " ↑↓ Navegar  / Buscar  Tab Visão  Enter Detalhes  S Iniciar  F5 Atualizar  ? Ajuda  Q Sair " + suffix)]

    search_control = BufferControl(buffer=search_buffer)
    list_window = Window(list_control, wrap_lines=False)
    root = HSplit([
        Window(FormattedTextControl(header), height=1, style="class:top"),
        Window(FormattedTextControl(navigation), height=1, style="class:nav"),
        VSplit([Window(FormattedTextControl(lambda: [("class:search", " / Buscar > ")]), width=13, height=1),
                Window(search_control, height=1, style="class:content")], height=1),
        VSplit([
            Frame(list_window, title="ITENS", width=Dimension(min=24, preferred=47), style="class:panel"),
            Frame(Window(FormattedTextControl(right_panel), wrap_lines=True), title="DETALHES", style="class:panel"),
        ], padding=1),
        Window(FormattedTextControl(footer), height=1, style="class:foot"),
    ])
    style = Style.from_dict({
        "top": "bg:#12212b #e4f2ef", "brand": "bg:#197a70 #ffffff bold", "muted": "#90aaa9",
        "nav": "bg:#163039", "tab": "#a4bbc4", "tabactive": "bg:#1c8079 #ffffff bold",
        "panel": "bg:#0f1c24 #e5f0f0", "entry": "#c5d7d9", "selected": "bg:#225a64 #ffffff bold",
        "content": "#d1e4e2", "search": "#80e2d1 bold", "footer": "#c1dbdb",
        "foot": "bg:#153740", "failure": "#ff8a92 bold",
    })
    app = Application(layout=Layout(root), key_bindings=kb,
                      style=style, full_screen=True, mouse_support=False)
    # Keep the explicit Window reference; Frame is lowered to an HSplit internally.
    app.layout.focus(list_window)

    def invalidate() -> None:
        app.invalidate()

    async def load_view(*, reset: bool = False) -> None:
        nonlocal generation
        if reset:
            state.selected = 0
        generation += 1
        local_gen = generation
        state.loading = True
        state.error = None
        state.detail = None
        invalidate()
        section = state.section
        try:
            data = await asyncio.to_thread(collect_view, ado, view=section[0], all_users=section[1],
                                            failed=section[2], team=team, limit=100)
        except Exception as exc:  # API/network errors are rendered without breaking the TUI
            if generation == local_gen:
                state.error = str(exc)
                state.data = {}
        else:
            if generation == local_gen:
                state.data = data
        finally:
            if generation == local_gen:
                state.loading = False
                invalidate()

    def request_load(reset: bool = False) -> None:
        app.create_background_task(load_view(reset=reset))

    async def load_detail(record: dict, which_view: str, gen: int) -> None:
        try:
            detail = await asyncio.to_thread(fetch_details, ado, which_view, record)
        except Exception as exc:
            detail = {"Falha na consulta": str(exc)}
        if generation == gen and state.current is not None and state.current.get("id") == record.get("id"):
            state.detail = detail
            invalidate()

    @kb.add("up")
    def up(event):
        state.move(-1); invalidate()

    @kb.add("down")
    def down(event):
        state.move(1); invalidate()

    @kb.add("tab")
    def next_section(event):
        state.switch(state.section_idx + 1); search_buffer.text = ""; app.layout.focus(list_window); request_load(reset=True)

    @kb.add("s-tab")
    def previous_section(event):
        state.switch(state.section_idx - 1); search_buffer.text = ""; app.layout.focus(list_window); request_load(reset=True)

    for ix in range(len(SECTIONS)):
        def bind_section(idx):
            @kb.add(str(idx + 1), filter=~has_focus(search_control))
            def switch_section(event):
                state.switch(idx); search_buffer.text = ""; request_load(reset=True)
        bind_section(ix)

    @kb.add("/")
    def focus_search(event):
        app.layout.focus(search_control)

    @kb.add("escape")
    def clear_search(event):
        search_buffer.text = ""; state.set_search(""); app.layout.focus(list_window); invalidate()

    @kb.add("enter", filter=~has_focus(search_control))
    def details(event):
        current = state.current
        if current and not state.loading:
            app.create_background_task(load_detail(current, state.section[0], generation))

    @kb.add("enter", filter=has_focus(search_control))
    def accept_search(event):
        app.layout.focus(list_window)

    @kb.add("f5")
    def refresh(event):
        request_load(reset=False)

    @kb.add("?")
    def help_toggle(event):
        nonlocal help_mode
        help_mode = not help_mode
        invalidate()

    @kb.add("s", filter=~has_focus(search_control))
    def start_task(event):
        nonlocal request_to_start
        record = state.current
        if record and state.section[0] == "tasks" and isinstance(record.get("id"), int):
            request_to_start = int(record["id"])
            event.app.exit()

    @kb.add("q", filter=~has_focus(search_control))
    @kb.add("c-c")
    def quit_dashboard(event):
        event.app.exit()

    def changed(buffer):
        state.set_search(buffer.text)
        invalidate()
    search_buffer.on_text_changed += changed

    app.pre_run_callables.append(lambda: request_load())
    app.run()

    if request_to_start is not None:
        from .cli import do_start
        confirmation = input(f"Iniciar Task #{request_to_start} e trocar de branch? [s/N] ").strip().casefold()
        if confirmation in {"s", "sim", "y", "yes"}:
            do_start(ado, cfg, request_to_start)
        else:
            print("Operação cancelada; nenhuma branch foi modificada.")

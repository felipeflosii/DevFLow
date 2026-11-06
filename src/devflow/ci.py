"""Formatação segura e normalização da observabilidade CI/CD do Azure DevOps.

Funções puras: nenhuma modificação de pipelines, builds, releases ou ambientes.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .core import DevError, render_table, truncate


def checked_limit(value: int, *, maximum: int = 100) -> int:
    if not 1 <= value <= maximum:
        raise DevError(f"O limite deve estar entre 1 e {maximum}.")
    return value


def short_date(value: str | None) -> str:
    if not value or value.startswith("0001-"):
        return "—"
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return instant.strftime("%d/%m %H:%M")
    except ValueError:
        return truncate(value, 16)


def duration(start: str | None, finish: str | None) -> str:
    if not start or not finish:
        return "—"
    try:
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(finish.replace("Z", "+00:00"))
        seconds = max(0, int((b - a).total_seconds()))
    except (ValueError, TypeError):
        return "—"
    if seconds >= 3600:
        return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"
    return f"{seconds // 60}m{seconds % 60:02d}s"


def status_label(status: str | None, result: str | None) -> str:
    """Prioriza resultado somente se a execução terminou."""
    s = str(status or "").casefold()
    r = str(result or "").casefold()
    if s in {"inprogress", "in_progress", "notstarted", "postponed", "pending", "canceling", "queued"}:
        return {"inprogress": "Executando", "in_progress": "Executando", "notstarted": "Na fila",
                "postponed": "Adiado", "pending": "Pendente", "canceling": "Cancelando", "queued": "Na fila"}[s]
    if r == "succeeded":
        return "Sucesso"
    if r == "succeededwithissues" or r == "partiallysucceeded":
        return "Parcial"
    if r in {"failed", "failure"}:
        return "Falhou"
    if r in {"canceled", "cancelled"}:
        return "Cancelado"
    if r == "skipped":
        return "Ignorado"
    if r == "abandoned":
        return "Abandonado"
    if s in {"completed", "finished"}:
        return "Concluído (sem resultado)"
    return status or result or "Desconhecido"


def build_status(build: dict) -> str:
    return status_label(build.get("status"), build.get("result"))


def run_status(run: dict) -> str:
    return status_label(run.get("state"), run.get("result"))


def branch_name(value: str | None) -> str:
    return str(value or "—").removeprefix("refs/heads/")


def web_url(data: dict) -> str | None:
    links = data.get("_links") or {}
    web = links.get("web") or {}
    return web.get("href") or data.get("webAccessUri")


def pipeline_summary(pipelines: list[dict], builds: list[dict]) -> list[dict]:
    """Retorna a amostra de builds; ausência não significa pipeline nunca executada."""
    recent: dict[int, dict] = {}
    for build in builds:
        definition = build.get("definition") or {}
        pid = definition.get("id")
        if pid is not None and int(pid) not in recent:
            recent[int(pid)] = build
    return [{"id": int(p["id"]), "name": str(p.get("name", "")),
             "folder": p.get("folder") or "\\", "recentBuild": recent.get(int(p["id"]))}
            for p in pipelines]


def timeline_summary(timeline: dict) -> dict:
    """Somente campos operacionais: evita imprimir payloads brutos/variáveis secretas."""
    records = timeline.get("records") or []
    rows = []
    failed = []
    for record in records:
        typ = record.get("type")
        if typ not in {"Stage", "Phase", "Job", "Task"}:
            continue
        issues = []
        for issue in (record.get("issues") or []):
            if (issue.get("type") or "").casefold() == "error":
                msg = str(issue.get("message") or "").strip().replace("\r", " ").replace("\n", " ")
                if msg:
                    issues.append(truncate(msg, 200))
        row = {"type": typ, "name": record.get("name", "—"),
               "state": record.get("state"), "result": record.get("result"),
               "status": status_label(record.get("state"), record.get("result")),
               "duration": duration(record.get("startTime"), record.get("finishTime")),
               "errors": issues[:3], "logId": (record.get("log") or {}).get("id")}
        rows.append(row)
        if row["status"] == "Falhou" or issues:
            failed.append(row)
    return {"stages": [r for r in rows if r["type"] == "Stage"],
            "failures": failed, "records": rows}


def deployment_status(deployment: dict) -> str:
    if deployment.get("source") == "classic":
        raw = str(deployment.get("deploymentStatus") or "")
        normal = {"succeeded": "Sucesso", "failed": "Falhou", "inprogress": "Executando",
                  "notdeployed": "Não implantado", "partiallysucceeded": "Parcial", "queued": "Na fila",
                  "pending": "Pendente", "canceled": "Cancelado", "rejected": "Rejeitado"}
        return normal.get(raw.casefold(), raw or "Desconhecido")
    return status_label(None, deployment.get("result"))


def normalize_yaml_deploy(environment: dict, records: list[dict]) -> list[dict]:
    output = []
    for record in records:
        pipeline = record.get("definition") or {}
        owner = record.get("owner") or {}
        output.append({"source": "yaml", "id": record.get("id"),
                       "environment": environment.get("name", "—"),
                       "environmentId": environment.get("id"),
                       "pipeline": pipeline.get("name") or "—", "pipelineId": pipeline.get("id"),
                       "runId": owner.get("id"), "release": None,
                       "stage": record.get("stageName") or record.get("jobName") or "—",
                       "result": record.get("result"),
                       "startTime": record.get("startTime"), "finishTime": record.get("finishTime")})
    return output


def normalize_classic_deploy(records: list[dict]) -> list[dict]:
    output = []
    for record in records:
        definition = record.get("releaseDefinition") or {}
        release = record.get("release") or {}
        environment = record.get("releaseEnvironment") or {}
        output.append({"source": "classic", "id": record.get("id"),
                       "environment": environment.get("name") or "—", "environmentId": environment.get("id"),
                       "pipeline": definition.get("name") or "—", "pipelineId": definition.get("id"),
                       "runId": None, "release": release.get("name"), "releaseId": release.get("id"),
                       "stage": environment.get("name") or "—", "deploymentStatus": record.get("deploymentStatus"),
                       "result": record.get("deploymentStatus"), "startTime": record.get("startedOn"),
                       "finishTime": record.get("completedOn") or record.get("lastModifiedOn"),
                       "url": web_url(release)})
    return output


def print_pipelines(pipelines: list[dict], builds: list[dict], *, sample: int) -> None:
    items = pipeline_summary(pipelines, builds)
    print("\nPipelines — Azure DevOps")
    if not items:
        print("Nenhuma pipeline encontrada para o projeto.")
        return
    rows = [[str(p["id"]), truncate(p["name"], 40),
             (str(p["recentBuild"]["id"]) if p["recentBuild"] else "—"),
             (build_status(p["recentBuild"]) if p["recentBuild"] else "—")]
            for p in items]
    print(render_table(["ID", "Pipeline", "Build (amostra)", "Situação"], rows))
    print(f"\nÚltimo build conhecido entre as {sample} execuções consultadas. '—' não significa que nunca rodou.")
    print("Use: dev runs <PIPELINE_ID> | dev builds --pipeline <PIPELINE_ID>")


def print_builds(builds: list[dict]) -> None:
    print("\nExecuções de Build — Azure DevOps")
    if not builds:
        print("Nenhum build encontrado para este filtro.")
        return
    rows = []
    for b in builds:
        rows.append([str(b.get("id", "")), truncate((b.get("definition") or {}).get("name", "—"), 30),
                     build_status(b), truncate(branch_name(b.get("sourceBranch")), 22),
                     short_date(b.get("queueTime") or b.get("startTime")),
                     duration(b.get("startTime"), b.get("finishTime"))])
    print(render_table(["Build", "Pipeline", "Situação", "Branch", "Início", "Duração"], rows))
    print("\nUse: dev build <BUILD_ID>")


def print_runs(pipeline_id: int, runs: list[dict]) -> None:
    print(f"\nExecuções da Pipeline #{pipeline_id}")
    if not runs:
        print("Nenhuma execução encontrada.")
        return
    rows = [[str(r.get("id", "")), truncate(r.get("name", "—"), 25), run_status(r),
             short_date(r.get("createdDate")), duration(r.get("createdDate"), r.get("finishedDate"))]
            for r in runs]
    print(render_table(["Run", "Nome", "Situação", "Início", "Duração"], rows))
    print(f"\nUse: dev run {pipeline_id} <RUN_ID>")


def print_run_detail(run: dict, timeline: dict | None) -> None:
    print(f"\nPipeline #{(run.get('pipeline') or {}).get('id', '—')} — Run #{run.get('id', '—')}")
    print("Nome:      " + str(run.get("name") or "—"))
    print("Situação:  " + run_status(run))
    print("Criada em: " + short_date(run.get("createdDate")))
    print("Duração:   " + duration(run.get("createdDate"), run.get("finishedDate")))
    link = web_url(run)
    if link:
        print("URL:       " + link)
    if timeline is None:
        print("Stages/tarefas indisponíveis pela API de Build; consulte a execução no Azure Pipelines.")
        return
    summary = timeline_summary(timeline)
    print("\nStages:")
    if summary["stages"]:
        print(render_table(["Stage", "Situação", "Duração"],
                           [[truncate(s["name"], 42), s["status"], s["duration"]] for s in summary["stages"]]))
    else:
        print("Nenhum stage disponível na timeline.")
    if summary["failures"]:
        print("\nEtapas com falha/erros:")
        for r in summary["failures"][:15]:
            print(f"  [{r['type']}] {r['name']} — {r['status']}")
            for error in r["errors"]:
                print("      " + error)
    else:
        print("\nNenhuma falha registrada nas etapas consultadas.")


def print_deploys(deploys: list[dict], *, source: str, errors: list[str] | None = None) -> None:
    print("\nDeploys — Azure DevOps (" + source + ")")
    if not deploys:
        print("Nenhum deploy encontrado para este filtro.")
    else:
        rows = []
        for d in deploys:
            rows.append([str(d.get("source")), truncate(d.get("environment", "—"), 20),
                         truncate(d.get("pipeline", "—"), 26), deployment_status(d),
                         short_date(d.get("startTime")), str(d.get("runId") or d.get("release") or "—")])
        print(render_table(["Tipo", "Ambiente", "Pipeline", "Situação", "Início", "Run/Release"], rows))
    for error in errors or []:
        print("AVISO: " + error)

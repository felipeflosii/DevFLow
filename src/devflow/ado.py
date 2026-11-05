"""Cliente Azure DevOps REST 7.1 (stdlib) com PAT ou token Entra do az login."""
from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .core import DevError, change_plan_tags

_RESOURCE = "499b84ac-1321-427f-aa17-267ca6975798"


def get_auth_headers() -> dict[str, str]:
    pat = os.getenv("ADO_PAT") or os.getenv("AZURE_DEVOPS_EXT_PAT")
    if pat:
        basic = base64.b64encode((":" + pat).encode()).decode()
        return {"Authorization": f"Basic {basic}"}
    try:
        process = subprocess.run(
            ["az", "account", "get-access-token", "--resource", _RESOURCE,
             "--query", "accessToken", "-o", "tsv"],
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError as exc:
        raise DevError("Autenticacao ausente: instale Azure CLI e execute 'az login', ou defina ADO_PAT.") from exc
    if process.returncode or not process.stdout.strip():
        raise DevError("Nao foi possivel obter token Azure DevOps. Execute 'az login' com o tenant correto "
                       "ou defina ADO_PAT. Detalhes: " + process.stderr.strip()[:350])
    return {"Authorization": "Bearer " + process.stdout.strip()}


class AzureDevOps:
    def __init__(self, org: str, project: str, repo: str):
        self.org = org.strip("/")
        self.project = project
        self.repo = repo
        self.base = f"https://dev.azure.com/{urllib.parse.quote(self.org, safe='')}"
        self.project_url = self.base + "/" + urllib.parse.quote(project, safe="")
        self._headers: dict[str, str] | None = None
        self._project_id: str | None = None
        self._repo_id: str | None = None

    def request(self, method: str, api_path: str, *, body: Any = None, params: dict | None = None,
                patch: bool = False, project: bool = True, version: str = "7.1") -> Any:
        values = {"api-version": version}
        values.update(params or {})
        root = self.project_url if project else self.base
        url = root + "/" + api_path.lstrip("/") + "?" + urllib.parse.urlencode(values)
        if self._headers is None:
            self._headers = get_auth_headers()
        headers = {**self._headers, "Accept": "application/json", "User-Agent": "DevFlow/0.1"}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json-patch+json" if patch else "application/json"
        req = urllib.request.Request(url, headers=headers, data=data, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                content = response.read()
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as exc:
            content = exc.read().decode("utf-8", errors="replace")[:1200]
            try:
                data = json.loads(content)
                detail = data.get("message") or data.get("Message") or content
            except ValueError:
                detail = content
            raise DevError(f"Azure DevOps HTTP {exc.code} em {method} {api_path}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise DevError(f"Sem conexao com Azure DevOps: {exc}") from exc

    def identity(self) -> dict:
        result = self.request("GET", "_apis/connectionData", project=False, version="7.1-preview.1")
        user = result.get("authenticatedUser") or {}
        if not user:
            raise DevError("Azure DevOps nao retornou o usuario autenticado.")
        return user

    def project_id(self) -> str:
        if not self._project_id:
            result = self.request("GET", f"_apis/projects/{urllib.parse.quote(self.project, safe='')}", project=False)
            self._project_id = result["id"]
        return self._project_id

    def repo_id(self) -> str:
        if not self._repo_id:
            repo = urllib.parse.quote(self.repo, safe="")
            result = self.request("GET", f"_apis/git/repositories/{repo}")
            self._repo_id = result["id"]
        return self._repo_id

    def get_item(self, item_id: int, *, relations: bool = False) -> dict:
        params = {"$expand": "relations"} if relations else None
        return self.request("GET", f"_apis/wit/workitems/{item_id}", params=params)

    def assigned_ids(self) -> list[int]:
        identity = self.identity()
        username = identity.get("uniqueName") or identity.get("providerDisplayName")
        if not username:
            raise DevError("Usuario nao possui uniqueName. Use PAT associado a uma conta com identidade Azure Boards.")
        safe_user = str(username).replace("'", "''")
        safe_project = self.project.replace("'", "''")
        wiql = (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{safe_project}' "
            f"AND [System.AssignedTo] = '{safe_user}' "
            "ORDER BY [System.ChangedDate] DESC"
        )
        response = self.request("POST", "_apis/wit/wiql", body={"query": wiql}, params={"$top": 1000})
        return [int(x["id"]) for x in response.get("workItems", [])]

    def assigned_items(self) -> list[dict]:
        result = []
        ids = self.assigned_ids()
        for offset in range(0, len(ids), 200):
            batch = self.request("POST", "_apis/wit/workitemsbatch",
                                 body={"ids": ids[offset:offset + 200], "errorPolicy": "Omit"})
            result.extend(batch.get("value", []))
        return result

    def patch_item(self, item_id: int, changes: list[dict]) -> dict:
        return self.request("PATCH", f"_apis/wit/workitems/{item_id}", body=changes, patch=True)

    def update_field(self, item_id: int, field: str, value: str) -> dict:
        return self.patch_item(item_id, [{"op": "add", "path": "/fields/" + field, "value": value}])

    def plan_item(self, item_id: int, day) -> dict:
        item = self.get_item(item_id)
        current = item.get("fields", {})
        return self.update_field(item_id, "System.Tags", change_plan_tags(current, day))

    def create_item(self, title: str, *, item_type: str = "Task", assign: str | None = None,
                    day=None) -> dict:
        path = f"_apis/wit/workitems/${urllib.parse.quote(item_type, safe='')}"
        changes = [{"op": "add", "path": "/fields/System.Title", "value": title}]
        if assign:
            changes.append({"op": "add", "path": "/fields/System.AssignedTo", "value": assign})
        if day:
            changes.append({"op": "add", "path": "/fields/System.Tags", "value": "devday:" + day.isoformat()})
        return self.request("POST", path, body=changes, patch=True)

    def valid_states(self, item_type: str) -> list[str]:
        path = f"_apis/wit/workitemtypes/{urllib.parse.quote(item_type, safe='')}/states"
        try:
            data = self.request("GET", path)
            return [str(i["name"]) for i in data.get("value", [])]
        except DevError:
            return []

    def move_to_in_progress(self, item: dict) -> str | None:
        fields = item.get("fields", {})
        states = self.valid_states(str(fields.get("System.WorkItemType", "Task")))
        current = str(fields.get("System.State", ""))
        for desired in ("Doing", "In Progress", "Active"):
            target = next((s for s in states if s.lower() == desired.lower()), None)
            if target:
                if current.lower() == target.lower():
                    return current
                self.update_field(int(item["id"]), "System.State", target)
                return target
        return None

    def add_artifact_link(self, item_id: int, kind: str, fragment: str) -> bool:
        """Link Branch/Commit/Pull Request como artefato, idempotente."""
        kind_paths = {"Branch": "Ref", "Commit": "Commit", "Pull Request": "PullRequestId"}
        kind_path = kind_paths[kind]
        project_id = self.project_id()
        repo_id = self.repo_id()
        if kind == "Branch":
            # Em Azure Repos, GB identifica uma Git Branch; %2F tambem e exigido dentro do nome.
            suffix = "GB" + fragment
        else:
            suffix = str(fragment)
        encoded = "%2F".join([
            urllib.parse.quote(project_id, safe=""),
            urllib.parse.quote(repo_id, safe=""),
            urllib.parse.quote(suffix, safe=""),
        ])
        artifact = f"vstfs:///Git/{kind_path}/{encoded}"
        item = self.get_item(item_id, relations=True)
        if any(rel.get("url", "").lower() == artifact.lower() for rel in item.get("relations", [])):
            return False
        self.patch_item(item_id, [{"op": "add", "path": "/relations/-", "value": {
            "rel": "ArtifactLink", "url": artifact,
            "attributes": {"name": kind, "comment": "Associado pelo DevFlow"}
        }}])
        return True

    def active_pr(self, branch: str) -> dict | None:
        path = f"_apis/git/repositories/{urllib.parse.quote(self.repo, safe='')}/pullrequests"
        params = {"searchCriteria.sourceRefName": "refs/heads/" + branch,
                  "searchCriteria.status": "active", "$top": 50}
        result = self.request("GET", path, params=params)
        return next((pr for pr in result.get("value", []) if pr.get("sourceRefName") == "refs/heads/" + branch), None)

    def create_pr(self, branch: str, base: str, title: str, item_id: int) -> dict:
        path = f"_apis/git/repositories/{urllib.parse.quote(self.repo, safe='')}/pullrequests"
        body = {"sourceRefName": "refs/heads/" + branch,
                "targetRefName": "refs/heads/" + base,
                "title": f"AB#{item_id} - {title}"[:200],
                "description": f"Implementacao da tarefa AB#{item_id}.\n\nAzure Boards: {self.project_url}/_workitems/edit/{item_id}"}
        return self.request("POST", path, body=body)

    def pr_web_url(self, pr_id: int) -> str:
        # URL em GUI preserva os nomes do projeto via percent encoding.
        return self.project_url + "/_git/" + urllib.parse.quote(self.repo, safe="") + "/pullrequest/" + str(pr_id)

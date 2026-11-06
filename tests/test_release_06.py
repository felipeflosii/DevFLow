import io
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
from devflow.ado import AzureDevOps
from devflow.cli import parser_build, sprint_status, pick_current_sprint, sprint_summary, show_sprint, run
from devflow.core import DevError
from devflow import __version__


def work_item(wid, typ="Task", status="To Do", parent=False, assigned=None, project="project"):
    f = {"System.Title": f"Tarefa {wid}", "System.WorkItemType": typ,
         "System.State": status, "System.TeamProject": project}
    if assigned:
        f["System.AssignedTo"] = {"displayName": assigned}
    return {"id": wid, "rev": 5, "url": f"https://dev.azure.com/org/_apis/wit/workitems/{wid}", "fields": f}


class Release06Tests(unittest.TestCase):
    def test_version_and_flags(self):
        self.assertEqual(__version__, "0.8.0")
        parser = parser_build()
        self.assertEqual(parser.parse_args(["new", "Criar login", "--parent", "5"]).parent, 5)
        self.assertTrue(parser.parse_args(["claim", "7", "--yes"]).yes)
        self.assertEqual(parser.parse_args(["sprint", "--team", "Backend"]).team, "Backend")

    def test_create_task_links_to_existing_pbi_atomically(self):
        ado = AzureDevOps("org", "project", "repo")
        with patch.object(ado, "get_item", return_value=work_item(5, typ="Product Backlog Item")), \
             patch.object(ado, "request", return_value={"id": 8}) as request:
            result = ado.create_item("Backend JWT", parent_id=5)
        self.assertEqual(result["id"], 8)
        body = request.call_args.kwargs["body"]
        rel = next(op for op in body if op["path"] == "/relations/-")
        self.assertEqual(rel["value"]["rel"], "System.LinkTypes.Hierarchy-Reverse")
        self.assertTrue(rel["value"]["url"].endswith("/5"))
        self.assertTrue(request.call_args.kwargs["patch"])

    def test_create_pbi_parent_feature(self):
        ado = AzureDevOps("org", "project", "repo")
        with patch.object(ado, "get_item", return_value=work_item(4, typ="Feature")), \
             patch.object(ado, "request", return_value={"id": 12}) as request:
            result = ado.create_item("Criar App Services", item_type="Product Backlog Item", parent_id=4)
        self.assertEqual(result["id"], 12)
        self.assertEqual(request.call_args.kwargs["body"][-1]["path"], "/relations/-")

    def test_incompatible_parent_rejected_before_creation(self):
        ado = AzureDevOps("org", "project", "repo")
        with patch.object(ado, "get_item", return_value=work_item(4, typ="Epic")), \
             patch.object(ado, "request") as request:
            with self.assertRaisesRegex(DevError, "deve ter como pai"):
                ado.create_item("Criar App Services", parent_id=4)
        request.assert_not_called()

    def test_other_project_parent_rejected(self):
        ado = AzureDevOps("org", "project", "repo")
        with patch.object(ado, "get_item", return_value=work_item(5, typ="Product Backlog Item", project="foreign")), \
             patch.object(ado, "request") as request:
            with self.assertRaisesRegex(DevError, "projetos diferentes"):
                ado.create_item("Task", parent_id=5)
        request.assert_not_called()

    def test_claim_task_with_optimistic_rev(self):
        ado = AzureDevOps("org", "project", "repo")
        with patch.object(ado, "get_item", return_value=work_item(7)), \
             patch.object(ado, "identity", return_value={"uniqueName": "user@example.com"}), \
             patch.object(ado, "patch_item", return_value={"id": 7}) as patch_item:
            ado.claim_task(7)
        changes = patch_item.call_args.args[1]
        self.assertEqual(changes[0], {"op": "test", "path": "/rev", "value": 5})
        self.assertEqual(changes[1]["value"], "user@example.com")

    def test_claim_rejects_assigned_closed_and_pbi(self):
        ado = AzureDevOps("org", "project", "repo")
        for doc in [work_item(8, assigned="Ana"), work_item(8, status="Done"),
                    work_item(8, typ="Product Backlog Item")]:
            with patch.object(ado, "get_item", return_value=doc), \
                 patch.object(ado, "patch_item") as patch_item:
                with self.assertRaises(DevError):
                    ado.claim_task(8)
                patch_item.assert_not_called()

    def test_claim_requires_revision(self):
        ado = AzureDevOps("org", "project", "repo")
        doc = work_item(8)
        del doc["rev"]
        with patch.object(ado, "get_item", return_value=doc), \
             patch.object(ado, "identity", return_value={"uniqueName": "user@example.com"}), \
             patch.object(ado, "patch_item") as patch_item:
            with self.assertRaisesRegex(DevError, "revisão"):
                ado.claim_task(8)
        patch_item.assert_not_called()

    def test_team_iteration_api_with_team_and_current(self):
        ado = AzureDevOps("org", "project", "repo")
        with patch.object(ado, "request", return_value={"value": [{"id": "sprint-guid"}]}) as request:
            self.assertEqual(len(ado.team_iterations(team="Equipe Backend", current=True)), 1)
        self.assertEqual(request.call_args.args[1], "Equipe%20Backend/_apis/work/teamsettings/iterations")
        self.assertEqual(request.call_args.kwargs["params"], {"$timeframe": "current"})

    def test_sprint_items_dedup_and_batch(self):
        ado = AzureDevOps("org", "project", "repo")
        payload = {"workItemRelations": [{"target": {"id": 7}}, {"target": {"id": 7}},
                                          {"source": {"id": 5}, "target": {"id": 8}}]}
        with patch.object(ado, "request", return_value=payload), patch.object(ado, "get_items", return_value=[work_item(7), work_item(8)]) as fetch:
            self.assertEqual(len(ado.sprint_work_items("it-guid")), 2)
        fetch.assert_called_once_with([7, 8])

    def test_sprint_current_and_summary(self):
        current = {"id": "guid", "name": "Sprint 1", "attributes": {"startDate": "2026-11-05T00:00:00Z", "finishDate": "2026-11-09T00:00:00Z"}}
        future = {"id": "later", "name": "Sprint 2", "attributes": {"startDate": "2026-11-10T00:00:00Z", "finishDate": "2026-11-15T00:00:00Z"}}
        self.assertEqual(sprint_status(current, date(2026, 11, 6)), "Atual")
        self.assertEqual(pick_current_sprint([future, current], date(2026, 11, 6)), current)
        ado = MagicMock()
        ado.sprint_work_items.return_value = [work_item(6), work_item(7, status="Done"), work_item(5, typ="Product Backlog Item")]
        summary = sprint_summary(ado, current)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["percent"], 50)
        output = io.StringIO()
        with redirect_stdout(output):
            show_sprint(summary)
        self.assertIn("1/2 concluídas", output.getvalue())

    def test_claim_cli_no_user_confirmation_with_yes(self):
        cfg = {"org":"org", "project":"project", "repo":"repo", "remote":"origin", "base":"main"}
        ado = MagicMock()
        ado.get_item.return_value = work_item(8)
        out = io.StringIO()
        with patch("devflow.cli.g.git_root", return_value=Path.cwd()), \
             patch("devflow.cli.read_config", return_value=cfg), \
             patch("devflow.cli.client", return_value=ado), \
             patch("builtins.input", side_effect=AssertionError("Não deve perguntar")), \
             redirect_stdout(out):
            self.assertEqual(run(["claim", "8", "--yes"]), 0)
        ado.claim_task.assert_called_once_with(8)

    def test_new_cli_passes_parent(self):
        cfg = {"org":"org", "project":"project", "repo":"repo", "remote":"origin", "base":"main"}
        ado = MagicMock()
        ado.create_item.return_value = {"id": 12}
        ado.project_url = "https://dev.azure.com/org/project"
        with patch("devflow.cli.g.git_root", return_value=Path.cwd()), \
             patch("devflow.cli.read_config", return_value=cfg), \
             patch("devflow.cli.client", return_value=ado), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(run(["new", "Criar script", "--parent", "5"]), 0)
        self.assertEqual(ado.create_item.call_args.kwargs["parent_id"], 5)

    def test_sprint_cli_fallback_to_all_if_current_not_found(self):
        cfg = {"org":"org", "project":"project", "repo":"repo", "remote":"origin", "base":"main"}
        itr = {"id": "guid", "name": "Sprint 1", "attributes": {"startDate": "2026-01-01T00:00:00Z", "finishDate": "2026-12-31T00:00:00Z"}}
        ado = MagicMock()
        ado.team_iterations.side_effect = [[], [itr]]
        ado.sprint_work_items.return_value = [work_item(7)]
        with patch("devflow.cli.g.git_root", return_value=Path.cwd()), \
             patch("devflow.cli.read_config", return_value=cfg), \
             patch("devflow.cli.client", return_value=ado), \
             redirect_stdout(io.StringIO()) as out:
            self.assertEqual(run(["sprint"]), 0)
        self.assertIn("Sprint 1", out.getvalue())
        self.assertEqual(ado.team_iterations.call_count, 2)


if __name__ == "__main__":
    unittest.main()

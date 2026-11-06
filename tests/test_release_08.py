"""Regressão v0.8.0 — dashboard interativo e consultas seguras."""
import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import MagicMock, patch

from devflow import __version__
from devflow.cli import parser_build, run
from devflow.core import DevError
from devflow.dashboard import (
    collect_tasks, collect_prs, collect_sprint, collect_pipelines, collect_builds,
    collect_summary, collect_view, execute_dashboard, filter_task_state,
    interactive_dashboard, render_view, task_rows,
)

CFG = {"org": "org", "project": "Project", "repo": "repo", "remote": "origin", "base": "main"}


def task(ident=6, *, typ="Task", state="To Do", assigned="Luiz Felipe", area="Infraestrutura"):
    return {"id": ident, "fields": {"System.WorkItemType": typ,
                                   "System.Title": f"Task {ident}", "System.State": state,
                                   "System.AssignedTo": {"displayName": assigned} if assigned else None,
                                   "System.AreaPath": "Project\\" + area},
            "relations": [{"rel": "System.LinkTypes.Hierarchy-Reverse",
                           "url": "https://dev.azure.com/org/Project/_apis/wit/workitems/5"}]}


def setup_ado():
    ado = MagicMock()
    ado.assigned_items.return_value = [task(6), task(7, state="In Progress")]
    ado.query_ids.return_value = [6, 7, 8]
    ado.get_items.return_value = [{"id": 5, "fields": {"System.WorkItemType": "Product Backlog Item"}}]
    ado.list_prs.return_value = [{"pullRequestId": 9, "title": "feat: IA",
                                  "status": "active", "createdBy": {"displayName": "Luiz"},
                                  "sourceRefName": "refs/heads/feature/6-ia"}]
    ado.list_builds.return_value = [{"id": 81, "status": "completed", "result": "failed",
                                     "definition": {"id": 9, "name": "Java"},
                                     "sourceBranch": "refs/heads/main"}]
    ado.team_iterations.return_value = [{"id": "guid", "name": "Sprint 1", "path": "Project\\Sprint 1",
                                         "attributes": {"startDate": "2026-11-05", "finishDate": "2026-11-15"}}]
    ado.sprint_work_items.return_value = [task(6), task(7, state="Done")]
    ado.list_pipelines.return_value = [{"id": 9, "name": "Java"}]
    return ado


class DashboardV08Tests(unittest.TestCase):
    def test_version_parser(self):
        self.assertEqual(__version__, "0.8.0")
        p = parser_build()
        args = p.parse_args(["dashboard", "--view", "tasks", "--all", "--state", "To Do",
                             "--area", "Infraestrutura", "--limit", "7", "--json"])
        self.assertEqual(args.view, "tasks")
        self.assertEqual(args.state, "To Do")
        self.assertEqual(args.limit, 7)
        self.assertTrue(args.all)

    def test_task_filter_state_casefold_exact(self):
        items = [task(1), task(2, state="In Progress"), task(3, state="Done")]
        self.assertEqual([i["id"] for i in filter_task_state(items, "TO DO")], [1])
        self.assertEqual([i["id"] for i in filter_task_state(items, None)], [1, 2, 3])
        self.assertEqual(filter_task_state(items, "Doing"), [])

    def test_task_rows_sanitized(self):
        i = task()
        i["fields"]["System.Description"] = "senha=never-print-this"
        data = task_rows([i], pbi_ids={6: 5})
        self.assertEqual(data[0]["pbi"], 5)
        self.assertNotIn("never-print-this", str(data))

    def test_tasks_mine_and_parent(self):
        ado = setup_ado()
        result = collect_tasks(ado)
        self.assertEqual(result["total"], 2)
        self.assertEqual([x["pbi"] for x in result["tasks"]], [5, 5])
        ado.assigned_items.assert_called_once_with(relations=True)
        ado.query_ids.assert_not_called()

    def test_tasks_all_other_assignees_and_filters(self):
        ado = setup_ado()
        ado.get_items.side_effect = [[task(6), task(7, area="Mobile"), task(8, typ="Product Backlog Item")],
                                     [task(5, typ="Product Backlog Item")]]
        result = collect_tasks(ado, all_users=True, area="infraestrutura", state="to do")
        self.assertEqual([t["id"] for t in result["tasks"]], [6])
        self.assertEqual(result["scope"], "project")
        self.assertEqual(result["total"], 1)
        ado.query_ids.assert_called_once_with(item_types={"Task"}, mine=False)

    def test_tasks_parent_verified_not_guessed(self):
        ado = setup_ado()
        ado.get_items.return_value = [task(5, typ="Feature")]
        result = collect_tasks(ado)
        self.assertIsNone(result["tasks"][0]["pbi"])

    def test_tasks_limit_reports_total(self):
        ado = setup_ado()
        result = collect_tasks(ado, limit=1)
        self.assertEqual((result["showing"], result["total"]), (1, 2))

    def test_prs_only_my_active_or_all(self):
        ado = setup_ado()
        data = collect_prs(ado)
        self.assertEqual(data["pullRequests"][0]["branch"], "feature/6-ia")
        ado.list_prs.assert_called_with(status="active", mine=True, limit=20)
        collect_prs(ado, all_users=True)
        ado.list_prs.assert_called_with(status="active", mine=False, limit=20)

    def test_sprint_summary(self):
        ado = setup_ado()
        with patch("devflow.dashboard.date") as mock_day:
            from datetime import date
            mock_day.today.return_value = date(2026, 11, 6)
            data = collect_sprint(ado)
        self.assertEqual(data["name"], "Sprint 1")
        self.assertEqual(data["percent"], 50)
        self.assertEqual(len(data["tasks"]), 2)

    def test_pipelines_builds(self):
        ado = setup_ado()
        pipelines = collect_pipelines(ado)
        self.assertEqual(pipelines["pipelines"][0]["recentStatus"], "Falhou")
        builds = collect_builds(ado, failed=True)
        self.assertEqual(builds["builds"][0]["branch"], "main")
        ado.list_builds.assert_called_with(limit=20, failed=True)

    def test_summary_all_services(self):
        ado = setup_ado()
        from datetime import date
        with patch("devflow.dashboard.date") as mock_day:
            mock_day.today.return_value = date(2026, 11, 6)
            result = collect_summary(ado)
        self.assertEqual(result["tasks"]["open"], 2)
        self.assertEqual(result["pullRequests"]["active"], 1)
        self.assertEqual(result["sprint"]["percent"], 50)
        self.assertEqual(result["ci"]["failedInSample"], 1)
        self.assertEqual(result["warnings"], [])

    def test_summary_partial_failure_not_zero(self):
        ado = setup_ado()
        ado.list_builds.side_effect = DevError("sem acesso ao build")
        ado.team_iterations.side_effect = DevError("sem sprint")
        data = collect_summary(ado)
        self.assertIsNone(data["ci"])
        self.assertIsNone(data["sprint"])
        self.assertEqual(data["tasks"]["open"], 2)
        self.assertIn("indisponível", render_view("summary", data))
        self.assertEqual(len(data["warnings"]), 2)

    def test_invalid_filters_rejected_without_api(self):
        ado = setup_ado()
        for opts in [dict(view="prs", state="To Do"), dict(view="summary", area="Infra"),
                     dict(view="tasks", failed=True), dict(view="builds", limit=0),
                     dict(view="builds", limit=201)]:
            with self.subTest(opts=opts), self.assertRaises(DevError):
                collect_view(ado, **opts)
        ado.list_prs.assert_not_called()

    def test_renderer_does_not_crash_for_empty_views(self):
        self.assertIn("Nenhuma", render_view("tasks", {"scope": "mine", "showing": 0, "total": 0, "tasks": []}))
        self.assertIn("Nenhuma", render_view("prs", {"scope": "mine", "pullRequests": []}))
        self.assertIn("Nenhuma", render_view("pipelines", {"pipelines": []}))
        self.assertIn("Nenhum", render_view("builds", {"failedOnly": False, "builds": []}))

    def test_cli_json_tasks_sanitized(self):
        ado = setup_ado()
        captured = io.StringIO()
        with patch("devflow.cli.g.git_root", return_value=Path.cwd()), \
             patch("devflow.cli.read_config", return_value=CFG), \
             patch("devflow.cli.client", return_value=ado), redirect_stdout(captured):
            self.assertEqual(run(["dashboard", "--view", "tasks", "--json"]), 0)
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed["tasks"][0]["pbi"], 5)
        self.assertNotIn("System.AssignedTo", captured.getvalue())

    def test_cli_pr_filter_and_non_interactive_summary(self):
        ado = setup_ado()
        out = io.StringIO()
        with patch("devflow.cli.g.git_root", return_value=Path.cwd()), \
             patch("devflow.cli.read_config", return_value=CFG), \
             patch("devflow.cli.client", return_value=ado), \
             patch("devflow.dashboard.sys.stdin.isatty", return_value=False), \
             redirect_stdout(out):
            self.assertEqual(run(["dashboard"]), 0)
        self.assertIn("Modo não interativo", out.getvalue())

    def test_interactive_view_filters_and_exit(self):
        ado = setup_ado()
        actions = iter(['t state="To Do" area=Infraestrutura', 'p', 'q'])
        out = io.StringIO()
        with redirect_stdout(out):
            interactive_dashboard(ado, CFG, input_fn=lambda _: next(actions))
        self.assertIn("Tasks — mine", out.getvalue())
        self.assertIn("Pull Requests ativas", out.getvalue())

    def test_interactive_dangerous_start_requires_confirmation(self):
        ado = setup_ado()
        prompts = iter(['start 6', 'n', 'q'])
        with patch("devflow.cli.do_start") as do_start, redirect_stdout(io.StringIO()):
            interactive_dashboard(ado, CFG, input_fn=lambda _: next(prompts))
        do_start.assert_not_called()

    def test_interactive_confirmed_start_once_and_exits(self):
        ado = setup_ado()
        prompts = iter(['start 6', 's'])
        with patch("devflow.cli.do_start") as do_start, redirect_stdout(io.StringIO()):
            interactive_dashboard(ado, CFG, input_fn=lambda _: next(prompts))
        do_start.assert_called_once_with(ado, CFG, 6)

    def test_interactive_bad_filters_dont_crash(self):
        ado = setup_ado()
        prompts = iter(['t wrongfilter', 't state=ToDo', 'q'])
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            interactive_dashboard(ado, CFG, input_fn=lambda _: next(prompts))

    def test_json_requires_view_and_filter_requires_view(self):
        ado = setup_ado()
        args = parser_build().parse_args(['dashboard', '--json'])
        with self.assertRaises(DevError):
            execute_dashboard(ado, CFG, args)
        args = parser_build().parse_args(['dashboard', '--state', 'To Do'])
        with self.assertRaises(DevError):
            execute_dashboard(ado, CFG, args)


if __name__ == '__main__':
    unittest.main()

class DashboardTeamSummaryTests(unittest.TestCase):
    def test_project_summary_shows_project_data(self):
        ado = setup_ado()
        ado.get_items.return_value = [task(6), task(7), task(8, typ="Feature")]
        data = collect_summary(ado, all_users=True)
        self.assertEqual(data["scope"], "project")
        self.assertEqual(data["tasks"]["open"], 2)
        self.assertIn("do projeto", render_view("summary", data))
        ado.list_prs.assert_called_with(status="active", mine=False, limit=100)

    def test_all_is_rejected_for_unrelated_view(self):
        with self.assertRaises(DevError):
            collect_view(setup_ado(), view="pipelines", all_users=True)

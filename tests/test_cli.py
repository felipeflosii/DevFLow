import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from devflow.cli import (do_start, ensure_task, load_pbi_ids, my_tasks,
                         parser_build, print_tasks, show_item)
from devflow.core import DevError


def item(i, typ="Task", state="To Do", title="Teste", assigned="Luiz Felipe", parent=None):
    fields = {"System.WorkItemType": typ, "System.State": state,
              "System.Title": title, "System.AssignedTo": {"displayName": assigned}}
    x = {"id":i, "fields":fields}
    if parent:
        x["relations"] = [{"rel":"System.LinkTypes.Hierarchy-Reverse",
                           "url":f"https://dev.azure.com/org/project/_apis/wit/workitems/{parent}"}]
    return x


class CliTests(unittest.TestCase):
    def test_version_and_parser(self):
        from devflow import __version__
        self.assertEqual(__version__, "1.0.0")
        parsed = parser_build().parse_args(["tasks"])
        self.assertFalse(parsed.all)
        self.assertFalse(parsed.mine)
        self.assertFalse(parsed.today)
        self.assertTrue(parser_build().parse_args(["tasks", "--all"]).all)
        self.assertEqual(parser_build().parse_args(["main"]).action, "main")

    def test_main_runs_git_flow_without_calling_azure_api(self):
        from devflow.cli import run
        from pathlib import Path
        config = {"org": "Example", "project": "Dev", "repo": "api", "remote": "origin", "base": "main"}
        output = io.StringIO()
        with patch("devflow.cli.g.git_root", return_value=Path.cwd()), \
             patch("devflow.cli.read_config", return_value=config), \
             patch("devflow.cli.config_guard"), \
             patch("devflow.cli.g.switch_base", return_value="selecionada") as switch, \
             patch("devflow.cli.client") as client, redirect_stdout(output):
            self.assertEqual(run(["main"]), 0)
        switch.assert_called_once_with("origin", "main")
        client.assert_not_called()
        self.assertIn("Nenhum pull", output.getvalue())

    def test_finish_returns_to_main_after_creating_pr(self):
        from devflow.cli import do_finish
        ado = MagicMock()
        ado.get_item.return_value = item(7)
        ado.active_pr.return_value = None
        ado.create_pr.return_value = {"pullRequestId": 42}
        ado.pr_web_url.return_value = "https://dev.azure.com/org/proj/pr/42"
        actions = []
        def fake_switch(remote, base):
            actions.append(("switch", remote, base))
            return "selecionada"
        def fake_pr(*args):
            actions.append(("create_pr",) + args)
            return {"pullRequestId": 42}
        ado.create_pr.side_effect = fake_pr
        cfg = {"org":"org", "project":"proj", "repo":"api", "base":"main", "remote":"origin"}
        buf = io.StringIO()
        with patch("devflow.cli.config_guard"), \
             patch("devflow.cli.g.branch", return_value="feature/7-provisionamento-dotnet"), \
             patch("devflow.cli.g.git", side_effect=lambda *args, **kwargs: "2" if args[:2] == ("rev-list", "--count") else ""), \
             patch("devflow.cli.g.sync"), \
             patch("devflow.cli.g.ensure_base"), \
             patch("devflow.cli.g.switch_base", side_effect=fake_switch), \
             redirect_stdout(buf):
            do_finish(ado, cfg, message=None, yes=False)
        self.assertEqual([a[0] for a in actions], ["create_pr", "switch"])
        self.assertEqual(actions[-1], ("switch", "origin", "main"))
        self.assertIn("PR #42 criada", buf.getvalue())
        self.assertIn("Branch principal main", buf.getvalue())
        self.assertIn("sem pull", buf.getvalue())

    def test_finish_branch_switch_failure_does_not_erase_created_pr(self):
        from devflow.cli import do_finish
        ado = MagicMock()
        ado.get_item.return_value = item(7)
        ado.active_pr.return_value = None
        ado.create_pr.return_value = {"pullRequestId": 42}
        ado.pr_web_url.return_value = "https://dev.azure.com/org/proj/pr/42"
        cfg = {"org":"org", "project":"proj", "repo":"api", "base":"main", "remote":"origin"}
        output, errors = io.StringIO(), io.StringIO()
        with patch("devflow.cli.config_guard"), \
             patch("devflow.cli.g.branch", return_value="feature/7-provisionamento-dotnet"), \
             patch("devflow.cli.g.git", side_effect=lambda *args, **kwargs: "2" if args[:2] == ("rev-list", "--count") else ""), \
             patch("devflow.cli.g.sync"), \
             patch("devflow.cli.g.ensure_base"), \
             patch("devflow.cli.g.switch_base", side_effect=DevError("alterações locais")), \
             redirect_stdout(output), redirect_stderr(errors):
            do_finish(ado, cfg, message=None, yes=False)
        self.assertIn("PR #42 criada", output.getvalue())
        self.assertIn("PR #42 foi criada", errors.getvalue())
        self.assertIn("dev main", errors.getvalue())

    def test_finish_does_not_switch_if_pr_not_created(self):
        from devflow.cli import do_finish
        ado = MagicMock()
        ado.get_item.return_value = item(7)
        ado.active_pr.return_value = None
        ado.create_pr.side_effect = DevError("falha no Azure DevOps")
        cfg = {"org":"org", "project":"proj", "repo":"api", "base":"main", "remote":"origin"}
        with patch("devflow.cli.config_guard"), \
             patch("devflow.cli.g.branch", return_value="feature/7-provisionamento-dotnet"), \
             patch("devflow.cli.g.git", side_effect=lambda *args, **kwargs: "2" if args[:2] == ("rev-list", "--count") else ""), \
             patch("devflow.cli.g.sync"), \
             patch("devflow.cli.g.ensure_base"), \
             patch("devflow.cli.g.switch_base") as sw:
            with self.assertRaisesRegex(DevError, "falha no Azure DevOps"):
                do_finish(ado, cfg, message=None, yes=False)
        sw.assert_not_called()

    def test_default_is_all_my_open_tasks_even_without_dates(self):
        ado = MagicMock()
        ado.assigned_items.return_value = [item(5, typ="Product Backlog Item"), item(6),
                                           item(7, state="In Progress"), item(8, state="Done")]
        args = parser_build().parse_args(["tasks"])
        items, mode, day = my_tasks(ado, args)
        self.assertEqual(mode, "all")
        self.assertEqual([x["id"] for x in items], [6, 7])
        ado.assigned_items.assert_called_once_with(relations=True)
        ado.query_ids.assert_not_called()

    def test_today_requires_explicit_flag(self):
        ado = MagicMock()
        ado.assigned_items.return_value = [item(6), item(7)]
        args = parser_build().parse_args(["tasks", "--today"])
        items, mode, _ = my_tasks(ado, args)
        self.assertEqual(mode, "today")
        self.assertEqual(items, [])

    def test_all_queries_entire_project(self):
        ado = MagicMock()
        ado.query_ids.return_value = [6, 7, 8]
        ado.get_items.return_value = [item(6), item(7, assigned="Maria Souza"), item(8, assigned="")]
        args = parser_build().parse_args(["tasks", "--all"])
        tasks, mode, _ = my_tasks(ado, args)
        self.assertEqual(len(tasks), 3)
        self.assertEqual(mode, "all")
        ado.query_ids.assert_called_once_with(item_types={"Task"}, mine=False, include_closed=False)
        ado.get_items.assert_called_once_with([6, 7, 8], relations=True)
        ado.assigned_items.assert_not_called()

    def test_load_pbi_ids_only_if_parent_is_pbi(self):
        ado = MagicMock()
        ado.get_items.return_value = [item(5, typ="Product Backlog Item"), item(4, typ="Feature")]
        result = load_pbi_ids(ado, [item(6, parent=5), item(7, parent=5), item(8, parent=4)])
        self.assertEqual(result, {6:5, 7:5})
        ado.get_items.assert_called_once_with([4, 5])

    def test_print_all_columns_assignee_pbi(self):
        out=io.StringIO()
        with redirect_stdout(out):
            print_tasks([item(6, title="Criar script IA", assigned="Luiz Felipe Flosi"),
                         item(7, title="Criar script .NET", assigned="Maria Souza")],
                        mode="all", on_day=date(2026,11,5), show_assignee=True,
                        pbi_ids={6:5,7:5})
        content = out.getvalue()
        for expected in ("Responsável", "Luiz F.", "Maria S.", "#5", "Criar script IA", "Criar script .NET"):
            self.assertIn(expected, content)

    def test_ensure_task_rejects_pbi(self):
        ensure_task(item(6))
        with self.assertRaisesRegex(DevError, "não Task"):
            ensure_task(item(5, typ="Product Backlog Item"))

    def test_start_cannot_start_pbi_even_when_assigned(self):
        ado=MagicMock()
        ado.get_item.return_value=item(5, typ="Product Backlog Item")
        with self.assertRaises(DevError):
            do_start(ado, {}, 5)
        ado.assigned_ids.assert_not_called()

    def test_show_hierarchy(self):
        ado=MagicMock()
        ado.get_item.side_effect=lambda i, relations=False: {
            8:item(8, parent=5),
            5:item(5, typ="Product Backlog Item", parent=4),
            4:item(4, typ="Feature", parent=3),
            3:item(3, typ="Epic"),
        }[i]
        ado.project_url="https://dev.azure.com/org/proj"
        out=io.StringIO()
        with redirect_stdout(out):
            show_item(ado,8)
        result=out.getvalue()
        for expected in ("Epic #3", "Feature #4", "Product Backlog Item #5", "Task #8"):
            self.assertIn(expected, result)


if __name__ == '__main__':
    unittest.main()

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch
from devflow.cli import parser_build, print_prs, show_pr, run
from devflow.ado import AzureDevOps
from devflow.core import DevError
from devflow import gitops as g


class Release05Tests(unittest.TestCase):
    def test_parser(self):
        args = parser_build().parse_args(["prs", "--mine", "--all", "--limit", "5"])
        self.assertTrue(args.mine and args.all)
        self.assertEqual(args.limit, 5)
        self.assertTrue(parser_build().parse_args(["main", "--update"]).update)
        self.assertEqual(parser_build().parse_args(["pr", "9"]).id, 9)

    def test_list_prs_uses_paginated_api(self):
        ado = AzureDevOps("org", "project", "repo")
        pages = []
        def req(method, path, **kwargs):
            pages.append(kwargs["params"])
            if kwargs["params"]["$skip"] == 0:
                return {"value": [{"pullRequestId": i} for i in range(100)]}
            return {"value": [{"pullRequestId": 100}]}
        with patch.object(ado, "request", side_effect=req):
            prs = ado.list_prs(status="all", limit=150)
        self.assertEqual(len(prs), 101)
        self.assertEqual([p["$skip"] for p in pages], [0, 100])
        self.assertTrue(all(p["searchCriteria.status"] == "all" for p in pages))

    def test_list_prs_mine_uses_authenticated_identity(self):
        ado = AzureDevOps("org", "proj", "repo")
        with patch.object(ado, "identity", return_value={"id": "abcd"}), \
             patch.object(ado, "request", return_value={"value": []}) as req:
            self.assertEqual(ado.list_prs(mine=True), [])
        self.assertEqual(req.call_args.kwargs["params"]["searchCriteria.creatorId"], "abcd")

    def test_pr_detail_and_workitems(self):
        ado = AzureDevOps("org", "p", "r")
        def req(method, path, **kwargs):
            if path.endswith("/workitems"):
                return {"value": [{"id":"5"}, {"id":"6"}]}
            return {"pullRequestId": 12, "status": "active"}
        with patch.object(ado, "request", side_effect=req) as request:
            self.assertEqual(ado.get_pr(12)["status"], "active")
            self.assertEqual(ado.pr_work_items(12), [5, 6])
        self.assertEqual(request.call_args.args[0], "GET")
        with self.assertRaises(DevError):
            ado.get_pr(0)

    def test_print_prs_and_show(self):
        ado = MagicMock()
        ado.get_pr.return_value = {"title":"Implantar IA", "status":"active", "createdBy":{"displayName":"Ana Lima"},
                                   "reviewers":[{"displayName":"Leo", "vote":10}], "mergeStatus":"succeeded"}
        ado.pr_work_items.return_value = [8]
        ado.pr_web_url.return_value = "https://example/pr/3"
        output = io.StringIO()
        with redirect_stdout(output):
            print_prs(ado,[{"pullRequestId":3,"title":"Implementar IA","createdBy":{"displayName":"Ana Lima"},"status":"active"}],status="active")
            show_pr(ado,3)
        content = output.getvalue()
        for phrase in ["Implementar IA", "PR #3", "Leo: aprovou", "#8", "succeeded"]:
            self.assertIn(phrase, content)

    def test_main_update_fast_forward(self):
        config = {"org":"org", "project":"p", "repo":"r", "remote":"origin", "base":"main"}
        stdout = io.StringIO()
        with patch("devflow.cli.g.git_root", return_value=Path.cwd()), \
             patch("devflow.cli.read_config", return_value=config), \
             patch("devflow.cli.config_guard"), \
             patch("devflow.cli.g.switch_base") as sw, \
             patch("devflow.cli.g.fast_forward_base") as ff, \
             patch("devflow.cli.client") as client, redirect_stdout(stdout):
            self.assertEqual(run(["main", "--update"]), 0)
        sw.assert_called_once_with("origin", "main")
        ff.assert_called_once_with("origin", "main")
        client.assert_not_called()
        self.assertIn("fast-forward", stdout.getvalue())

    def test_fast_forward_protects_current_branch(self):
        with patch.object(g, "require_clean"), patch.object(g, "branch", return_value="feature/8-test"), \
             patch.object(g, "git") as command:
            with self.assertRaises(DevError):
                g.fast_forward_base("origin", "main")
        command.assert_not_called()

    def test_fast_forward_runs_only_ff_only(self):
        with patch.object(g, "require_clean"), patch.object(g, "branch", return_value="main"), \
             patch.object(g, "ensure_base"), patch.object(g, "git") as command:
            g.fast_forward_base("origin", "main")
        command.assert_called_once_with("merge", "--ff-only", "origin/main", capture=False)


if __name__ == "__main__":
    unittest.main()

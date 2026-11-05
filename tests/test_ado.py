import unittest
from unittest.mock import patch
from datetime import date
from devflow.ado import AzureDevOps


class AdoTests(unittest.TestCase):
    def test_pr_url(self):
        ado = AzureDevOps("org", "Projeto Legal", "api")
        self.assertEqual(ado.pr_web_url(8),
                         "https://dev.azure.com/org/Projeto%20Legal/_git/api/pullrequest/8")

    def test_wiql_user_literal(self):
        ado = AzureDevOps("org", "projeto", "api")
        observed = {}
        def fake_req(method, path, **kwargs):
            observed.update({"method": method, "path": path, **kwargs})
            return {"workItems": [{"id": 142}, {"id": 143}]}
        with patch.object(ado, "identity", return_value={"uniqueName": "a'b@example.com"}), \
                patch.object(ado, "request", side_effect=fake_req):
            self.assertEqual(ado.assigned_ids(), [142, 143])
        self.assertIn("a''b@example.com", observed["body"]["query"])

    def test_plan_preserves_tags(self):
        ado = AzureDevOps("org", "project", "repo")
        with patch.object(ado, "get_item", return_value={"fields": {"System.Tags": "backend"}}), \
                patch.object(ado, "update_field", return_value={"id": 5}) as update:
            ado.plan_item(5, date(2026, 11, 6))
            update.assert_called_once_with(5, "System.Tags", "backend; devday:2026-11-06")

    def test_branch_artifact_uri_encoding(self):
        ado = AzureDevOps("org", "proj", "repo")
        request_args = {}
        def fake_patch(item_id, changes):
            request_args["changes"] = changes
            return {"id": item_id}
        with patch.object(ado, "project_id", return_value="project-guid"), \
                patch.object(ado, "repo_id", return_value="repo-guid"), \
                patch.object(ado, "get_item", return_value={"relations": []}), \
                patch.object(ado, "patch_item", side_effect=fake_patch):
            self.assertTrue(ado.add_artifact_link(142, "Branch", "feature/142-login"))
        url = request_args["changes"][0]["value"]["url"]
        self.assertEqual(url, "vstfs:///Git/Ref/project-guid%2Frepo-guid%2FGBfeature%2F142-login")

    def test_branch_link_idempotent(self):
        ado = AzureDevOps("org", "proj", "repo")
        uri = "vstfs:///Git/Ref/project-guid%2Frepo-guid%2FGBfeature%2F142-login"
        with patch.object(ado, "project_id", return_value="project-guid"), \
                patch.object(ado, "repo_id", return_value="repo-guid"), \
                patch.object(ado, "get_item", return_value={"relations": [{"url": uri}]}), \
                patch.object(ado, "patch_item") as patcher:
            self.assertFalse(ado.add_artifact_link(142, "Branch", "feature/142-login"))
            patcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()

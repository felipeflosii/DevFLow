import unittest
from unittest.mock import patch
from devflow.ado import AzureDevOps


class AdoTests(unittest.TestCase):
    def setUp(self):
        self.ado = AzureDevOps("VetSync", "GS2 - Azure DevOps", "zeroviagem-api-java")

    def test_query_all_has_no_assignedto_constraint(self):
        params = {}
        def request(method, path, **kw):
            params.update(kw)
            return {"workItems": [{"id": 6}, {"id": 7}, {"id": 8}]}
        with patch.object(self.ado, "request", side_effect=request):
            ids = self.ado.query_ids(item_types={"Task"}, mine=False)
        self.assertEqual(ids, [6, 7, 8])
        self.assertIn("[System.WorkItemType] IN ('Task')", params["body"]["query"])
        self.assertNotIn("[System.AssignedTo]", params["body"]["query"])
        self.assertIn("[System.TeamProject]", params["body"]["query"])

    def test_query_mine_uses_macro(self):
        params = {}
        def request(method, path, **kw):
            params.update(kw)
            return {"workItems": []}
        with patch.object(self.ado, "request", side_effect=request):
            self.ado.query_ids(item_types={"Task"}, mine=True)
        self.assertIn("[System.AssignedTo] = @Me", params["body"]["query"])

    def test_workitem_batch_requests_relations_and_chunks(self):
        calls = []
        def request(method, path, **kw):
            calls.append((method, path, kw))
            return {"value": [{"id": x, "fields": {}} for x in kw["body"]["ids"]]}
        with patch.object(self.ado, "request", side_effect=request):
            results = self.ado.get_items(list(range(1, 221)), relations=True)
        self.assertEqual(len(results), 220)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][2]["body"]["$expand"], "Relations")
        self.assertEqual(len(calls[0][2]["body"]["ids"]), 200)
        self.assertEqual(len(calls[1][2]["body"]["ids"]), 20)

    def test_workitems_empty_does_not_call_api(self):
        with patch.object(self.ado, "request") as fake:
            self.assertEqual(self.ado.get_items([]), [])
            fake.assert_not_called()

    def test_assigned_ids_escapes_user(self):
        params = {}
        def request(method, path, **kw):
            params.update(kw)
            return {"workItems": [{"id": 6}]}
        with patch.object(self.ado, "identity", return_value={"uniqueName": "a'b@example.com"}), \
                patch.object(self.ado, "request", side_effect=request):
            self.assertEqual(self.ado.assigned_ids(), [6])
        self.assertIn("a''b@example.com", params["body"]["query"])

    def test_pr_url(self):
        self.assertEqual(self.ado.pr_web_url(8),
                         "https://dev.azure.com/VetSync/GS2%20-%20Azure%20DevOps/_git/zeroviagem-api-java/pullrequest/8")

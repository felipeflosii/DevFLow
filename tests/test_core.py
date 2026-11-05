import unittest
from datetime import date
from devflow.core import (
    DevError, ado_remote, assignee_name, branch_for, branch_work_id,
    change_plan_tags, filter_items, parent_id, parse_day, plan_tag,
    scheduled_day, short_assignee, slugify, tags_of, truncate,
)


def item(item_id, *, typ="Task", status="To Do", day=None, title="Criar login", tags="", area="GS2\\DevOps", parent=None):
    fields = {"System.Title": title, "System.WorkItemType": typ,
              "System.State": status, "System.Tags": tags, "System.AreaPath": area}
    if day:
        fields["System.Tags"] = f"{tags}; devday:{day}" if tags else f"devday:{day}"
    result = {"id": item_id, "fields": fields}
    if parent is not None:
        result["relations"] = [{"rel": "System.LinkTypes.Hierarchy-Reverse",
                                "url": f"https://dev.azure.com/org/p/_apis/wit/workitems/{parent}"}]
    return result


class CoreTests(unittest.TestCase):
    def test_branch_basics(self):
        self.assertEqual(slugify("Autenticação JWT + Testes!"), "autenticacao-jwt-testes")
        self.assertEqual(branch_for(item(142)), "feature/142-criar-login")
        self.assertEqual(branch_for(item(143, typ="Bug")), "fix/143-criar-login")
        self.assertEqual(branch_work_id("feature/142-criar-login"), 142)
        for bad in ("main", "feature/hello"):
            with self.assertRaises(DevError):
                branch_work_id(bad)

    def test_dates_and_tags(self):
        fields = {"System.Tags": "urgente; devday:2026-11-05; backend"}
        self.assertEqual(change_plan_tags(fields, date(2026,11,6)),
                         "urgente; backend; devday:2026-11-06")
        self.assertEqual(scheduled_day({"System.Tags":"devday:2026-11-06"}), date(2026,11,6))
        self.assertIsNone(scheduled_day({"System.Tags":"devday:abc"}))
        self.assertEqual(tags_of({"System.Tags":""}), [])
        self.assertEqual(plan_tag(date(2026,11,6)), "devday:2026-11-06")
        with self.assertRaises(DevError):
            parse_day("06/11/2026")

    def test_tasks_all_include_unplanned_but_exclude_pbis_and_closed(self):
        items = [item(1), item(2, status="Done"), item(3, typ="Product Backlog Item"),
                 item(4, typ="Epic"), item(5, status="In Progress")]
        self.assertEqual([x["id"] for x in filter_items(items, mode="all", on_day=date(2026,11,6))], [1, 5])
        self.assertEqual([x["id"] for x in filter_items(items, mode="all", on_day=date(2026,11,6), include_closed=True)], [1, 2, 5])

    def test_date_filters_remain_optional(self):
        items = [item(1, day="2026-11-05"), item(2, day="2026-11-06"),
                 item(3, day="2026-11-09"), item(4)]
        self.assertEqual([x["id"] for x in filter_items(items, mode="today", on_day=date(2026,11,6))], [1, 2])
        self.assertEqual([x["id"] for x in filter_items(items, mode="week", on_day=date(2026,11,5))], [1, 2])
        self.assertEqual([x["id"] for x in filter_items(items, mode="date", on_day=date(2026,11,6))], [2])

    def test_area_filter(self):
        values = [item(1, area="GS2\\Infraestrutura e DevOps"), item(2, area="GS2\\Backend Java")]
        self.assertEqual([x["id"] for x in filter_items(values, mode="all", on_day=date(2026,11,6), area="DEvOps")], [1])

    def test_parent_relation_and_fallback(self):
        self.assertEqual(parent_id(item(8, parent=5)), 5)
        self.assertEqual(parent_id({"id": 8, "fields": {"System.Parent": 5}}), 5)
        self.assertIsNone(parent_id(item(8)))

    def test_responsible_initials(self):
        self.assertEqual(short_assignee({"System.AssignedTo": {"displayName": "Luiz Felipe Flosi dos Santos"}}), "Luiz F.")
        self.assertEqual(short_assignee({"System.AssignedTo": {"displayName": "Maria Souza"}}), "Maria S.")
        self.assertEqual(short_assignee({}), "Não atribuído")
        self.assertEqual(short_assignee({"System.AssignedTo":"dev@example.com"}), "dev")
        self.assertEqual(assignee_name({"System.AssignedTo":{"displayName":"Luiz F."}}), "Luiz F.")
        self.assertEqual(truncate("uma frase maior", 7), "uma fr…")

    def test_remote_urls(self):
        self.assertEqual(ado_remote("https://dev.azure.com/VetSync/GS2%20-%20Azure%20DevOps/_git/zeroviagem-api-java"),
                         {"org":"VetSync", "project":"GS2 - Azure DevOps", "repo":"zeroviagem-api-java"})
        self.assertEqual(ado_remote("git@ssh.dev.azure.com:v3/Org/Projeto/Repo"),
                         {"org":"Org", "project":"Projeto", "repo":"Repo"})
        self.assertIsNone(ado_remote("https://github.com/owner/repo.git"))

import unittest
from datetime import date

from devflow.core import (
    slugify, branch_for, branch_work_id, parse_day, plan_tag, change_plan_tags,
    tags_of, scheduled_day, filter_items, ado_remote, DevError,
)


def item(item_id, *, typ="Task", status="To Do", day=None, title="Criar login", tags=""):
    fields = {"System.Title": title, "System.WorkItemType": typ,
              "System.State": status, "System.Tags": tags}
    if day:
        fields["System.Tags"] = f"{tags}; devday:{day}" if tags else f"devday:{day}"
    return {"id": item_id, "fields": fields}


class CoreTests(unittest.TestCase):
    def test_slugify_and_branch(self):
        self.assertEqual(slugify("Autenticação JWT + Testes!"), "autenticacao-jwt-testes")
        self.assertEqual(branch_for(item(142)), "feature/142-criar-login")
        self.assertEqual(branch_for(item(143, typ="Bug")), "fix/143-criar-login")

    def test_branch_work_id(self):
        self.assertEqual(branch_work_id("feature/142-criar-login"), 142)
        with self.assertRaises(DevError):
            branch_work_id("main")
        with self.assertRaises(DevError):
            branch_work_id("feature/hello")

    def test_plan_tags_preserve_other_tags(self):
        fields = {"System.Tags": "urgente; devday:2026-11-05; backend"}
        self.assertEqual(change_plan_tags(fields, date(2026, 11, 6)),
                         "urgente; backend; devday:2026-11-06")
        self.assertEqual(scheduled_day({"System.Tags": "teste; devday:2026-11-06"}), date(2026, 11, 6))
        self.assertIsNone(scheduled_day({"System.Tags": "teste; devday:malformada"}))
        self.assertEqual(tags_of({"System.Tags": ""}), [])

    def test_today_shows_today_and_overdue_but_not_future(self):
        values = [item(1, day="2026-11-05"), item(2, day="2026-11-06"),
                  item(3, day="2026-11-07"), item(4),
                  item(5, day="2026-11-05", status="Done")]
        selected = filter_items(values, mode="today", on_day=date(2026, 11, 6))
        self.assertEqual([x["id"] for x in selected], [1, 2])

    def test_all_show_unplanned_but_exclude_closed(self):
        values = [item(1), item(2, status="Closed"), item(3, typ="Feature")]
        selected = filter_items(values, mode="all", on_day=date(2026, 11, 6))
        self.assertEqual([x["id"] for x in selected], [1])

    def test_week_includes_upcoming_week_and_overdue(self):
        values = [item(1, day="2026-11-02"), item(2, day="2026-11-08"), item(3, day="2026-11-09")]
        selected = filter_items(values, mode="week", on_day=date(2026, 11, 5))
        self.assertEqual([x["id"] for x in selected], [1, 2])

    def test_exact_date_excludes_overdue(self):
        values = [item(1, day="2026-11-02"), item(2, day="2026-11-06")]
        selected = filter_items(values, mode="date", on_day=date(2026, 11, 6))
        self.assertEqual([x["id"] for x in selected], [2])

    def test_invalid_day(self):
        self.assertEqual(plan_tag(date(2026, 11, 6)), "devday:2026-11-06")
        with self.assertRaises(DevError):
            parse_day("06/11/2026")

    def test_remote_urls(self):
        self.assertEqual(ado_remote("https://dev.azure.com/MinhaOrg/Meu%20Projeto/_git/API"),
                         {"org": "MinhaOrg", "project": "Meu Projeto", "repo": "API"})
        self.assertEqual(ado_remote("git@ssh.dev.azure.com:v3/Org/Projeto/Repo"),
                         {"org": "Org", "project": "Projeto", "repo": "Repo"})
        self.assertIsNone(ado_remote("https://github.com/company/repo.git"))


if __name__ == "__main__":
    unittest.main()

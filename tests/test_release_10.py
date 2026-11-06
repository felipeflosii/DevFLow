"""Testes de lançamento v1.0.0: TUI, atualização e compatibilidade."""
import io
import unittest
from unittest.mock import Mock, patch

from devflow import __version__
from devflow.cli import parser_build, run
from devflow.core import DevError
from devflow.dashboard import execute_dashboard
from devflow.tui import DashboardState, entries, fetch_details, launch_dashboard, preview_text
from devflow.updater import StepProgress, install_release, latest_tag, run_update, validate_tag


class TuiTests(unittest.TestCase):
    def test_dashboard_rows_and_filter(self):
        state = DashboardState()
        state.switch(1)  # Minhas Tasks
        state.data = {"tasks": [
            {"id": 6, "title": "Criar script de IA", "state": "To Do", "responsible": "Luiz F."},
            {"id": 7, "title": "Criar script .NET", "state": "Doing", "responsible": "Maria S."},
        ]}
        self.assertEqual(len(state.rows), 2)
        state.set_search("MARIA")
        self.assertEqual([item["id"] for item in state.rows], [7])
        self.assertEqual(state.selected, 0)
        self.assertIn("Criar script .NET", state.current["name"])
        state.switch(2)
        self.assertEqual(state.rows, [])
        self.assertEqual(state.search, "")

    def test_dashboard_move_clamps_selected(self):
        state = DashboardState(section_idx=1, data={"tasks": [{"id": 6}, {"id": 7}]})
        state.move(42)
        self.assertEqual(state.selected, 1)
        state.move(-42)
        self.assertEqual(state.selected, 0)
        state.set_search("não existe")
        self.assertIsNone(state.current)
        self.assertEqual(state.selected, 0)

    def test_preview_is_useful_without_records(self):
        self.assertIn("Nenhum item", preview_text(("tasks", False, False, "Minhas Tasks"), None))
        self.assertIn("#5", preview_text(("tasks", False, False, "Minhas Tasks"),
                  {"id": 6, "title": "Criar IA", "pbi": 5, "state": "To Do"}))

    def test_entries_summary_and_details_readonly(self):
        self.assertEqual(len(entries("summary", {"tasks": {"open": 1}})), 4)
        fake = Mock()
        fake.get_item.return_value = {"fields": {"System.WorkItemType": "Task", "System.Description": "descrição"}}
        fake.project_url = "https://dev.azure.com/org/p"
        details = fetch_details(fake, "tasks", {"id": 8})
        self.assertIn("/_workitems/edit/8", details["URL"])
        fake.get_item.assert_called_once_with(8, relations=True)

    def test_dashboard_constructs_prompt_toolkit_layout(self):
        """Regressão: Frame converte layout interno em HSplit; foco usa Window direta."""
        with patch("prompt_toolkit.application.Application.run", return_value=None):
            launch_dashboard(Mock(), {}, team=None)

    def test_noninteractive_mode_keeps_existing_output(self):
        args = Mock(view=None, json=False, all=False, area=None, state=None, failed=False, team=None)
        with patch("devflow.dashboard.collect_summary", return_value={
            "tasks": {"open": 2}, "pullRequests": {"active": 1},
            "sprint": None, "ci": None, "warnings": []
        }), patch("devflow.dashboard.sys.stdin.isatty", return_value=False), \
                patch("devflow.dashboard.sys.stdout.isatty", return_value=False), \
                patch("builtins.print") as printer:
            self.assertEqual(execute_dashboard(Mock(), {}, args), 0)
        self.assertTrue(printer.called)


class UpdateTests(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(__version__, "1.0.0")
        self.assertEqual(validate_tag("v1.0.0"), "v1.0.0")
        for tag in ("main", "v1.0.0;echo hi", "feature/a", "../v1.0.0", "v 1.0.0"):
            with self.subTest(tag=tag), self.assertRaises(DevError):
                validate_tag(tag)

    def test_latest_tag(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *exc): return False
            def read(self): return b'{"tag_name":"v1.0.0"}'
        with patch("devflow.updater.urllib.request.urlopen", return_value=FakeResponse()):
            self.assertEqual(latest_tag(), "v1.0.0")

    def test_progress_is_steps_not_fake_bytes(self):
        stream = io.StringIO()
        progress = StepProgress(total=3, stream=stream)
        progress.start("Baixando arquivo")
        progress.done("Primeira etapa")
        self.assertIn("[0/3] Baixando arquivo", stream.getvalue())
        self.assertIn("[1/3] Primeira etapa", stream.getvalue())
        self.assertNotIn("%", stream.getvalue())

    def test_update_check_without_install(self):
        with patch("devflow.updater.latest_tag", return_value="v1.0.0"), \
                patch("devflow.updater.install_release") as install:
            self.assertEqual(run_update(check=True), 0)
            install.assert_not_called()

    def test_no_silent_install_without_confirmation(self):
        with patch("devflow.updater.sys.stdin.isatty", return_value=False), \
                patch("devflow.updater.install_release") as install:
            with self.assertRaises(DevError):
                run_update(tag="v1.0.0")
            install.assert_not_called()

    def test_pipx_failure_does_not_report_success(self):
        failure = Mock(returncode=1)
        with patch("devflow.updater.subprocess.run", return_value=failure):
            with self.assertRaises(DevError):
                install_release("v1.0.0", pipx=["pipx"], progress=StepProgress(stream=io.StringIO()))

    def test_successful_pipx_invocation(self):
        def completed(*args, **kwargs):
            return Mock(returncode=0, stdout="ok")
        with patch("devflow.updater.subprocess.run", side_effect=completed) as proc:
            install_release("v1.0.0", pipx=["pipx"], progress=StepProgress(stream=io.StringIO()))
            invocations = [p.args[0] for p in proc.call_args_list]
            self.assertIn("git+https://github.com/felipeflosii/devflow-cli.git@v1.0.0", invocations[0])
            self.assertEqual(invocations[-1], ["pipx", "ensurepath"])

    def test_update_does_not_require_git_repository(self):
        with patch("devflow.updater.run_update", return_value=0) as updater, \
                patch("devflow.cli.g.git_root", side_effect=AssertionError("should not reach git")):
            self.assertEqual(run(["update", "--check"]), 0)
            updater.assert_called_once_with(check=True, tag=None, yes=False)

    def test_cli_options(self):
        parser = parser_build()
        self.assertEqual(parser.parse_args(["update", "--tag", "v1.0.0", "--yes"]).tag, "v1.0.0")
        self.assertEqual(parser.parse_args(["dashboard", "--view", "summary", "--json"]).view, "summary")


if __name__ == "__main__":
    unittest.main()

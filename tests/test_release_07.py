import io
import json
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import MagicMock, patch

from devflow import __version__
from devflow.ado import AzureDevOps
from devflow.ci import (
    checked_limit, short_date, duration, build_status, run_status,
    pipeline_summary, timeline_summary, normalize_yaml_deploy,
    normalize_classic_deploy, deployment_status,
)
from devflow.cli import parser_build, run
from devflow.core import DevError


CFG = {"org": "org", "project": "Project", "repo": "repo", "remote": "origin", "base": "main"}
SAMPLE_BUILD = {"id": 81, "buildNumber": "20261106.1",
                "definition": {"id": 9, "name": "ZeroViagem Java"},
                "status": "completed", "result": "failed",
                "sourceBranch": "refs/heads/main",
                "queueTime": "2026-11-06T12:00:00Z",
                "startTime": "2026-11-06T12:01:00Z", "finishTime": "2026-11-06T12:04:00Z",
                "_links": {"web": {"href": "https://dev.azure.com/org/Project/_build/results?buildId=81"}}}
SAMPLE_RUN = {"id": 81, "name": "20261106.1", "pipeline": {"id": 9, "name": "Java"},
              "state": "completed", "result": "failed", "createdDate": "2026-11-06T12:00:00Z",
              "finishedDate": "2026-11-06T12:04:00Z", "variables": {"TOKEN": {"value": "SECRET_VALUE"}}}
SAMPLE_TIMELINE = {"records": [
    {"type": "Stage", "name": "Build", "state": "completed", "result": "failed",
     "startTime": "2026-11-06T12:01:00Z", "finishTime": "2026-11-06T12:04:00Z"},
    {"type": "Task", "name": "Unit tests", "state": "completed", "result": "failed",
     "issues": [{"type": "error", "message": "Falhou suite de testes"},
                {"type": "warning", "message": "warn"}], "log": {"id": 2}},
    {"type": "Task", "name": "Install", "state": "completed", "result": "succeeded"},
]}


def call_cli(args, ado):
    stdout, stderr = io.StringIO(), io.StringIO()
    with patch("devflow.cli.g.git_root", return_value=Path.cwd()), \
         patch("devflow.cli.read_config", return_value=CFG), \
         patch("devflow.cli.client", return_value=ado), \
         redirect_stdout(stdout), redirect_stderr(stderr):
        result = run(args)
    return result, stdout.getvalue(), stderr.getvalue()


class CiHelperTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.0.0")

    def test_parser(self):
        p = parser_build()
        self.assertEqual(p.parse_args(["pipelines", "--limit", "15"]).limit, 15)
        self.assertEqual(p.parse_args(["builds", "--pipeline", "9", "--failed"]).pipeline, 9)
        self.assertEqual(p.parse_args(["run", "9", "81"]).run_id, 81)
        self.assertEqual(p.parse_args(["deploys", "--source", "yaml"]).source, "yaml")

    def test_limits(self):
        for n in (0, -1, 101):
            with self.assertRaises(DevError):
                checked_limit(n)
        self.assertEqual(checked_limit(100), 100)

    def test_durations_dates(self):
        self.assertEqual(duration("2026-11-06T10:00:00Z", "2026-11-06T10:02:30Z"), "2m30s")
        self.assertEqual(short_date("2026-11-06T10:00:00Z"), "06/11 10:00")
        self.assertEqual(duration(None, "2026-11-06T10:00:00Z"), "—")
        self.assertEqual(short_date("0001-01-01T00:00:00Z"), "—")

    def test_build_and_run_status(self):
        self.assertEqual(build_status(SAMPLE_BUILD), "Falhou")
        self.assertEqual(run_status(SAMPLE_RUN), "Falhou")
        self.assertEqual(run_status({"state": "inProgress", "result": None}), "Executando")
        self.assertEqual(run_status({"state": "completed", "result": "succeeded"}), "Sucesso")

    def test_pipeline_summary_is_a_sample_not_a_fact_about_history(self):
        pipelines = [{"id": 9, "name": "Java"}, {"id": 10, "name": "IA"}]
        data = pipeline_summary(pipelines, [SAMPLE_BUILD])
        self.assertEqual(data[0]["recentBuild"]["id"], 81)
        self.assertIsNone(data[1]["recentBuild"])

    def test_timeline_failures_and_stages(self):
        summary = timeline_summary(SAMPLE_TIMELINE)
        self.assertEqual(summary["stages"][0]["name"], "Build")
        self.assertEqual(len(summary["failures"]), 2)
        self.assertEqual(summary["failures"][1]["errors"], ["Falhou suite de testes"])
        self.assertNotIn("warn", json.dumps(summary))

    def test_deploy_normalization(self):
        env = {"id": 5, "name": "production"}
        record = {"id": 11, "definition": {"id": 9, "name": "Java"}, "owner": {"id": 81},
                  "stageName": "Deploy", "result": "succeeded"}
        yaml = normalize_yaml_deploy(env, [record])[0]
        self.assertEqual(yaml["runId"], 81)
        self.assertEqual(deployment_status(yaml), "Sucesso")
        classic_record = {"id": 12, "deploymentStatus": "failed", "releaseDefinition": {"name": "Legacy"},
                          "releaseEnvironment": {"name": "QA"}, "release": {"name": "R-1"}}
        classic = normalize_classic_deploy([classic_record])[0]
        self.assertEqual(classic["source"], "classic")
        self.assertEqual(deployment_status(classic), "Falhou")


class CiApiTests(unittest.TestCase):
    def setUp(self):
        self.ado = AzureDevOps("org", "Projeto A", "repo")

    def test_pipeline_list_path_and_limit(self):
        with patch.object(self.ado, "request", return_value={"value": [{"id": 9}]}) as request:
            self.assertEqual(self.ado.list_pipelines(limit=5), [{"id": 9}])
        self.assertEqual(request.call_args.args[1], "_apis/pipelines")
        self.assertEqual(request.call_args.kwargs["params"], {"$top": 5})

    def test_builds_filter_uses_server_side_params(self):
        with patch.object(self.ado, "request", return_value={"value": [SAMPLE_BUILD]}) as request:
            self.ado.list_builds(limit=5, pipeline_id=9, failed=True)
        self.assertEqual(request.call_args.kwargs["params"]["definitions"], 9)
        self.assertEqual(request.call_args.kwargs["params"]["resultFilter"], "failed")
        self.assertEqual(request.call_args.kwargs["params"]["queryOrder"], "queueTimeDescending")

    def test_run_and_timeline_paths(self):
        with patch.object(self.ado, "request", return_value={"value": [SAMPLE_RUN]}) as request:
            self.assertEqual(self.ado.list_runs(9, limit=5), [SAMPLE_RUN])
        self.assertEqual(request.call_args.args[1], "_apis/pipelines/9/runs")
        with patch.object(self.ado, "request", return_value=SAMPLE_TIMELINE) as request:
            self.ado.build_timeline(81)
        self.assertEqual(request.call_args.args[1], "_apis/build/builds/81/timeline")

    def test_environment_deploys_list_supports_object_and_array(self):
        with patch.object(self.ado, "request", return_value=[{"id": 1}]) as request:
            self.assertEqual(self.ado.list_environment_deployments(5), [{"id": 1}])
        self.assertEqual(request.call_args.kwargs["params"], {"top": 20})
        with patch.object(self.ado, "request", return_value={"value": [{"id": 2}]}):
            self.assertEqual(self.ado.list_environment_deployments(5), [{"id": 2}])

    def test_classic_release_hostname(self):
        self.assertEqual(self.ado.release_project_url,
                         "https://vsrm.dev.azure.com/org/Projeto%20A")
        with patch.object(self.ado, "request", return_value={"value": []}) as request:
            self.ado.list_classic_deployments(limit=6)
        self.assertTrue(request.call_args.kwargs["release"])
        self.assertEqual(request.call_args.kwargs["params"]["queryOrder"], "descending")

    def test_release_request_uses_vsrm_host_and_encoded_project(self):
        import io as python_io
        with patch("devflow.ado.get_auth_headers", return_value={"Authorization": "Bearer example"}), \
             patch("devflow.ado.urllib.request.urlopen", return_value=python_io.BytesIO(b'{"value": []}')) as opener:
            self.ado.request("GET", "_apis/release/deployments", release=True)
        req = opener.call_args.args[0]
        self.assertTrue(req.full_url.startswith(
            "https://vsrm.dev.azure.com/org/Projeto%20A/_apis/release/deployments?"))
        self.assertIn("api-version=7.1", req.full_url)

    def test_runs_newest_first(self):
        runs = [{"id": 1, "createdDate": "2026-11-04T00:00:00Z"},
                {"id": 2, "createdDate": "2026-11-06T00:00:00Z"}]
        with patch.object(self.ado, "request", return_value={"value": runs}):
            self.assertEqual([r["id"] for r in self.ado.list_runs(9)], [2, 1])

    def test_invalid_ids_fail_before_network(self):
        for fn in [lambda: self.ado.get_run(9, 0), lambda: self.ado.get_build(0),
                   lambda: self.ado.build_timeline(-1), lambda: self.ado.list_runs(-1)]:
            with self.assertRaises(DevError):
                fn()


class CiCliTests(unittest.TestCase):
    def setUp(self):
        self.ado = MagicMock()

    def test_pipelines_no_builds_when_no_pipelines(self):
        self.ado.list_pipelines.return_value = []
        _, out, _ = call_cli(["pipelines"], self.ado)
        self.assertIn("Nenhuma pipeline", out)
        self.ado.list_builds.assert_not_called()

    def test_pipelines_json_summary_does_not_leak_unexpected_fields(self):
        self.ado.list_pipelines.return_value = [{"id": 9, "name": "Java"}]
        self.ado.list_builds.return_value = [dict(SAMPLE_BUILD, secret="DO_NOT_PRINT")]
        _, out, _ = call_cli(["pipelines", "--json"], self.ado)
        data = json.loads(out)
        self.assertEqual(data["pipelines"][0]["recentBuild"]["id"], 81)
        self.assertNotIn("DO_NOT_PRINT", out)

    def test_builds_failed_cli(self):
        self.ado.list_builds.return_value = [SAMPLE_BUILD]
        _, out, _ = call_cli(["builds", "--pipeline", "9", "--failed"], self.ado)
        self.ado.list_builds.assert_called_once_with(limit=20, pipeline_id=9, failed=True)
        self.assertIn("Falhou", out)
        self.assertIn("ZeroViagem Java", out)

    def test_runs_cli(self):
        self.ado.list_runs.return_value = [SAMPLE_RUN]
        _, out, _ = call_cli(["runs", "9"], self.ado)
        self.assertIn("20261106.1", out)
        self.ado.list_runs.assert_called_once_with(9, limit=10)

    def test_run_detail_hides_variables(self):
        self.ado.get_run.return_value = SAMPLE_RUN
        self.ado.build_timeline.return_value = SAMPLE_TIMELINE
        _, out, _ = call_cli(["run", "9", "81", "--json"], self.ado)
        self.assertIn("Falhou suite de testes", out)
        self.assertNotIn("SECRET_VALUE", out)
        self.assertEqual(json.loads(out)["run"]["pipelineId"], 9)

    def test_build_detail_timeline_fallback(self):
        self.ado.get_build.return_value = SAMPLE_BUILD
        self.ado.build_timeline.side_effect = DevError("timeline sem acesso")
        _, out, err = call_cli(["build", "81"], self.ado)
        self.assertIn("indisponíveis", out)
        self.assertIn("timeline sem acesso", err)

    def test_deploys_classic_yaml_combined(self):
        self.ado.list_environments.return_value = [{"id": 5, "name": "prod"}]
        self.ado.list_environment_deployments.return_value = [{"id": 12, "result": "succeeded", "startTime": "2026-11-06T12:00:00Z"}]
        self.ado.list_classic_deployments.return_value = [{"id": 13, "deploymentStatus": "failed", "releaseEnvironment": {"name": "staging"}}]
        _, out, _ = call_cli(["deploys"], self.ado)
        self.assertIn("prod", out)
        self.assertIn("staging", out)
        self.assertIn("Falhou", out)

    def test_deploys_warning_for_partial_source(self):
        self.ado.list_environments.return_value = [{"id": 5, "name": "prod"}]
        self.ado.list_environment_deployments.return_value = []
        self.ado.list_classic_deployments.side_effect = DevError("Sem permissão Classic")
        _, out, _ = call_cli(["deploys"], self.ado)
        self.assertIn("AVISO", out)
        self.assertIn("Sem permissão Classic", out)

    def test_deploys_all_sources_error(self):
        self.ado.list_environments.side_effect = DevError("Erro no YAML")
        self.ado.list_classic_deployments.side_effect = DevError("Erro no Classic")
        with self.assertRaises(DevError):
            call_cli(["deploys"], self.ado)

    def test_deploys_environment_filter(self):
        self.ado.list_environments.return_value = [{"id": 5, "name": "produção"}, {"id": 6, "name": "staging"}]
        self.ado.list_environment_deployments.return_value = []
        _, _, _ = call_cli(["deploys", "--source", "yaml", "--environment", "staging"], self.ado)
        self.ado.list_environment_deployments.assert_called_once_with(6, limit=20)


if __name__ == "__main__":
    unittest.main()

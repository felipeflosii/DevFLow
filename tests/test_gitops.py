import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devflow import gitops as g
from devflow.core import DevError


def cmd(*args, cwd=None):
    result = subprocess.run([*args], cwd=cwd, text=True, capture_output=True, check=True)
    return result.stdout.strip()


class LocalGitWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cwd = Path.cwd()
        self.root = Path(self.tmp.name)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "work"
        cmd("git", "init", "--bare", "--initial-branch=main", str(self.remote))
        cmd("git", "clone", str(self.remote), str(self.repo))
        cmd("git", "config", "user.name", "Tester", cwd=self.repo)
        cmd("git", "config", "user.email", "tester@example.com", cwd=self.repo)
        (self.repo / "README.md").write_text("# Arquivo original\n")
        cmd("git", "add", "README.md", cwd=self.repo)
        cmd("git", "commit", "-m", "initial", cwd=self.repo)
        cmd("git", "push", "-u", "origin", "main", cwd=self.repo)
        os.chdir(self.repo)

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    def test_create_branch_commit_push_and_resume(self):
        action = g.switch_task("origin", "main", "feature/142-login")
        self.assertEqual(action, "criada")
        self.assertEqual(g.branch(), "feature/142-login")
        (self.repo / "src.py").write_text("print('ok')\n")
        self.assertTrue(g.commit_and_push("origin", 142, "feat: criar login", yes=True))
        self.assertIn("AB#142", cmd("git", "log", "-1", "--format=%s"))
        self.assertEqual(g.switch_task("origin", "main", "feature/142-login"), "retomada")
        self.assertEqual(cmd("git", "rev-parse", "main"), cmd("git", "rev-parse", "origin/main"))

    def test_reject_dirty_switch(self):
        (self.repo / "README.md").write_text("edicao local\n")
        with self.assertRaises(DevError):
            g.switch_task("origin", "main", "feature/143-cpf")
        self.assertEqual(g.branch(), "main")

    def test_reject_env_secret(self):
        g.switch_task("origin", "main", "feature/144-seguro")
        (self.repo / ".env").write_text("API_KEY=nao-commitar\n")
        with self.assertRaises(DevError):
            g.commit_and_push("origin", 144, "feat: configuracao", yes=True)
        self.assertEqual(cmd("git", "log", "-1", "--format=%s"), "initial")


if __name__ == "__main__":
    unittest.main()

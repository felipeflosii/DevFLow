"""Testes de troca segura para a branch base do DevFlow."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, call

from devflow import gitops as g
from devflow.core import DevError


class SwitchBaseUnitTests(unittest.TestCase):
    @patch.object(g, 'git')
    @patch.object(g, 'branch', return_value='feature/6-ia')
    @patch.object(g, 'ref_exists', return_value=True)
    @patch.object(g, 'ensure_base')
    @patch.object(g, 'sync')
    @patch.object(g, 'require_clean')
    def test_existing_main(self, clean, sync, ensure, exists, branch, git):
        self.assertEqual(g.switch_base('origin', 'main'), 'selecionada')
        clean.assert_called_once()
        sync.assert_called_once_with('origin')
        ensure.assert_called_once_with('origin', 'main')
        git.assert_called_once_with('switch', 'main', capture=False)

    @patch.object(g, 'git')
    @patch.object(g, 'branch', return_value='feature/6-ia')
    @patch.object(g, 'ref_exists', return_value=False)
    @patch.object(g, 'ensure_base')
    @patch.object(g, 'sync')
    @patch.object(g, 'require_clean')
    def test_create_tracking_branch_when_missing(self, clean, sync, ensure, exists, branch, git):
        self.assertEqual(g.switch_base('origin', 'main'), 'criada e selecionada a partir do remoto')
        git.assert_called_once_with('switch', '--track', '-c', 'main', 'origin/main', capture=False)

    @patch.object(g, 'git')
    @patch.object(g, 'branch', return_value='main')
    @patch.object(g, 'ref_exists')
    @patch.object(g, 'ensure_base')
    @patch.object(g, 'sync')
    @patch.object(g, 'require_clean')
    def test_already_on_main(self, clean, sync, ensure, exists, branch, git):
        self.assertEqual(g.switch_base('origin', 'main'), 'já selecionada')
        git.assert_not_called()
        exists.assert_not_called()

    @patch.object(g, 'git')
    @patch.object(g, 'sync')
    @patch.object(g, 'require_clean', side_effect=DevError('Alterações locais'))
    def test_dirty_tree_rejects_without_fetch_or_switch(self, clean, sync, git):
        with self.assertRaisesRegex(DevError, 'Alterações locais'):
            g.switch_base('origin', 'main')
        sync.assert_not_called()
        git.assert_not_called()


@unittest.skipUnless(__import__('shutil').which('git'), 'git não encontrado')
class SwitchBaseIntegrationTests(unittest.TestCase):
    def cmd(self, *args, cwd=None):
        return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bare = Path(self.tmp.name) / 'remote.git'
        self.work = Path(self.tmp.name) / 'work'
        self.cmd('init', '--bare', str(self.bare))
        self.cmd('init', '-b', 'main', str(self.work))
        self.cmd('config', 'user.email', 'ci@example.org', cwd=self.work)
        self.cmd('config', 'user.name', 'CI', cwd=self.work)
        (self.work / 'test.txt').write_text('main\n')
        self.cmd('add', '.', cwd=self.work)
        self.cmd('commit', '-m', 'init', cwd=self.work)
        self.cmd('remote', 'add', 'origin', str(self.bare), cwd=self.work)
        self.cmd('push', '-u', 'origin', 'main', cwd=self.work)
        self.old_cwd = os.getcwd()
        os.chdir(self.work)
        self.addCleanup(lambda: os.chdir(self.old_cwd))

    def test_switch_existing_main_after_fetch(self):
        self.cmd('switch', '-c', 'feature/test', cwd=self.work)
        self.assertEqual(g.switch_base('origin', 'main'), 'selecionada')
        self.assertEqual(self.cmd('branch', '--show-current', cwd=self.work), 'main')

    def test_switch_creates_tracking_main_if_missing(self):
        self.cmd('switch', '-c', 'feature/test', cwd=self.work)
        self.cmd('branch', '-D', 'main', cwd=self.work)
        self.assertEqual(g.switch_base('origin', 'main'), 'criada e selecionada a partir do remoto')
        self.assertEqual(self.cmd('rev-parse', '--abbrev-ref', 'main@{upstream}', cwd=self.work), 'origin/main')

    def test_does_not_discard_uncommitted_changes(self):
        self.cmd('switch', '-c', 'feature/test', cwd=self.work)
        (self.work / 'test.txt').write_text('alteração\n')
        with self.assertRaisesRegex(DevError, 'alterações locais'):
            g.switch_base('origin', 'main')
        self.assertEqual(self.cmd('branch', '--show-current', cwd=self.work), 'feature/test')
        self.assertEqual((self.work / 'test.txt').read_text(), 'alteração\n')


if __name__ == '__main__':
    unittest.main()

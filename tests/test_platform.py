import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devflow.core import config_file, read_config, save_config
from devflow.ado import get_auth_headers
from devflow.core import DevError
from devflow import gitops


class PlatformTests(unittest.TestCase):
    def test_windows_config_uses_localappdata(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('devflow.core.sys.platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': folder}):
                self.assertEqual(config_file(), Path(folder) / 'DevFlow' / 'config.json')

    def test_windows_config_appdata_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            variables = {'LOCALAPPDATA': '', 'APPDATA': folder}
            with patch('devflow.core.sys.platform', 'win32'), patch.dict(os.environ, variables):
                self.assertEqual(config_file(), Path(folder) / 'DevFlow' / 'config.json')

    def test_unix_config_xdg_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('devflow.core.sys.platform', 'linux'), patch.dict(os.environ, {'XDG_CONFIG_HOME': folder}):
                with tempfile.TemporaryDirectory() as repo:
                    data = {'org': 'o', 'project': 'p', 'repo': 'r', 'remote': 'origin', 'base': 'main'}
                    loc = save_config(Path(repo), data)
                    self.assertEqual(loc, Path(folder) / 'devflow' / 'config.json')
                    self.assertEqual(read_config(Path(repo)), data)

    def test_windows_save_config_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as repo:
            with patch('devflow.core.sys.platform', 'win32'), patch.dict(os.environ, {'LOCALAPPDATA': folder}):
                cfg = {'org': 'o', 'project': 'p', 'repo': 'r'}
                save_config(Path(repo), cfg)
                self.assertEqual(read_config(Path(repo)), cfg)

    def test_git_missing_error_is_os_neutral(self):
        with patch('devflow.gitops.shutil.which', return_value=None):
            with self.assertRaisesRegex(DevError, 'seu sistema'):
                gitops.git('--version')

    def test_az_missing_error_is_os_neutral(self):
        with patch.dict(os.environ, {'ADO_PAT': '', 'AZURE_DEVOPS_EXT_PAT': ''}):
            with patch('devflow.ado.shutil.which', return_value=None):
                with self.assertRaisesRegex(DevError, 'Azure CLI'):
                    get_auth_headers()

    def test_az_cmd_is_used_when_found(self):
        from unittest.mock import MagicMock
        process = MagicMock(returncode=0, stdout='abc-token\n', stderr='')
        with patch.dict(os.environ, {'ADO_PAT': '', 'AZURE_DEVOPS_EXT_PAT': ''}):
            with patch('devflow.ado.shutil.which', return_value=r'C:\\Program Files\\Azure CLI\\wbin\\az.cmd'):
                with patch('devflow.ado.subprocess.run', return_value=process) as call:
                    result = get_auth_headers()
        self.assertEqual(result, {'Authorization': 'Bearer abc-token'})
        self.assertTrue(call.call_args.args[0][0].endswith('az.cmd'))


if __name__ == '__main__':
    unittest.main()

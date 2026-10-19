import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'native'))
from platform_paths import data_directory, deno_path, runtime_python

spec = importlib.util.spec_from_file_location('mac_installer', ROOT / 'native/macos/installer.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class MacPaths(unittest.TestCase):
    def test_mac_without_windows_environment(self):
        self.assertEqual(data_directory('CaptionCraft', 'CAPTIONCRAFT_HOME', {}, 'darwin', '/Users/测试 用户'),
                         Path('/Users/测试 用户/Library/Application Support/CaptionCraft/Data'))

    def test_override_does_not_evaluate_windows_fallback(self):
        self.assertEqual(data_directory('CaptionCraft', 'CAPTIONCRAFT_HOME',
            {'CAPTIONCRAFT_HOME': '/tmp/data'}, 'darwin'), Path('/tmp/data'))

    def test_windows_paths_retained(self):
        self.assertEqual(data_directory('CaptionCraft', 'CAPTIONCRAFT_HOME',
            {'LOCALAPPDATA': '/windows/user'}, 'win32'), Path('/windows/user/CaptionCraft/Data'))
        self.assertEqual(runtime_python('/app', 'win32'), Path('/app/runtime/python.exe'))
        self.assertEqual(deno_path('/app', 'win32'), Path('/app/tools/deno/deno.exe'))
        self.assertEqual(runtime_python('/app', 'darwin'), Path('/app/runtime/bin/python3'))
        self.assertEqual(deno_path('/app', 'darwin'), Path('/app/tools/deno/deno'))


@unittest.skipUnless(sys.platform == 'darwin', 'macOS installer')
class MacInstall(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='Mac 测试 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root / 'payload'
        (self.payload / 'extension').mkdir(parents=True)
        (self.payload / 'native').mkdir()
        (self.payload / 'runtime/bin').mkdir(parents=True)
        (self.payload / 'runtime/bin/python3').write_text('fixture')
        self.manifest = json.loads((ROOT / 'extension/manifest.json').read_text())
        (self.payload / 'extension/manifest.json').write_text(json.dumps(self.manifest))
        self.config = {'product': ROOT.name, 'version': self.manifest['version'],
            'extension_id': installer.extension_id(self.manifest),
            'host': 'com.' + ROOT.name.lower() + '.assistant', 'data_variable': ROOT.name.upper() + '_HOME'}
        self.destination = self.root / '安装 目录'
        self.chrome = self.root / 'Chrome/NativeMessagingHosts'

    def install(self):
        with patch.object(installer.subprocess, 'run'):
            return installer.install(self.payload, self.config, self.destination, self.chrome)

    def test_reinstall_preserves_data_and_extension_path(self):
        first = self.install()
        token = Path(first['data']) / 'sentinel'; token.write_text('keep')
        second = self.install()
        self.assertEqual(first['extension'], second['extension'])
        self.assertNotEqual(first['app'], second['app'])
        self.assertTrue(Path(first['app']).is_dir())
        self.assertEqual(token.read_text(), 'keep')
        registration = json.loads(Path(second['registration']).read_text())
        self.assertEqual(registration['allowed_origins'], ['chrome-extension://' + self.config['extension_id'] + '/'])
        launcher = Path(registration['path'])
        self.assertTrue(launcher.is_absolute())
        self.assertTrue(os.access(launcher, os.X_OK))
        self.assertIn('安装 目录', launcher.read_text())
        self.assertTrue(list(self.destination.glob('Extension.previous-*')))

    def test_changed_key_refused_before_install(self):
        self.config['extension_id'] = 'a' * 32
        with self.assertRaises(ValueError): self.install()
        self.assertFalse(self.destination.exists())

    def test_unrelated_registration_preserved(self):
        self.chrome.mkdir(parents=True)
        target = self.chrome / (self.config['host'] + '.json')
        target.write_text(json.dumps({'name': self.config['host'], 'allowed_origins': ['foreign']}))
        with self.assertRaises(ValueError): self.install()
        self.assertEqual(json.loads(target.read_text())['allowed_origins'], ['foreign'])

    def test_failure_keeps_previous_extension_and_registration(self):
        first = self.install()
        before = Path(first['registration']).read_bytes()
        original = installer.atomic_json
        with patch.object(installer.subprocess, 'run'), patch.object(installer, 'atomic_json', wraps=original) as write:
            def fail(path, value):
                if Path(path) == Path(first['registration']): raise OSError('fixture registration failure')
                original(path, value)
            write.side_effect = fail
            with self.assertRaises(OSError):
                installer.install(self.payload, self.config, self.destination, self.chrome)
        self.assertEqual(Path(first['registration']).read_bytes(), before)
        self.assertEqual(json.loads((Path(first['extension'])/'manifest.json').read_text()), self.manifest)


if __name__ == '__main__': unittest.main()

"""Build a relocatable Apple Silicon .app installer from a prepared Python runtime."""
import argparse
import json
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from installer import extension_id

ROOT = Path(__file__).resolve().parents[2]


def build(runtime, output, product, deno=None):
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise RuntimeError('Build on an Apple Silicon Mac with an arm64 runtime.')
    runtime = Path(runtime).resolve()
    manifest = json.loads((ROOT / 'extension/manifest.json').read_text())
    config = {'product': product, 'display_name': '字幕翻译生成 · CaptionCraft' if product == 'CaptionCraft' else '音频转文字 · AudioScribe',
              'version': manifest['version'], 'extension_id': extension_id(manifest),
              'host': 'com.' + product.lower() + '.assistant', 'data_variable': product.upper() + '_HOME'}
    probe = subprocess.check_output([str(runtime / 'bin/python3'), '-I', '-c',
                                    'import platform; print(platform.machine())'], text=True).strip()
    if probe != 'arm64':
        raise RuntimeError('Expected an arm64 Python runtime.')
    app = Path(output).resolve() / (product + ' Installer.app')
    if app.exists():
        raise FileExistsError('Use an empty output directory: ' + str(app))
    resources = app / 'Contents/Resources'
    macos = app / 'Contents/MacOS'
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    payload = resources / 'payload'
    payload.mkdir()
    ignore = shutil.ignore_patterns('__pycache__', '*.pyc', '*.log', '.DS_Store', 'config.json', 'config.js')
    for folder in ('helper', 'native', 'shared', 'extension'):
        if (ROOT / folder).is_dir():
            shutil.copytree(ROOT / folder, payload / folder, ignore=ignore)
    mac_manifest = dict(manifest, version_name=manifest['version'] + ' macOS preview 1')
    (payload / 'extension/manifest.json').write_text(json.dumps(mac_manifest, ensure_ascii=False, indent=2))
    shutil.copytree(runtime, payload / 'runtime', symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    if product == 'CaptionCraft':
        if not deno or not Path(deno).is_file():
            raise ValueError('CaptionCraft requires --deno with the official arm64 binary.')
        tools = payload / 'tools/deno'; tools.mkdir(parents=True)
        shutil.copy2(deno, tools / 'deno'); (tools / 'deno').chmod(0o755)
        license_file = Path(deno).with_name('LICENSE.md')
        if not license_file.exists(): raise ValueError('Place Deno LICENSE.md alongside its binary.')
        shutil.copy2(license_file, tools / 'LICENSE.md')
    for name in ('LICENSE', 'THIRD-PARTY-NOTICES.md'):
        if (ROOT / name).exists(): shutil.copy2(ROOT / name, payload / name)
    shutil.copy2(ROOT / 'Logo.png', resources / 'Logo.png')
    shutil.copy2(Path(__file__).with_name('installer.py'), resources / 'installer.py')
    (resources / 'product.json').write_text(json.dumps(config, ensure_ascii=False, indent=2))
    launcher = macos / 'install'
    launcher.write_text('#!/bin/sh\nset -eu\n'
        'BUNDLE_RESOURCES="$(CDPATH= cd -- "$(dirname -- "$0")/../Resources" && pwd)"\n'
        'exec "$BUNDLE_RESOURCES/payload/runtime/bin/python3" -I "$BUNDLE_RESOURCES/installer.py" "$@"\n')
    launcher.chmod(0o755)
    with (app / 'Contents/Info.plist').open('wb') as out:
        plistlib.dump({'CFBundleName': product + ' Installer', 'CFBundleDisplayName': config['display_name'] + ' 安装器',
            'CFBundleExecutable': 'install', 'CFBundleIdentifier': 'com.' + product.lower() + '.installer',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': manifest['version'],
            'CFBundleShortVersionString': manifest['version'], 'LSMinimumSystemVersion': '14.0',
            'NSHighResolutionCapable': True, 'LSArchitecturePriority': ['arm64']}, out)
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--deno', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--product', choices=['CaptionCraft', 'AudioScribe'], default=ROOT.name)
    args = parser.parse_args()
    print(build(args.runtime, args.output, args.product, args.deno))

"""Build the complete Windows installer using a prebuilt licensed Python runtime ZIP.

python native/build_windows.py --runtime-zip path/to/runtime.zip --build-dir build
The runtime ZIP must contain runtime/python.exe and the dependencies in requirements.txt.
No model weights, tokens, transcripts or user media are copied into distributions.
"""
import argparse
import base64
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--runtime-zip', required=True)
parser.add_argument('--build-dir', required=True)
args = parser.parse_args()
build = Path(args.build_dir).resolve()
build.mkdir(parents=True, exist_ok=True)
csc = Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
public = (ROOT / 'native/extension-public-key.txt').read_text().strip()
digest = hashlib.sha256(base64.b64decode(public)).hexdigest()[:32]
extension_id = ''.join(chr(97 + int(c, 16)) for c in digest)
manifest = json.loads((ROOT / 'extension/manifest.json').read_text(encoding='utf8'))
assert manifest['key'] == public
setup = build / 'Setup.cs'
setup.write_text((ROOT / 'native/Setup.cs').read_text(encoding='utf8').replace('__EXTENSION_ID__', extension_id), encoding='utf-8-sig')
refs = ['/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
        '/r:' + str(csc.parent / 'System.IO.Compression.dll'), '/r:' + str(csc.parent / 'System.IO.Compression.FileSystem.dll')]
host = build / 'AudioScribeHost.exe'
maintenance = build / 'AudioScribeMaintenance.exe'
subprocess.run([str(csc), '/nologo', '/target:exe', '/platform:x64', '/out:' + str(host), str(ROOT / 'native/Bridge.cs')], check=True)
logo = ROOT / 'Logo.png'
icon = ROOT / 'native/app.ico'
subprocess.run([str(csc), '/nologo', '/target:winexe', '/platform:x64', '/out:' + str(maintenance), *refs,
                '/win32icon:' + str(icon), '/resource:' + str(logo) + ',logo.png', str(setup)], check=True)
payload = build / 'payload.zip'
with zipfile.ZipFile(args.runtime_zip) as runtime, zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for item in runtime.infolist():
        # Only runtime and license files. Ignore old apps, credentials and media.
        if item.filename.startswith(('runtime/', 'licenses/')) or item.filename == 'LICENSE':
            archive.writestr(item, runtime.read(item))
    for folder in ['helper', 'native']:
        for file in (ROOT / folder).rglob('*'):
            if file.is_file() and file.suffix not in ('.pyc', '.log') and '__pycache__' not in file.parts and file.name != 'config.json':
                archive.write(file, file.relative_to(ROOT).as_posix())
    archive.write(host, 'AudioScribeHost.exe')
    archive.write(maintenance, 'AudioScribeMaintenance.exe')
    assert 'runtime/python.exe' in archive.namelist()
extension = build / 'extension.zip'
with zipfile.ZipFile(extension, 'w', zipfile.ZIP_DEFLATED) as archive:
    for file in (ROOT / 'extension').rglob('*'):
        if file.is_file():
            archive.write(file, file.relative_to(ROOT / 'extension').as_posix())
output = ROOT.parent / 'AudioScribe-Setup-v0.1.0.exe'
subprocess.run([str(csc), '/nologo', '/target:winexe', '/platform:x64', '/out:' + str(output), *refs,
                '/win32icon:' + str(icon), '/resource:' + str(logo) + ',logo.png',
                '/resource:' + str(payload) + ',payload.zip', '/resource:' + str(extension) + ',extension.zip', str(setup)], check=True)
with zipfile.ZipFile(ROOT.parent / 'AudioScribe-Extension-v0.1.0.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for file in (ROOT / 'extension').rglob('*'):
        if file.is_file():
            archive.write(file, file.relative_to(ROOT / 'extension').as_posix())
with zipfile.ZipFile(ROOT.parent / 'AudioScribe-Source-v0.1.0.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for file in ROOT.rglob('*'):
        if file.is_file() and not any(p in ('__pycache__', '.venv', 'models', 'Data', 'build') for p in file.relative_to(ROOT).parts) and file.suffix not in ('.pyc', '.log', '.exe'):
            archive.write(file, 'audio-to-text/' + file.relative_to(ROOT).as_posix())
print('Extension ID:', extension_id)
print('Installer:', output, output.stat().st_size)

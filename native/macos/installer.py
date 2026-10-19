"""Self-contained, per-user macOS installer. No administrator privileges."""
import argparse
import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path

RESOURCES = Path(__file__).resolve().parent


def extension_id(manifest):
    digest = hashlib.sha256(base64.b64decode(manifest['key'], validate=True)).hexdigest()[:32]
    return ''.join(chr(97 + int(c, 16)) for c in digest)


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    temporary.replace(path)


def install(payload, config, destination=None, chrome_directory=None, progress=lambda _: None):
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        raise RuntimeError('本安装包需要 Apple Silicon Mac（M 系列芯片）。')
    if int(platform.mac_ver()[0].split('.')[0]) < 14:
        raise RuntimeError('本安装包需要 macOS 14 或更新版本。')
    payload = Path(payload).resolve()
    support = Path.home() / 'Library' / 'Application Support'
    destination = Path(destination or support / config['product']).resolve()
    chrome_directory = Path(chrome_directory or support / 'Google' / 'Chrome' / 'NativeMessagingHosts').resolve()
    manifest = json.loads((payload / 'extension' / 'manifest.json').read_text())
    if extension_id(manifest) != config['extension_id']:
        raise ValueError('安装包扩展标识校验失败。')
    if not (payload / 'runtime' / 'bin' / 'python3').is_file():
        raise ValueError('安装包不完整，请重新下载。')
    registration_path = chrome_directory / (config['host'] + '.json')
    origins = ['chrome-extension://' + config['extension_id'] + '/']
    if registration_path.exists():
        previous = json.loads(registration_path.read_text())
        if previous.get('name') != config['host'] or previous.get('allowed_origins') != origins:
            raise ValueError('发现不同来源的助手注册，请先检查已有安装。')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    versions = destination / 'Versions'
    versions.mkdir(exist_ok=True, mode=0o700)
    build_id = config['version'] + '-mac1-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    app = versions / build_id
    progress('正在安装运行环境和本地助手…')
    shutil.copytree(payload, app, symlinks=True)
    data = destination / 'Data'
    data.mkdir(exist_ok=True, mode=0o700)
    launcher = app / 'native' / 'launch-host.sh'
    # Quoting is evaluated by Python, never interpolated into a shell command.
    import shlex
    launcher.write_text('#!/bin/sh\nset -eu\numask 077\n'
        + 'APP_DIR=' + shlex.quote(str(app)) + '\n'
        + 'export ' + config['data_variable'] + '=' + shlex.quote(str(data)) + '\n'
        + 'exec "$APP_DIR/runtime/bin/python3" -I -u "$APP_DIR/native/host.py" "$@"\n')
    launcher.chmod(0o700)
    registration = {'name': config['host'], 'description': config['product'] + ' local assistant',
        'path': str(launcher), 'type': 'stdio', 'allowed_origins': origins}
    atomic_json(app / 'native-host.json', registration)
    progress('正在检查安装后的运行环境…')
    check = 'import faster_whisper,av,numpy,tkinter'
    if config['product'] == 'CaptionCraft':
        check += ',sherpa_onnx,sentencepiece,sacremoses,subword_nmt,yt_dlp,yt_dlp_ejs'
    subprocess.run([str(app / 'runtime/bin/python3'), '-I', '-c', check],
                   check=True, capture_output=True, timeout=90)
    # Keep the extension path stable. Backups preserve any previous version.
    extension = destination / 'Extension'
    staged_extension = destination / ('Extension.new-' + uuid.uuid4().hex)
    shutil.copytree(app / 'extension', staged_extension)
    backup = None
    if extension.exists():
        backup = destination / ('Extension.previous-' + build_id)
        extension.rename(backup)
    try:
        staged_extension.rename(extension)
        chrome_directory.mkdir(parents=True, exist_ok=True)
        if registration_path.exists():
            shutil.copy2(registration_path, app / 'previous-registration.json')
        # Register last, after validating the new installation.
        atomic_json(registration_path, registration)
    except Exception:
        if extension.exists():
            extension.rename(destination / ('Extension.failed-' + build_id))
        if backup is not None:
            backup.rename(extension)
        raise
    result = {'product': config['product'], 'version': config['version'], 'app': str(app),
              'extension': str(extension), 'registration': str(registration_path), 'data': str(data)}
    atomic_json(destination / 'installation.json', result)
    progress('安装完成。下一步在 Chrome 加载扩展。')
    return result


def gui(config):
    import tkinter as tk
    from tkinter import ttk, messagebox
    window = tk.Tk()
    window.title(config['display_name'] + ' · Mac 安装')
    window.geometry('640x600')
    window.minsize(640, 600)
    window.configure(bg='#f4f7fc')
    style = ttk.Style(window)
    style.configure('TButton', padding=(16, 10))
    frame = tk.Frame(window, bg='#f4f7fc', padx=32, pady=24)
    frame.pack(fill='both', expand=True)
    logo_path = RESOURCES / 'Logo.png'
    if logo_path.exists():
        logo = tk.PhotoImage(file=str(logo_path))
        logo = logo.subsample(max(1, logo.width() // 64))
        label = tk.Label(frame, image=logo, bg='#f4f7fc'); label.image = logo
        label.pack(anchor='w')
    tk.Label(frame, text=config['display_name'], font=('Helvetica', 25, 'bold'),
             bg='#f4f7fc', fg='#17243d').pack(anchor='w', pady=(14, 6))
    tk.Label(frame, text='Apple Silicon · ' + config['version'] + ' Mac 测试版',
             font=('Helvetica', 13), bg='#f4f7fc', fg='#56647a').pack(anchor='w')
    tk.Label(frame, text='一次安装本地助手和 Chrome 扩展。\n内置运行环境，无需手动安装 Python。',
             justify='left', font=('Helvetica', 14), bg='#f4f7fc', fg='#17243d').pack(anchor='w', pady=20)
    status = tk.StringVar(value='模型在首次使用时下载，语音识别在本机完成。')
    tk.Label(frame, textvariable=status, wraplength=565, justify='left',
             bg='#f4f7fc', fg='#42516b', font=('Helvetica', 13)).pack(anchor='w', pady=(0, 12))
    state = {}
    bar = ttk.Progressbar(frame, mode='indeterminate')
    bar.pack(fill='x', pady=(0, 10))
    def report(text): window.after(0, status.set, text)
    def complete(result):
        state.update(result); bar.stop(); install_button.configure(state='normal', text='重新安装 / 修复')
        copy_button.configure(state='normal'); folder_button.configure(state='normal')
        path.set(result['extension'])
    def failed(error):
        bar.stop(); install_button.configure(state='normal')
        status.set('安装未完成。')
        messagebox.showerror('安装失败', str(error), parent=window)
    def work():
        try:
            result = install(RESOURCES / 'payload', config, progress=report)
        except Exception as exc:
            window.after(0, failed, exc)
        else: window.after(0, complete, result)
    def begin():
        install_button.configure(state='disabled'); bar.start(12)
        threading.Thread(target=work, daemon=True).start()
    install_button = ttk.Button(frame, text='安装助手和插件', command=begin)
    install_button.pack(fill='x', pady=(0, 14))
    tk.Label(frame, text='安装后，在 Chrome 完成一次确认：', bg='#f4f7fc', fg='#17243d',
             font=('Helvetica', 14, 'bold')).pack(anchor='w')
    tk.Label(frame, text='开发者模式 → 加载已解压的扩展程序\n按 ⌘⇧G，粘贴下方路径，回车，再点“选择”。',
             justify='left', bg='#f4f7fc', fg='#42516b', font=('Helvetica', 13)).pack(anchor='w', pady=8)
    path = tk.StringVar(value='安装后这里会显示准确的扩展文件夹路径')
    ttk.Entry(frame, textvariable=path, state='readonly').pack(fill='x', pady=(0, 10))
    def copy_open():
        window.clipboard_clear(); window.clipboard_append(state['extension']); window.update()
        subprocess.Popen(['/usr/bin/open', '-a', 'Google Chrome', 'chrome://extensions/'])
    copy_button = ttk.Button(frame, text='复制路径并打开 Chrome', command=copy_open, state='disabled')
    copy_button.pack(fill='x')
    folder_button = ttk.Button(frame, text='打开插件文件夹',
        command=lambda: subprocess.Popen(['/usr/bin/open', state['extension']]), state='disabled')
    folder_button.pack(fill='x', pady=6)
    window.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true', help='Install without opening the GUI')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--chrome-directory', type=Path)
    args = parser.parse_args()
    config = json.loads((RESOURCES / 'product.json').read_text())
    if args.install:
        result = install(RESOURCES / 'payload', config, args.destination, args.chrome_directory,
                         progress=lambda value: print(value, file=sys.stderr, flush=True))
        print(json.dumps(result, ensure_ascii=False))
    else:
        gui(config)


if __name__ == '__main__':
    main()

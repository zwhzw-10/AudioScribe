"""Platform paths shared by the native host and macOS packaging tests."""
import os
import sys
from pathlib import Path


def data_directory(product, variable, environ=None, platform=None, user_directory=None):
    env = os.environ if environ is None else environ
    target = sys.platform if platform is None else platform
    if env.get(variable):
        return Path(env[variable]).expanduser()
    user = Path.home() if user_directory is None else Path(user_directory)
    if target == 'darwin':
        return user / 'Library' / 'Application Support' / product / 'Data'
    if target == 'win32':
        return Path(env.get('LOCALAPPDATA', user / 'AppData' / 'Local')) / product / 'Data'
    return Path(env.get('XDG_DATA_HOME', user / '.local' / 'share')) / product / 'Data'


def runtime_python(app, platform=None):
    target = sys.platform if platform is None else platform
    return Path(app) / ('runtime/python.exe' if target == 'win32' else 'runtime/bin/python3')


def deno_path(app, platform=None):
    target = sys.platform if platform is None else platform
    return Path(app) / 'tools' / 'deno' / ('deno.exe' if target == 'win32' else 'deno')

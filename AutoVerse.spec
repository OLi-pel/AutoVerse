# AutoVerse.spec

# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

# --- FIX: Import torch to find its library path ---
import torch
torch_root = os.path.dirname(torch.__file__)
torch_lib_path = os.path.join(torch_root, 'lib')
# ------------------------------------------------

# Determine the ffmpeg binary path based on the OS.
if sys.platform == 'win32':
    ffmpeg_binary_path = os.path.join('bin', 'ffmpeg.exe')
else:
    # For macOS and Linux
    ffmpeg_binary_path = os.path.join('bin', 'ffmpeg')

datas = [
    ('tutorials.json', '.'),
    ('ui/main_window.ui', 'ui'),
    ('assets', 'assets'),
    *collect_data_files('lightning_fabric'),
    *collect_data_files('speechbrain'),
    *collect_data_files('pyannote'),
    *collect_data_files('tiktoken'),
    *collect_data_files('transformers')
]

# --- FIX: Explicitly collect torch DLLs (especially libiomp5md.dll) ---
# We add them to 'torch/lib' in the bundle so c10.dll can find them.
torch_binaries = []
if os.path.exists(torch_lib_path):
    torch_binaries.append((os.path.join(torch_lib_path, '*.dll'), os.path.join('torch', 'lib')))
# -----------------------------------------------------------------------

a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=[(ffmpeg_binary_path, 'bin')] + torch_binaries, # Add torch binaries here
    datas=datas,
    hiddenimports=[
        'torch', 'torchaudio', 'soundfile', 'pyaudio', 'speechbrain',
        'pyannote.audio', 'pandas', 'sklearn', 'tiktoken', 'scipy',
        'moviepy', 'PySide6', 'lightning_fabric', 'transformers'
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoVerse',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join('assets', 'logo.icns' if sys.platform == 'darwin' else 'logo.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutoVerse_App'
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='AutoVerse.app',
        icon=os.path.join('assets', 'logo.icns'),
        bundle_identifier=None,
    )
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

torch_binaries = []
if sys.platform == 'win32':
    # Explicitly find the site-packages/torch/lib directory
    # We use a dummy import to find the path reliably on the build machine
    import torch
    torch_root = os.path.dirname(torch.__file__)
    torch_lib = os.path.join(torch_root, 'lib')
    
    if os.path.exists(torch_lib):
        torch_binaries.append((os.path.join(torch_lib, '*'), os.path.join('torch', 'lib')))

a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=[(ffmpeg_binary_path, 'bin')] + torch_binaries, # Add torch binaries here
    datas=datas,
    hiddenimports=[
        'torch', 'torchaudio', 'soundfile', 'pyaudio', 'speechbrain',
        'pyannote.audio', 'pandas', 'sklearn', 'tiktoken', 'scipy',
        'moviepy', 'PySide6', 'lightning_fabric', 'transformers',
        'pyannote.audio.models.embedding', 
        'pyannote.audio.models.segmentation',
        'speechbrain.lobes.models.ECAPA_TDNN',
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)

new_binaries = []
for (src, dest, typecode) in a.binaries:
    # If the file is libiomp5md.dll and it's going to the root '.', skip it
    if 'libiomp5md.dll' in src.lower() and (dest == '.' or dest == ''):
        print(f"Excluding duplicate binary: {src}")
        continue
    new_binaries.append((src, dest, typecode))
a.binaries = new_binaries

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
# AutoVerse.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

# --- Import torch to find its library path ---
import torch
torch_root = os.path.dirname(torch.__file__)
torch_lib_path = os.path.join(torch_root, 'lib')
# ---------------------------------------------

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
    if os.path.exists(torch_lib_path):
        # Collect everything in torch/lib to dist/AutoVerse/torch/lib
        # This includes c10.dll, torch_cpu.dll, etc.
        torch_binaries.append((os.path.join(torch_lib_path, '*'), os.path.join('torch', 'lib')))

a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=[(ffmpeg_binary_path, 'bin')] + torch_binaries,
    datas=datas,
    hiddenimports=[
        'torch', 'torchaudio', 'soundfile', 'pyaudio', 'speechbrain',
        'pyannote.audio', 'pandas', 'sklearn', 'tiktoken', 'scipy',
        'moviepy', 'PySide6', 'lightning_fabric', 'transformers',
        'pyannote.audio.models.embedding', 
        'pyannote.audio.models.segmentation',
        'speechbrain.lobes.models.ECAPA_TDNN',
        'sklearn.neighbors._typedefs',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
        'torch.distributions',
        'torch.random',
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)

# --- CRITICAL FIX: MANAGE libiomp5md.dll ---
# 1. Remove ANY auto-collected libiomp5md.dll (e.g. from numpy) to prevent conflicts.
# 2. Explicitly add the one from Torch to the ROOT of the application.
#    Windows searches the application directory first. This ensures c10.dll finds
#    the compatible OpenMP library immediately.

new_binaries = []
torch_iomp5_src = os.path.join(torch_lib_path, 'libiomp5md.dll')

for (src, dest, typecode) in a.binaries:
    filename = os.path.basename(src).lower()
    # Filter out any generic libiomp5md.dll
    if filename == 'libiomp5md.dll':
        continue
    new_binaries.append((src, dest, typecode))

# Force add the Torch version to the root ('.')
if os.path.exists(torch_iomp5_src):
    print(f"Force-adding {torch_iomp5_src} to application root.")
    new_binaries.append((torch_iomp5_src, '.', 'BINARY'))
else:
    print("Warning: Could not find libiomp5md.dll in torch/lib")

a.binaries = new_binaries
# -------------------------------------------

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
# AutoVerse.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import glob  # Added glob for robust file finding
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

# --- Collect Torch Binaries Safely ---
torch_binaries = []
if sys.platform == 'win32':
    if os.path.exists(torch_lib_path):
        # Use glob to find all files, instead of relying on wildcards in the tuple
        # Analysis binaries expects (source_path, dest_folder)
        dll_files = glob.glob(os.path.join(torch_lib_path, '*'))
        for f in dll_files:
            if os.path.isfile(f):
                # Place them in dist/AutoVerse/torch/lib
                torch_binaries.append((f, os.path.join('torch', 'lib')))

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

new_binaries = []
torch_iomp5_src = os.path.join(torch_lib_path, 'libiomp5md.dll')

# a.binaries is a list of tuples: (INTERNAL_DEST_NAME, EXTERNAL_SOURCE_PATH, TYPECODE)
for (dest_name, source_path, typecode) in a.binaries:
    filename = os.path.basename(dest_name).lower()
    
    # Filter out any generic libiomp5md.dll
    if filename == 'libiomp5md.dll':
        print(f"Excluding auto-collected: {dest_name} from {source_path}")
        continue
        
    new_binaries.append((dest_name, source_path, typecode))

# Force add the Torch version to the root
if os.path.exists(torch_iomp5_src):
    print(f"Force-adding {torch_iomp5_src} to application root.")
    # CORRECT FORMAT: ('internal_filename', 'external_absolute_path', 'BINARY')
    new_binaries.append(('libiomp5md.dll', torch_iomp5_src, 'BINARY'))
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
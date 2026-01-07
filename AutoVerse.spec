# AutoVerse.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import glob
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
        # Use glob to find all files in torch/lib
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
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)

# --- CRITICAL FIX 1: MANAGE libiomp5md.dll ---
# 1. Remove ANY auto-collected libiomp5md.dll to prevent conflicts.
# 2. Explicitly add the one from Torch to the ROOT of the application.

new_binaries = []
torch_iomp5_src = os.path.join(torch_lib_path, 'libiomp5md.dll')

# --- CRITICAL FIX 2: FORCE vcruntime140_1.dll ---
# c10.dll specifically requires vcruntime140_1.dll, but PyInstaller often only bundles vcruntime140.dll
# We try to find it in the system directory or the Python directory.
vcruntime1_found = False
# Common places for vcruntime140_1.dll
sys_path = os.path.join(os.environ['SystemRoot'], 'System32', 'vcruntime140_1.dll')
py_path = os.path.join(os.path.dirname(sys.executable), 'vcruntime140_1.dll')

vcruntime1_src = None
if os.path.exists(sys_path):
    vcruntime1_src = sys_path
elif os.path.exists(py_path):
    vcruntime1_src = py_path

for (dest_name, source_path, typecode) in a.binaries:
    filename = os.path.basename(dest_name).lower()
    
    # Filter out generic libiomp5md.dll
    if filename == 'libiomp5md.dll':
        continue
    
    # Check if we already have vcruntime140_1
    if filename == 'vcruntime140_1.dll':
        vcruntime1_found = True
        
    new_binaries.append((dest_name, source_path, typecode))

# Force add Torch libiomp5md.dll to root
if os.path.exists(torch_iomp5_src):
    print(f"Force-adding {torch_iomp5_src} to application root.")
    new_binaries.append(('libiomp5md.dll', torch_iomp5_src, 'BINARY'))
else:
    print("Warning: Could not find libiomp5md.dll in torch/lib")

# Force add vcruntime140_1.dll if missing
if not vcruntime1_found and vcruntime1_src:
    print(f"Force-adding {vcruntime1_src} to application root (missing dependency for c10.dll).")
    new_binaries.append(('vcruntime140_1.dll', vcruntime1_src, 'BINARY'))
elif not vcruntime1_found:
    print("Warning: Could not locate vcruntime140_1.dll. Application may fail to load c10.dll.")

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
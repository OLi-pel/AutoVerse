# AutoVerse.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import shutil
from PyInstaller.utils.hooks import collect_data_files

# --- 1. CONFIGURATION ---
block_cipher = None

# Determine FFmpeg binary name based on OS
if sys.platform == 'win32':
    ffmpeg_binary_name = 'ffmpeg.exe'
else:
    ffmpeg_binary_name = 'ffmpeg'

# Path to local bin folder (for bundling)
ffmpeg_local_path = os.path.join('bin', ffmpeg_binary_name)

# --- 2. DATA COLLECTION ---
datas = [
    ('tutorials.json', '.'),
    ('ui/main_window.ui', 'ui'),
    ('assets', 'assets'),
    *collect_data_files('lightning_fabric'),
    *collect_data_files('speechbrain'),
    *collect_data_files('pyannote'),
    *collect_data_files('tiktoken'),
    *collect_data_files('transformers'),
    *collect_data_files('whisper'),
]

# --- 3. BINARY COLLECTION ---
binaries = []

# Verify FFmpeg exists before building
if os.path.exists(ffmpeg_local_path):
    print(f"Bundling FFmpeg from: {ffmpeg_local_path}")
    binaries.append((ffmpeg_local_path, 'bin'))
else:
    print(f"WARNING: FFmpeg not found at {ffmpeg_local_path}. App may crash if not in system PATH.")

# --- WINDOWS SPECIFIC: AGGRESSIVE DLL BUNDLING ---
if sys.platform == 'win32':
    import torch
    torch_root = os.path.dirname(torch.__file__)
    torch_lib_path = os.path.join(torch_root, 'lib')
    
    # List of DLLs that MUST be in the root folder for c10.dll to load
    critical_dlls = [
        "libiomp5md.dll", 
        "vcruntime140.dll", 
        "vcruntime140_1.dll", 
        "msvcp140.dll", 
        "msvcp140_1.dll"
    ]

    # 1. Search in Torch Library first (best for libiomp5md.dll)
    for dll in critical_dlls:
        found = False
        potential_path = os.path.join(torch_lib_path, dll)
        if os.path.exists(potential_path):
            print(f"Found {dll} in Torch: {potential_path}")
            binaries.append((potential_path, '.')) # Copy to ROOT
            found = True
        
        # 2. If not in Torch, search System32 (best for vcruntime/msvcp)
        if not found:
            sys32 = os.path.join(os.environ['SystemRoot'], 'System32')
            potential_path = os.path.join(sys32, dll)
            if os.path.exists(potential_path):
                print(f"Found {dll} in System32: {potential_path}")
                binaries.append((potential_path, '.')) # Copy to ROOT
                found = True
        
        if not found:
            print(f"WARNING: Could not find critical DLL: {dll}")

    # 3. Collect other Torch DLLs normally
    if os.path.exists(torch_lib_path):
        import glob
        dlls = glob.glob(os.path.join(torch_lib_path, '*.dll'))
        for dll in dlls:
            # We already handled libiomp5md explicitly above, but duplicating to torch/lib is safe
            binaries.append((dll, 'torch/lib'))

# ---------------------------------------------------------

a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=binaries,
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
        'scipy.special.cython_special',
        'scipy.spatial.transform._rotation_groups',
        'passlib.handlers.bcrypt', 
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    argv_emulation=False,
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
    name='AutoVerse_App',
)

# macOS Bundle Creation
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='AutoVerse.app',
        icon=os.path.join('assets', 'logo.icns'),
        bundle_identifier='com.olipel.autoverse',
    )
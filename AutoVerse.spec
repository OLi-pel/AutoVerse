# AutoVerse.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import glob
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

# --- WINDOWS SPECIFIC: Handle DLL Hell (WinError 1114) ---
if sys.platform == 'win32':
    import torch
    torch_root = os.path.dirname(torch.__file__)
    torch_lib_path = os.path.join(torch_root, 'lib')
    
    # 1. Find and Bundle Critical PyTorch Dependencies (OpenMP)
    iomp5_src = os.path.join(torch_lib_path, 'libiomp5md.dll')
    if not os.path.exists(iomp5_src):
        # Fallback search
        for root, dirs, files in os.walk(torch_root):
            if 'libiomp5md.dll' in files:
                iomp5_src = os.path.join(root, 'libiomp5md.dll')
                break
    
    if os.path.exists(iomp5_src):
        print(f"Force-bundling libiomp5md.dll from: {iomp5_src}")
        # Place it in root (.) AND inside torch/lib to be safe
        binaries.append((iomp5_src, '.'))
        binaries.append((iomp5_src, 'torch/lib'))
    
    # 2. Collect other Torch DLLs
    if os.path.exists(torch_lib_path):
        dlls = glob.glob(os.path.join(torch_lib_path, '*.dll'))
        for dll in dlls:
            if 'libiomp5md.dll' not in dll: 
                binaries.append((dll, 'torch/lib'))

    # 3. FORCE BUNDLE C++ RUNTIME (VCRUNTIME140_1.dll)
    # This fixes the c10.dll initialization error on fresh installs
    import ctypes.util
    
    critical_system_dlls = [
        "vcruntime140.dll",
        "vcruntime140_1.dll", 
        "msvcp140.dll",
        "msvcp140_1.dll"
    ]
    
    for dll_name in critical_system_dlls:
        # Try to find it in the system path of the BUILD machine
        dll_path = ctypes.util.find_library(dll_name)
        if not dll_path:
            # Fallback check in System32 directly if find_library fails
            sys32 = os.path.join(os.environ['SystemRoot'], 'System32')
            candidate = os.path.join(sys32, dll_name)
            if os.path.exists(candidate):
                dll_path = candidate

        if dll_path and os.path.exists(dll_path):
            print(f"Force-bundling System DLL: {dll_name} from {dll_path}")
            # Put them in the root of the app so Python finds them immediately
            binaries.append((dll_path, '.'))
        else:
            print(f"WARNING: Could not find system DLL {dll_name} on build machine.")

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
    console=False, # Set to True for debugging console, False for release
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
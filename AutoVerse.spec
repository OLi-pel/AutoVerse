# AutoVerse.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# --- Configuration ---
if sys.platform == 'win32':
    ffmpeg_binary_name = 'ffmpeg.exe'
else:
    ffmpeg_binary_name = 'ffmpeg'

ffmpeg_local_path = os.path.join('bin', ffmpeg_binary_name)

# --- Data Collection ---
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

# --- Binary Collection ---
binaries = []
if os.path.exists(ffmpeg_local_path):
    print(f"Bundling FFmpeg from: {ffmpeg_local_path}")
    binaries.append((ffmpeg_local_path, 'bin'))

# --- Analysis ---
a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'scipy.special.cython_special',
        'scipy.spatial.transform._rotation_groups',
        'sklearn.neighbors._typedefs',
        'sklearn.utils._cython_blas',
        'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils',
        'passlib.handlers.bcrypt', 
        'torchaudio.lib.libtorchaudio',
    ],
    # IMPORTANT: Point to your new hooks folder
    hookspath=['hook'], 
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
    # DISABLE UPX to prevent corruption of the C++ Runtime DLLs we just bundled
    upx=False, 
    console=True,
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
    upx=False,
    upx_exclude=[],
    name='AutoVerse_App',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='AutoVerse.app',
        icon=os.path.join('assets', 'logo.icns'),
        bundle_identifier='com.olipel.autoverse',
    )
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import glob
from PyInstaller.utils.hooks import collect_data_files

import torch
torch_root = os.path.dirname(torch.__file__)
torch_lib_path = os.path.join(torch_root, 'lib')

if sys.platform == 'win32':
    ffmpeg_binary_path = os.path.join('bin', 'ffmpeg.exe')
else:
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
        dll_files = glob.glob(os.path.join(torch_lib_path, '*'))
        for f in dll_files:
            if os.path.isfile(f):
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

new_binaries = []
torch_iomp5_src = os.path.join(torch_lib_path, 'libiomp5md.dll')

vcruntime1_found = False
sys_path = os.path.join(os.environ['SystemRoot'], 'System32', 'vcruntime140_1.dll')
py_path = os.path.join(os.path.dirname(sys.executable), 'vcruntime140_1.dll')

vcruntime1_src = None
if os.path.exists(sys_path):
    vcruntime1_src = sys_path
elif os.path.exists(py_path):
    vcruntime1_src = py_path

for (dest_name, source_path, typecode) in a.binaries:
    filename = os.path.basename(dest_name).lower()
    if filename == 'libiomp5md.dll':
        continue
    if filename == 'vcruntime140_1.dll':
        vcruntime1_found = True
    new_binaries.append((dest_name, source_path, typecode))

if os.path.exists(torch_iomp5_src):
    print(f"Force-adding {torch_iomp5_src} to application root.")
    new_binaries.append(('libiomp5md.dll', torch_iomp5_src, 'BINARY'))

if not vcruntime1_found and vcruntime1_src:
    print(f"Force-adding {vcruntime1_src} to application root.")
    new_binaries.append(('vcruntime140_1.dll', vcruntime1_src, 'BINARY'))

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
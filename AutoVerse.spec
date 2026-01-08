# AutoVerse.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

block_cipher = None

# Determine the ffmpeg binary path based on the OS.
if sys.platform == 'win32':
    ffmpeg_binary_name = 'ffmpeg.exe'
else:
    ffmpeg_binary_name = 'ffmpeg'

ffmpeg_local_path = os.path.join('bin', ffmpeg_binary_name)

# Collect datas
datas = [
    ('ui/main_window.ui', 'ui'),
    ('assets', 'assets'),
    ('tutorials.json', '.'), 
    *collect_data_files('lightning_fabric'),
    *collect_data_files('speechbrain'),
    *collect_data_files('pyannote'),
    *collect_data_files('tiktoken'),
    *collect_data_files('transformers'),
    *collect_data_files('whisper'),
    *copy_metadata('tqdm'),
    *copy_metadata('regex'),
    *copy_metadata('requests'),
    *copy_metadata('packaging'),
    *copy_metadata('filelock'),
    *copy_metadata('numpy'),
    *copy_metadata('tokenizers'),
    *copy_metadata('huggingface-hub'),
    *copy_metadata('safetensors'),
    *copy_metadata('pyyaml'),
]

# Binaries
binaries = []
if os.path.exists(ffmpeg_local_path):
    print(f"Bundling FFmpeg from: {ffmpeg_local_path}")
    binaries.append((ffmpeg_local_path, 'bin'))

a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    # --- UPDATED HIDDENIMPORTS ---
    hiddenimports=[
        'torch', 'torchaudio', 'soundfile', 'pyaudio', 'speechbrain',
        'pyannote.audio',
        # Explicitly include pyannote dynamic modules
        'pyannote.audio.pipelines',
        'pyannote.audio.pipelines.speaker_diarization',
        'pyannote.audio.models',
        'pyannote.audio.models.segmentation',
        'pyannote.audio.models.embedding',
        'asteroid_filterbanks',
        # Standard dependencies
        'pandas', 'sklearn', 'tiktoken', 'scipy',
        'moviepy', 'PySide6', 'lightning_fabric', 'transformers',
        'scipy.special.cython_special', 'sklearn.neighbors._typedefs',
        'sklearn.utils._cython_blas', 'sklearn.neighbors._quad_tree',
        'sklearn.tree._utils'
    ],
    # REMOVE THE CUSTOM HOOK PATH
    hookspath=[], 
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
    console=True, # Keep True for debugging if it crashes, switch to False later
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

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='AutoVerse.app',
        icon=os.path.join('assets', 'logo.icns'),
        bundle_identifier='com.olipel.autoverse',
    )
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

# This spec file is designed to be cross-platform for Windows and macOS.

# --- Platform-specific setup ---
# This approach makes the spec file adaptable. The Windows runner will
# bundle ffmpeg, while the macOS runner (using setup-ffmpeg) will not.
if sys.platform == 'win32':
    app_name = 'TranscriptionOli' # The .exe will be added automatically
    runtime_hooks = ['win_pre_init_hook.py']
    ffmpeg_binary_list = [('bin/ffmpeg.exe', 'bin')]
else:
    app_name = 'TranscriptionOli'
    runtime_hooks = []
    ffmpeg_binary_list = [] # ffmpeg is found in the PATH on the GitHub runner


a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=ffmpeg_binary_list,
    datas=[
        # Add the core UI and assets needed by the application
        ('ui/main_window.ui', 'ui'),
        ('assets', 'assets'),
        
        # Explicitly collect all data files from these key libraries
        *collect_data_files('lightning_fabric'),
        *collect_data_files('speechbrain'),
        *collect_data_files('pyannote')
    ],
    hiddenimports=[
        'torch', 'torchaudio', 'soundfile', 'pyaudio', 'speechbrain',
        'pyannote.audio', 'pandas', 'sklearn', 'tiktoken', 'scipy',
        'moviepy', 'PySide6', 'lightning_fabric',
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
    excludes=[],
    noarchive=False
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
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
    name='TranscriptionOli_App'
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='TranscriptionOli.app',
        icon=os.path.join('assets', 'logo.icns'),
        bundle_identifier=None,
    )
# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

# --- Unified Configuration ---
# This spec file is now fully cross-platform for Windows and macOS.

# Define platform-specific binaries
if sys.platform == 'win32':
    ffmpeg_binary_path = os.path.join('bin', 'ffmpeg.exe')
else:
    ffmpeg_binary_path = os.path.join('bin', 'ffmpeg')

a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=[(ffmpeg_binary_path, 'bin')], # Bundle ffmpeg for all platforms
    datas=[
        ('ui/main_window.ui', 'ui'),
        ('assets', 'assets'),
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
    runtime_hooks=['runtime_hook.py'], # Use the unified hook for all platforms
    excludes=[],
    noarchive=False
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TranscriptionOli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Use an inline if to select the correct icon format
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
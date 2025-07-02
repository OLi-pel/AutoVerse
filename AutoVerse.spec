# AutoVerse.spec

# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files

# Determine the ffmpeg binary path based on the OS.
if sys.platform == 'win32':
    ffmpeg_binary_path = os.path.join('bin', 'ffmpeg.exe')
else:
    # For macOS and Linux
    ffmpeg_binary_path = os.path.join('bin', 'ffmpeg')

datas = [
    ('ui/main_window.ui', 'ui'),
    ('assets', 'assets'),
    *collect_data_files('lightning_fabric'),
    *collect_data_files('speechbrain'),
    *collect_data_files('pyannote'),
    *collect_data_files('tiktoken'),
    *collect_data_files('transformers')
]

a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=[(ffmpeg_binary_path, 'bin')],
    datas=datas,
    hiddenimports=[
        'torch', 'torchaudio', 'soundfile', 'pyaudio', 'speechbrain',
        'pyannote.audio', 'pandas', 'sklearn', 'tiktoken', 'scipy',
        'moviepy', 'PySide6', 'lightning_fabric', 'transformers'
    ],
    hookspath=['.'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)
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

# --- NEW SECTION: Define the updater executable ---
updater_analysis = Analysis(
    ['updater.py'], # Updater script entry point
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['requests'], # Add requests here if it is used
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False
)
updater_pyz = PYZ(updater_analysis.pure)
updater_exe = EXE(
    updater_pyz,
    updater_analysis.scripts,
    exclude_binaries=True,
    name='updater',
    debug=False,
    strip=False,
    upx=True,
    console=True, # Updater is a console app
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)

# --- END NEW SECTION ---
coll = COLLECT(
    exe,
    updater_exe, # <--- ADD THE UPDATER EXE HERE
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
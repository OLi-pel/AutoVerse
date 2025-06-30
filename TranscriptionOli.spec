# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files

# This spec file is designed to be cross-platform for Windows and macOS.

# --- Platform-specific setup ---
# Set the executable name and runtime hook for Windows
if sys.platform == 'win32':
    app_name = 'TranscriptionOli.exe'
    runtime_hooks = ['win_pre_init_hook.py']
    # Include ffmpeg binary for Windows
    ffmpeg_binary = [('bin/ffmpeg.exe', 'bin')]
else:
    app_name = 'TranscriptionOli'
    runtime_hooks = []
    ffmpeg_binary = []


a = Analysis(
    ['main_pyside.py'],  # Main entry point for the PySide6 app
    pathex=[],
    binaries=ffmpeg_binary, # Include ffmpeg only on Windows
    datas=[
        # Add the core UI and assets needed by the application
        ('ui/main_window.ui', 'ui'),
        ('assets', 'assets')
    ],
    hiddenimports=[
        # A comprehensive list to ensure stability
        'torch',
        'torchaudio',
        'soundfile',
        'pyaudio',
        'speechbrain',
        'pyannote.audio',
        'pandas',
        'sklearn',
        'tiktoken',
        'scipy',
        'moviepy',
        'PySide6',
        'lightning_fabric', # From old spec, good to keep
    ],
    hookspath=['.'], # Look for our custom hooks (hook-whisper.py, etc.) in the root dir
    hooksconfig={},
    runtime_hooks=runtime_hooks, # Include the pre-init hook only on Windows
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
    console=False, # This is a GUI app, not a console app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # TODO: Create a logo.icns for macOS and logo.ico for Windows in the 'assets' dir
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
    name='TranscriptionOli_App' # The final folder name will be this
)

# --- macOS Specific BUNDLE block ---
# This part only runs when building on a Mac, creating the .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='TranscriptionOli.app',
        icon=os.path.join('assets', 'logo.icns'), # Path to your .icns file
        bundle_identifier=None, # e.g., 'com.yourname.transcriptionoli'
    )
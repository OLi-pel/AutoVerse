# win_pre_init_hook.py
# This is a PyInstaller runtime hook.
# It runs right before the main script to set up the environment.

import os
import sys

# On Windows, PyInstaller unpacks all files to a temporary directory.
# The path to this directory is stored in sys._MEIPASS.
# Our ffmpeg.exe is in a 'bin' subdirectory within this temp folder.
# We must add this 'bin' subdirectory to the system PATH so that moviepy
# and other libraries can find and use ffmpeg.exe.

if hasattr(sys, '_MEIPASS'):
    bin_dir = os.path.join(sys._MEIPASS, 'bin')
    os.environ['PATH'] = bin_dir + os.pathsep + os.environ.get('PATH', '')
# hook-whisper.py
from PyInstaller.utils.hooks import collect_data_files

# Collect the 'assets' directory from the whisper package.
# The files will be placed in 'whisper/assets' in the bundle by default
# when 'subdir' is specified.
datas = collect_data_files('whisper', subdir='assets', include_py_files=False)

print(f"Hook-whisper: Adding data files: {datas}")
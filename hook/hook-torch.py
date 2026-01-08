# hooks/hook-torch.py
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# 1. Standard Collection - This usually covers everything needed
datas = collect_data_files('torch')
binaries = collect_dynamic_libs('torch')

# [FIX]: Removed the "Brute Force DLL Bundling" block that copied 
# all DLLs to the root. This was causing duplication and WinError 1114.

# 2. Collect CUDA extras if visible (for local builds mostly, but safe to keep)
try:
    import pynvjitlink
    binaries.extend(collect_dynamic_libs('pynvjitlink'))
except ImportError:
    pass
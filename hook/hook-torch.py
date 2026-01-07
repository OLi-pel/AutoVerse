# hooks/hook-torch.py
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

print("--- CUSTOM TORCH HOOK: Hybrid CPU/GPU Strategy ---")

# 1. Standard Collection
datas = collect_data_files('torch')
binaries = collect_dynamic_libs('torch')

# 2. Windows Specific: Brute Force DLL Bundling
if sys.platform == 'win32':
    import torch
    torch_root = os.path.dirname(torch.__file__)
    torch_lib = os.path.join(torch_root, 'lib')
    
    print(f"--- HOOK: Scanning {torch_lib} for DLLs ---")

    if os.path.exists(torch_lib):
        for filename in os.listdir(torch_lib):
            # Bundle EVERY .dll found in torch/lib to the application root
            # This solves WinError 1114 by ensuring dependencies are strictly adjacent to the exe
            if filename.lower().endswith('.dll'):
                full_path = os.path.join(torch_lib, filename)
                # Tuple format: (source_path, destination_folder)
                # '.' means place it right next to AutoVerse.exe
                binaries.append((full_path, '.'))
                # print(f"--- HOOK: Bundling {filename} to root")

# 3. Collect CUDA extras if visible (for local builds mostly, but safe to keep)
try:
    import pynvjitlink
    binaries.extend(collect_dynamic_libs('pynvjitlink'))
except ImportError:
    pass
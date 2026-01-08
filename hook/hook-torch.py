import os
import glob
from PyInstaller.utils.hooks import get_package_paths
from PyInstaller.compat import is_win

# --- SAFETY FIX: Do NOT import torch directly ---
try:
    # 1. Find the package path without initializing the DLLs
    _, torch_root = get_package_paths('torch')
    
    print(f"--- CUSTOM HOOK: Found Torch root at {torch_root} ---")

    datas = []
    binaries = []

    # 2. Manually collect shared libraries (lib/*.dll)
    lib_dir = os.path.join(torch_root, 'lib')
    if os.path.exists(lib_dir):
        for file in os.listdir(lib_dir):
            if file.lower().endswith(('.dll', '.lib', '.so', '.dylib')):
                full_path = os.path.join(lib_dir, file)
                binaries.append((full_path, 'torch/lib'))
                if 'libomp' in file or 'asmjit' in file:
                    print(f"--- CUSTOM HOOK: Explicitly found critical DLL: {file}")
    
    # 3. Manually collect 'bin' folder
    bin_dir = os.path.join(torch_root, 'bin')
    if os.path.exists(bin_dir):
        for file in os.listdir(bin_dir):
             if file.endswith('.dll') or file.endswith('.exe'):
                full_path = os.path.join(bin_dir, file)
                binaries.append((full_path, 'torch/bin'))

    # 4. Recursively collect all data files (configs, etc.)
    for root, dirs, files in os.walk(torch_root):
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
        
        for filename in files:
            if filename.endswith(('.pyc', '.pyo')):
                continue
            
            # Skip DLLs here because we handled them in binaries
            if filename.lower().endswith('.dll'):
                continue

            src_path = os.path.join(root, filename)
            rel_path = os.path.relpath(src_path, os.path.dirname(torch_root))
            dest_dir = os.path.dirname(rel_path)
            
            datas.append((src_path, dest_dir))

    print(f"--- CUSTOM HOOK: Collected {len(binaries)} binaries and {len(datas)} data files manually ---")

except Exception as e:
    print(f"--- CUSTOM HOOK ERROR: Could not manually collect torch files: {e} ---")
    from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
    datas = collect_data_files('torch')
    binaries = collect_dynamic_libs('torch')

# 5. Handle pynvjitlink if present
try:
    import pynvjitlink
    from PyInstaller.utils.hooks import collect_dynamic_libs
    binaries.extend(collect_dynamic_libs('pynvjitlink'))
except ImportError:
    pass
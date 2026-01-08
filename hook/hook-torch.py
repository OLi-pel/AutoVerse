# hook/hook-torch.py
import os
from PyInstaller.utils.hooks import get_package_paths

# --- SAFETY FIX: Do NOT import torch directly ---
# Importing torch (with CUDA) on a CPU-only CI runner causes 
# an Access Violation (0xc0000005) in _load_dll_libraries.
# Instead, we find the path using get_package_paths which is safer.

try:
    # 1. Find the package path without initializing the DLLs
    _, torch_root = get_package_paths('torch')
    
    print(f"--- CUSTOM HOOK: Found Torch root at {torch_root} ---")

    datas = []
    binaries = []

    # 2. Manually collect shared libraries (lib/*.dll)
    # The standard hook does collect_dynamic_libs, which imports torch.
    # We will do it manually to avoid the crash.
    lib_dir = os.path.join(torch_root, 'lib')
    if os.path.exists(lib_dir):
        # Collect all DLLs in torch/lib
        # We put them in 'torch/lib' inside the bundle
        for file in os.listdir(lib_dir):
            if file.endswith('.dll') or file.endswith('.lib') or file.endswith('.so') or file.endswith('.dylib'):
                full_path = os.path.join(lib_dir, file)
                binaries.append((full_path, 'torch/lib'))
    
    # 3. Manually collect 'bin' folder (for nvrtc, etc if present)
    bin_dir = os.path.join(torch_root, 'bin')
    if os.path.exists(bin_dir):
        for file in os.listdir(bin_dir):
             if file.endswith('.dll') or file.endswith('.exe'):
                full_path = os.path.join(bin_dir, file)
                binaries.append((full_path, 'torch/bin'))

    # 4. Recursively collect all data files (Python files are handled by analysis, but we need configs, etc)
    # We simply map the whole torch folder structure (excluding __pycache__) to datas
    # This ensures assets, libs, and extra python files are present.
    # Note: PyInstaller Analysis will find the .py files for import, but copying them as data 
    # ensures non-python assets inside the tree are kept.
    for root, dirs, files in os.walk(torch_root):
        # Skip pycache
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
        
        for filename in files:
            # We skip .pyc, .pyo
            if filename.endswith(('.pyc', '.pyo')):
                continue
            
            # Skip DLLs here because we handled them in binaries (optional, but cleaner)
            if filename.endswith('.dll'):
                continue

            src_path = os.path.join(root, filename)
            # Calculate relative path for destination
            rel_path = os.path.relpath(src_path, os.path.dirname(torch_root))
            dest_dir = os.path.dirname(rel_path)
            
            datas.append((src_path, dest_dir))

    print(f"--- CUSTOM HOOK: Collected {len(binaries)} binaries and {len(datas)} data files manually ---")

except Exception as e:
    print(f"--- CUSTOM HOOK ERROR: Could not manually collect torch files: {e} ---")
    # Fallback (might crash, but better than nothing)
    from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
    datas = collect_data_files('torch')
    binaries = collect_dynamic_libs('torch')

# 5. Handle pynvjitlink if present (safe to try import here as it's usually pure python or simple)
try:
    import pynvjitlink
    from PyInstaller.utils.hooks import collect_dynamic_libs
    binaries.extend(collect_dynamic_libs('pynvjitlink'))
except ImportError:
    pass
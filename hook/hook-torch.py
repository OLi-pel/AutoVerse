# hooks/hook-torch.py
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import ctypes.util
import os
import sys
import torch

print("--- CUSTOM TORCH HOOK STARTED: Bundling C++ Runtime & OpenMP ---")

# 1. Standard Collection
datas = collect_data_files('torch')
binaries = collect_dynamic_libs('torch')

# 2. WINDOWS SPECIFIC: FORCE BUNDLE DLLs
if sys.platform == 'win32':
    torch_root = os.path.dirname(torch.__file__)
    
    # --- A. Bundle Intel OpenMP (libiomp5md.dll) ---
    # Critical for PyTorch. We search specifically for it.
    iomp5_path = None
    candidate = os.path.join(torch_root, 'lib', 'libiomp5md.dll')
    if os.path.exists(candidate):
        iomp5_path = candidate
    else:
        for root, _, files in os.walk(torch_root):
            if 'libiomp5md.dll' in files:
                iomp5_path = os.path.join(root, 'libiomp5md.dll')
                break
    
    if iomp5_path:
        print(f"HOOK-TORCH: Found OpenMP at {iomp5_path}")
        # Copy to root (.) so the EXE sees it immediately (Fixes WinError 1114)
        binaries.append((iomp5_path, '.')) 
        # Also keep it in torch/lib
        binaries.append((iomp5_path, 'torch/lib'))
    else:
        print("HOOK-TORCH: WARNING - Could not find libiomp5md.dll!")

    # --- B. Bundle C++ Redistributable (App-Local Deployment) ---
    # This removes the need for the user to install vc_redist.x64.exe
    redist_dlls = [
        "vcruntime140.dll",
        "vcruntime140_1.dll", 
        "msvcp140.dll",
        "msvcp140_1.dll",
        "concrt140.dll" # Concurrency runtime (sometimes needed)
    ]
    
    # We look in System32 because the GitHub Runner definitely has them installed there.
    sys32 = os.path.join(os.environ['SystemRoot'], 'System32')
    
    for dll in redist_dlls:
        # Try finding via ctypes first
        dll_path = ctypes.util.find_library(dll)
        
        # Fallback to direct System32 check
        if not dll_path or not os.path.exists(dll_path):
            candidate = os.path.join(sys32, dll)
            if os.path.exists(candidate):
                dll_path = candidate
        
        if dll_path and os.path.exists(dll_path):
            print(f"HOOK-TORCH: Bundling Redist DLL {dll} from {dll_path}")
            # Put directly in root next to AutoVerse.exe
            binaries.append((dll_path, '.'))
        else:
            print(f"HOOK-TORCH: WARNING - Could not find system DLL {dll}!")

# 3. CUDA Support (if applicable)
try:
    if torch.cuda.is_available():
        binaries.extend(collect_dynamic_libs('pynvjitlink'))
except ImportError:
    pass
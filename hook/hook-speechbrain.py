# hook-speechbrain.py
import os
from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    copy_metadata,
    get_package_paths
)

# Collect all Python submodules from speechbrain.
hiddenimports = collect_submodules('speechbrain')
# Also explicitly add submodules that might be dynamically imported by importutils
# We will keep the more general ones and remove the specific .utils ones that caused issues.
hiddenimports.extend([
    'speechbrain.dataio.sampler',
    'speechbrain.dataio.dataloader',
    'speechbrain.dataio.dataset',
    'speechbrain.dataio.batch',
    'speechbrain.dataio.wer', # This one seems to be from dataio, likely okay.
    'speechbrain.utils.checkpoints',
    'speechbrain.utils.data_pipeline',
    'speechbrain.utils.distributed',
    # 'speechbrain.utils.dynamic_chunking', # Removed - caused warning
    'speechbrain.utils.edit_distance',
    'speechbrain.utils.fetching',
    'speechbrain.utils.hpopt',
    'speechbrain.utils.importutils',
    'speechbrain.utils.Accuracy', # Note: Class names are usually not needed in hiddenimports
                                 # unless they are in files named Accuracy.py and meant to be imported.
                                 # collect_submodules should handle actual modules.
                                 # For now, keeping as per your original if it resolved something else.
    'speechbrain.utils.metric_stats',
    'speechbrain.utils.parallel',
    # 'speechbrain.utils.profiler',           # Removed - caused warning
    'speechbrain.utils.text_to_sequence',
    'speechbrain.utils.torch_audio_backend',
    'speechbrain.utils.train_logger',
    # 'speechbrain.utils.wav2vec2_prepare',   # Removed - caused warning
    # 'speechbrain.utils.wer',                # Removed - caused warning (speechbrain.dataio.wer might be the correct one)
])


datas = []
try:
    datas += copy_metadata('speechbrain')
except Exception as e:
    print(f"Hook-speechbrain: Warning - could not copy metadata for speechbrain: {e}")

try:
    # Collect all data files from the speechbrain package, excluding .py files already handled by imports
    # and pycache. This is a broad approach.
    datas += collect_data_files(
        'speechbrain',
        include_py_files=False, # Python files are modules, not data in this context
        excludes=['**/__pycache__', '*.pyc']
    )
except Exception as e:
    print(f"Hook-speechbrain: Warning - could not collect general data files for speechbrain: {e}")

# The following explicit additions of 'utils' and 'dataio' directories might be
# redundant if collect_data_files above works correctly and comprehensively.
# However, keeping them if they were added to solve specific prior issues.
# PyInstaller's collect_data_files should ideally handle subdirectory contents.
try:
    pkg_base, pkg_dir = get_package_paths('speechbrain')
    
    # Handle speechbrain/utils
    utils_source_path = os.path.join(pkg_dir, 'utils')
    if os.path.isdir(utils_source_path):
        # This copies the entire 'utils' directory as data.
        # Python files within it will be treated as data unless also found as modules.
        datas.append((utils_source_path, 'speechbrain/utils'))
        print(f"Hook-speechbrain: Added speechbrain/utils directory from {utils_source_path}")
    else:
        print(f"Hook-speechbrain: Note - Could not find speechbrain/utils directory at {utils_source_path}")

    # Handle speechbrain/dataio
    dataio_source_path = os.path.join(pkg_dir, 'dataio')
    if os.path.isdir(dataio_source_path):
        datas.append((dataio_source_path, 'speechbrain/dataio'))
        print(f"Hook-speechbrain: Added speechbrain/dataio directory from {dataio_source_path}")
    else:
        print(f"Hook-speechbrain: Note - Could not find speechbrain/dataio directory at {dataio_source_path}")

    # Example for adding specific configuration files if needed:
    # If speechbrain has top-level .yaml configs it loads dynamically.
    # config_files_path = os.path.join(pkg_dir, 'config') # Example path
    # if os.path.isdir(config_files_path):
    # datas.append((config_files_path, 'speechbrain/config'))
    # print(f"Hook-speechbrain: Added speechbrain/config directory from {config_files_path}")

except Exception as e:
    print(f"Hook-speechbrain: Error processing speechbrain subdirectories: {e}")

print(f"Hook-speechbrain final hiddenimports: {hiddenimports}")
print(f"Hook-speechbrain final datas: {datas}")
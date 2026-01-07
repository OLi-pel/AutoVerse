# hook-pyannote.audio.py
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

# Collect all submodules from pyannote.audio, especially under .models
hiddenimports = collect_submodules('pyannote.audio.models')
hiddenimports.append('pyannote.audio.models.segmentation') # Be explicit just in case
hiddenimports.extend(collect_submodules('pyannote.audio.features'))
hiddenimports.extend(collect_submodules('pyannote.audio.pipelines'))
# You might need to add other pyannote.audio submodules if further errors occur,
# for example, 'pyannote.audio.core' if not already picked up.

# Collect metadata for pyannote.audio (e.g., entry points, licenses)
datas = copy_metadata('pyannote.audio')

print(f"Hook-pyannote.audio: Adding hidden imports: {hiddenimports}")
print(f"Hook-pyannote.audio: Adding datas: {datas}")
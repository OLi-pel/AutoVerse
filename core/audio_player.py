# core/audio_player.py
import logging
import time
import os
import tempfile
import subprocess
import platform
import numpy as np
import pyaudio
import soundfile as sf
from moviepy.editor import AudioFileClip
from scipy import signal
from PySide6.QtCore import QObject, Signal, Slot, QThread, QCoreApplication, QEventLoop

logger = logging.getLogger(__name__)

SIMPLE_AUDIO_EXTENSIONS = ('.wav', '.flac', '.ogg')

def _is_complex_format(file_path):
    return not file_path.lower().endswith(SIMPLE_AUDIO_EXTENSIONS)

class _PlayerWorker(QObject):
    position_changed = Signal(float)
    finished = Signal()
    state_changed = Signal(bool)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.pyaudio_instance = None
        self.stream = None
        self._playback_data = None
        self._playback_sr = 0
        self._num_channels = 0
        self._current_frame = 0
        self._total_frames = 0
        self._chunk_size_frames = 1024
        self._is_paused = False
        self._stop_requested = False

    @Slot(np.ndarray, int)
    def load_data(self, audio_data, sample_rate):
        self._stop()
        self._playback_data = audio_data
        self._playback_sr = sample_rate
        self._num_channels = self._playback_data.shape[1] if self._playback_data.ndim > 1 else 1
        self._total_frames = len(self._playback_data)
        self.set_position_in_seconds(0.0)

    @Slot()
    def play(self):
        if self.stream and self.stream.is_active():
            if self._is_paused:
                self._is_paused = False
                self.state_changed.emit(True)
            return
        if self._current_frame >= self._total_frames:
            self._current_frame = 0
        self._stop_requested = False
        self.state_changed.emit(True)
        self._playback_loop()

    @Slot()
    def pause(self):
        self._is_paused = True
        self.state_changed.emit(False)

    @Slot()
    def _stop(self):
        self._stop_requested = True
        self._is_paused = False

    @Slot(float)
    def set_position_in_seconds(self, seconds):
        if self._playback_sr > 0:
            self._current_frame = int(np.clip(seconds * self._playback_sr, 0, self._total_frames))
            self.position_changed.emit(self._current_frame / self._playback_sr)
        else:
            self.position_changed.emit(0.0)

    def _playback_loop(self):
        self.pyaudio_instance = pyaudio.PyAudio()
        output_device_index = None
        try:
            device_info = self.pyaudio_instance.get_default_output_device_info()
            output_device_index = device_info['index']
            logger.info(f"Worker: Attempting to play on device '{device_info['name']}' at {self._playback_sr}Hz")
        except Exception as e:
            logger.warning(f"Worker: Could not get default output device. Error: {e}")
            
        try:
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self._num_channels,
                rate=self._playback_sr,
                output=True,
                output_device_index=output_device_index,
                frames_per_buffer=self._chunk_size_frames
            )
        except Exception as e:
            logger.error(f"Failed to open PyAudio stream: {e}", exc_info=True)
            self.error.emit(f"Could not play on device: {e}")
            if self.pyaudio_instance: self.pyaudio_instance.terminate()
            self.state_changed.emit(False)
            return

        loop = QEventLoop()
        while self._current_frame < self._total_frames and not self._stop_requested:
            if self._is_paused:
                time.sleep(0.01)
                loop.processEvents()
                continue

            frames_to_write = min(self._chunk_size_frames, self._total_frames - self._current_frame)
            try:
                self.stream.write(self._playback_data[self._current_frame : self._current_frame + frames_to_write].tobytes())
            except OSError as e:
                logger.warning(f"OSError writing to stream: {e}")
                break

            self._current_frame += frames_to_write
            self.position_changed.emit(self._current_frame / self._playback_sr)
            loop.processEvents()

        if self.stream:
            try: self.stream.stop_stream(); self.stream.close()
            except OSError as e: logger.warning(f"OSError closing stream: {e}")
        
        self.stream = None
        self._stop_requested = False
        if self.pyaudio_instance:
             self.pyaudio_instance.terminate()
             self.pyaudio_instance = None

        if self._current_frame >= self._total_frames:
            self.finished.emit()
        self.state_changed.emit(False)

    def cleanup(self):
        self._stop()
        if self.pyaudio_instance: self.pyaudio_instance.terminate()

class AudioPlayer(QObject):
    _load_requested = Signal(np.ndarray, int)
    _play_requested = Signal()
    _pause_requested = Signal()
    _stop_requested = Signal()
    _position_set_requested = Signal(float)
    progress = Signal(float)
    finished = Signal()
    is_ready = Signal(bool)
    error = Signal(str)
    crashed = Signal()
    state_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self._duration = 0.0
        self._current_time = 0.0
        self._normalized_waveform = []
        self._prepared_for_device_name = None
        self.is_playing = False
        self._temp_wav_path = None
        self.thread = QThread()
        self.worker = _PlayerWorker()

        self._load_requested.connect(self.worker.load_data)
        self._play_requested.connect(self.worker.play)
        self._pause_requested.connect(self.worker.pause)
        self._stop_requested.connect(self.worker._stop)
        self._position_set_requested.connect(self.worker.set_position_in_seconds)
        self.worker.position_changed.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.error.connect(self._on_crashed)
        self.worker.moveToThread(self.thread)
        self.thread.start()
        
    @Slot(str)
    def _on_crashed(self, error_message):
        self.error.emit(error_message)
        self.crashed.emit()

    def load_file(self, file_path):
        self.is_ready.emit(False)
        path_to_load = file_path
        
        try:
            self._cleanup_temp_file()
            if _is_complex_format(file_path):
                logger.info(f"Converting '{file_path}' to temp WAV.")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f: self._temp_wav_path = f.name
                with AudioFileClip(file_path) as audio_clip: audio_clip.write_audiofile(self._temp_wav_path, codec='pcm_s16le', logger=None)
                path_to_load = self._temp_wav_path

            logger.info(f"Loading '{path_to_load}' with soundfile.")
            source_data_float, source_sr = sf.read(path_to_load, dtype='float32')
            
            mono_for_viz = source_data_float.mean(axis=1) if source_data_float.ndim > 1 else source_data_float
            
            pa = pyaudio.PyAudio()
            playback_sr = source_sr
            try:
                device_info = pa.get_default_output_device_info()
                self._prepared_for_device_name = device_info['name']
                target_sr = int(device_info['defaultSampleRate'])
                logger.info(f"Loader: Found device '{self._prepared_for_device_name}' with SR {target_sr}Hz.")
                if source_sr != target_sr:
                    logger.info(f"Loader: Resampling from {source_sr}Hz to {target_sr}Hz.")
                    playback_sr = target_sr
                    num_frames = int(len(mono_for_viz) * target_sr / source_sr)
                    mono_for_viz = signal.resample(mono_for_viz, num_frames)
            except Exception as e:
                logger.warning(f"Loader: Could not get device info, using source SR. Error: {e}")
                self._prepared_for_device_name = "Unknown"
            finally:
                pa.terminate()

            playback_data_stereo = np.stack([mono_for_viz, mono_for_viz], axis=-1)
            playback_data_int16 = (playback_data_stereo * 32767).astype(np.int16)

            max_val = np.max(np.abs(mono_for_viz))
            self._normalized_waveform = (mono_for_viz / max_val if max_val > 0 else mono_for_viz).tolist()
            self._duration = len(mono_for_viz) / float(playback_sr)
            
            self._load_requested.emit(playback_data_int16, playback_sr)
            self.is_ready.emit(True)
            logger.info(f"Successfully loaded. Duration: {self._duration:.2f}s, Final SR: {playback_sr}Hz")
            return True
            
        except Exception as e:
            logger.exception("Error loading audio/video file for playback.")
            self.error.emit(f"Failed to load media file for playback: {e}")
            self._cleanup_temp_file()
            return False

    def get_prepared_device_name(self) -> str | None:
        return self._prepared_for_device_name

    @staticmethod
    def get_current_device_name() -> str | None:
        """
        Get the current default audio output device name using OS-specific APIs.
        This bypasses PyAudio's caching issue by querying the OS directly.
        """
        system = platform.system()
        
        if system == "Darwin":  # macOS
            return AudioPlayer._get_current_device_name_macos()
        elif system == "Windows":
            return AudioPlayer._get_current_device_name_windows()
        else:
            logger.debug(f"Unsupported platform: {system}, falling back to PyAudio")
            return AudioPlayer._get_current_device_name_fallback()
    
    @staticmethod
    def _get_current_device_name_macos() -> str | None:
        """Get current device name on macOS using system APIs."""
        try:
            # Method 1: Direct approach using defaults and system_profiler
            result = subprocess.run([
                'defaults', 'read', 'com.apple.audio.DeviceSettings'
            ], capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0:
                import re
                match = re.search(r'DefaultOutputDevice.*?=.*?"(.*?)";', result.stdout, re.DOTALL)
                if match:
                    device_uid = match.group(1)
                    logger.debug(f"Found device UID: {device_uid}")
                    
                    prof_result = subprocess.run([
                        'system_profiler', 'SPAudioDataType'
                    ], capture_output=True, text=True, timeout=5)
                    
                    if prof_result.returncode == 0:
                        lines = prof_result.stdout.split('\n')
                        for i, line in enumerate(lines):
                            if device_uid in line:
                                for j in range(i-1, max(0, i-20), -1):
                                    stripped_line = lines[j].strip()
                                    if stripped_line.endswith(':') and lines[j].startswith('        ') and not lines[j].startswith('          '):
                                        device_name = ' '.join(stripped_line[:-1].split())
                                        logger.debug(f"Found device name: {device_name}")
                                        return device_name
                                break
                        
        except Exception as e:
            logger.debug(f"macOS defaults method failed: {e}")
        
        try:
            # Method 2: Try SwitchAudioSource if available
            result = subprocess.run([
                'SwitchAudioSource', '-c'
            ], capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0 and result.stdout.strip():
                device_name = result.stdout.strip()
                logger.debug(f"Found device via SwitchAudioSource: {device_name}")
                return device_name
                
        except FileNotFoundError:
            logger.debug("SwitchAudioSource not installed")
        except Exception as e:
            logger.debug(f"SwitchAudioSource failed: {e}")
        
        try:
            # Method 3: Parse system_profiler output directly
            result = subprocess.run([
                'system_profiler', 'SPAudioDataType'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                current_device = None
                
                for line in lines:
                    stripped_line = line.strip()
                    if stripped_line.endswith(':') and line.startswith('        ') and not line.startswith('          '):
                        current_device = ' '.join(stripped_line[:-1].split())
                    elif current_device and 'Default Output Device:' in stripped_line and 'Yes' in stripped_line:
                        logger.debug(f"Found default device via system_profiler: {current_device}")
                        return current_device
                        
        except Exception as e:
            logger.debug(f"system_profiler parsing failed: {e}")
        
        logger.debug("All macOS-specific methods failed")
        return None
    
    @staticmethod
    def _get_current_device_name_windows() -> str | None:
        """Get current device name on Windows using system APIs."""
        try:
            # Method 1: Use PowerShell to get the default audio device
            # This queries the Windows Audio Service directly
            powershell_script = '''
            Add-Type -AssemblyName System.Core
            Add-Type -TypeDefinition @"
                using System;
                using System.Runtime.InteropServices;
                
                public class AudioDeviceHelper {
                    [DllImport("ole32.dll")]
                    public static extern int CoInitialize(IntPtr pvReserved);
                    
                    [DllImport("ole32.dll")]
                    public static extern void CoUninitialize();
                }
            "@
            
            try {
                [AudioDeviceHelper]::CoInitialize([IntPtr]::Zero)
                
                # Get the default audio endpoint
                $deviceEnumerator = New-Object -ComObject MMDeviceEnumerator
                $defaultDevice = $deviceEnumerator.GetDefaultAudioEndpoint(0, 0)  # eRender, eConsole
                $deviceName = $defaultDevice.GetPropertyValue("{a45c254e-df1c-4efd-8020-67d146a850e0},14")  # PKEY_Device_FriendlyName
                
                Write-Output $deviceName
            } finally {
                [AudioDeviceHelper]::CoUninitialize()
            }
            '''
            
            result = subprocess.run([
                'powershell', '-Command', powershell_script
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                device_name = result.stdout.strip()
                logger.debug(f"Found device via PowerShell: {device_name}")
                return device_name
                
        except Exception as e:
            logger.debug(f"PowerShell method failed: {e}")
        
        try:
            # Method 2: Use wmic (Windows Management Instrumentation Command-line)
            result = subprocess.run([
                'wmic', 'sounddev', 'where', 'status="OK"', 'get', 'name', '/format:list'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if line.startswith('Name=') and line.strip() != 'Name=':
                        device_name = line.replace('Name=', '').strip()
                        if device_name:
                            logger.debug(f"Found device via wmic: {device_name}")
                            return device_name
                        
        except Exception as e:
            logger.debug(f"wmic method failed: {e}")
        
        try:
            # Method 3: Try using reg query to get default device from registry
            result = subprocess.run([
                'reg', 'query', 'HKEY_CURRENT_USER\\SOFTWARE\\Microsoft\\Multimedia\\Audio\\DefaultFormat',
                '/v', 'Device'
            ], capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Device' in line and 'REG_SZ' in line:
                        parts = line.split('REG_SZ')
                        if len(parts) > 1:
                            device_name = parts[1].strip()
                            if device_name:
                                logger.debug(f"Found device via registry: {device_name}")
                                return device_name
                        
        except Exception as e:
            logger.debug(f"Registry method failed: {e}")
        
        logger.debug("All Windows-specific methods failed")
        return None
    
    @staticmethod
    def _get_current_device_name_fallback() -> str | None:
        """Fallback method using PyAudio (may have caching issues)."""
        pa = None
        try:
            pa = pyaudio.PyAudio()
            device_info = pa.get_default_output_device_info()
            logger.debug(f"PyAudio fallback returned: {device_info['name']}")
            return device_info['name']
        except Exception as e:
            logger.warning(f"PyAudio fallback failed: {e}")
            return None
        finally:
            if pa:
                pa.terminate()
    
    @staticmethod
    def get_current_device_name() -> str | None:
        """
        Get the current default audio output device name using OS-specific APIs.
        Falls back to PyAudio if OS-specific methods fail.
        """
        system = platform.system()
        
        # Try OS-specific methods first
        if system == "Darwin":  # macOS
            device_name = AudioPlayer._get_current_device_name_macos()
        elif system == "Windows":
            device_name = AudioPlayer._get_current_device_name_windows()
        else:
            logger.debug(f"Unsupported platform: {system}")
            device_name = None
        
        # If OS-specific methods failed, fall back to PyAudio
        if device_name is None:
            logger.warning("OS-specific methods failed, falling back to PyAudio (may have caching issues)")
            device_name = AudioPlayer._get_current_device_name_fallback()
        
        return device_name

    def _cleanup_temp_file(self):
        if self._temp_wav_path and os.path.exists(self._temp_wav_path):
            try:
                os.remove(self._temp_wav_path)
                logger.info(f"Cleaned up temp audio file: {self._temp_wav_path}")
                self._temp_wav_path = None
            except OSError as e:
                logger.warning(f"Could not remove temp file {self._temp_wav_path}: {e}")

    def play(self): self._play_requested.emit()
    def pause(self): self._pause_requested.emit()
    def set_position(self, seconds): self._position_set_requested.emit(seconds)
    def seek(self, offset_seconds): self.set_position(self._current_time + offset_seconds)
    
    @Slot(float)
    def _on_progress(self, current_time): self._current_time = current_time; self.progress.emit(current_time)
    @Slot()
    def _on_finished(self): self.is_playing = False; self.state_changed.emit(False); self.finished.emit()
    @Slot(bool)
    def _on_state_changed(self, is_now_playing): self.is_playing = is_now_playing; self.state_changed.emit(is_now_playing)
    
    def get_duration(self): return self._duration
    def get_normalized_waveform(self): return self._normalized_waveform
    
    def destroy(self):
        logger.info("Destroying AudioPlayer resources.")
        self._cleanup_temp_file()
        if self.thread.isRunning():
            self._stop_requested.emit()
            self.worker.cleanup()
            self.thread.quit()
            if not self.thread.wait(3000):
                logger.warning("Audio player thread did not quit gracefully. Terminating.")
                self.thread.terminate()
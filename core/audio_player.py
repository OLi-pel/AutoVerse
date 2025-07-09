# core/audio_player.py
import logging
import time
import os
import tempfile
import numpy as np
import pyaudio
import soundfile as sf
from moviepy.editor import AudioFileClip
from scipy import signal
from PySide6.QtCore import QObject, Signal, Slot, QThread, QCoreApplication, QEventLoop

logger = logging.getLogger(__name__)
TARGET_PLAYBACK_SR = 44100

SIMPLE_AUDIO_EXTENSIONS = ('.wav', '.flac', '.ogg')

def _is_complex_format(file_path):
    return not file_path.lower().endswith(SIMPLE_AUDIO_EXTENSIONS)

class _PlayerWorker(QObject):
    # This class is unchanged...
    # ...
    position_changed = Signal(float)
    finished = Signal()
    state_changed = Signal(bool)
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.pyaudio_instance = None
        self.stream = None
        self._audio_data = None
        self._sample_rate = 0
        self._num_channels = 0
        self._sample_width_bytes = 0
        self._current_frame = 0
        self._total_frames = 0
        self._chunk_size_frames = 1024
        self._is_paused = False
        self._stop_requested = False

    @Slot()
    def initialize_pyaudio(self):
        if self.pyaudio_instance is None:
            self.pyaudio_instance = pyaudio.PyAudio()

    @Slot(np.ndarray, int)
    def load_data(self, audio_data, sample_rate):
        self._stop()
        self._audio_data = audio_data
        self._sample_rate = sample_rate
        self._num_channels = self._audio_data.shape[1] if self._audio_data.ndim > 1 else 1
        self._sample_width_bytes = self._audio_data.dtype.itemsize
        self._total_frames = len(self._audio_data)
        self.set_position(0.0)

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

    @Slot()  # <-- Make _stop a slot
    def _stop(self):
        self._stop_requested = True
        self._is_paused = False

    @Slot(float)
    def set_position(self, seconds):
        if self._sample_rate > 0:
            self._current_frame = int(np.clip(seconds * self._sample_rate, 0, self._total_frames))
            self.position_changed.emit(self._current_frame / self._sample_rate)
        else:
            self.position_changed.emit(0.0)

    def _playback_loop(self):
        if not self.pyaudio_instance: self.initialize_pyaudio()
            
        try:
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=self._num_channels,
                rate=self._sample_rate,
                output=True,
                frames_per_buffer=self._chunk_size_frames
            )
        except Exception as e:
            logger.error(f"Failed to open PyAudio stream: {e}")
            self.error.emit(str(e))
            self.state_changed.emit(False)
            return

        loop = QEventLoop()
        while self._current_frame < self._total_frames and not self._stop_requested:
            if self._is_paused:
                time.sleep(0.01)
                loop.processEvents()
                continue

            remaining_frames = self._total_frames - self._current_frame
            frames_to_write = min(self._chunk_size_frames, remaining_frames)
            
            try:
                self.stream.write(self._audio_data[self._current_frame:self._current_frame + frames_to_write].tobytes())
            except OSError as e: # Handle cases where stream is closed mid-write
                logger.warning(f"OSError during stream write (stream likely closed): {e}")
                break

            self._current_frame += frames_to_write
            self.position_changed.emit(self._current_frame / self._sample_rate)
            loop.processEvents()

        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except OSError as e:
                logger.warning(f"OSError closing stream (already closed is okay): {e}")
        
        self.stream = None
        self._stop_requested = False
        if self._current_frame >= self._total_frames:
            self.finished.emit()
        self.state_changed.emit(False)

    def cleanup(self):
        self._stop()
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()

class AudioPlayer(QObject):
    # ... Signals are unchanged ...
    _load_requested = Signal(np.ndarray, int)
    _play_requested = Signal()
    _pause_requested = Signal()
    _stop_requested = Signal() # <--- NEW Signal
    _position_set_requested = Signal(float)
    progress = Signal(float)
    finished = Signal()
    is_ready = Signal(bool)
    error = Signal(str)
    state_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        # ... properties are unchanged ...
        self._duration = 0.0
        self._current_time = 0.0
        self._normalized_waveform = []
        self.is_playing = False
        self._temp_wav_path = None
        self.thread = QThread()
        self.worker = _PlayerWorker()

        self.thread.started.connect(self.worker.initialize_pyaudio)
        self._load_requested.connect(self.worker.load_data)
        self._play_requested.connect(self.worker.play)
        self._pause_requested.connect(self.worker.pause)
        self._stop_requested.connect(self.worker._stop) # <-- Connect new signal
        self._position_set_requested.connect(self.worker.set_position)
        self.worker.position_changed.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.error.connect(self.error)

        self.worker.moveToThread(self.thread)
        self.thread.start()

    def load_file(self, file_path):
        # This function is now correct and doesn't need to be changed again.
        # ... (paste the robust load_file from the previous step)
        self.is_ready.emit(False)
        path_to_load = file_path
        
        try:
            self._cleanup_temp_file()
            
            if _is_complex_format(file_path):
                logger.info(f"AudioPlayer: Complex format detected. Converting '{file_path}' to temporary WAV.")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    self._temp_wav_path = f.name
                
                with AudioFileClip(file_path) as audio_clip:
                    audio_clip.write_audiofile(self._temp_wav_path, codec='pcm_s16le')
                
                path_to_load = self._temp_wav_path
                logger.info(f"AudioPlayer: Converted to '{path_to_load}'.")

            logger.info(f"AudioPlayer: Loading '{path_to_load}' with soundfile.")
            audio_data_float, source_sr = sf.read(path_to_load, dtype='float32')

            if audio_data_float.ndim > 1:
                mono_for_viz = audio_data_float.mean(axis=1)
            else:
                mono_for_viz = audio_data_float

            playback_sr = source_sr
            if source_sr != TARGET_PLAYBACK_SR:
                num_frames = int(len(mono_for_viz) * TARGET_PLAYBACK_SR / source_sr)
                mono_for_playback = signal.resample(mono_for_viz, num_frames)
                playback_sr = TARGET_PLAYBACK_SR
            else:
                mono_for_playback = mono_for_viz
            
            if mono_for_playback.ndim == 1:
                mono_for_playback_stereo = np.stack([mono_for_playback, mono_for_playback], axis=-1)
            else: 
                mono_for_playback_stereo = mono_for_playback

            audio_data_int16 = (mono_for_playback_stereo * 32767).astype(np.int16)
            
            max_val = np.max(np.abs(mono_for_viz))
            self._normalized_waveform = (mono_for_viz / max_val if max_val > 0 else mono_for_viz).tolist()
            
            self._duration = len(mono_for_playback) / float(playback_sr)
            
            self._load_requested.emit(audio_data_int16, playback_sr)
            self.is_ready.emit(True)
            logger.info(f"Successfully loaded for playback. Duration: {self._duration:.2f}s")
            return True
            
        except Exception as e:
            logger.exception("Error loading audio/video file for playback.")
            self.error.emit(f"Failed to load media file for playback: {e}")
            self._cleanup_temp_file() # Clean up even on error
            return False


    def _cleanup_temp_file(self):
        if self._temp_wav_path and os.path.exists(self._temp_wav_path):
            try:
                os.remove(self._temp_wav_path)
                logger.info(f"Cleaned up temporary audio file: {self._temp_wav_path}")
                self._temp_wav_path = None
            except OSError as e:
                logger.warning(f"Could not remove temporary audio file {self._temp_wav_path}: {e}")
    
    # ...
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
    
    # --- The definitive destroy() method ---
    def destroy(self):
        """Gracefully shuts down the worker thread and cleans up resources."""
        logger.info("Destroying AudioPlayer resources.")
        self._cleanup_temp_file()
        
        if self.thread.isRunning():
            # Signal the worker to stop any playback loop and clean up its pyaudio instance
            self._stop_requested.emit()
            self.worker.cleanup()

            # Tell the thread to quit its event loop
            self.thread.quit()
            
            # Wait for the thread to finish gracefully
            if not self.thread.wait(3000): # Wait up to 3 seconds
                logger.warning("Audio player thread did not quit gracefully. Terminating.")
                self.thread.terminate()
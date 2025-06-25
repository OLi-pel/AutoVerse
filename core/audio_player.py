# core/audio_player.py
import logging
import numpy as np
import pyaudio
import soundfile as sf
from PySide6.QtCore import QObject, Signal, QThread, Slot

logger = logging.getLogger(__name__)

class _Worker(QObject):
    position_changed = Signal(float)
    finished = Signal()

    def __init__(self, stream, data_bytes, sample_rate, start_byte, sample_width_bytes, num_channels):
        super().__init__()
        self.stream = stream
        self._data_bytes = data_bytes
        self._sample_rate = sample_rate
        self._position_bytes = start_byte
        self._sample_width_bytes = sample_width_bytes
        self._num_channels = num_channels
        self._chunk_size_bytes = 1024 * self._sample_width_bytes * self._num_channels
        self.is_running = True

    def run(self):
        bytes_per_frame = self._sample_width_bytes * self._num_channels
        if bytes_per_frame == 0:
            self.finished.emit()
            return
        data_len_bytes = len(self._data_bytes)
        while self.is_running and self._position_bytes < data_len_bytes:
            try:
                chunk_end = self._position_bytes + self._chunk_size_bytes
                data_chunk = self._data_bytes[self._position_bytes:chunk_end]
                if not data_chunk or not self.stream.is_active(): break
                self.stream.write(data_chunk)
                self._position_bytes += len(data_chunk)
                current_frame = self._position_bytes / bytes_per_frame
                current_time = current_frame / self._sample_rate
                self.position_changed.emit(current_time)
            except (IOError, AttributeError) as e:
                logger.error(f"PyAudio stream write error in worker: {e}")
                break
        self.finished.emit()

    def stop(self):
        self.is_running = False

class AudioPlayer(QObject):
    progress = Signal(float)
    finished = Signal()
    is_ready = Signal(bool)
    error = Signal(str)
    state_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.pyaudio_instance = pyaudio.PyAudio()
        self.stream = None
        self.thread = None
        self.worker = None
        self._audio_data_numpy = None
        self._normalized_waveform = None
        self._sample_rate = 0
        self._duration = 0.0
        self._current_time = 0.0
        self.num_channels = 0
        self.sample_width_bytes = 0
        self.is_playing = False

    def load_file(self, file_path):
        try:
            self.stop_and_reset()
            self._audio_data_numpy, self._sample_rate = sf.read(file_path, dtype='int16')
            self.num_channels = self._audio_data_numpy.shape[1] if self._audio_data_numpy.ndim > 1 else 1
            audio_data_mono = self._audio_data_numpy.mean(axis=1).astype(np.int16) if self.num_channels > 1 else self._audio_data_numpy
            self._duration = len(self._audio_data_numpy) / float(self._sample_rate)
            self._normalized_waveform = audio_data_mono / 32768.0
            self.sample_width_bytes = self._audio_data_numpy.dtype.itemsize
            self.stream = self.pyaudio_instance.open(format=self.pyaudio_instance.get_format_from_width(self.sample_width_bytes), channels=self.num_channels, rate=self._sample_rate, output=True)
            self.is_ready.emit(True)
            logger.info(f"Successfully loaded audio file: {file_path}, Duration: {self._duration:.2f}s")
            return True
        except Exception as e:
            logger.exception("Error loading audio file."); self.is_ready.emit(False)
            self.error.emit(str(e))
            return False

    def play(self):
        if self.is_playing or not self.stream: return
        self._set_is_playing(True)
        if self._current_time >= self._duration: self._current_time = 0.0
        self.thread = QThread()
        start_byte = int(self._current_time * self._sample_rate) * self.sample_width_bytes * self.num_channels
        self.worker = _Worker(self.stream, self._audio_data_numpy.tobytes(), self._sample_rate, start_byte, self.sample_width_bytes, self.num_channels)
        self.worker.moveToThread(self.thread)
        self.worker.position_changed.connect(self._on_progress)
        self.worker.finished.connect(self._on_playback_finished)
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def pause(self):
        if not self.is_playing: return
        self._stop_playback_thread()
        self._set_is_playing(False)

    def stop_and_reset(self):
        self._stop_playback_thread()
        self._current_time = 0.0
        self.progress.emit(0.0)
        self._set_is_playing(False)

    def set_position(self, seconds):
        # --- THE DEFINITIVE SEEK/DRAG FIX ---
        was_playing = self.is_playing
        self._stop_playback_thread()
        
        self._current_time = max(0, min(seconds, self._duration))
        self.progress.emit(self._current_time)
        
        # If the player was playing before, automatically resume playback
        if was_playing:
            self.play()

    def seek(self, offset_seconds):
        self.set_position(self._current_time + offset_seconds)

    def _set_is_playing(self, playing):
        if self.is_playing != playing:
            self.is_playing = playing
            self.state_changed.emit(playing)

    def _stop_playback_thread(self):
        if self.worker: self.worker.stop()
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.thread = None
        self.worker = None

    @Slot(float)
    def _on_progress(self, current_time):
        self._current_time = current_time
        self.progress.emit(current_time)

    @Slot()
    def _on_playback_finished(self):
        is_at_end = self._duration - self._current_time < 0.1
        self._stop_playback_thread()
        if is_at_end: self.progress.emit(self._duration)
        self.finished.emit()
        self._set_is_playing(False)

    def get_duration(self): return self._duration
    def get_normalized_waveform(self): return self._normalized_waveform.tolist() if self._normalized_waveform is not None else []
    def destroy(self):
        self._stop_playback_thread()
        if self.stream: self.stream.close()
        if self.pyaudio_instance: self.pyaudio_instance.terminate()
        logger.info("AudioPlayer resources completely destroyed.")
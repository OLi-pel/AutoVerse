# core/audio_player.py
import logging
import time
import os
import numpy as np
import pyaudio
import soundfile as sf
from moviepy.editor import VideoFileClip
from scipy import signal
from PySide6.QtCore import QObject, Signal, Slot, QThread, QCoreApplication

logger = logging.getLogger(__name__)
TARGET_PLAYBACK_SR = 44100

VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv')

def _is_video_file(file_path):
    if not isinstance(file_path, str):
        return False
    return file_path.lower().endswith(VIDEO_EXTENSIONS)

class _PlayerWorker(QObject):
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

        while self._current_frame < self._total_frames and not self._stop_requested:
            if self._is_paused:
                time.sleep(0.01)
                QCoreApplication.processEvents()
                continue

            remaining_frames = self._total_frames - self._current_frame
            frames_to_write = min(self._chunk_size_frames, remaining_frames)
            chunk_data = self._audio_data[self._current_frame:self._current_frame + frames_to_write].tobytes()
            self.stream.write(chunk_data)
            self._current_frame += frames_to_write
            self.position_changed.emit(self._current_frame / self._sample_rate)
            QCoreApplication.processEvents()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
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
    progress = Signal(float)
    finished = Signal()
    is_ready = Signal(bool)
    error = Signal(str)
    state_changed = Signal(bool)

    _load_requested = Signal(np.ndarray, int)
    _play_requested = Signal()
    _pause_requested = Signal()
    _position_set_requested = Signal(float)

    def __init__(self):
        super().__init__()
        self._duration = 0.0
        self._current_time = 0.0
        self._normalized_waveform = []
        self.is_playing = False
        self.thread = QThread()
        self.worker = _PlayerWorker()

        self.thread.started.connect(self.worker.initialize_pyaudio)
        self._load_requested.connect(self.worker.load_data)
        self._play_requested.connect(self.worker.play)
        self._pause_requested.connect(self.worker.pause)
        self._position_set_requested.connect(self.worker.set_position)
        self.worker.position_changed.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.state_changed.connect(self._on_state_changed)
        self.worker.error.connect(self.error)

        self.worker.moveToThread(self.thread)
        self.thread.start()

    def load_file(self, file_path):
        try:
            self.is_ready.emit(False)
            audio_data_float = None
            source_sr = TARGET_PLAYBACK_SR

            if _is_video_file(file_path):
                logger.info(f"Detected video file, extracting audio in memory: {file_path}")
                with VideoFileClip(file_path) as video:
                    source_sr = video.audio.fps
                    # --- THIS IS THE FINAL, CORRECTED LOGIC ---
                    # 1. Provide the required `chunksize` to `iter_chunks`.
                    # 2. Use `np.concatenate` to join the chunks into a single stream.
                    audio_chunks = [chunk for chunk in video.audio.iter_chunks(chunksize=source_sr)]
                    audio_data_float = np.concatenate(audio_chunks)

            else:
                logger.info(f"Detected audio file, loading directly: {file_path}")
                audio_data_float, source_sr = sf.read(file_path, dtype='float32')

            # Ensure data is 1D (mono) for initial processing.
            if audio_data_float.ndim > 1:
                mono_for_viz = audio_data_float.mean(axis=1)
            else:
                mono_for_viz = audio_data_float

            playback_sr = source_sr
            if source_sr != TARGET_PLAYBACK_SR:
                logger.info(f"Resampling audio from {source_sr}Hz to {TARGET_PLAYBACK_SR}Hz")
                num_frames = int(len(mono_for_viz) * TARGET_PLAYBACK_SR / source_sr)
                mono_for_playback = signal.resample(mono_for_viz, num_frames)
                playback_sr = TARGET_PLAYBACK_SR
            else:
                mono_for_playback = mono_for_viz
            
            # Prepare data for PyAudio worker: stereo, 16-bit integer
            if mono_for_playback.ndim == 1:
                mono_for_playback_stereo = np.stack([mono_for_playback, mono_for_playback], axis=-1)
            else: # Already stereo, no need to stack
                mono_for_playback_stereo = mono_for_playback

            audio_data_int16 = (mono_for_playback_stereo * 32767).astype(np.int16)
            
            # Prepare data for waveform visualization
            max_val = np.max(np.abs(mono_for_viz))
            self._normalized_waveform = (mono_for_viz / max_val if max_val > 0 else mono_for_viz).tolist()
            
            self._duration = len(mono_for_playback) / float(playback_sr)
            
            self._load_requested.emit(audio_data_int16, playback_sr)
            self.is_ready.emit(True)
            logger.info(f"Successfully loaded. Duration: {self._duration:.2f}s, Playback SR: {playback_sr}Hz")
            return True
            
        except Exception as e:
            logger.exception("Error loading audio/video file.")
            self.error.emit(f"Failed to load media file: {e}")
            return False

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
        if self.thread.isRunning():
            self.thread.quit()
            if not self.thread.wait(1000):
                self.thread.terminate()
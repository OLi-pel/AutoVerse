# core/transcription_handler.py (With Stream Capture)

import logging
import whisper
import os
import contextlib
import sys

# Import our new stream class
from utils.streams import TqdmSignalStream

logger = logging.getLogger(__name__)

class TranscriptionHandler:
    def __init__(self, model_name: str, device: str, cache_dir: str = None):
        self.model_name = model_name
        self.device = device
        self.cache_dir = cache_dir
        self.model = self._load_model()

    def is_model_loaded(self) -> bool:
        return self.model is not None

    def _load_model(self):
        logger.info(f"TranscriptionHandler: Loading Whisper model ('{self.model_name}') on device '{self.device}'...")
        model = None
        try:
            whisper_cache_dir = os.path.join(self.cache_dir, "whisper") if self.cache_dir else None
            if whisper_cache_dir:
                os.makedirs(whisper_cache_dir, exist_ok=True)
                logger.info(f"Ensured Whisper model cache directory exists: {whisper_cache_dir}")
            
            model = whisper.load_model(self.model_name, device=self.device, download_root=whisper_cache_dir)
            logger.info(f"TranscriptionHandler: Whisper model '{self.model_name}' loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Whisper model '{self.model_name}': {e}", exc_info=True)
        return model

    def transcribe(self, audio_path: str, tqdm_stream: TqdmSignalStream = None) -> list | None:
        """
        Transcribes the audio. If a tqdm_stream is provided, it redirects stderr
        to capture the progress bar output.
        """
        if not self.model:
            logger.error("Transcription model is not loaded. Cannot transcribe.")
            return None

        logger.info(f"TranscriptionHandler: Starting transcription for {audio_path}")
        try:
            # Use a context manager to temporarily redirect stderr to our custom stream
            # The 'sys.stderr' is a fallback in case no stream is provided.
            stream_target = tqdm_stream if tqdm_stream else sys.stderr
            with contextlib.redirect_stderr(stream_target):
                result = whisper.transcribe(
                    self.model,
                    audio_path,
                    word_timestamps=True,
                )
            
            logger.info("TranscriptionHandler: Transcription completed successfully.")
            
            if result and 'segments' in result:
                return result['segments']
            else:
                logger.error("Transcription result is missing 'segments' key.")
                return None

        except Exception as e:
            logger.error(f"An error occurred during transcription: {e}", exc_info=True)
            return None
        
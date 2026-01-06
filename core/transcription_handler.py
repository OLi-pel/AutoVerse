# core/transcription_handler.py
import logging
import os
import whisper
from utils import constants

logger = logging.getLogger(__name__)

class TranscriptionHandler:
    def __init__(self, model_name, device, progress_callback=None, cache_dir=None):
        self.model_name = model_name
        self.device = device
        self.progress_callback = progress_callback
        self.cache_dir = cache_dir
        self.model = self._load_model()

    def _report_progress(self, message: str, percentage: int = None):
        if self.progress_callback:
            try:
                self.progress_callback(message, percentage)
            except Exception as e:
                logger.error(f"Error in TranscriptionHandler progress_callback: {e}", exc_info=True)

    def is_model_loaded(self) -> bool:
        return self.model is not None

    def _load_model(self):
        logger.info(f"TranscriptionHandler: Loading Whisper model ('{self.model_name}') on device '{self.device}'...")
        
        whisper_cache_path = None
        if self.cache_dir:
            try:
                whisper_cache_path = self.cache_dir 
                os.makedirs(whisper_cache_path, exist_ok=True)
                logger.info(f"Using application-specific cache directory for Whisper: {whisper_cache_path}")
            except OSError as e:
                logger.error(f"Could not create cache directory. Using default. Error: {e}")
                whisper_cache_path = None

        try:
            model = whisper.load_model(
                self.model_name,
                device=self.device,
                download_root=whisper_cache_path
            )
            logger.info(f"TranscriptionHandler: Whisper model '{self.model_name}' loaded successfully.")
            return model
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}", exc_info=True)
            self._report_progress(f"Error loading model: {e}", 0)
            raise
        
    def transcribe(self, audio_path: str):
        """
        Transcribes the audio file. 
        CRITICAL: verbose=False forces the progress bar to show (which we capture).
        verbose=None or True might disable it or print text instead.
        """
        logger.info(f"TranscriptionHandler: Starting transcription for {audio_path}")
        try:
            # FIX: verbose=False enables the tqdm progress bar
            result = self.model.transcribe(audio_path, verbose=False)
            logger.info("TranscriptionHandler: Transcription completed successfully.")
            return result
        except Exception as e:
            logger.error(f"Error during transcription: {e}", exc_info=True)
            raise
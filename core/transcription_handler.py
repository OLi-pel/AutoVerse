# core/transcription_handler.py
import logging
import os
import whisper

logger = logging.getLogger(__name__)

class TranscriptionHandler:
    def __init__(self, model_name, device, progress_callback=None, cache_dir=None):
        """
        Initializes the TranscriptionHandler.

        Args:
            model_name (str): The name of the Whisper model to load.
            device (str): The device to run the model on ('cpu' or 'cuda').
            progress_callback (function, optional): A callback for reporting progress.
            cache_dir (str, optional): The root directory for caching models.
        """
        self.model_name = model_name
        self.device = device
        self.progress_callback = progress_callback
        self.cache_dir = cache_dir  # Store the cache directory
        self.model = self._load_model()

    def _report_progress(self, message: str, percentage: int = None):
        """Safely calls the progress callback if it exists."""
        if self.progress_callback:
            try:
                self.progress_callback(message, percentage)
            except Exception as e:
                logger.error(f"Error in TranscriptionHandler progress_callback: {e}", exc_info=True)

    def is_model_loaded(self) -> bool:
        """Checks if the model has been loaded successfully."""
        return self.model is not None

    def _load_model(self):
        """
        Loads the Whisper model, using a specified cache directory if provided.
        """
        logger.info(f"TranscriptionHandler: Loading Whisper model ('{self.model_name}') on device '{self.device}'...")
        self._report_progress(f"Loading transcription model '{self.model_name}'...")
        
        # --- MODIFIED CACHE LOGIC ---
        # Determine the specific path for whisper models and ensure it exists.
        whisper_cache_path = None
        if self.cache_dir:
            try:
                # Models will be stored in a 'whisper' subdirectory of the main cache folder.
                whisper_cache_path = os.path.join(self.cache_dir, "whisper")
                os.makedirs(whisper_cache_path, exist_ok=True)
                logger.info(f"Ensured Whisper model cache directory exists: {whisper_cache_path}")
            except OSError as e:
                logger.error(f"Could not create cache directory {whisper_cache_path}. Models will use default cache. Error: {e}")
                whisper_cache_path = None # Fallback to default if creation fails

        try:
            # Pass the explicit download_root to the load_model function.
            # If whisper_cache_path is None, whisper uses its default location.
            model = whisper.load_model(self.model_name, device=self.device, download_root=whisper_cache_path)
            
            logger.info(f"TranscriptionHandler: Whisper model '{self.model_name}' loaded successfully.")
            self._report_progress(f"Transcription model '{self.model_name}' loaded.", 100)
            return model
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}", exc_info=True)
            self._report_progress(f"Error loading model: {e}", 0)
            raise

    def transcribe(self, audio_path: str):
        """Transcribes the audio file."""
        logger.info(f"TranscriptionHandler: Starting transcription for {audio_path}")
        try:
            # The verbose parameter prints detailed progress to the console, which can be useful for debugging.
            result = self.model.transcribe(audio_path, verbose=False)
            logger.info("TranscriptionHandler: Transcription completed successfully.")
            return result
        except Exception as e:
            logger.error(f"Error during transcription: {e}", exc_info=True)
            raise

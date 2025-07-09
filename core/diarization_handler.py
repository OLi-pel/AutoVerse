#core/diarization_handler.py

import logging
import os
from pyannote.audio import Pipeline
import torch
import torch.nn.functional as F
# --- [NEW/REQUIRED IMPORTS] ---
import numpy as np
from moviepy.editor import AudioFileClip
# --- [END IMPORTS] ---

logger = logging.getLogger(__name__)

class DiarizationHandler:
    def __init__(self, hf_token: str, use_auth_token_flag: bool, device, progress_callback=None, cache_dir=None):
        """
        Initializes the DiarizationHandler.
        #... (rest of the __init__ method is unchanged) ...
        """
        self.hf_token = hf_token
        self.use_auth_token = use_auth_token_flag
        self.device = device
        self.progress_callback = progress_callback
        self.cache_dir = cache_dir
        self.pipeline = self._load_pipeline()

    #... (the _report_progress, is_model_loaded, and _load_pipeline methods are unchanged) ...

    def _report_progress(self, message: str, percentage: int = None):
        """Safely calls the progress callback if it exists."""
        if self.progress_callback:
            try:
                self.progress_callback(message, percentage)
            except Exception as e:
                logger.error(f"Error in DiarizationHandler progress_callback: {e}", exc_info=True)

    def is_model_loaded(self) -> bool:
        """Checks if the diarization pipeline has been loaded successfully."""
        return self.pipeline is not None

    def _load_pipeline(self):
        """
        Loads the pyannote.audio diarization pipeline, using a specified
        cache directory and authentication token if provided.
        """
        if not self.use_auth_token or not self.hf_token:
            logger.warning("Diarization disabled: Hugging Face token is required but not provided or not enabled.")
            self._report_progress("Diarization disabled (no token).", 0)
            return None

        logger.info("DiarizationHandler: Loading pyannote.audio pipeline...")
        self._report_progress("Loading diarization model (may download)...", 0)
        
        original_cache = os.environ.get('HF_HUB_CACHE')
        if self.cache_dir:
            try:
                pyannote_cache_path = os.path.join(self.cache_dir, "pyannote")
                os.makedirs(pyannote_cache_path, exist_ok=True)
                os.environ['HF_HUB_CACHE'] = pyannote_cache_path
                logger.info(f"Set HF_HUB_CACHE for pyannote to: {pyannote_cache_path}")
            except OSError as e:
                logger.error(f"Could not create pyannote cache directory. It will use the default. Error: {e}")

        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )
            pipeline.to(self.device)
            logger.info("DiarizationHandler: pyannote.audio pipeline loaded successfully.")
            self._report_progress("Diarization model loaded.", 100)
            return pipeline
        except Exception as e:
            logger.error(f"Failed to load pyannote pipeline: {e}", exc_info=True)
            self._report_progress(f"Diarization Error: {e}", 0)
            if "401" in str(e):
                 logger.error("Got a 401 Client Error. This strongly indicates the Hugging Face token is invalid or expired.")
                 self._report_progress("Diarization Error: Invalid Hugging Face token.", 0)
            return None
        finally:
            if original_cache:
                os.environ['HF_HUB_CACHE'] = original_cache
            elif 'HF_HUB_CACHE' in os.environ:
                del os.environ['HF_HUB_CACHE']
            logger.info("Restored original HF_HUB_CACHE environment.")

    def diarize(self, audio_path: str):
        """
        Performs speaker diarization on a given audio file path.
        Assumes the file is a simple, readable format like WAV.
        """
        if not self.is_model_loaded():
            logger.error("Cannot diarize: pipeline not loaded.")
            return None
        
        logger.info(f"DiarizationHandler: Starting diarization for {audio_path}")
        try:
            # We are back to the simplest call, as we now only pass clean WAV files.
            diarization_result = self.pipeline(audio_path)
            logger.info("DiarizationHandler: Diarization completed successfully.")
            return diarization_result
        except Exception as e:
            logger.error(f"Error during diarization: {e}", exc_info=True)
            raise
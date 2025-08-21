#core/diarization_handler.py
import logging
import os
from pyannote.audio import Pipeline
import torch
import torch.nn.functional as F
import numpy as np
from moviepy.editor import AudioFileClip

logger = logging.getLogger(__name__)

class DiarizationHandler:
    def __init__(self, hf_token: str, use_auth_token_flag: bool, device, progress_callback=None, cache_dir=None):
        self.hf_token = hf_token
        self.use_auth_token = use_auth_token_flag
        self.device = device
        self.cache_dir = cache_dir
        # progress_callback is no longer used here but kept for signature consistency
        self.pipeline = self._load_pipeline()

    def is_model_loaded(self) -> bool:
        return self.pipeline is not None

    def _load_pipeline(self):
        if not self.use_auth_token or not self.hf_token:
            return None

        logger.info("DiarizationHandler: Loading/Downloading pyannote.audio pipeline...")
        
        pyannote_cache_path = None
        if self.cache_dir:
            try:
                pyannote_cache_path = os.path.join(self.cache_dir, "pyannote")
                os.makedirs(pyannote_cache_path, exist_ok=True)
            except OSError as e:
                logger.error(f"Could not create pyannote cache directory. Error: {e}")
                pyannote_cache_path = None

        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token,
                cache_dir=pyannote_cache_path
            )
            pipeline.to(self.device)
            logger.info("DiarizationHandler: pyannote.audio pipeline loaded successfully.")
            return pipeline
        except Exception as e:
            logger.error(f"Failed to load pyannote pipeline: {e}", exc_info=True)
            if "401" in str(e):
                 logger.error("Got a 401 Client Error. Invalid Hugging Face token.")
            # Let AudioProcessor handle error reporting to the user
            raise

    def diarize(self, audio_path: str):
        if not self.is_model_loaded():
            return None
        
        logger.info(f"DiarizationHandler: Starting diarization for {audio_path}")
        try:
            diarization_result = self.pipeline(audio_path)
            logger.info("DiarizationHandler: Diarization completed successfully.")
            return diarization_result
        except RuntimeError as e:
            if "Sizes of tensors must match except in dimension 0" in str(e):
                logger.warning(f"Tensor size mismatch in diarization for {audio_path}. Attempting to preprocess audio...")
                try:
                    # Try preprocessing the audio to fix tensor size issues
                    preprocessed_result = self._preprocess_and_diarize(audio_path)
                    if preprocessed_result is not None:
                        logger.info("DiarizationHandler: Diarization completed successfully after preprocessing.")
                        return preprocessed_result
                    else:
                        logger.warning(f"Preprocessing failed for {audio_path}. Skipping diarization.")
                        return None
                except Exception as preprocess_error:
                    logger.warning(f"Preprocessing failed for {audio_path}: {preprocess_error}. Skipping diarization.")
                    return None
            else:
                logger.error(f"Error during diarization: {e}", exc_info=True)
                raise
        except Exception as e:
            logger.error(f"Error during diarization: {e}", exc_info=True)
            raise

    def _preprocess_and_diarize(self, audio_path: str):
        """
        Preprocess audio to handle tensor size mismatches by ensuring consistent chunk sizes.
        """
        from utils.audio_utils import preprocess_audio_for_diarization, cleanup_temp_file
        
        temp_path = None
        try:
            # Preprocess the audio to fix tensor size issues
            temp_path = preprocess_audio_for_diarization(audio_path)
            
            if temp_path is None:
                logger.error("Audio preprocessing failed")
                return None
            
            # Try diarization with the preprocessed audio
            diarization_result = self.pipeline(temp_path)
            return diarization_result
            
        except Exception as e:
            logger.error(f"Error in preprocessed diarization: {e}", exc_info=True)
            return None
        finally:
            # Clean up temporary file
            if temp_path:
                cleanup_temp_file(temp_path)
# core/diarization_handler.py
import logging
import os
import soundfile as sf
from pyannote.audio import Pipeline

logger = logging.getLogger(__name__)

class DiarizationHandler:
    def __init__(self, hf_token: str, use_auth_token_flag: bool, device, cache_dir=None):
        self.hf_token = hf_token
        self.use_auth_token = use_auth_token_flag
        self.device = device
        self.cache_dir = cache_dir
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
            raise

    def diarize(self, audio_path: str):
        if not self.is_model_loaded():
            return None
        
        logger.info(f"DiarizationHandler: Starting diarization for {audio_path}")
        
        # --- DIAGNOSTIC: Check Audio Readability using SoundFile ---
        try:
            # We use soundfile directly to check if the file is readable
            # This avoids the torchaudio version conflict
            info = sf.info(audio_path)
            logger.info(f"DiarizationHandler: Audio Check - Duration: {info.duration:.2f}s, SR: {info.samplerate}, Channels: {info.channels}")
            
            if info.duration < 0.5:
                logger.warning("DiarizationHandler: Audio is too short (<0.5s), Pyannote might ignore it.")
                
        except Exception as e:
            logger.error(f"DiarizationHandler: CRITICAL - SoundFile cannot load file: {e}")
            raise
        # ----------------------------------------

        try:
            # Run pipeline
            diarization_result = self.pipeline(audio_path)
            
            # Check if we got anything
            if diarization_result is None:
                logger.warning("DiarizationHandler: Pipeline returned None.")
            else:
                # Count segments safely
                try:
                    num_segments = len(list(diarization_result.itertracks()))
                    logger.info(f"DiarizationHandler: Success. Found {num_segments} speaker segments.")
                except Exception:
                    logger.info("DiarizationHandler: Success (could not count segments).")

            return diarization_result
        except Exception as e:
            logger.error(f"Error during diarization: {e}", exc_info=True)
            raise
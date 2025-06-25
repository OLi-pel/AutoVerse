# core/app_worker.py
import logging
import os
from core.audio_processor import AudioProcessor, ProcessedAudioResult
from utils import constants

logger = logging.getLogger(__name__)

def processing_worker_function(queue, audio_paths, options, cache_dir):
    """
    This function runs in a separate process and communicates via a queue.
    """
     # --- NEW LOGGING FIX ---
    # Get a logger instance, but configure it to not propagate messages
    # up to the root logger, effectively silencing it for this process.
    logger = logging.getLogger(__name__)
    logger.propagate = False
    # --- END OF FIX ---
    try:
        # 1. Create a progress callback that puts messages on the queue
        def progress_callback(message, percentage=None):
            if percentage is not None:
                queue.put(('progress', percentage))
            if message:
                queue.put(('status', message))

        # 2. Initialize the AudioProcessor
        def _map_ui_model_key_to_whisper_name(ui_model_key: str) -> str:
            mapping = {
                "tiny": "tiny", "base": "base", "small": "small", "medium": "medium",
                "large (recommended)": "large", "turbo": "small"
            }
            return mapping.get(ui_model_key, "large")

        processor_config = {
            'huggingface': {
                'use_auth_token': 'yes' if options['enable_diarization'] else 'no',
                'hf_token': options['hf_token']
            },
            'transcription': {
                'model_name': _map_ui_model_key_to_whisper_name(options['model_key'])
            }
        }
        
        # This part is CPU/memory intensive and is now isolated
        audio_processor = AudioProcessor(
            config=processor_config,
            progress_callback=progress_callback,
            enable_diarization=options['enable_diarization'],
            include_timestamps=options['include_timestamps'],
            include_end_times=options['include_end_times'],
            enable_auto_merge=options['auto_merge'],
            cache_dir=cache_dir
        )

        # 3. Process the audio
        if len(audio_paths) == 1:
            result = audio_processor.process_audio(audio_paths[0])
        else:
            result = ProcessedAudioResult(constants.STATUS_ERROR, message="Batch processing not implemented.")

        # 4. Put the final result on the queue
        queue.put(('finished', result))

    except Exception as e:
        logger.exception("An error occurred in the worker process.")
        error_result = ProcessedAudioResult(constants.STATUS_ERROR, message=str(e))
        queue.put(('finished', error_result))
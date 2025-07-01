# core/app_worker.py
import logging
import os
import sys
import tempfile
from moviepy.editor import VideoFileClip
import torchaudio
from core.audio_processor import AudioProcessor, ProcessedAudioResult
from utils import constants

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv']

def _is_video_file(file_path):
    """Checks if a file is a video based on its extension."""
    return any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS)

def _extract_audio(video_path):
    """Extracts audio from a video file."""
    try:
        video = VideoFileClip(video_path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio_file:
            temp_path = temp_audio_file.name
        video.audio.write_audiofile(temp_path, codec='pcm_s16le')
        logger.info(f"Successfully extracted audio from {video_path} to {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Failed to extract audio from {video_path}: {e}")
        raise

def processing_worker_function(queue, file_paths, options, cache_dir, dest_folder=None, ffmpeg_path=None):
    """
    This is the definitive worker function. It modifies the PATH for the entire process,
    making ffmpeg globally available to all libraries.
    """
    # --- Step 1: Worker-Specific Logging Setup ---
    log_dir = os.path.join(constants.APP_USER_DATA_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "worker.log")
    file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
    formatter = logging.Formatter(constants.LOG_FORMAT, datefmt=constants.LOG_DATE_FORMAT)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.setLevel(constants.ACTIVE_LOG_LEVEL)

    # --- Step 2: THE GLOBAL FFMPEG & AUDIO BACKEND FIX ---
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        logger.info(f"Worker received ffmpeg path: {ffmpeg_path}")
        # Get the directory containing the ffmpeg binary
        bin_dir = os.path.dirname(ffmpeg_path)
        # Prepend this directory to the process's PATH environment variable.
        # This makes the bundled ffmpeg discoverable by ANY library (moviepy, whisper, etc.)
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]
        logger.info(f"Worker PATH has been set to: {os.environ['PATH']}")
    else:
        logger.warning("No specific ffmpeg path received or path does not exist.")
        
    try:
        torchaudio.set_audio_backend("soundfile")
        logger.info("Successfully set torchaudio backend to 'soundfile'.")
    except Exception as e:
        logger.error(f"Failed to set torchaudio backend: {e}")
    # --- END GLOBAL FIX ---
    
    try:
        def progress_callback(message, percentage=None):
            if percentage is not None: queue.put((constants.MSG_TYPE_PROGRESS, percentage))
            if message: queue.put((constants.MSG_TYPE_STATUS, message))

        def _map_ui_model_key_to_whisper_name(ui_model_key: str) -> str:
            mapping = {"tiny": "tiny", "base": "base", "small": "small", "medium": "medium", "large (recommended)": "large", "turbo": "small"}
            return mapping.get(ui_model_key, "large")

        processor_config = {
            'huggingface': {'use_auth_token': 'yes' if options['enable_diarization'] else 'no', 'hf_token': options['hf_token']},
            'transcription': {'model_name': _map_ui_model_key_to_whisper_name(options['model_key'])}
        }
        
        audio_processor = AudioProcessor(
            config=processor_config, progress_callback=progress_callback,
            enable_diarization=options['enable_diarization'], include_timestamps=options['include_timestamps'],
            include_end_times=options['include_end_times'], enable_auto_merge=options['auto_merge'],
            cache_dir=cache_dir
        )
        
        all_results = []
        for idx, file_path in enumerate(file_paths):
            queue.put((constants.MSG_TYPE_BATCH_FILE_START, {
                'filename': os.path.basename(file_path),
                'current_idx': idx + 1,
                'total_files': len(file_paths)
            }))
            
            audio_to_process = file_path
            temp_audio_path = None
            try:
                if _is_video_file(file_path):
                    progress_callback(f"Extracting audio...", 0)
                    temp_audio_path = _extract_audio(file_path)
                    audio_to_process = temp_audio_path

                result = audio_processor.process_audio(audio_to_process)
                result.source_file = file_path

                if result.status == constants.STATUS_SUCCESS and len(file_paths) > 1 and dest_folder:
                    model_name_key = options["model_key"].split(" ")[0]
                    base_name, _ = os.path.splitext(os.path.basename(file_path))
                    output_filename = f"{base_name}_{model_name_key}_transcription.txt"
                    save_path = os.path.join(dest_folder, output_filename)
                    AudioProcessor.save_to_txt(save_path, result.data, result.is_plain_text_output)
                    result.output_path = save_path
                all_results.append(result)

            except Exception as e:
                full_traceback = traceback.format_exc()
                error_msg = f"Failed to process {os.path.basename(file_path)}:\n{full_traceback}"
                logger.error(f"Captured full traceback:\n{full_traceback}")
                all_results.append(ProcessedAudioResult(status=constants.STATUS_ERROR, message=error_msg, source_file=file_path))
            
            finally:
                if temp_audio_path and os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
        
        queue.put((constants.MSG_TYPE_BATCH_COMPLETED, {'all_results': all_results}))

    except Exception:
        full_traceback = traceback.format_exc()
        logger.error(f"Critical unhandled error in worker:\n{full_traceback}")
        queue.put(('finished', {'all_results': [ProcessedAudioResult(status=constants.STATUS_ERROR, message=full_traceback)]}))
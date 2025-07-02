# core/app_worker.py
import logging
import os
import sys
import tempfile
from moviepy.editor import VideoFileClip
import torchaudio
import traceback

# --- [THE FIX] ---
# The worker process is independent and needs its own imports.
from utils import constants
# --------------------

from core.audio_processor import AudioProcessor, ProcessedAudioResult

# It is good practice to initialize the logger at the module level
logger = logging.getLogger(__name__)

# A custom stream class that redirects stdout/stderr to a logger.
class TqdmLogStream:
    """
    A file-like object that redirects writes to a logger instance.
    Used to capture output from libraries like tqdm that write to stdout.
    """
    def __init__(self, logger_instance, level=logging.DEBUG):
        self.logger = logger_instance
        self.level = level
        self.linebuf = ''

    def write(self, buf):
        # Write each line to the log
        for line in buf.rstrip().splitlines():
            # Don't log empty lines
            if line.strip():
                self.logger.log(self.level, line.rstrip())

    def flush(self):
        # The flush method is required for compatibility with stream protocols.
        pass

VIDEO_EXTENSIONS = ['.mp4', '.mkv', 'avi', '.mov', '.flv', '.wmv']

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
        logger.error(f"Failed to extract audio from {video_path}: {e}", exc_info=True)
        raise

def processing_worker_function(queue, file_paths, options, cache_dir, dest_folder=None, ffmpeg_path=None):
    """
    The definitive worker function. Includes a global fix for the tqdm crash
    by redirecting console output to a log file.
    """
    # We must set up the logger first so we can redirect stdout to it.
    log_dir = os.path.join(constants.APP_USER_DATA_DIR, "logs") # This line now works
    os.makedirs(log_dir, exist_ok=True)
    worker_log_path = os.path.join(log_dir, "worker.log")
    file_handler = logging.FileHandler(worker_log_path, mode='w', encoding='utf-8')
    formatter = logging.Formatter(constants.LOG_FORMAT, datefmt=constants.LOG_DATE_FORMAT) # This now works
    file_handler.setFormatter(formatter)
    
    # Configure the logger specifically for this worker
    worker_logger = logging.getLogger("WorkerLogger")
    worker_logger.addHandler(file_handler)
    worker_logger.setLevel(constants.LOG_LEVEL_DEBUG) # This now works
    
    if getattr(sys, 'frozen', False):
        sys.stdout = TqdmLogStream(worker_logger, level=logging.DEBUG)
        sys.stderr = TqdmLogStream(worker_logger, level=logging.ERROR)
        worker_logger.info("Worker stdout and stderr redirected to log file.")
    
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        worker_logger.info(f"Worker received ffmpeg path: {ffmpeg_path}")
        bin_dir = os.path.dirname(ffmpeg_path)
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]
        worker_logger.info(f"Worker PATH has been set to: {os.environ['PATH']}")
    else:
        worker_logger.warning("No specific ffmpeg path received or path does not exist.")
        
    try:
        torchaudio.set_audio_backend("soundfile")
        worker_logger.info("Successfully set torchaudio backend to 'soundfile'.")
    except Exception as e:
        worker_logger.error(f"Failed to set torchaudio backend: {e}")

    try:
        def progress_callback(message, percentage=None):
            # This line and the one below now work
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
            # This block now works because all constants are defined
            queue.put((constants.MSG_TYPE_BATCH_FILE_START, {
                'filename': os.path.basename(file_path),
                'current_idx': idx + 1,
                'total_files': len(file_paths)
            }))
            
            audio_to_process = file_path
            temp_audio_path = None
            try:
                if _is_video_file(file_path):
                    progress_callback("Extracting audio...", 0)
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
                worker_logger.error(f"Captured full traceback for file {file_path}:\n{full_traceback}")
                all_results.append(ProcessedAudioResult(status=constants.STATUS_ERROR, message=error_msg, source_file=file_path))
            
            finally:
                if temp_audio_path and os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
        
        queue.put((constants.MSG_TYPE_BATCH_COMPLETED, {'all_results': all_results}))

    except Exception:
        full_traceback = traceback.format_exc()
        worker_logger.error(f"Critical unhandled error in worker:\n{full_traceback}")
        queue.put((constants.MSG_TYPE_BATCH_COMPLETED, {'all_results': [ProcessedAudioResult(status=constants.STATUS_ERROR, message=f"A critical worker error occurred:\n{full_traceback}")]}))
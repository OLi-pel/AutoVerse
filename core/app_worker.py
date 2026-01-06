# core/app_worker.py

import logging
import os
import sys
import tempfile
import traceback
import re
import time

from utils import constants
from core.audio_processor import ProcessedAudioResult, AudioProcessor
from moviepy.editor import AudioFileClip

logger = logging.getLogger(__name__)

# --- Helper Classes ---

class TqdmLogStream:
    """
    Captures stdout/stderr to find tqdm progress bars.
    """
    def __init__(self, queue, logger_instance, level=logging.DEBUG):
        self.queue = queue
        self.logger = logger_instance
        self.level = level
        self.progress_regex = re.compile(r"(\d{1,3})%")
        self.last_percentage = -1

    def write(self, buf):
        clean_buf = buf.replace('\r', '\n')
        
        for line in clean_buf.splitlines():
            line = line.strip()
            if line:
                if "%" in line:
                    match = self.progress_regex.search(line)
                    if match:
                        try: 
                            percentage = int(match.group(1))
                            
                            # --- FIX 1: Ignore 100% ---
                            # This prevents the bar from jumping to 100 (or 90 mapped) 
                            # when a background download/conversion finishes while 
                            # another task is running. We let manual callbacks handle completion.
                            if percentage == 100:
                                continue

                            # --- FIX 2: Allow Reset ---
                            # Use != instead of > so the bar can go back to 0 for the next task
                            if percentage != self.last_percentage:
                                self.queue.put((constants.MSG_TYPE_REALTIME_PROGRESS, percentage))
                                self.last_percentage = percentage
                        except (ValueError, IndexError): 
                            pass

    def flush(self): 
        pass

    def isatty(self):
        return True

# --- Helper Functions ---

COMPLEX_AUDIO_EXTENSIONS = ['.m4a', '.aac', '.wma', '.ogg', '.flac']
VIDEO_EXTENSIONS = ['.mp4', '.mkv', 'avi', '.mov', '.flv', '.wmv']

def _is_complex_format(file_path):
    return any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS + COMPLEX_AUDIO_EXTENSIONS)

def _convert_to_wav(media_path):
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f: 
            temp_path = f.name
        with AudioFileClip(media_path) as audio_clip: 
            audio_clip.write_audiofile(temp_path, codec='pcm_s16le', logger=None)
        return temp_path
    except Exception as e:
        logger.error(f"Failed to convert audio from {media_path}: {e}", exc_info=True)
        raise

# --- Main Worker Function ---

def processing_worker_function(queue, file_paths, options, cache_dir, dest_folder=None, ffmpeg_path=None):
    # Setup logging
    log_dir = os.path.join(constants.APP_USER_DATA_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    worker_log_path = os.path.join(log_dir, "worker.log")
    
    file_handler = logging.FileHandler(worker_log_path, mode='w', encoding='utf-8')
    formatter = logging.Formatter(constants.LOG_FORMAT, datefmt=constants.LOG_DATE_FORMAT)
    file_handler.setFormatter(formatter)
    
    worker_logger = logging.getLogger("WorkerLogger")
    worker_logger.addHandler(file_handler)
    worker_logger.setLevel(constants.LOG_LEVEL_DEBUG)
    
    # Redirect stderr to catch tqdm
    stream_capture = TqdmLogStream(queue, worker_logger, level=logging.INFO)
    sys.stdout = stream_capture
    sys.stderr = stream_capture
    
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]

    try:
        def progress_callback(message, percentage=None):
            if percentage is not None: 
                queue.put((constants.MSG_TYPE_PROGRESS, percentage))
            if message: 
                queue.put((constants.MSG_TYPE_STATUS, message))

        whisper_model_name = "large"

        progress_callback("Initializing AI models...", 5)
        
        audio_processor = AudioProcessor(
            config={
                'huggingface': {'hf_token': options['hf_token']}, 
                'transcription': {'model_name': whisper_model_name}
            },
            progress_callback=progress_callback, 
            enable_diarization=options['enable_diarization'], 
            cache_dir=cache_dir,
            logger_instance=worker_logger
        )
        
        if audio_processor._initialization_error: 
            raise Exception(audio_processor._initialization_error)
        
        all_results = []
        for idx, file_path in enumerate(file_paths):
            queue.put((constants.MSG_TYPE_BATCH_FILE_START, { 
                'filename': os.path.basename(file_path), 
                'current_idx': idx + 1, 
                'total_files': len(file_paths) 
            }))
            
            try:
                temp_audio_path = None
                audio_to_process = file_path
                
                if _is_complex_format(file_path):
                    progress_callback(f"Converting {os.path.basename(file_path)}...", 10)
                    temp_audio_path = _convert_to_wav(file_path)
                    audio_to_process = temp_audio_path
                    progress_callback("Conversion complete.", 15)
                
                diarization_result = None
                if options['enable_diarization']:
                    progress_callback("Identifying speakers...", 20)
                    try:
                        diarization_result = audio_processor.diarization_handler.diarize(audio_to_process)
                    except Exception as diar_error:
                        worker_logger.warning(f"Diarization failed: {diar_error}")
                        diarization_result = None
                    progress_callback("Speaker identification complete.", 30)

                # --- TRANSCRIPTION PHASE ---
                progress_callback(f"Transcribing with '{whisper_model_name}' model...", 30)
                
                # verbose=False in transcription_handler triggers the bar we capture here
                transcription_result = audio_processor.transcription_handler.transcribe(audio_to_process)
                
                progress_callback("Finalizing...", 95)
                
                result = audio_processor.finalize_processing(diarization_result, transcription_result)
                result.source_file = file_path

                if result.status == constants.STATUS_SUCCESS and len(file_paths) > 1 and dest_folder:
                    base_name, _ = os.path.splitext(os.path.basename(file_path))
                    output_filename = f"{base_name}_{whisper_model_name}_transcription.txt"
                    save_path = os.path.join(dest_folder, output_filename)
                    AudioProcessor.save_to_txt(save_path, result.data, result.is_plain_text_output)
                    result.output_path = save_path
                
                all_results.append(result)

            except Exception as e:
                full_traceback = traceback.format_exc()
                error_msg = f"Failed to process {os.path.basename(file_path)}:\n{full_traceback}"
                worker_logger.error(error_msg)
                all_results.append(ProcessedAudioResult(status=constants.STATUS_ERROR, message=error_msg, source_file=file_path))
            finally:
                if temp_audio_path and os.path.exists(temp_audio_path):
                    try: os.remove(temp_audio_path)
                    except OSError: pass

        queue.put((constants.MSG_TYPE_BATCH_COMPLETED, {'all_results': all_results}))

    except Exception as e:
        full_traceback = traceback.format_exc()
        worker_logger.error(f"Critical error: {e}\n{full_traceback}")
        queue.put((constants.MSG_TYPE_BATCH_COMPLETED, {'all_results': [ProcessedAudioResult(status=constants.STATUS_ERROR, message=f"Critical error: {full_traceback}")]}))
# core/app_worker.py

import logging
import os
import sys
import tempfile
import torchaudio
import traceback
import re
import time
import threading
from tinytag import TinyTag

from utils import constants
from utils.config_manager import ConfigManager
from core.audio_processor import ProcessedAudioResult, AudioProcessor

logger = logging.getLogger(__name__)

# TqdmLogStream and TimerThread classes are correct and remain unchanged.
class TqdmLogStream:
    def __init__(self, queue, logger_instance, level=logging.DEBUG):
        self.queue, self.logger, self.level = queue, logger_instance, level
        self.progress_regex = re.compile(r"(\d+)\s*%\|")
    def write(self, buf):
        for line in buf.rstrip().splitlines():
            if line.strip():
                self.logger.log(self.level, line.rstrip())
                match = self.progress_regex.search(line)
                if match:
                    try: self.queue.put((constants.MSG_TYPE_REALTIME_PROGRESS, int(match.group(1))))
                    except (ValueError, IndexError): pass
    def flush(self): pass

class TimerThread(threading.Thread):
    def __init__(self, queue, total_seconds_predicted, stop_event):
        super().__init__()
        self.queue, self.total_seconds_predicted, self.stop_event = queue, max(0.1, total_seconds_predicted), stop_event
        self.start_time = time.time()
        self.daemon = True
    def run(self):
        while not self.stop_event.is_set():
            progress = ((time.time() - self.start_time) / self.total_seconds_predicted) * 100
            self.queue.put((constants.MSG_TYPE_REALTIME_PROGRESS, int(min(progress, 99))))
            time.sleep(0.2)

# Helper functions are unchanged...
from moviepy.editor import AudioFileClip
COMPLEX_AUDIO_EXTENSIONS = ['.m4a', '.aac', '.wma', '.ogg', '.flac']; VIDEO_EXTENSIONS = ['.mp4', '.mkv', 'avi', '.mov', '.flv', '.wmv']
def _is_complex_format(file_path):
    return any(file_path.lower().endswith(ext) for ext in VIDEO_EXTENSIONS + COMPLEX_AUDIO_EXTENSIONS)
def _convert_to_wav(media_path):
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f: temp_path = f.name
        with AudioFileClip(media_path) as audio_clip: audio_clip.write_audiofile(temp_path, codec='pcm_s16le', logger=None)
        return temp_path
    except Exception as e:
        logger.error(f"Failed to convert audio from {media_path}: {e}", exc_info=True); raise

def processing_worker_function(queue, file_paths, options, cache_dir, dest_folder=None, ffmpeg_path=None):
    # Setup logger and stdout/stderr redirection...
    log_dir = os.path.join(constants.APP_USER_DATA_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True); worker_log_path = os.path.join(log_dir, "worker.log")
    file_handler = logging.FileHandler(worker_log_path, mode='w', encoding='utf-8'); formatter = logging.Formatter(constants.LOG_FORMAT, datefmt=constants.LOG_DATE_FORMAT); file_handler.setFormatter(formatter)
    worker_logger = logging.getLogger("WorkerLogger"); worker_logger.addHandler(file_handler); worker_logger.setLevel(constants.LOG_LEVEL_DEBUG)
    sys.stdout = TqdmLogStream(queue, worker_logger, level=logging.INFO); sys.stderr = TqdmLogStream(queue, worker_logger, level=logging.ERROR)
    
    if ffmpeg_path and os.path.exists(ffmpeg_path):
        os.environ["PATH"] = os.path.dirname(ffmpeg_path) + os.pathsep + os.environ["PATH"]

    try:
        config_manager = ConfigManager(constants.DEFAULT_CONFIG_FILE)
        MODEL_SPEEDS = { "tiny": 10, "base": 7, "small": 4, "medium": 2, "large": 1, "turbo": 4, "diarization": 1.5 }

        def progress_callback(message, percentage=None):
            if percentage is not None: queue.put((constants.MSG_TYPE_PROGRESS, percentage))
            if message: queue.put((constants.MSG_TYPE_STATUS, message))

        def _map_ui_model_key_to_whisper_name(ui_model_key: str) -> str:
            return ui_model_key.split(" ")[0]
        
        whisper_model_name = _map_ui_model_key_to_whisper_name(options['model_key'])

        progress_callback("Initializing AI models (downloading if needed)...", 0)
        audio_processor = AudioProcessor(
            config={'huggingface': {'hf_token': options['hf_token']}, 'transcription': {'model_name': whisper_model_name}},
            progress_callback=progress_callback, enable_diarization=options['enable_diarization'], cache_dir=cache_dir
        )
        if audio_processor._initialization_error: raise Exception(audio_processor._initialization_error)
        
        all_results = []
        for idx, file_path in enumerate(file_paths):
            queue.put((constants.MSG_TYPE_BATCH_FILE_START, { 'filename': os.path.basename(file_path), 'current_idx': idx + 1, 'total_files': len(file_paths) }))
            try:
                temp_audio_path = None; audio_to_process = file_path
                if _is_complex_format(file_path):
                    progress_callback(f"Converting {os.path.basename(file_path)}...", 0)
                    temp_audio_path = _convert_to_wav(file_path)
                    audio_to_process = temp_audio_path
                    progress_callback("Conversion complete.", 100)
                
                duration_sec = (TinyTag.get(audio_to_process).duration or 1.0)
                
                if options['enable_diarization']:
                    factor = config_manager.get_performance_factor("diarization")
                    predicted_time = (duration_sec / MODEL_SPEEDS['diarization']) * factor
                    progress_callback("Identifying speakers...", 0)
                    
                    # --- THIS IS THE FIX ---
                    stop_event = threading.Event()
                    timer = TimerThread(queue, predicted_time, stop_event)
                    timer.start()
                    
                    start_time = time.time()
                    diarization_result = audio_processor.diarization_handler.diarize(audio_to_process)
                    actual_time = time.time() - start_time
                    stop_event.set()
                    
                    if actual_time > 1.0 and duration_sec > 2.0:
                        new_factor = (actual_time * MODEL_SPEEDS['diarization']) / duration_sec
                        queue.put((constants.MSG_TYPE_SAVE_PERFORMANCE_FACTOR, ("diarization", new_factor)))
                    
                    progress_callback("Speaker identification complete.", 100)
                else:
                    diarization_result = None
                
                model_key_simple = whisper_model_name
                factor = config_manager.get_performance_factor(model_key_simple)
                predicted_time = (duration_sec / MODEL_SPEEDS.get(model_key_simple, 1)) * factor
                progress_callback(f"Transcribing with '{model_key_simple}' model...", 0)

                # --- AND THIS IS THE SECOND FIX ---
                stop_event = threading.Event()
                timer = TimerThread(queue, predicted_time, stop_event)
                timer.start()
                
                start_time = time.time()
                transcription_result = audio_processor.transcription_handler.transcribe(audio_to_process)
                actual_time = time.time() - start_time
                stop_event.set()
                
                if actual_time > 1.0 and duration_sec > 2.0:
                    new_factor = (actual_time * MODEL_SPEEDS.get(model_key_simple, 1)) / duration_sec
                    queue.put((constants.MSG_TYPE_SAVE_PERFORMANCE_FACTOR, (model_key_simple, new_factor)))
                
                result = audio_processor.finalize_processing(diarization_result, transcription_result)
                result.source_file = file_path

                if result.status == constants.STATUS_SUCCESS and len(file_paths) > 1 and dest_folder:
                    base_name, _ = os.path.splitext(os.path.basename(file_path)); output_filename = f"{base_name}_{model_key_simple}_transcription.txt"; save_path = os.path.join(dest_folder, output_filename)
                    AudioProcessor.save_to_txt(save_path, result.data, result.is_plain_text_output); result.output_path = save_path
                all_results.append(result)

            except Exception as e:
                full_traceback = traceback.format_exc(); error_msg = f"Failed to process {os.path.basename(file_path)}:\n{full_traceback}"
                worker_logger.error(f"Captured full traceback for file {file_path}:\n{full_traceback}")
                all_results.append(ProcessedAudioResult(status=constants.STATUS_ERROR, message=error_msg, source_file=file_path))
            finally:
                if temp_audio_path and os.path.exists(temp_audio_path):
                    try: os.remove(temp_audio_path)
                    except OSError: pass
        queue.put((constants.MSG_TYPE_BATCH_COMPLETED, {'all_results': all_results}))
    except Exception as e:
        full_traceback = traceback.format_exc(); worker_logger.error(f"Critical unhandled error in worker:\n{e}\n{full_traceback}")
        queue.put((constants.MSG_TYPE_BATCH_COMPLETED, {'all_results': [ProcessedAudioResult(status=constants.STATUS_ERROR, message=f"A critical worker error occurred:\n{full_traceback}")]}))
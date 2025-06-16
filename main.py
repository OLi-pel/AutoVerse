# main.py (Final Fixes)

import os
import sys
import logging
import multiprocessing
import threading

# --- PySide6 Imports ---
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot, QEvent

# This block should be at the very top of your main.py file.
# It handles stdout/stderr redirection for bundled applications (PyInstaller).
if getattr(sys, 'frozen', False):
    _devnull = open(os.devnull, 'w')
    if sys.stdout is None: sys.stdout = _devnull
    if sys.stderr is None: sys.stderr = _devnull
    try:
        from tqdm import tqdm
        from functools import partial
        tqdm = partial(tqdm, file=sys.stdout)
    except Exception as e:
        print(f"Error applying tqdm patch: {e}", file=sys.stderr)

# --- Add the bundled ffmpeg to the PATH ---
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    ffmpeg_path = os.path.join(bundle_dir, 'bin')
    os.environ["PATH"] += os.pathsep + ffmpeg_path

# --- Local Application Imports ---
from utils import constants
from utils.logging_setup import setup_logging
from utils.config_manager import ConfigManager
from core.audio_processor import AudioProcessor
from ui.main_window import MainWindow
from ui.correction_window import CorrectionWindow
from ui.launch_screen import LaunchScreen

# Initialize logging for the application
setup_logging()
logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    """Defines signals available from a running worker thread."""
    status_update = Signal(str)
    progress_update = Signal(int)
    processing_complete = Signal(dict)
    batch_processing_complete = Signal(dict)
    error = Signal(str)

class AudioProcessingWorker(QRunnable):
    """Worker thread for running audio processing in the background."""
    def __init__(self, audio_processor_instance, files_to_process):
        super().__init__()
        self.audio_processor = audio_processor_instance
        self.files_to_process = files_to_process
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            def progress_callback(message: str, percentage: int = None):
                if message: self.signals.status_update.emit(message)
                if percentage is not None: self.signals.progress_update.emit(percentage)
            
            self.audio_processor.progress_callback = progress_callback

            if len(self.files_to_process) == 1:
                self._process_single_file(self.files_to_process[0])
            else:
                self._process_batch(self.files_to_process)
        except Exception as e:
            logger.exception("Unhandled error in AudioProcessingWorker.")
            self.signals.error.emit(f"A critical error occurred in the processing thread: {e}")

    def _process_single_file(self, audio_path):
        logger.info(f"Worker: Starting single file processing for: {audio_path}")
        result_obj = self.audio_processor.process_audio(audio_path)
        payload = {
            constants.KEY_FINAL_STATUS: result_obj.status,
            constants.KEY_ERROR_MESSAGE: result_obj.message,
            constants.KEY_IS_EMPTY_RESULT: result_obj.status == constants.STATUS_EMPTY,
            "processed_data": result_obj.data,
            "is_plain_text_output": result_obj.is_plain_text_output,
            "original_audio_path": audio_path
        }
        self.signals.processing_complete.emit(payload)

    def _process_batch(self, file_list):
        logger.info(f"Worker: Starting batch processing for {len(file_list)} files.")
        all_results = []
        total_files = len(file_list)
        for i, file_path in enumerate(file_list):
            base_filename = os.path.basename(file_path)
            # Update status for the current file in the batch
            self.signals.status_update.emit(f"Batch ({i+1}/{total_files}): Processing {base_filename}")
            result_obj = self.audio_processor.process_audio(file_path)
            all_results.append({
                "original_path": file_path,
                "status": result_obj.status,
                "message": result_obj.message,
                "is_empty": result_obj.status == constants.STATUS_EMPTY,
                "data": result_obj.data,
                "is_plain_text_output": result_obj.is_plain_text_output
            })
        self.signals.batch_processing_complete.emit({constants.KEY_BATCH_ALL_RESULTS: all_results})

class MainApp(QObject):
    """The main application controller."""
    startup_finished = Signal(bool, str)

    def __init__(self, q_app_instance):
        super().__init__()
        self.q_app = q_app_instance
        self.config_manager = ConfigManager(constants.DEFAULT_CONFIG_FILE)
        self.audio_processor = None
        self.audio_file_paths = []
        self.last_successful_audio_path = None
        self.last_successful_transcription_path = None
        self.main_window, self.correction_window, self.launch_screen = None, None, None
        self.thread_pool = QThreadPool()
        logger.info(f"Using a QThreadPool with max {self.thread_pool.maxThreadCount()} threads.")
        self.startup_finished.connect(self._finalize_startup_on_main_thread)

    def start(self):
        self.launch_screen = LaunchScreen()
        self.launch_screen.show_and_process()
        model_loader_thread = threading.Thread(target=self._load_models_and_finalize, daemon=True)
        model_loader_thread.start()

    def _load_models_and_finalize(self):
        self.launch_screen.update_text("Loading models, please wait...")
        try:
            self._ensure_audio_processor_initialized(is_initial_setup=True)
            self.startup_finished.emit(True, "")
        except Exception as e:
            logger.error(f"Failed to initialize essential models: {e}", exc_info=True)
            self.startup_finished.emit(False, str(e))

    @Slot(bool, str)
    def _finalize_startup_on_main_thread(self, models_loaded_ok, error_msg=None):
        if self.launch_screen:
            self.launch_screen.close()
            self.launch_screen = None
        if models_loaded_ok:
            logger.info("Models loaded. Creating and showing main window.")
            self.main_window = MainWindow(
                start_processing_callback=self.start_processing,
                select_audio_file_callback=self.select_audio_files,
                open_correction_window_callback=self.open_correction_window,
                config_manager_instance=self.config_manager,
                initial_show_tips_state=self.config_manager.get_main_window_show_tips()
            )
            self.main_window.set_save_token_callback(self.save_huggingface_token)
            self._load_and_display_saved_token()
            self.main_window.show()
        else:
            QMessageBox.critical(None, "Application Startup Error", f"Failed to load essential models: {error_msg}")
            self.q_app.quit()

    def select_audio_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self.main_window, "Select Audio File(s)", "", "Audio Files (*.wav *.mp3 *.aac *.flac *.m4a);;All files (*.*)")
        if paths:
            self.audio_file_paths = paths
            self.main_window.update_audio_file_entry_display(self.audio_file_paths)
            self.last_successful_audio_path, self.last_successful_transcription_path = None, None

    def start_processing(self):
        if not self.audio_file_paths:
            QMessageBox.warning(self.main_window, "No Files", "Please select one or more audio files first.")
            return
        try:
            self._ensure_audio_processor_initialized()
        except Exception as e:
            QMessageBox.critical(self.main_window, "Initialization Error", f"Could not initialize audio processor: {e}")
            return
        self.main_window.disable_ui_for_processing()
        worker = AudioProcessingWorker(self.audio_processor, self.audio_file_paths)
        worker.signals.status_update.connect(lambda text: self.main_window.update_status_and_progress(status_text=text))
        worker.signals.progress_update.connect(lambda val: self.main_window.update_status_and_progress(progress_value=val))
        worker.signals.error.connect(self._on_processing_error)
        worker.signals.processing_complete.connect(self._on_single_processing_complete)
        worker.signals.batch_processing_complete.connect(self._on_batch_processing_complete)
        self.thread_pool.start(worker)

    def open_correction_window(self):
        if not self.correction_window:
            self.correction_window = CorrectionWindow(parent_root=self.main_window, config_manager_instance=self.config_manager, initial_show_tips_state=self.config_manager.get_correction_window_show_tips())
            self.correction_window.show()
            self.correction_window.destroyed.connect(lambda: setattr(self, 'correction_window', None))
        self.correction_window.activateWindow()
        self.correction_window.raise_()

    @Slot(dict)
    def _on_single_processing_complete(self, payload):
        self.main_window.enable_ui_after_processing()
        status = payload.get(constants.KEY_FINAL_STATUS)
        err_msg = payload.get(constants.KEY_ERROR_MESSAGE)
        if status == constants.STATUS_SUCCESS and payload.get("processed_data"):
            self._prompt_for_save_location_and_save_single(
                payload.get("processed_data"),
                payload.get("is_plain_text_output", False),
                payload.get("original_audio_path")
            )
        elif status == constants.STATUS_EMPTY:
            self.main_window.update_status_and_progress(err_msg or "No speech detected.", 100)
            self.main_window.display_processed_output(processing_returned_empty=True)
        else: # Error case
            self.main_window.update_status_and_progress(f"Error: {err_msg[:100]}...", 0)
            self.main_window.update_output_text(f"Error processing {os.path.basename(payload.get('original_audio_path'))}:\n{err_msg}")

    @Slot(dict)
    def _on_batch_processing_complete(self, payload):
        self.main_window.enable_ui_after_processing()
        all_results = payload.get(constants.KEY_BATCH_ALL_RESULTS)
        self.main_window.update_status_and_progress("Batch processing finished. Awaiting save location...", 100)
        self._prompt_for_batch_save_directory_and_save(all_results)

    def _prompt_for_save_location_and_save_single(self, data_to_save, is_plain_text, original_audio_path):
        default_fn = f"{os.path.splitext(os.path.basename(original_audio_path))[0]}_transcription.txt"
        save_path, _ = QFileDialog.getSaveFileName(self.main_window, "Save Transcription As", default_fn, "Text Files (*.txt)")
        if save_path:
            try:
                self.audio_processor.save_to_txt(save_path, data_to_save, is_plain_text)
                self.last_successful_transcription_path, self.last_successful_audio_path = save_path, original_audio_path
                self.main_window.update_status_and_progress("Transcription saved!", 100)
                self.main_window.display_processed_output(output_file_path=save_path)
            except Exception as e:
                QMessageBox.critical(self.main_window, "Save Error", f"Could not save file: {e}")
        else:
            self.main_window.update_status_and_progress("Save cancelled by user.", 100)
            display_content = data_to_save if is_plain_text else "\n".join(data_to_save or [])
            self.main_window.update_output_text(f"File not saved. Transcription content:\n\n{display_content}")

    def _prompt_for_batch_save_directory_and_save(self, all_processed_results):
        """FIXED: Fully implemented batch saving logic."""
        if not any(item['status'] == constants.STATUS_SUCCESS for item in all_processed_results):
            QMessageBox.information(self.main_window, "Batch Complete", "No successful transcriptions to save.")
            self.main_window.update_output_text("Batch processing finished. No results were generated or all failed.")
            return
            
        output_dir = QFileDialog.getExistingDirectory(self.main_window, "Select Directory to Save Batch Transcriptions")
        if not output_dir:
            QMessageBox.warning(self.main_window, "Save Cancelled", "No directory selected. Batch results not saved.")
            self.main_window.display_processed_output(is_batch_summary=True, batch_summary_message="Batch save cancelled. No files were saved.")
            return

        successful_saves, failed_saves = 0, 0
        batch_summary_log = [f"Batch Processing Summary (Saved to: {output_dir}):"]
        
        for item in all_processed_results:
            original_path = item['original_path']
            base_filename = os.path.basename(original_path)
            
            if item['status'] == constants.STATUS_SUCCESS and item.get("data"):
                transcript_filename_base, _ = os.path.splitext(base_filename)
                model_name_suffix = self.audio_processor.transcription_handler.model_name.replace('.', '')
                output_filename = f"{transcript_filename_base}_{model_name_suffix}_transcript.txt"
                full_output_path = os.path.join(output_dir, output_filename)
                
                try:
                    self.audio_processor.save_to_txt(full_output_path, item["data"], item.get("is_plain_text_output", False))
                    batch_summary_log.append(f"  SUCCESS: {base_filename} -> {output_filename}")
                    successful_saves += 1
                except Exception as e:
                    logger.exception(f"Batch save: Failed to save {full_output_path}")
                    batch_summary_log.append(f"  FAIL_SAVE: {base_filename} (Error: {e})")
                    failed_saves += 1
            else:
                batch_summary_log.append(f"  SKIPPED ({item['status']}): {base_filename} - {item['message']}")
                failed_saves += 1
        
        summary_message = f"Batch processing complete.\nSuccessfully saved: {successful_saves} file(s).\nFailed/Skipped: {failed_saves} file(s).\n\nLocation: {output_dir}"
        QMessageBox.information(self.main_window, "Batch Save Complete", summary_message)
        self.main_window.display_processed_output(is_batch_summary=True, batch_summary_message="\n".join(batch_summary_log))

    def _ensure_audio_processor_initialized(self, is_initial_setup=False):
        ui = self.main_window
        model_key = ui.model_combo.currentText() if ui else "large (recommended)"
        current_enable_diarization = ui.diarization_checkbox.isChecked() if ui else False
        current_include_timestamps = ui.timestamps_checkbox.isChecked() if ui else True
        current_include_end_times = ui.end_times_checkbox.isChecked() if ui and current_include_timestamps else False
        current_auto_merge_enabled = ui.auto_merge_checkbox.isChecked() if ui and current_enable_diarization else False
        
        actual_model_name = self._map_ui_model_key_to_whisper_name(model_key)
        
        needs_reinit = False
        if not self.audio_processor:
            needs_reinit = True
        else:
            options_changed = (
                self.audio_processor.transcription_handler.model_name != actual_model_name or
                self.audio_processor.output_enable_diarization != current_enable_diarization or
                self.audio_processor.output_include_timestamps != current_include_timestamps or
                self.audio_processor.output_include_end_times != current_include_end_times or
                self.audio_processor.output_enable_auto_merge != current_auto_merge_enabled
            )
            if options_changed:
                needs_reinit = True
        
        if needs_reinit:
            logger.info(f"Initializing/Re-initializing AudioProcessor. Model: '{actual_model_name}', Diarization: {current_enable_diarization}")
            cache_dir_path = os.path.join(os.path.expanduser('~'), 'TranscriptionOli_Cache')
            use_auth = self.config_manager.get_use_auth_token()
            hf_token = self.config_manager.load_huggingface_token() if use_auth else None
            processor_config = {
                'huggingface': {'use_auth_token': 'yes' if use_auth else 'no', 'hf_token': hf_token},
                'transcription': {'model_name': actual_model_name}
            }
            self.audio_processor = AudioProcessor(
                config=processor_config, enable_diarization=current_enable_diarization,
                include_timestamps=current_include_timestamps, include_end_times=current_include_end_times,
                enable_auto_merge=current_auto_merge_enabled, cache_dir=cache_dir_path
            )

    def _map_ui_model_key_to_whisper_name(self, ui_model_key: str) -> str:
        mapping = {"tiny": "tiny", "base": "base", "small": "small", "medium": "medium", "large (recommended)": "large", "turbo": "small"}
        return mapping.get(ui_model_key, "large")

    def _load_and_display_saved_token(self):
        token = self.config_manager.load_huggingface_token()
        if self.main_window: self.main_window.load_token_ui(token)

    def save_huggingface_token(self, token: str):
        self.config_manager.save_huggingface_token(token)
        self.config_manager.set_use_auth_token(bool(token))
        QMessageBox.information(self.main_window, "Token Saved", "Hugging Face token has been updated.")

    @Slot(str)
    def _on_processing_error(self, error_message):
        QMessageBox.critical(self.main_window, "Processing Error", error_message)
        self.main_window.enable_ui_after_processing()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    q_app = QApplication(sys.argv)
    app_controller = MainApp(q_app)
    app_controller.start()
    sys.exit(q_app.exec())





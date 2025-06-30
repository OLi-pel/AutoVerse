# main_pyside.py
import sys
import os
import logging
import multiprocessing
from queue import Empty

from PySide6.QtWidgets import (QApplication, QFileDialog, QMessageBox, QLineEdit, QPushButton, 
                               QComboBox, QFrame, QCheckBox, QProgressBar, QLabel, QTextEdit, 
                               QWidget, QTabWidget, QGroupBox)
from PySide6.QtCore import QTimer, Slot
from PySide6.QtGui import QIcon, QFontMetrics, QFont, QFontDatabase
from PySide6.QtUiTools import QUiLoader

from utils.logging_setup import setup_logging
from utils import constants
from utils.config_manager import ConfigManager
from ui.correction_view_logic import CorrectionViewLogic
from core.app_worker import processing_worker_function
from core.audio_processor import AudioProcessor
from ui.selectable_text_edit import SelectableTextEdit


multiprocessing.set_start_method('spawn', force=True)

setup_logging()
logger = logging.getLogger(__name__)

class MainApplication:
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        loader = QUiLoader()
        loader.registerCustomWidget(SelectableTextEdit)

        ui_file_path = os.path.join(os.path.dirname(__file__), "ui", "main_window.ui")
        self.window = loader.load(ui_file_path, None)
        
        if not self.window:
            print(f"CRITICAL: Failed to load UI file: {ui_file_path}", file=sys.stderr)
            sys.exit(1)
        
        self.config_manager = ConfigManager(constants.DEFAULT_CONFIG_FILE)
        
        self.is_processing = False # Processing state flag
        
        self._promote_widgets()
        self._setup_fonts()
        self._setup_icons()
        
        self.correction_logic = CorrectionViewLogic(self.window)

        self.audio_file_paths = []
        self.process = None
        self.queue = None
        self.last_single_file_result_path = None # For "head to correction"

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_queue)
        
        self.connect_signals()
        self.load_initial_settings()
        
        self.window.show()

    def _promote_widgets(self):
        # Main Tab
        self.window.audio_file_entry = self.window.findChild(QLineEdit, "audio_file_entry")
        self.window.browse_button = self.window.findChild(QPushButton, "browse_button")
        self.window.model_dropdown = self.window.findChild(QComboBox, "model_dropdown")
        self.window.diarization_checkbutton = self.window.findChild(QCheckBox, "diarization_checkbutton")
        self.window.auto_merge_checkbutton = self.window.findChild(QCheckBox, "auto_merge_checkbutton")
        self.window.timestamps_checkbutton_2 = self.window.findChild(QCheckBox, "timestamps_checkbutton_2")
        self.window.end_times_checkbutton = self.window.findChild(QCheckBox, "end_times_checkbutton")
        self.window.huggingface_token_frame = self.window.findChild(QGroupBox, "huggingface_token_frame")
        self.window.huggingface_token_entry = self.window.findChild(QLineEdit, "huggingface_token_entry")
        self.window.save_token_button = self.window.findChild(QPushButton, "save_token_button")
        self.window.start_processing_button = self.window.findChild(QPushButton, "start_processing_button")
        self.window.status_label = self.window.findChild(QLabel, "status_label")
        self.window.progress_bar = self.window.findChild(QProgressBar, "progress_bar")
        self.window.output_text_area = self.window.findChild(QTextEdit, "output_text_area")
        self.window.correction_button = self.window.findChild(QPushButton, "correction_button")
        
        # Correction Tab
        self.window.main_tab_widget = self.window.findChild(QTabWidget, "tabWidget")
        self.window.correction_transcription_entry = self.window.findChild(QLineEdit, "correction_transcription_entry")
        self.window.correction_browse_transcription_btn = self.window.findChild(QPushButton, "correction_browse_transcription_btn")
        self.window.correction_audio_entry = self.window.findChild(QLineEdit, "correction_audio_entry")
        self.window.correction_browse_audio_btn = self.window.findChild(QPushButton, "correction_browse_audio_btn")
        self.window.correction_load_files_btn = self.window.findChild(QPushButton, "correction_load_files_btn")
        self.window.correction_assign_speakers_btn = self.window.findChild(QPushButton, "correction_assign_speakers_btn")
        self.window.correction_save_changes_btn = self.window.findChild(QPushButton, "correction_save_changes_btn")
        self.window.correction_play_pause_btn = self.window.findChild(QPushButton, "correction_play_pause_btn")
        self.window.correction_rewind_btn = self.window.findChild(QPushButton, "correction_rewind_btn")
        self.window.correction_forward_btn = self.window.findChild(QPushButton, "correction_forward_btn")
        self.window.correction_timeline_frame = self.window.findChild(QWidget, "correction_timeline_frame")
        self.window.correction_time_label = self.window.findChild(QLabel, "correction_time_label")
        self.window.correction_text_area = self.window.findChild(SelectableTextEdit, "correction_text_area")
        
        self.window.edit_speaker_btn = self.window.findChild(QPushButton, "edit_speaker_btn")
        self.window.correction_text_edit_btn = self.window.findChild(QPushButton, "correction_text_edit_btn")
        self.window.correction_timestamp_edit_btn = self.window.findChild(QPushButton, "correction_timestamp_edit_btn")
        self.window.segment_btn = self.window.findChild(QPushButton, "segment_btn")
        self.window.save_timestamp_btn = self.window.findChild(QPushButton, "save_timestamp_btn")
        self.window.change_highlight_color_btn = self.window.findChild(QPushButton, "change_highlight_color_btn")
        self.window.delete_segment_btn = self.window.findChild(QPushButton, "delete_segment_btn")
        self.window.merge_segments_btn = self.window.findChild(QPushButton, "merge_segments_btn")
        self.window.text_font_combo = self.window.findChild(QComboBox, "text_font")
        self.window.font_size_combo = self.window.findChild(QComboBox, "Police_size")

    def _setup_fonts(self):
        font_id = QFontDatabase.font("Monaco", "Roman", 12)
        if font_id == -1: self.window.monospace_font = QFont("Monospace", 12)
        else: self.window.monospace_font = QFont("Monaco")
        self.window.monospace_font.setStyleHint(QFont.StyleHint.Monospace)

    def _setup_icons(self):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        icon_dir = os.path.join(base_dir, 'assets', 'icons')

        icon_map = {
            self.window.browse_button: "folder-open.png",
            self.window.save_token_button: "disk.png",
            self.window.correction_button: "next.png",
            self.window.correction_browse_transcription_btn: "folder-open.png",
            self.window.correction_browse_audio_btn: "folder-open.png",
            self.window.correction_save_changes_btn: "disk.png",
            self.window.correction_load_files_btn: "sort-down.png",
            self.window.correction_rewind_btn: "rewind.png",
            self.window.correction_forward_btn: "forward.png",
            self.window.correction_assign_speakers_btn: "user-add.png",
            self.window.findChild(QPushButton, "Undo_button"): "undo.png",
            self.window.findChild(QPushButton, "Redo_Button"): "redo.png",
            self.window.findChild(QCheckBox, "show_tips_checkbox"): "interrogation.png",
            self.window.change_highlight_color_btn: "palette.png",
            self.window.edit_speaker_btn: "user-pen.png",
            self.window.correction_text_edit_btn: "pencil.png", 
            self.window.correction_timestamp_edit_btn: "stopwatch.png",
            self.window.segment_btn: "multiple.png",
            self.window.save_timestamp_btn: "disk.png",
            self.window.merge_segments_btn: "merge.png",
            self.window.delete_segment_btn: "trash.png",
        }
        for widget, filename in icon_map.items():
            if widget:
                icon_path = os.path.join(icon_dir, filename)
                if os.path.exists(icon_path):
                    widget.setIcon(QIcon(icon_path))
                else:
                    logger.warning(f"Icon not found: {icon_path}")

        self.window.icon_play = QIcon(os.path.join(icon_dir, "play.png"))
        self.window.icon_abort = QIcon(os.path.join(icon_dir, "stop.png")) 
        self.window.icon_pause = QIcon(os.path.join(icon_dir, "pause.png"))
        self.window.icon_edit_text = QIcon(os.path.join(icon_dir, "pencil.png"))
        self.window.icon_save_edit = QIcon(os.path.join(icon_dir, "sign-out-alt.png"))
        self.window.icon_edit_timestamp = QIcon(os.path.join(icon_dir, "stopwatch.png"))
        self.window.icon_cancel_edit = self.window.icon_save_edit
        
        self.window.start_processing_button.setIcon(self.window.icon_play)
        self.window.correction_play_pause_btn.setIcon(self.window.icon_play)

    def connect_signals(self):
        self.window.browse_button.clicked.connect(self.select_files)
        self.window.start_processing_button.clicked.connect(self.start_or_abort_processing)
        self.window.save_token_button.clicked.connect(self.save_huggingface_token)
        self.window.diarization_checkbutton.stateChanged.connect(self.toggle_advanced_options)
        self.window.correction_button.clicked.connect(self.go_to_correction)

    def toggle_advanced_options(self, state):
        is_checked = (state == 2)
        if self.window.huggingface_token_frame: self.window.huggingface_token_frame.setVisible(is_checked)
        if self.window.auto_merge_checkbutton: self.window.auto_merge_checkbutton.setEnabled(is_checked)
        if not is_checked: self.window.auto_merge_checkbutton.setChecked(False)

    def set_ui_for_processing(self, is_processing):
        self.window.findChild(QGroupBox, "Audio_file_frame").setEnabled(not is_processing)
        self.window.findChild(QGroupBox, "Processing_options_frame").setEnabled(not is_processing)
        self.window.start_processing_button.setEnabled(True) 
        self.window.main_tab_widget.setTabEnabled(1, not is_processing)
        
        if is_processing:
            self.window.start_processing_button.setText("Abort")
            self.window.start_processing_button.setIcon(self.window.icon_abort)
        else:
            self.window.start_processing_button.setText("Start Processing")
            self.window.start_processing_button.setIcon(self.window.icon_play)
        
        self.is_processing = is_processing

    def get_processing_options(self):
        return {"model_key": self.window.model_dropdown.currentText(), "enable_diarization": self.window.diarization_checkbutton.isChecked(), "auto_merge": self.window.auto_merge_checkbutton.isChecked(), "include_timestamps": self.window.timestamps_checkbutton_2.isChecked(), "include_end_times": self.window.end_times_checkbutton.isChecked(), "hf_token": self.window.huggingface_token_entry.text().strip()}

    def load_initial_settings(self):
        self.window.correction_button.setEnabled(False)
        self.window.model_dropdown.addItems(["tiny", "base", "small", "medium", "large (recommended)", "turbo"])
        self.window.model_dropdown.setCurrentText("large (recommended)")
        if self.window.huggingface_token_frame: self.window.huggingface_token_frame.hide()
        token = self.config_manager.load_huggingface_token()
        if token: self.window.huggingface_token_entry.setText(token)
        
        font_sizes = ["8", "9", "10", "11", "12", "14", "16", "18", "24", "36"]
        self.window.font_size_combo.addItems(font_sizes)
        self.window.font_size_combo.setCurrentText("12")

        db = QFontDatabase()
        font_families = db.families()
        self.window.text_font_combo.addItems(font_families)
        
        default_font = "Monaco" if "Monaco" in font_families else "Courier New" if "Courier New" in font_families else "Monospace"
        self.window.text_font_combo.setCurrentText(default_font)

        # --- THE FIX for button size ---
        if self.window.correction_play_pause_btn:
            button = self.window.correction_play_pause_btn
            font_metrics = QFontMetrics(button.font())
            # Calculate width based on the longest text ("Pause") plus padding
            text_width = font_metrics.boundingRect("Pause ").width()
            # Padding for the icon and some breathing room
            padding = 40 
            button.setFixedWidth(text_width + padding)
            
        logger.info("Initial settings loaded.")

    def save_huggingface_token(self):
        token = self.window.huggingface_token_entry.text().strip()
        self.config_manager.save_huggingface_token(token)
        self.config_manager.set_use_auth_token(bool(token))
        QMessageBox.information(self.window, "Token Saved", "Hugging Face token has been saved." if token else "Hugging Face token has been cleared.")

    @Slot()
    def select_files(self):
        if self.is_processing: return
        file_filter = (
            "All Media Files (*.wav *.mp3 *.aac *.flac *.m4a *.mp4 *.mov *.avi *.mkv);;"
            "Audio Files (*.wav *.mp3 *.aac *.flac *.m4a);;"
            "Video Files (*.mp4 *.mov *.avi *.mkv);;"
            "All Files (*)"
        )
        paths, _ = QFileDialog.getOpenFileNames(self.window, "Select Audio or Video Files", "", file_filter)

        if paths:
            self.audio_file_paths = paths
            self.window.audio_file_entry.setText(paths[0] if len(paths) == 1 else f"{len(paths)} files selected")
            self.window.correction_button.setEnabled(False)

    @Slot()
    def start_or_abort_processing(self):
        if self.is_processing and self.process:
            if self.process.is_alive():
                self.process.terminate()
                self.process.join(timeout=1)
            self.timer.stop()
            self.process = None
            self.window.status_label.setText("Processing aborted by user.")
            self.window.progress_bar.setValue(0)
            self.set_ui_for_processing(False)
            return

        if not self.audio_file_paths:
            QMessageBox.critical(self.window, "Error", "Please select one or more audio/video files first.")
            return

        destination_folder = None
        if len(self.audio_file_paths) > 1:
            destination_folder = QFileDialog.getExistingDirectory(self.window, "Select Destination Folder for Transcriptions")
            if not destination_folder:
                self.window.status_label.setText("Batch processing cancelled by user.")
                return

        self.set_ui_for_processing(True)
        self.window.progress_bar.setValue(0)
        self.window.output_text_area.clear()
        
        options = self.get_processing_options()
        cache_dir = os.path.join(os.path.expanduser('~'), 'TranscriptionOli_Cache')
        
        self.queue = multiprocessing.Queue()
        self.process = multiprocessing.Process(
            target=processing_worker_function, 
            args=(self.queue, self.audio_file_paths, options, cache_dir, destination_folder),
            daemon=True
        )
        self.process.start()
        self.timer.start(100)

    def check_queue(self):
        try:
            msg_type, data = self.queue.get_nowait()

            if msg_type == constants.MSG_TYPE_PROGRESS:
                self.window.progress_bar.setValue(data)
            elif msg_type == constants.MSG_TYPE_STATUS:
                self.window.status_label.setText(data)
            elif msg_type == constants.MSG_TYPE_BATCH_FILE_START:
                file_info = data
                status_text = f"Processing file {file_info[constants.KEY_BATCH_CURRENT_IDX]} of {file_info[constants.KEY_BATCH_TOTAL_FILES]}: {file_info[constants.KEY_BATCH_FILENAME]}"
                self.window.status_label.setText(status_text)
                self.window.progress_bar.setValue(0)
            elif msg_type == constants.MSG_TYPE_BATCH_COMPLETED:
                self.timer.stop()
                if self.process:
                    self.process.join()
                    self.process = None
                self.handle_batch_results(data)
        
        except Empty:
            if self.is_processing and (not self.process or not self.process.is_alive()):
                self.timer.stop()
                self.process = None
                self.set_ui_for_processing(False)
                if self.window.status_label.text() != "Processing aborted by user.":
                    QMessageBox.critical(self.window, "Error", "Processing stopped unexpectedly. Check logs for details.")
                    self.window.status_label.setText("Error: Processing stopped unexpectedly.")

    def handle_batch_results(self, final_payload):
        results = final_payload[constants.KEY_BATCH_ALL_RESULTS]
        
        summary = []
        successful_count = 0
        error_count = 0
        
        if len(results) == 1:
             result = results[0]
             self.window.progress_bar.setValue(100)
             if result.status == constants.STATUS_SUCCESS:
                output_text = "\n".join(result.data) if isinstance(result.data, list) else str(result.data)
                self.window.output_text_area.setPlainText(output_text)
                self.prompt_and_save_single_result(result)
             else:
                msg = result.message or "An unknown error occurred."
                self.window.status_label.setText(f"Error: {msg[:100]}...")
                self.window.output_text_area.setPlainText(f"An error occurred:\n{msg}")
                QMessageBox.critical(self.window, "Processing Error", msg)
        
        else: # Batch summary
             for result in results:
                file_name = os.path.basename(result.source_file)
                if result.status == constants.STATUS_SUCCESS:
                    successful_count += 1
                    summary.append(f"SUCCESS: '{file_name}' saved to '{os.path.basename(result.output_path)}'")
                else:
                    error_count += 1
                    summary.append(f"ERROR: '{file_name}' - {result.message}")
            
             self.window.output_text_area.setPlainText("\n".join(summary))
             final_status_msg = f"Batch finished. {successful_count} successful, {error_count} failed."
             self.window.status_label.setText(final_status_msg)
             QMessageBox.information(self.window, "Batch Processing Complete", final_status_msg)

        self.set_ui_for_processing(False)
    
    def prompt_and_save_single_result(self, result):
        if hasattr(result, 'output_path') and result.output_path:
             self.last_single_file_result_path = result.output_path
             self.window.correction_button.setEnabled(True)
             self.window.status_label.setText(f"Transcription saved to {os.path.basename(result.output_path)}")
             return

        base_name, _ = os.path.splitext(os.path.basename(result.source_file))
        model_name = self.get_processing_options()["model_key"].split(" ")[0]
        default_fn = os.path.join(os.getcwd(), f"{base_name}_{model_name}_transcription.txt")

        save_path, _ = QFileDialog.getSaveFileName(self.window, "Save Transcription As", default_fn, "Text Files (*.txt)")
        
        if save_path:
            try:
                AudioProcessor.save_to_txt(save_path, result.data, result.is_plain_text_output)
                self.window.status_label.setText(f"Transcription saved to {os.path.basename(save_path)}")
                QMessageBox.information(self.window, "Success", f"Transcription saved to {save_path}")
                self.last_single_file_result_path = save_path
                self.window.correction_button.setEnabled(True)
            except Exception as e:
                QMessageBox.critical(self.window, "Save Error", f"Could not save file: {e}")
                self.window.correction_button.setEnabled(False)
        else:
            self.window.status_label.setText("Save cancelled by user.")
            self.window.correction_button.setEnabled(False)

    @Slot()
    def go_to_correction(self):
        if not self.last_single_file_result_path or not self.audio_file_paths:
            QMessageBox.warning(self.window, "Error", "Cannot find the necessary file paths to load into the correction window.")
            return
            
        audio_path = self.audio_file_paths[0]
        txt_path = self.last_single_file_result_path
        
        self.correction_logic.load_files_from_paths(audio_path=audio_path, txt_path=txt_path)
        
        self.window.main_tab_widget.setCurrentIndex(1)
        
    def run(self): sys.exit(self.app.exec())

if __name__ == "__main__":
    main_app = MainApplication()
    main_app.run()
# main_pyside.py
import sys
import os
import logging
import multiprocessing
from queue import Empty

from PySide6.QtWidgets import (QApplication, QFileDialog, QMessageBox, QLineEdit, QPushButton, 
                               QComboBox, QFrame, QCheckBox, QProgressBar, QLabel, QTextEdit, 
                               QWidget, QTabWidget, QGroupBox)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon, QFontMetrics, QFont, QFontDatabase
from PySide6.QtUiTools import QUiLoader

from utils.logging_setup import setup_logging
from utils import constants
from utils.config_manager import ConfigManager
from ui.correction_view_logic import CorrectionViewLogic
from core.app_worker import processing_worker_function
from core.audio_processor import AudioProcessor
# --- NEW: Import our custom widget class ---
from ui.selectable_text_edit import SelectableTextEdit


multiprocessing.set_start_method('spawn', force=True)

setup_logging()
logger = logging.getLogger(__name__)

class MainApplication:
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # --- FIX: Register the custom widget before loading the UI ---
        loader = QUiLoader()
        loader.registerCustomWidget(SelectableTextEdit)

        ui_file_path = os.path.join(os.path.dirname(__file__), "ui", "main_window.ui")
        self.window = loader.load(ui_file_path, None)
        # ----------------------------------------------------------------
        
        if not self.window:
            print(f"CRITICAL: Failed to load UI file: {ui_file_path}", file=sys.stderr)
            sys.exit(1)
        
        self.config_manager = ConfigManager(constants.DEFAULT_CONFIG_FILE)
        
        self._promote_widgets()
        self._setup_fonts()
        self._setup_icons()
        
        # This will now work correctly because the widget is a true SelectableTextEdit
        self.correction_logic = CorrectionViewLogic(self.window)

        self.audio_file_paths = []
        self.process = None
        self.queue = None
        self.last_result = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_queue)
        
        self.connect_signals()
        self.load_initial_settings()
        
        self.window.show()

    def _promote_widgets(self):
        # NOTE: When finding the promoted widget, we look for its base class (QTextEdit)
        # but the object that is returned will be the correct SelectableTextEdit type.
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
        # IMPORTANT: findChild looks for the original base class from the .ui file
        self.window.correction_text_area = self.window.findChild(QTextEdit, "correction_text_area")
        
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

    # ... All other methods from _setup_fonts onwards are unchanged.
    def _setup_fonts(self):
        font_id = QFontDatabase.font("Monaco", "Roman", 12)
        if font_id == -1: self.window.monospace_font = QFont("Monospace", 12)
        else: self.window.monospace_font = QFont("Monaco")
        self.window.monospace_font.setStyleHint(QFont.StyleHint.Monospace)

    def _setup_icons(self):
        """Manually loads icons from a local folder, ignoring system themes."""
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(__file__)
        
        icon_dir = os.path.join(base_dir, 'assets', 'icons')

        icon_map = {
            self.window.browse_button: "folder-open.png",
            self.window.save_token_button: "disk.png",
            self.window.start_processing_button: "play.png",
            self.window.correction_button: "next.png",
            self.window.correction_browse_transcription_btn: "folder-open.png",
            self.window.correction_browse_audio_btn: "folder-open.png",
            self.window.correction_save_changes_btn: "disk.png",
            self.window.correction_load_files_btn: "sort-down.png",
            self.window.correction_play_pause_btn: "play.png",
            self.window.correction_rewind_btn: "rewind.png",
            self.window.correction_forward_btn: "forward.png",
            self.window.correction_assign_speakers_btn: "user-add.png",
            self.window.findChild(QPushButton, "Undo_button"): "undo.png",
            self.window.findChild(QPushButton, "Redo_Button"): "redo.png",
            self.window.findChild(QCheckBox, "show_tips_checkbox"): "interrogation.png",
            self.window.change_highlight_color_btn: "palette.png",
            self.window.edit_speaker_btn: "user-pen.png",
            self.window.correction_text_edit_btn: "pencil.png", 
            # --- MODIFIED: The default timestamp icon ---
            self.window.correction_timestamp_edit_btn: "stopwatch.png", # Changed from 'pending.png' for clarity
            self.window.segment_btn: "multiple.png",
            self.window.save_timestamp_btn: "disk.png",
            self.window.merge_segments_btn: "merge.png",
            self.window.delete_segment_btn: "trash.png",
        }
        # ... (icon setting loop is the same)
        for widget, filename in icon_map.items():
            if widget:
                icon_path = os.path.join(icon_dir, filename)
                if os.path.exists(icon_path):
                    widget.setIcon(QIcon(icon_path))
                else:
                    print(f"Icon not found: {icon_path}")
        
        # Pre-load icons for state changes
        play_icon_path = os.path.join(icon_dir, "play.png")
        pause_icon_path = os.path.join(icon_dir, "pause.png")
        self.window.icon_play = QIcon(play_icon_path) if os.path.exists(play_icon_path) else QIcon()
        self.window.icon_pause = QIcon(pause_icon_path) if os.path.exists(pause_icon_path) else QIcon()
        
        edit_icon_path = os.path.join(icon_dir, "pencil.png")
        save_edit_icon_path = os.path.join(icon_dir, "sign-out-alt.png")
        self.window.icon_edit_text = QIcon(edit_icon_path) if os.path.exists(edit_icon_path) else QIcon()
        self.window.icon_save_edit = QIcon(save_edit_icon_path) if os.path.exists(save_edit_icon_path) else QIcon()

        # --- NEW: Pre-load the timestamp editing icon ---
        edit_ts_icon_path = os.path.join(icon_dir, "stopwatch.png")
        self.window.icon_edit_timestamp = QIcon(edit_ts_icon_path) if os.path.exists(edit_ts_icon_path) else QIcon()
        # The cancel icon will be the same as the save/exit text edit icon
        self.window.icon_cancel_edit = self.window.icon_save_edit 
    
    def connect_signals(self):
        self.window.browse_button.clicked.connect(self.select_audio_files)
        self.window.start_processing_button.clicked.connect(self.start_processing)
        self.window.save_token_button.clicked.connect(self.save_huggingface_token)
        self.window.diarization_checkbutton.stateChanged.connect(self.toggle_advanced_options)

    def toggle_advanced_options(self, state):
        is_checked = (state == 2)
        if self.window.huggingface_token_frame: self.window.huggingface_token_frame.setVisible(is_checked)
        if self.window.auto_merge_checkbutton: self.window.auto_merge_checkbutton.setEnabled(is_checked)
        if not is_checked: self.window.auto_merge_checkbutton.setChecked(False)
    
    def set_ui_for_processing(self, is_processing):
        self.window.findChild(QGroupBox, "Audio_file_frame").setEnabled(not is_processing)
        self.window.findChild(QGroupBox, "Processing_options_frame").setEnabled(not is_processing)
        self.window.start_processing_button.setEnabled(not is_processing)
        self.window.main_tab_widget.setTabEnabled(1, not is_processing)
        self.window.start_processing_button.setText("Processing..." if is_processing else "Start Processing")

    def get_processing_options(self):
        return {"model_key": self.window.model_dropdown.currentText(), "enable_diarization": self.window.diarization_checkbutton.isChecked(),
                "auto_merge": self.window.auto_merge_checkbutton.isChecked(), "include_timestamps": self.window.timestamps_checkbutton_2.isChecked(),
                "include_end_times": self.window.end_times_checkbutton.isChecked(), "hf_token": self.window.huggingface_token_entry.text().strip()}

    def load_initial_settings(self):
        if self.window.save_timestamp_btn:
            self.window.save_timestamp_btn.setVisible(False)
        self.window.model_dropdown.addItems(["tiny", "base", "small", "medium", "large (recommended)", "turbo"])
        self.window.model_dropdown.setCurrentText("large (recommended)")
        if self.window.huggingface_token_frame: self.window.huggingface_token_frame.hide()
        token = self.config_manager.load_huggingface_token()
        if token: self.window.huggingface_token_entry.setText(token)
        if self.window.correction_play_pause_btn:
            button = self.window.correction_play_pause_btn
            font_metrics = QFontMetrics(button.font()); text_width = font_metrics.boundingRect("Resume ").width()
            padding = 40; button.setFixedWidth(text_width + padding)
        logger.info("Initial settings loaded.")

    def save_huggingface_token(self):
        token = self.window.huggingface_token_entry.text().strip()
        self.config_manager.save_huggingface_token(token)
        self.config_manager.set_use_auth_token(bool(token))
        QMessageBox.information(self.window, "Token Saved", "Hugging Face token has been saved." if token else "Hugging Face token has been cleared.")

    def select_audio_files(self):
        if self.process and self.process.is_alive(): return
        paths, _ = QFileDialog.getOpenFileNames(self.window, "Select Audio Files", "", "Audio Files (*.wav *.mp3 *.aac *.flac *.m4a);;All files (*.*)")
        if paths:
            self.audio_file_paths = paths
            self.window.audio_file_entry.setText(paths[0] if len(paths) == 1 else f"{len(paths)} files selected")

    def start_processing(self):
        if not self.audio_file_paths: QMessageBox.critical(self.window, "Error", "Please select an audio file first."); return
        if self.process and self.process.is_alive(): QMessageBox.warning(self.window, "Busy", "Processing is already in progress."); return
        self.set_ui_for_processing(True); self.window.progress_bar.setValue(0)
        options = self.get_processing_options()
        cache_dir = os.path.join(os.path.expanduser('~'), 'TranscriptionOli_Cache')
        self.queue = multiprocessing.Queue()
        self.process = multiprocessing.Process(target=processing_worker_function, args=(self.queue, self.audio_file_paths, options, cache_dir))
        self.process.start(); self.timer.start(100)

    def check_queue(self):
        try:
            msg_type, data = self.queue.get_nowait()
            if msg_type == 'progress': self.window.progress_bar.setValue(data)
            elif msg_type == 'status': self.window.status_label.setText(data)
            elif msg_type == 'finished':
                self.last_result = data; self.timer.stop(); self.process.join(); self.process = None; self.handle_results()
        except Empty:
            if self.process and not self.process.is_alive():
                self.timer.stop(); QMessageBox.critical(self.window, "Error", "Processing stopped unexpectedly."); self.set_ui_for_processing(False)

    def handle_results(self):
        if not self.last_result: return
        result = self.last_result; self.window.progress_bar.setValue(100)
        if result.status == constants.STATUS_SUCCESS:
            output_text = "\n".join(result.data) if isinstance(result.data, list) else str(result.data)
            self.window.output_text_area.setPlainText(output_text)
            self.prompt_and_save_results(result)
        else:
            msg = result.message or "An unknown error occurred."
            self.window.status_label.setText(f"Error: {msg[:100]}..."); self.window.output_text_area.setPlainText(f"An error occurred:\n{msg}")
            QMessageBox.critical(self.window, "Processing Error", msg)
        self.set_ui_for_processing(False)

    def prompt_and_save_results(self, result):
        name, _ = os.path.splitext(os.path.basename(self.audio_file_paths[0])); model_name = self.get_processing_options()["model_key"].split(" ")[0]
        default_fn = f"{name}_{model_name}_transcription.txt"
        save_path, _ = QFileDialog.getSaveFileName(self.window, "Save Transcription As", default_fn, "Text Files (*.txt)")
        if save_path:
            try:
                AudioProcessor.save_to_txt(save_path, result.data, result.is_plain_text_output)
                self.window.status_label.setText("Transcription saved!"); QMessageBox.information(self.window, "Success", f"Transcription saved to {save_path}")
            except Exception as e: QMessageBox.critical(self.window, "Save Error", f"Could not save file: {e}")
        else: self.window.status_label.setText("Save cancelled by user.")
    
    def run(self): sys.exit(self.app.exec())

if __name__ == "__main__":
    main_app = MainApplication()
    main_app.run()
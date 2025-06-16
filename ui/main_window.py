# ui/main_window.py (Final Fixes)

import logging
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox,
                               QProgressBar, QCheckBox, QGroupBox, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils.tips_data import get_tip

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """
    The main application window, rewritten in PySide6.
    It provides the primary interface for selecting files, setting options,
    and viewing transcription results.
    """
    def __init__(self, start_processing_callback, select_audio_file_callback,
                 open_correction_window_callback, config_manager_instance, 
                 initial_show_tips_state):
        super().__init__()

        # --- Store callbacks and config ---
        self.start_processing_callback = start_processing_callback
        self.select_audio_file_callback = select_audio_file_callback
        self.open_correction_window_callback = open_correction_window_callback
        self.config_manager = config_manager_instance
        self.save_token_callback = None

        # --- UI State ---
        self.initial_show_tips_state = initial_show_tips_state
        self._widget_tooltips = {}
        
        # --- Build the UI ---
        self._setup_ui()
        self._connect_signals()
        
        # --- Final Setup ---
        self.setWindowTitle("Audio Transcription and Diarization")
        self.setGeometry(100, 100, 800, 750)
        
        # Apply initial state
        self.show_tips_checkbox.setChecked(self.initial_show_tips_state)
        # FIX: Explicitly call the handler to ensure initial state is applied
        self._on_toggle_tips(self.initial_show_tips_state)

        logger.info("PySide6 MainWindow initialized.")
        
    def _setup_ui(self):
        """Creates and arranges all widgets in the window."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        header_layout = QHBoxLayout()
        self.show_tips_checkbox = QCheckBox("Show Tips")
        header_layout.addStretch()
        header_layout.addWidget(self.show_tips_checkbox)
        self._register_tooltip(self.show_tips_checkbox, "show_tips_checkbox_main")

        file_group = QGroupBox("Audio File(s)")
        file_layout = QHBoxLayout(file_group)
        self.audio_file_entry = QLineEdit()
        self.audio_file_entry.setReadOnly(True)
        self.browse_button = QPushButton("Browse...")
        file_layout.addWidget(QLabel("File Path(s):"))
        file_layout.addWidget(self.audio_file_entry)
        file_layout.addWidget(self.browse_button)
        self._register_tooltip(self.browse_button, "audio_file_browse")

        options_group = QGroupBox("Processing Options")
        options_layout = QVBoxLayout(options_group)

        model_layout = QHBoxLayout()
        self.model_label = QLabel("Transcription Model:")
        self.model_combo = QComboBox()
        self.model_options = {
            "tiny": get_tip("main_window", "model_option_tiny") or "Tiny model",
            "base": get_tip("main_window", "model_option_base") or "Base model",
            "small": get_tip("main_window", "model_option_small") or "Small model",
            "medium": get_tip("main_window", "model_option_medium") or "Medium model",
            "large (recommended)": get_tip("main_window", "model_option_large") or "Large model",
            "turbo": get_tip("main_window", "model_option_turbo") or "Turbo model (uses 'small')"
        }
        self.model_combo.addItems(self.model_options.keys())
        self.model_combo.setCurrentText("large (recommended)")
        self.model_description_label = QLabel()
        self.model_description_label.setWordWrap(True)
        self.model_description_label.setStyleSheet("color: grey;")
        model_layout.addWidget(self.model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addWidget(self.model_description_label, 1)
        self._register_tooltip(self.model_combo, "transcription_model_dropdown", 300)

        checkbox_layout = QHBoxLayout()
        self.diarization_checkbox = QCheckBox("Enable Speaker Diarization")
        self.timestamps_checkbox = QCheckBox("Include Timestamps")
        self.timestamps_checkbox.setChecked(True)
        self.end_times_checkbox = QCheckBox("Include End Times")
        self.auto_merge_checkbox = QCheckBox("Auto-Merge Same Speakers")
        checkbox_layout.addWidget(self.diarization_checkbox)
        checkbox_layout.addWidget(self.timestamps_checkbox)
        checkbox_layout.addWidget(self.end_times_checkbox)
        checkbox_layout.addWidget(self.auto_merge_checkbox)
        checkbox_layout.addStretch()
        self._register_tooltip(self.diarization_checkbox, "enable_diarization_checkbox")
        self._register_tooltip(self.timestamps_checkbox, "include_timestamps_checkbox")
        self._register_tooltip(self.end_times_checkbox, "include_end_times_checkbox")
        self._register_tooltip(self.auto_merge_checkbox, "auto_merge_checkbox")
        
        self.token_group = QGroupBox("Hugging Face API Token (Required for Diarization)")
        token_layout = QHBoxLayout(self.token_group)
        self.token_entry = QLineEdit()
        self.token_entry.setEchoMode(QLineEdit.Password)
        self.save_token_button = QPushButton("Save Token")
        token_layout.addWidget(QLabel("Token:"))
        token_layout.addWidget(self.token_entry)
        token_layout.addWidget(self.save_token_button)
        self.token_group.setVisible(False)
        self._register_tooltip(self.token_entry, "huggingface_token_entry", 350)
        self._register_tooltip(self.save_token_button, "save_huggingface_token_button")

        options_layout.addLayout(model_layout)
        options_layout.addLayout(checkbox_layout)
        options_layout.addWidget(self.token_group)

        self.process_button = QPushButton("Start Processing")
        font = self.process_button.font(); font.setPointSize(14); self.process_button.setFont(font)
        self._register_tooltip(self.process_button, "start_processing_button")

        status_layout = QVBoxLayout()
        self.status_label = QLabel("Status: Idle")
        self.progress_bar = QProgressBar()
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        self._register_tooltip(self.status_label, "status_label")
        self._register_tooltip(self.progress_bar, "progress_bar")

        output_group = QGroupBox("Processed Output (Last File / Summary)")
        output_layout = QVBoxLayout(output_group)
        self.output_text_area = QTextEdit()
        self.output_text_area.setReadOnly(True)
        output_layout.addWidget(self.output_text_area)
        self._register_tooltip(self.output_text_area, "output_text_area")

        self.correction_button = QPushButton("Transcript Correction (Last Successful)")
        self._register_tooltip(self.correction_button, "correction_window_button")

        main_layout.addLayout(header_layout)
        main_layout.addWidget(file_group)
        main_layout.addWidget(options_group)
        main_layout.addWidget(self.process_button)
        main_layout.addLayout(status_layout)
        main_layout.addWidget(output_group, 1)
        main_layout.addWidget(self.correction_button)

    def _connect_signals(self):
        self.browse_button.clicked.connect(self.select_audio_file_callback)
        self.process_button.clicked.connect(self.start_processing_callback)
        self.correction_button.clicked.connect(self.open_correction_window_callback)
        self.save_token_button.clicked.connect(self.save_token_ui)
        
        self.show_tips_checkbox.stateChanged.connect(self._on_toggle_tips)
        self.model_combo.currentTextChanged.connect(self._show_model_description_label)
        self.diarization_checkbox.stateChanged.connect(self._update_diarization_dependent_options)
        self.timestamps_checkbox.stateChanged.connect(self._toggle_end_time_option)
        
        self._toggle_end_time_option()
        self._update_diarization_dependent_options()
        self._show_model_description_label(self.model_combo.currentText())

    def disable_ui_for_processing(self):
        self._set_ui_enabled(False)

    def enable_ui_after_processing(self):
        self._set_ui_enabled(True)
        
    def update_status_and_progress(self, status_text=None, progress_value=None):
        if status_text is not None: self.status_label.setText(f"Status: {status_text}")
        if progress_value is not None: self.progress_bar.setValue(progress_value)
    
    def update_audio_file_entry_display(self, file_paths: list):
        if not file_paths: display_text = ""
        elif len(file_paths) == 1: display_text = file_paths[0]
        else: display_text = f"{len(file_paths)} files selected"
        self.audio_file_entry.setText(display_text)
        
    def update_output_text(self, text_content: str):
        self.output_text_area.setPlainText(text_content)
        
    def set_save_token_callback(self, callback):
        self.save_token_callback = callback
        
    def save_token_ui(self):
        if self.save_token_callback: self.save_token_callback(self.token_entry.text())
            
    def load_token_ui(self, token: str):
        self.token_entry.setText(token or "")
    
    def _set_ui_enabled(self, enabled: bool):
        """Helper to enable/disable all relevant controls."""
        self.browse_button.setEnabled(enabled)
        self.process_button.setEnabled(enabled)
        self.correction_button.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.save_token_button.setEnabled(enabled)
        
        # FIX: Include all checkboxes in the disable/enable logic
        self.diarization_checkbox.setEnabled(enabled)
        self.timestamps_checkbox.setEnabled(enabled)
        self.end_times_checkbox.setEnabled(enabled)
        self.auto_merge_checkbox.setEnabled(enabled)

        if enabled:
            self._toggle_end_time_option()
            self._update_diarization_dependent_options()

    def _register_tooltip(self, widget, tip_key, wraplength=250):
        tip_text = get_tip("main_window", tip_key)
        if tip_text: self._widget_tooltips[widget] = tip_text

    def _on_toggle_tips(self, state):
        is_checked = state == Qt.Checked if isinstance(state, int) else bool(state)
        self.config_manager.set_main_window_show_tips(is_checked)
        for widget, tip_text in self._widget_tooltips.items():
            widget.setToolTip(tip_text if is_checked else "")
        self._show_model_description_label(self.model_combo.currentText())

    def _show_model_description_label(self, text):
        if self.show_tips_checkbox.isChecked():
            description = self.model_options.get(text, "")
            self.model_description_label.setText(description)
        else:
            self.model_description_label.setText("")

    def _update_diarization_dependent_options(self):
        diarization_enabled = self.diarization_checkbox.isChecked()
        self.token_group.setVisible(diarization_enabled)
        self.auto_merge_checkbox.setEnabled(diarization_enabled)
        if not diarization_enabled:
            self.auto_merge_checkbox.setChecked(False)

    def _toggle_end_time_option(self):
        timestamps_enabled = self.timestamps_checkbox.isChecked()
        self.end_times_checkbox.setEnabled(timestamps_enabled)
        if not timestamps_enabled:
            self.end_times_checkbox.setChecked(False)

    def display_processed_output(self, output_file_path: str = None, 
                                 processing_returned_empty: bool = False, 
                                 is_batch_summary: bool = False, 
                                 batch_summary_message: str = ""):
        logger.info(f"UI: Displaying results. Path: '{output_file_path}', Empty: {processing_returned_empty}, BatchSummary: {is_batch_summary}")
        if is_batch_summary:
            self.update_output_text(batch_summary_message)
            return
        if processing_returned_empty:
            self.update_output_text("No speech was detected or transcribed from the audio file.")
            return
        if not output_file_path:
            return
        try:
            with open(output_file_path, 'r', encoding='utf-8') as f:
                self.update_output_text(f.read())
        except Exception as e:
            logger.exception(f"UI: Error reading output file '{output_file_path}'")
            self.update_output_text(f"Error: Could not read result file.\n{e}")
# ui/correction_window.py (PySide6 Version)

import logging
import os
import queue
import math

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLineEdit, QLabel, QTextEdit, QFileDialog, QMessageBox, 
                               QInputDialog, QCheckBox, QDialog, QMenu, QGridLayout)
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QTextCursor

# --- Local Imports ---
try:
    from utils import constants
    from core.correction_window_logic import SegmentManager
    from .audio_player import AudioPlayer
    from .custom_widgets import AudioTimeline # Our new custom widget
except ImportError:
    # Fallback for different execution contexts
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from utils import constants
    from core.correction_window_logic import SegmentManager
    from ui.audio_player import AudioPlayer
    from ui.custom_widgets import AudioTimeline

logger = logging.getLogger(__name__)

class CorrectionWindow(QMainWindow):
    """
    Main window for the Transcription Correction Tool, rewritten in PySide6.
    This class manages the UI, state, and interactions for correcting transcriptions.
    """
    def __init__(self, parent_root,
                 config_manager_instance,
                 initial_show_tips_state,
                 initial_include_timestamps=True,
                 initial_include_end_times=False):
        super().__init__(parent_root)
        
        self.config_manager = config_manager_instance
        self.output_include_timestamps = initial_include_timestamps
        self.output_include_end_times = initial_include_end_times

        # --- Core Logic and Data ---
        self.segment_manager = SegmentManager(parent_window_for_dialogs=self)
        self.audio_player = None
        self.audio_player_update_queue = None

        # --- UI State ---
        self.text_edit_mode_active = False # This state is now managed via dialogs
        self.is_timestamp_editing_active = False
        self.segment_id_for_timestamp_edit = None
        self.start_timestamp_bar_value_seconds = 0.0
        self.end_timestamp_bar_value_seconds = 0.0
        self.is_end_time_bar_active = False
        self.was_playing_before_drag = False
        self.currently_highlighted_text_seg_id = None
        self.right_clicked_segment_id = None

        # --- Initialize UI ---
        self._setup_ui()
        self._connect_signals()
        
        # --- Timers and Final Setup ---
        # A QTimer is the Qt equivalent of tkinter's .after() for polling
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll_audio_player_queue)
        self.poll_timer.start(50) # Poll every 50ms

        self.setWindowTitle("Transcription Correction Tool")
        self.setGeometry(200, 200, 900, 700)
        
        self._disable_all_controls() # Disable controls until files are loaded
        logger.info("PySide6 CorrectionWindow fully initialized.")

    def _setup_ui(self):
        """Create and arrange all the widgets in the window."""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # --- Top Controls (File selection, etc.) ---
        top_controls_layout = QHBoxLayout()
        self.browse_transcription_button = QPushButton("Browse Transcription...")
        self.transcription_path_edit = QLineEdit()
        self.transcription_path_edit.setReadOnly(True)
        self.browse_audio_button = QPushButton("Browse Audio...")
        self.audio_path_edit = QLineEdit()
        self.audio_path_edit.setReadOnly(True)
        self.load_files_button = QPushButton("Load Files")
        
        top_controls_layout.addWidget(self.browse_transcription_button)
        top_controls_layout.addWidget(self.transcription_path_edit)
        top_controls_layout.addWidget(self.browse_audio_button)
        top_controls_layout.addWidget(self.audio_path_edit)
        top_controls_layout.addWidget(self.load_files_button)
        
        # --- Main Action Buttons ---
        action_buttons_layout = QHBoxLayout()
        self.assign_speakers_button = QPushButton("Assign/Edit Speakers...")
        self.save_changes_button = QPushButton("Save Changes...")
        action_buttons_layout.addStretch()
        action_buttons_layout.addWidget(self.assign_speakers_button)
        action_buttons_layout.addWidget(self.save_changes_button)
        action_buttons_layout.addStretch()

        # --- Audio Playback Controls ---
        playback_layout = QHBoxLayout()
        self.play_pause_button = QPushButton("Play")
        self.rewind_button = QPushButton("<< 5s")
        self.forward_button = QPushButton("5s >>")
        self.jump_to_segment_button = QPushButton("Jump to Segment Start")
        self.jump_to_segment_button.setVisible(False) # Hide until needed
        self.current_time_label = QLabel("00:00.000 / 00:00.000")
        
        playback_layout.addStretch()
        playback_layout.addWidget(self.rewind_button)
        playback_layout.addWidget(self.play_pause_button)
        playback_layout.addWidget(self.forward_button)
        playback_layout.addWidget(self.jump_to_segment_button)
        playback_layout.addWidget(self.current_time_label)
        playback_layout.addStretch()
        
        # --- Audio Timeline ---
        self.audio_timeline = AudioTimeline()

        # --- Timestamp Editing Controls (Initially Hidden) ---
        self.ts_edit_widget = QWidget()
        ts_edit_layout = QHBoxLayout(self.ts_edit_widget)
        self.ts_start_label = QLabel("Start: 00:00.000")
        self.ts_end_label = QLabel("End: 00:00.000")
        self.ts_toggle_end_time_checkbox = QCheckBox("Enable End Time")
        self.ts_save_button = QPushButton("Save Timestamps")
        self.ts_cancel_button = QPushButton("Cancel")
        ts_edit_layout.addStretch()
        ts_edit_layout.addWidget(self.ts_start_label)
        ts_edit_layout.addWidget(self.ts_end_label)
        ts_edit_layout.addWidget(self.ts_toggle_end_time_checkbox)
        ts_edit_layout.addWidget(self.ts_save_button)
        ts_edit_layout.addWidget(self.ts_cancel_button)
        ts_edit_layout.addStretch()
        self.ts_edit_widget.setVisible(False)

        # --- Transcription Text Area ---
        self.transcription_text = QTextEdit()
        self.transcription_text.setReadOnly(True)
        self.transcription_text.setFont(QFont("Helvetica", 12))
        self.transcription_text.setContextMenuPolicy(Qt.CustomContextMenu)

        # --- Add all layouts and widgets to the main layout ---
        main_layout.addLayout(top_controls_layout)
        main_layout.addLayout(action_buttons_layout)
        main_layout.addLayout(playback_layout)
        main_layout.addWidget(self.audio_timeline)
        main_layout.addWidget(self.ts_edit_widget)
        main_layout.addWidget(self.transcription_text)

    def _connect_signals(self):
        """Connect widget signals to corresponding handler slots."""
        # File controls
        self.browse_transcription_button.clicked.connect(self._browse_transcription_file)
        self.browse_audio_button.clicked.connect(self._browse_audio_file)
        self.load_files_button.clicked.connect(self._load_files)
        
        # Action controls
        self.save_changes_button.clicked.connect(self._save_changes)
        self.assign_speakers_button.clicked.connect(self._open_assign_speakers_dialog)

        # Playback controls
        self.play_pause_button.clicked.connect(self._toggle_play_pause)
        self.rewind_button.clicked.connect(lambda: self._handle_seek_button_click(-5.0))
        self.forward_button.clicked.connect(lambda: self._handle_seek_button_click(5.0))
        self.jump_to_segment_button.clicked.connect(self._jump_to_segment_start_action)

        # Timeline signals
        self.audio_timeline.seek_requested.connect(self._seek_from_timeline)
        self.audio_timeline.playback_head_dragged.connect(self._drag_playback_head)
        self.audio_timeline.start_bar_dragged.connect(self._drag_start_bar)
        self.audio_timeline.end_bar_dragged.connect(self._drag_end_bar)
        self.audio_timeline.drag_finished.connect(self._on_drag_finished)
        
        # Timestamp editor signals
        self.ts_toggle_end_time_checkbox.stateChanged.connect(self._handle_toggle_end_time_click)
        self.ts_save_button.clicked.connect(self._handle_save_times_click)
        self.ts_cancel_button.clicked.connect(self._handle_cancel_timestamp_edit_click)

        # Text area interactions
        self.transcription_text.mouseDoubleClickEvent = self._handle_text_area_double_click
        self.transcription_text.customContextMenuRequested.connect(self._show_context_menu)
        
        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_changes)
        QShortcut(QKeySequence(Qt.Key_Escape), self, self._handle_escape_key)

    # --- Major Logic Methods (rewritten for Qt) ---

    def _render_segments_to_text_area(self):
        """Renders all segments from SegmentManager into the QTextEdit using HTML."""
        if self.is_timestamp_editing_active:
            self._exit_timestamp_edit_mode(save_changes=False)
            
        self.currently_highlighted_text_seg_id = None
        html_lines = []
        
        # Define some CSS styles for our HTML
        styles = """
        <style>
            p { margin: 2px; }
            .timestamp { color: #007BFF; font-weight: bold; }
            .speaker { color: #28a745; font-weight: bold; }
            .placeholder { color: #6c757d; font-style: italic; }
            .highlight { background-color: #FFF3CD; }
        </style>
        """
        html_lines.append(styles)

        if not self.segment_manager.segments:
            html_lines.append("<p><i>No transcription data loaded.</i></p>")
        
        for idx, seg in enumerate(self.segment_manager.segments):
            line_parts = []
            
            # Add a data attribute to the paragraph for easy identification
            highlight_class = "highlight" if seg['id'] == self.currently_highlighted_text_seg_id else ""
            line_parts.append(f'<p id="{seg["id"]}" class="{highlight_class}">')

            # Timestamp
            if seg.get("has_timestamps"):
                start_str = self.segment_manager.seconds_to_time_str(seg['start_time'])
                ts_str = f"[{start_str}]"
                if seg.get("has_explicit_end_time") and seg['end_time'] is not None:
                    end_str = self.segment_manager.seconds_to_time_str(seg['end_time'])
                    ts_str = f"[{start_str} - {end_str}]"
                line_parts.append(f'<span class="timestamp">{ts_str}</span> ')

            # Speaker
            if seg['speaker_raw'] != constants.NO_SPEAKER_LABEL:
                display_speaker = self.segment_manager.speaker_map.get(seg['speaker_raw'], seg['speaker_raw'])
                line_parts.append(f'<span class="speaker">{display_speaker}:</span> ')
                
            # Text content
            text_to_display = seg['text']
            if not text_to_display:
                line_parts.append(f'<span class="placeholder">{constants.EMPTY_SEGMENT_PLACEHOLDER}</span>')
            else:
                # Escape HTML special characters in user text to prevent formatting issues
                escaped_text = text_to_display.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                line_parts.append(escaped_text)
            
            line_parts.append('</p>')
            html_lines.append("".join(line_parts))

        self.transcription_text.setHtml("\n".join(html_lines))

    def _load_files(self):
        """Core logic to load and process transcription and audio files."""
        transcription_path = self.transcription_path_edit.text()
        audio_path = self.audio_path_edit.text()
        
        if not transcription_path or not audio_path:
            QMessageBox.warning(self, "Missing Files", "Please select both a transcription and an audio file.")
            return

        logger.info(f"Core load: TXT='{transcription_path}', AUDIO='{audio_path}'")
        self._exit_timestamp_edit_mode(save_changes=False)
        
        try:
            # Cleanup old resources
            if self.audio_player:
                self.audio_player.stop_resources()
                self.audio_player = None
            if self.audio_player_update_queue:
                while not self.audio_player_update_queue.empty():
                    self.audio_player_update_queue.get_nowait()
                self.audio_player_update_queue = None

            # Load and parse transcription
            with open(transcription_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            if not self.segment_manager.parse_transcription_lines(lines):
                self._disable_all_controls()
                return

            self._render_segments_to_text_area()
            
            # Initialize audio player
            self.audio_player = AudioPlayer(audio_path, on_error_callback=self._handle_audio_player_error)
            if not self.audio_player.is_ready():
                self._disable_all_controls()
                return
            
            self.audio_player_update_queue = self.audio_player.get_update_queue()
            self.audio_timeline.set_audio_duration(self.audio_player.get_duration_seconds())
            self._update_time_labels_display()
            self._enable_all_controls()
            self.load_files_button.setText("Reload Files")
            logger.info("Files loaded successfully, controls enabled.")

        except Exception as e:
            logger.exception("Error during file loading.")
            QMessageBox.critical(self, "Load Error", f"An unexpected error occurred: {e}")
            self._disable_all_controls()

    def _save_changes(self):
        """Handles saving the corrected transcription to a file."""
        self._exit_timestamp_edit_mode(save_changes=True) # Save any pending TS edit
        
        formatted_lines = self.segment_manager.format_segments_for_saving(
            self.output_include_timestamps, self.output_include_end_times
        )
        if not formatted_lines:
            QMessageBox.warning(self, "Nothing to Save", "No valid segments found to save.")
            return
            
        content_to_save = "\n".join(formatted_lines) + "\n"
        
        initial_filename = "corrected_transcription.txt"
        if self.transcription_path_edit.text():
            try:
                base, ext = os.path.splitext(os.path.basename(self.transcription_path_edit.text()))
                initial_filename = f"{base}_corrected{ext or '.txt'}"
            except Exception: pass
            
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Corrected Transcription", initial_filename, "Text Files (*.txt);;All Files (*)"
        )
        
        if not save_path:
            logger.info("Save operation cancelled.")
            return
            
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(content_to_save)
            QMessageBox.information(self, "Saved Successfully", f"Corrected transcription saved to:\n{save_path}")
            logger.info(f"Changes saved to {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save file: {e}")
            logger.exception(f"Error saving changes to {save_path}")

    # --- Slot Implementations (Event Handlers) ---

    def _browse_transcription_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Transcription File", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.transcription_path_edit.setText(path)

    def _browse_audio_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.wav *.mp3 *.flac *.m4a);;All Files (*)")
        if path:
            self.audio_path_edit.setText(path)
            
    def _toggle_play_pause(self):
        if not self.audio_player or not self.audio_player.is_ready(): return
        if self.audio_player.playing:
            self.audio_player.pause()
        else:
            self.audio_player.play()
            
    def _handle_seek_button_click(self, base_delta_seconds: float):
        if not self.audio_player or not self.audio_player.is_ready(): return
        # In timestamp edit mode, seek by a smaller amount
        delta = 1.0 if self.is_timestamp_editing_active else 5.0
        actual_delta = delta * math.copysign(1, base_delta_seconds)
        self.audio_player.seek_by(actual_delta)
            
    def _seek_from_timeline(self, position_seconds: float):
        if self.audio_player and self.audio_player.is_ready():
            self.audio_player.set_pos_seconds(position_seconds)
            
    # --- Other UI Logic and Helpers ---

    def _update_time_labels_display(self):
        if not self.audio_player or not self.audio_player.is_ready():
            self.current_time_label.setText("--:--.--- / --:--.---")
            return
        current_s = self.audio_player.get_current_seconds()
        total_s = self.audio_player.get_duration_seconds()
        current_str = self.segment_manager.seconds_to_time_str(current_s)
        total_str = self.segment_manager.seconds_to_time_str(total_s)
        self.current_time_label.setText(f"{current_str} / {total_str}")
    
    def _poll_audio_player_queue(self):
        if self.audio_player_update_queue:
            try:
                while not self.audio_player_update_queue.empty():
                    msg_type, msg_data = self.audio_player_update_queue.get_nowait()
                    if msg_type in ['started', 'resumed']:
                        self.play_pause_button.setText("Pause")
                    elif msg_type == 'paused':
                        self.play_pause_button.setText("Play")
                    elif msg_type == 'finished':
                        self.play_pause_button.setText("Play")
                        self.audio_timeline.set_playback_position(self.audio_player.get_duration_seconds())
                    elif msg_type == 'progress':
                        current_seconds = msg_data
                        self.audio_timeline.set_playback_position(current_seconds)
                        if not self.is_any_edit_mode_active():
                            self._highlight_current_segment(current_seconds)
                    
                    self._update_time_labels_display()
                    self.audio_player_update_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                logger.exception("Error processing audio player queue.")

    def _disable_all_controls(self):
        """Disable all interactive widgets."""
        for widget in self.findChildren(QPushButton) + self.findChildren(QCheckBox):
            widget.setEnabled(False)
        self.audio_timeline.setEnabled(False)

    def _enable_all_controls(self):
        """Enable all interactive widgets."""
        for widget in self.findChildren(QPushButton) + self.findChildren(QCheckBox):
            widget.setEnabled(True)
        self.audio_timeline.setEnabled(True)
        # Re-apply any specific disabled states
        self._configure_ui_for_timestamp_edit_mode(self.is_timestamp_editing_active)

    def closeEvent(self, event):
        """Override close event to clean up resources."""
        logger.info("CorrectionWindow: Close requested.")
        self.poll_timer.stop()
        if self.audio_player:
            self.audio_player.stop_resources()
        event.accept()
        
    def _handle_escape_key(self):
        """Handle the Escape key press."""
        if self.is_timestamp_editing_active:
            self._handle_cancel_timestamp_edit_click()

    # Placeholder methods for functionality to be fully implemented
    def _open_assign_speakers_dialog(self):
        QMessageBox.information(self, "Not Implemented", "The 'Assign Speakers' dialog has not been migrated to Qt yet.")

    def _jump_to_segment_start_action(self):
        # This will be similar to the old logic but using Qt
        pass

    def _drag_playback_head(self, position_seconds: float):
        if not self.was_playing_before_drag and self.audio_player.playing:
            self.was_playing_before_drag = True
            self.audio_player.pause()
        self.audio_player.set_pos_seconds(position_seconds)
        
    def _drag_start_bar(self, position_seconds: float):
        pass # To be implemented
        
    def _drag_end_bar(self, position_seconds: float):
        pass # To be implemented
        
    def _on_drag_finished(self):
        if self.was_playing_before_drag:
            self.audio_player.play()
        self.was_playing_before_drag = False
        
    def _handle_toggle_end_time_click(self):
        pass # To be implemented
        
    def _handle_save_times_click(self):
        pass # To be implemented
        
    def _handle_cancel_timestamp_edit_click(self):
        self._exit_timestamp_edit_mode(save_changes=False)
        
    def _handle_text_area_double_click(self, event):
        pass # To be implemented
        
    def _show_context_menu(self, pos):
        pass # To be implemented
        
    def _highlight_current_segment(self, current_playback_seconds: float):
        pass # To be implemented
        
    def _configure_ui_for_timestamp_edit_mode(self, enabled: bool):
        self.ts_edit_widget.setVisible(enabled)
        # This is where the bug fix happens - we do NOT disable other controls
        self.play_pause_button.setEnabled(True)
        self.rewind_button.setEnabled(True)
        self.forward_button.setEnabled(True)
        self.audio_timeline.setEnabled(True)

    def _exit_timestamp_edit_mode(self, save_changes: bool):
        if not self.is_timestamp_editing_active: return
        # Logic to save changes if needed...
        self.is_timestamp_editing_active = False
        self.segment_id_for_timestamp_edit = None
        self._configure_ui_for_timestamp_edit_mode(False)
        
    def is_any_edit_mode_active(self) -> bool:
        return self.is_timestamp_editing_active

    def _handle_audio_player_error(self, error_message):
        logger.error(f"AudioPlayer error: {error_message}")
        QMessageBox.critical(self, "Audio Player Error", error_message)
        self._disable_all_controls()
        if self.audio_player:
            self.audio_player.stop_resources()
            self.audio_player = None

# This block allows testing the window independently
if __name__ == '__main__':
    import sys
    from utils.config_manager import ConfigManager
    
    app = QApplication(sys.argv)
    # A dummy config manager for testing
    config = ConfigManager(constants.DEFAULT_CONFIG_FILE)
    # Dummy parent widget
    parent = QWidget()
    
    window = CorrectionWindow(parent, config, True)
    window.show()
    
    sys.exit(app.exec())





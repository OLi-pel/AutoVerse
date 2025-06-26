# ui/correction_view_logic.py
import logging, sys, os
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QVBoxLayout, QColorDialog, QDialog,
                               QDialogButtonBox, QLabel, QLineEdit, QGridLayout, QScrollArea,
                               QWidget, QComboBox)
from PySide6.QtCore import QObject, Slot, Qt
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.correction_window_logic import SegmentManager
from core.audio_player import AudioPlayer # This is our new, robust audio player
from utils import constants
from ui.timeline_frame import WaveformFrame
from ui.selectable_text_edit import SelectableTextEdit

logger = logging.getLogger(__name__)

class CorrectionViewLogic(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.segment_manager = SegmentManager()
        self.audio_player = AudioPlayer() # Create initial instance
        self.selected_segment_id = None
        self.current_highlighted_segment_id = None
        self.editing_segment_id = None
        self.timestamp_editing_segment_id = None
        self.multi_selection_ids = []
        self.normal_format = QTextCharFormat()
        self.highlight_format = QTextCharFormat()
        self.selection_format = QTextCharFormat()
        self.multi_selection_format = QTextCharFormat()
        self.set_highlight_color(QColor(100, 149, 237))
        
        self.timeline = WaveformFrame()
        old_frame = self.main_window.correction_timeline_frame
        layout = old_frame.layout() or QVBoxLayout(old_frame)
        if not old_frame.layout(): old_frame.setLayout(layout)
        layout.setContentsMargins(0,0,0,0)
        
        while layout.count() > 0:
            item = layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        layout.addWidget(self.timeline)
            
        self.connect_signals()
        self.set_controls_enabled(False)

    def connect_audio_player_signals(self):
        """Helper method to connect signals from the current audio_player instance."""
        self.audio_player.progress.connect(self.update_audio_progress)
        self.audio_player.finished.connect(self.on_audio_finished)
        self.audio_player.error.connect(lambda msg: QMessageBox.critical(self.main_window, "Audio Player Error", msg))
        self.audio_player.state_changed.connect(self.update_play_button_state)

    def connect_signals(self):
        textarea = self.main_window.correction_text_area
        if textarea:
            textarea.segment_clicked.connect(self.on_segment_clicked)
            textarea.edit_requested.connect(self.on_edit_requested)
            textarea.edit_cancelled.connect(lambda: self.exit_edit_mode(save=False))
            textarea.focusOutEvent = lambda event: self.exit_edit_mode(save=True) if self.editing_segment_id else None
        
        if self.main_window.correction_text_edit_btn: self.main_window.correction_text_edit_btn.clicked.connect(self.on_edit_button_clicked)
        if self.main_window.edit_speaker_btn: self.main_window.edit_speaker_btn.clicked.connect(self.on_edit_speaker_clicked)
        if self.main_window.correction_timestamp_edit_btn: self.main_window.correction_timestamp_edit_btn.clicked.connect(self.on_timestamp_edit_button_clicked)
        if self.main_window.save_timestamp_btn: self.main_window.save_timestamp_btn.clicked.connect(self.on_save_timestamp_clicked)
        if self.main_window.merge_segments_btn: self.main_window.merge_segments_btn.clicked.connect(self.on_merge_button_clicked)

        self.main_window.correction_browse_transcription_btn.clicked.connect(self.browse_transcription_file)
        self.main_window.correction_browse_audio_btn.clicked.connect(self.browse_audio_file)
        self.main_window.correction_load_files_btn.clicked.connect(self.load_files)
        self.main_window.correction_assign_speakers_btn.clicked.connect(self.open_speaker_assignment_dialog)
        self.main_window.correction_save_changes_btn.clicked.connect(self.save_changes)
        if self.main_window.change_highlight_color_btn: self.main_window.change_highlight_color_btn.clicked.connect(self.open_change_highlight_color_dialog)

        self.main_window.correction_play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.main_window.correction_rewind_btn.clicked.connect(lambda: self.on_seek_button_clicked(is_forward=False))
        self.main_window.correction_forward_btn.clicked.connect(lambda: self.on_seek_button_clicked(is_forward=True))

        self.timeline.seek_requested.connect(self.seek_to_percentage)
        self.timeline.bar_dragged.connect(self.on_timestamp_bar_dragged)
        
        # Initial connection
        self.connect_audio_player_signals()

    # --- Start of new/changed methods ---
    @Slot()
    def toggle_play_pause(self):
        if not self.audio_player or not self.segment_manager.segments:
            QMessageBox.information(self.main_window, "No Audio", "Please load an audio file first.")
            return
        if self.audio_player.is_playing:
            self.audio_player.pause()
        else:
            self.audio_player.play()

    @Slot()
    def load_files(self): self._safe_action(self._load_files_action)

    def _load_files_action(self):
        txt = self.main_window.correction_transcription_entry.text()
        audio = self.main_window.correction_audio_entry.text()
        if not txt or not audio:
            QMessageBox.warning(self.main_window, "Error", "Please select both transcription and audio files.")
            return

        try:
            self.select_segment(None)
            
            # Destroy old player and create a new one to prevent stale state issues
            if self.audio_player:
                self.audio_player.destroy()
            self.audio_player = AudioPlayer()
            self.connect_audio_player_signals()

            with open(txt, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            self.segment_manager.parse_transcription_lines(lines)
            self.render_segments_to_textarea()

            if not self.audio_player.load_file(audio):
                raise IOError("Audio player failed to load or resample the file. Check logs for details.")

            self.timeline.set_waveform_data(self.audio_player.get_normalized_waveform())
            self.timeline.set_duration(self.audio_player.get_duration())
            self.update_audio_progress(0)
            self.set_controls_enabled(True)
            self.update_play_button_state(playing=False)
        except Exception as e:
            logger.exception("Load error.")
            self.set_controls_enabled(False)
            QMessageBox.critical(self.main_window, "Load Error", str(e))
    # --- End of new/changed methods ---


    # ... ALL OTHER METHODS FROM THIS POINT FORWARD REMAIN EXACTLY THE SAME AS YOUR ORIGINAL WORKING VERSION ...
    # ... (e.g., enter_timestamp_edit_mode, exit_timestamp_edit_mode, etc.) ...
    
    def enter_timestamp_edit_mode(self, segment_id):
        self.exit_all_edit_modes()
        segment = self.segment_manager.get_segment_by_id(segment_id)
        if not segment or not segment.get('has_timestamps'):
            QMessageBox.warning(self.main_window, "No Timestamp", "This segment does not have a timestamp to edit.")
            return

        logger.info(f"Entering timestamp edit mode for {segment_id}")
        self.timestamp_editing_segment_id = segment_id
        self.select_segment(segment_id)
        
        # UI Changes for Timestamp Edit Mode
        self.main_window.save_timestamp_btn.setVisible(True)
        self.main_window.correction_timestamp_edit_btn.setIcon(self.main_window.icon_cancel_edit)
        self.main_window.correction_rewind_btn.setText("-1s")
        self.main_window.correction_forward_btn.setText("+1s")
        
        start_time = segment.get('start_time', 0.0)
        self.audio_player.set_position(start_time)
        self.timeline.enter_edit_mode(start_time)
        self.update_edit_buttons_state()
        self.main_window.correction_text_area.setFocus()
        
    def exit_timestamp_edit_mode(self, save=False):
        if not self.timestamp_editing_segment_id: return
            
        logger.info(f"Exiting timestamp edit mode for {self.timestamp_editing_segment_id}. Save: {save}")
        if save:
            new_start_time = self.timeline.start_bar_pos_secs
            time_str = self.segment_manager.seconds_to_time_str(new_start_time)
            self.segment_manager.update_segment_timestamps(self.timestamp_editing_segment_id, time_str, None)
            self.render_segments_to_textarea()
            QMessageBox.information(self.main_window, "Timestamp Saved", f"Segment start time updated to {time_str}")

        # Revert UI Changes
        self.main_window.save_timestamp_btn.setVisible(False)
        self.main_window.correction_timestamp_edit_btn.setIcon(self.main_window.icon_edit_timestamp)
        self.main_window.correction_rewind_btn.setText("-5s")
        self.main_window.correction_forward_btn.setText("+5s")
        
        self.timestamp_editing_segment_id = None
        self.timeline.exit_edit_mode()
        self.update_edit_buttons_state()
        
    def on_seek_button_clicked(self, is_forward: bool):
        if self.timestamp_editing_segment_id:
            offset = 1.0 if is_forward else -1.0
        else:
            offset = 5.0 if is_forward else -5.0
        
        self.seek_by_offset(offset)

    @Slot(int, Qt.KeyboardModifiers)
    def on_segment_clicked(self, block_number, modifiers):
        is_click_on_valid_segment = 0 <= block_number < len(self.segment_manager.segments)
        
        if self.editing_segment_id or self.timestamp_editing_segment_id:
            self.exit_all_edit_modes()
            if is_click_on_valid_segment: self.select_segment_by_block(block_number)
            return

        if modifiers == Qt.KeyboardModifier.ShiftModifier and is_click_on_valid_segment:
            segment_id = self.segment_manager.segments[block_number]['id']
            if self.selected_segment_id:
                self._clear_selection()
                
            if segment_id in self.multi_selection_ids:
                self.multi_selection_ids.remove(segment_id)
                self._apply_format(segment_id, self.normal_format)
            else:
                self.multi_selection_ids.append(segment_id)
                self._apply_format(segment_id, self.multi_selection_format)
        else:
            self._clear_all_selections()
            if is_click_on_valid_segment:
                self.select_segment_by_block(block_number)

        self.update_edit_buttons_state()

    def _clear_all_selections(self):
        self._clear_selection()
        for seg_id in self.multi_selection_ids:
            self._apply_format(seg_id, self.normal_format)
        self.multi_selection_ids.clear()
        
    @Slot()
    def on_merge_button_clicked(self):
        self.exit_all_edit_modes()
        
        num_multi_selected = len(self.multi_selection_ids)
        if num_multi_selected > 1:
            new_target_id = self.segment_manager.merge_multiple_segments(self.multi_selection_ids)
            self._clear_all_selections()
            self.render_segments_to_textarea()
            if new_target_id:
                self.select_segment(new_target_id)
                
        elif self.selected_segment_id and num_multi_selected == 0:
            current_id = self.selected_segment_id
            current_index = self.segment_manager.get_segment_index(current_id)
            if current_index > 0:
                previous_id = self.segment_manager.segments[current_index - 1]['id']
                if self.segment_manager.merge_segment_upwards(current_id):
                    self._clear_all_selections()
                    self.render_segments_to_textarea()
                    self.select_segment(previous_id)

        self.update_edit_buttons_state()
    
    @Slot()
    def on_timestamp_edit_button_clicked(self):
        if self.timestamp_editing_segment_id:
            self.exit_timestamp_edit_mode(save=False)
        elif self.selected_segment_id:
            self.enter_timestamp_edit_mode(self.selected_segment_id)

    def _apply_format(self, segment_id, text_format, clear_first=False):
        segment = self.segment_manager.get_segment_by_id(segment_id)
        if segment and 'doc_positions' in segment:
            cursor = QTextCursor(self.main_window.correction_text_area.document())
            cursor.setPosition(segment['doc_positions'][0])
            cursor.setPosition(segment['doc_positions'][1], QTextCursor.MoveMode.KeepAnchor)
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, 1)
            cursor.setCharFormat(text_format)
            
    def set_highlight_color(self, color):
        self.highlight_format.setBackground(color)
        self.selection_format.setBackground(color.darker(150))
        self.multi_selection_format.setBackground(color.lighter(130))
        
    def _apply_selection(self, segment_id): 
        self._apply_format(segment_id, self.selection_format)

    def _apply_highlight(self, segment_id):
        if segment_id != self.selected_segment_id and not self.editing_segment_id:
            self._apply_format(segment_id, self.highlight_format)
    def _clear_selection(self):
        if self.selected_segment_id:
            is_highlighted = self.selected_segment_id == self.current_highlighted_segment_id
            self._apply_format(self.selected_segment_id, self.highlight_format if is_highlighted else self.normal_format)
        self.selected_segment_id = None
    def _clear_highlight(self):
        if self.current_highlighted_segment_id:
            is_selected = self.current_highlighted_segment_id == self.selected_segment_id
            self._apply_format(self.current_highlighted_segment_id, self.selection_format if is_selected else self.normal_format)
    @Slot()
    def on_edit_speaker_clicked(self): self._safe_action(self._open_change_speaker_dialog)
    def _open_change_speaker_dialog(self):
        if not self.selected_segment_id: QMessageBox.information(self.main_window, "No Segment Selected", "Please select a segment to change its speaker."); return
        segment = self.segment_manager.get_segment_by_id(self.selected_segment_id)
        if not segment: return
        dialog = QDialog(self.main_window); dialog.setWindowTitle("Change Segment Speaker"); layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Assign an existing speaker to this segment:"))
        combo = QComboBox(); combo.addItem("(No Speaker)", constants.NO_SPEAKER_LABEL)
        speaker_ids = sorted(list(self.segment_manager.unique_speaker_labels))
        for speaker_id in speaker_ids:
            display_name = self.segment_manager.speaker_map.get(speaker_id, speaker_id); combo.addItem(f"{display_name} ({speaker_id})", speaker_id)
        layout.addWidget(combo)
        current_speaker_index = combo.findData(segment.get("speaker_raw", constants.NO_SPEAKER_LABEL))
        if current_speaker_index != -1: combo.setCurrentIndex(current_speaker_index)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            final_speaker_id = combo.currentData()
            self.segment_manager.update_segment_speaker(self.selected_segment_id, final_speaker_id); self.render_segments_to_textarea()
            self.select_segment(self.selected_segment_id); self.main_window.correction_text_area.setFocus()
    def select_segment_by_block(self, block_number):
        if 0 <= block_number < len(self.segment_manager.segments): self.select_segment(self.segment_manager.segments[block_number]['id'])
    @Slot(int, int)
    def on_edit_requested(self, block_number, position_in_block):
        if not (0 <= block_number < len(self.segment_manager.segments)): return
        segment = self.segment_manager.segments[block_number]
        block = self.main_window.correction_text_area.document().findBlockByNumber(block_number)
        absolute_click_pos = block.position() + position_in_block
        if 'component_positions' in segment:
            positions = segment['component_positions']
            if 'speaker' in positions and positions['speaker'][0] <= absolute_click_pos < positions['speaker'][1]: self.select_segment(segment['id']); self._open_change_speaker_dialog(); return
            if 'timestamp' in positions and positions['timestamp'][0] <= absolute_click_pos < positions['timestamp'][1]: self.enter_timestamp_edit_mode(segment['id']); return
        if self.editing_segment_id and self.editing_segment_id != segment['id']: self.exit_edit_mode(save=True)
        self.enter_edit_mode(segment['id'], position_in_block)
    def enter_edit_mode(self, segment_id, click_pos_in_block: int = 0):
        if self.editing_segment_id == segment_id or self.timestamp_editing_segment_id: return
        self.exit_all_edit_modes(); self.editing_segment_id = segment_id
        logger.info(f"Entering text edit mode for {segment_id}"); self.select_segment(segment_id)
        block_number = self.segment_manager.get_segment_index(segment_id)
        if block_number != -1: self.main_window.correction_text_area.enter_edit_mode(block_number, click_pos_in_block)
        self.update_edit_buttons_state()
    def exit_edit_mode(self, save=False):
        if not self.editing_segment_id: return
        segment_id_to_exit = self.editing_segment_id
        if save:
            logger.info(f"Saving text changes for {segment_id_to_exit}"); block_number = self.segment_manager.get_segment_index(segment_id_to_exit)
            if block_number != -1:
                new_line_text = self.main_window.correction_text_area.document().findBlockByNumber(block_number).text()
                self.segment_manager.update_segment_from_full_line(segment_id_to_exit, new_line_text)
        else: logger.info(f"Cancelling text edit for {segment_id_to_exit}")
        self.editing_segment_id = None; self.main_window.correction_text_area.exit_edit_mode(); self.render_segments_to_textarea(); self.select_segment(segment_id_to_exit); self.update_edit_buttons_state()
    @Slot()
    def on_edit_button_clicked(self):
        if self.editing_segment_id: self.exit_edit_mode(save=True); self.main_window.correction_text_area.setFocus()
        elif self.selected_segment_id: self.enter_edit_mode(self.selected_segment_id)
    def select_segment(self, segment_id):
        if self.selected_segment_id == segment_id: return
        self._clear_selection()
        if segment_id: self._apply_selection(segment_id); self.selected_segment_id = segment_id
        else: self.selected_segment_id = None
        self.update_edit_buttons_state()
    @Slot(str, float)
    def on_timestamp_bar_dragged(self, bar_name, new_time):
        if bar_name == "start": self.timeline.set_start_bar_position(new_time)
        elif bar_name == "playhead": self.audio_player.set_position(new_time)
    @Slot()
    def on_save_timestamp_clicked(self): self.exit_timestamp_edit_mode(save=True)
    def exit_all_edit_modes(self): self.exit_edit_mode(save=True); self.exit_timestamp_edit_mode(save=False)
    def update_edit_buttons_state(self):
        is_text_editing = self.editing_segment_id is not None; is_ts_editing = self.timestamp_editing_segment_id is not None; is_selected = self.selected_segment_id is not None
        edit_button = self.main_window.correction_text_edit_btn
        if edit_button:
            edit_button.setEnabled((is_selected or is_text_editing) and not is_ts_editing)
            if is_text_editing: edit_button.setIcon(self.main_window.icon_save_edit); edit_button.setToolTip("Commit Changes")
            else: edit_button.setIcon(self.main_window.icon_edit_text); edit_button.setToolTip("Edit Selected Segment")
        ts_edit_button = self.main_window.correction_timestamp_edit_btn
        if ts_edit_button:
            ts_edit_button.setEnabled((is_selected or is_ts_editing) and not is_text_editing)
            ts_edit_button.setChecked(is_ts_editing)
        self.main_window.edit_speaker_btn.setEnabled(is_selected and not is_text_editing and not is_ts_editing)
        self.main_window.save_timestamp_btn.setEnabled(is_ts_editing)
        is_action_safe = not is_text_editing and not is_ts_editing
        for w in [self.main_window.correction_load_files_btn, self.main_window.correction_browse_audio_btn, self.main_window.correction_browse_transcription_btn, self.main_window.correction_assign_speakers_btn, self.main_window.change_highlight_color_btn, self.main_window.correction_save_changes_btn]:
            if w: w.setEnabled(is_action_safe)
        merge_button = self.main_window.merge_segments_btn
        if merge_button:
            can_merge = False
            if len(self.multi_selection_ids) > 1:
                can_merge = True
            elif self.selected_segment_id and self.segment_manager.get_segment_index(self.selected_segment_id) > 0:
                can_merge = True
            
            merge_button.setEnabled(can_merge)

    def _safe_action(self, action_func, *args): self.exit_all_edit_modes(); action_func(*args)
    @Slot()
    def save_changes(self): self._safe_action(self._save_changes_action)
    def _save_changes_action(self):
        if not self.segment_manager.segments: QMessageBox.information(self.main_window, "Nothing to save", "There are no segments loaded to save."); return
        path, _ = QFileDialog.getSaveFileName(self.main_window, "Save Corrected Transcription", "", "Text Files (*.txt)");
        if path:
            formatted_lines = self.segment_manager.format_segments_for_saving(True, True)
            try:
                with open(path, 'w', encoding='utf-8') as f: f.write('\n'.join(formatted_lines))
                QMessageBox.information(self.main_window, "Saved", f"Transcription saved to {path}")
            except IOError as e: QMessageBox.critical(self.main_window, "Save Error", f"Could not save file: {e}")
    @Slot()
    def browse_transcription_file(self): self._safe_action(self._browse_transcription_file_action)
    def _browse_transcription_file_action(self):
        path, _ = QFileDialog.getOpenFileName(self.main_window, "Select Transcription", "", "Text (*.txt)");
        if path: self.main_window.correction_transcription_entry.setText(path)
    @Slot()
    def browse_audio_file(self): self._safe_action(self._browse_audio_file_action)
    def _browse_audio_file_action(self):
        path, _ = QFileDialog.getOpenFileName(self.main_window, "Select Audio", "", "Audio (*.wav *.mp3 *.aac *.flac *.m4a)");
        if path: self.main_window.correction_audio_entry.setText(path)
    
    @Slot()
    def open_speaker_assignment_dialog(self): self._safe_action(self._open_speaker_assignment_dialog_action)
    def _open_speaker_assignment_dialog_action(self):
        if not self.segment_manager.segments: QMessageBox.information(self.main_window, "No Segments", "Please load a transcription file first."); return
        dialog = QDialog(self.main_window); dialog.setWindowTitle("Assign Speaker Names"); dialog.setMinimumWidth(400); layout = QVBoxLayout(dialog); scroll = QScrollArea(); scroll.setWidgetResizable(True); layout.addWidget(scroll); content = QWidget(); form = QGridLayout(content); entries = {}
        for i, label in enumerate(sorted(list(self.segment_manager.unique_speaker_labels))):
            form.addWidget(QLabel(f"<b>{label}:</b>"), i, 0); edit = QLineEdit(self.segment_manager.speaker_map.get(label, "")); form.addWidget(edit, i, 1); entries[label] = edit
        sep_row = len(entries); form.addWidget(QLabel("---<br><b>Add New</b>"), sep_row, 0, 1, 2, Qt.AlignCenter); form.addWidget(QLabel("ID:"), sep_row + 1, 0); id_edit = QLineEdit(); form.addWidget(id_edit, sep_row + 1, 1); form.addWidget(QLabel("Name:"), sep_row + 2, 0); name_edit = QLineEdit(); form.addWidget(name_edit, sep_row + 2, 1)
        scroll.setWidget(content); buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            for label, edit in entries.items():
                if edit.text().strip(): self.segment_manager.speaker_map[label] = edit.text().strip()
                elif label in self.segment_manager.speaker_map: del self.segment_manager.speaker_map[label]
            new_id = id_edit.text().strip().replace(" ", "_").upper();
            if new_id:
                self.segment_manager.unique_speaker_labels.add(new_id)
                if name_edit.text().strip(): self.segment_manager.speaker_map[new_id] = name_edit.text().strip()
            self.render_segments_to_textarea(); self.main_window.correction_text_area.setFocus()
    @Slot()
    def open_change_highlight_color_dialog(self): self._safe_action(self._open_change_highlight_color_dialog_action)
    def _open_change_highlight_color_dialog_action(self):
        new_color = QColorDialog.getColor(self.highlight_format.background().color(), self.main_window, "Select Highlight Color");
        if new_color.isValid(): self.set_highlight_color(new_color);
        if self.current_highlighted_segment_id: self._apply_highlight(self.current_highlighted_segment_id)
    def set_controls_enabled(self, enabled):
        widgets = [self.main_window.correction_play_pause_btn, self.main_window.correction_rewind_btn, self.main_window.correction_forward_btn, self.main_window.correction_assign_speakers_btn, self.main_window.correction_save_changes_btn, self.main_window.correction_timeline_frame, self.main_window.change_highlight_color_btn];
        for w in widgets:
            if w: w.setEnabled(enabled)
        self.update_edit_buttons_state()
    @Slot(bool)
    def update_play_button_state(self, playing):
        if playing: self.main_window.correction_play_pause_btn.setText("Pause"); self.main_window.correction_play_pause_btn.setIcon(self.main_window.icon_pause)
        else: self.main_window.correction_play_pause_btn.setText("Play"); self.main_window.correction_play_pause_btn.setIcon(self.main_window.icon_play)
    
    @Slot()
    def on_audio_finished(self): self._clear_highlight(); self.current_highlighted_segment_id = None
    @Slot(float)
    def update_audio_progress(self, current_time):
        duration = self.audio_player.get_duration(); self.main_window.correction_time_label.setText(f"{self.format_time(current_time)} / {self.format_time(duration)}")
        if hasattr(self.main_window, 'monospace_font'): self.main_window.correction_time_label.setFont(self.main_window.monospace_font)
        self.timeline.set_progress(current_time); self._update_text_highlight(current_time)
    def _update_text_highlight(self, current_time):
        active_id = None
        if self.audio_player.get_duration() > 0:
            for i, seg in enumerate(self.segment_manager.segments):
                if not seg.get("has_timestamps"): continue
                start_time = seg.get('start_time', -1)
                end_time = seg.get('end_time')
                if end_time is None:
                    is_last_segment = (i + 1) == len(self.segment_manager.segments)
                    if not is_last_segment and self.segment_manager.segments[i+1].get('has_timestamps'): end_time = self.segment_manager.segments[i+1].get('start_time')
                    else: end_time = self.audio_player.get_duration()
                if end_time is not None and start_time <= current_time < end_time: active_id = seg['id']; break
        if self.current_highlighted_segment_id != active_id:
            self._clear_highlight()
            if active_id: self._apply_highlight(active_id)
            self.current_highlighted_segment_id = active_id
    @Slot()
    def seek_by_offset(self, offset_seconds): self.audio_player.seek(offset_seconds)
    @Slot(float)
    def seek_to_percentage(self, percentage):
        if self.audio_player.get_duration() > 0: self.audio_player.set_position(percentage * self.audio_player.get_duration())
    def format_time(self, seconds):
        minutes = int(seconds // 60)
        return f"{minutes:02d}:{(seconds % 60):06.3f}"
    def render_segments_to_textarea(self):
        textarea = self.main_window.correction_text_area
        current_selection_id = self.selected_segment_id
        textarea.clear()
        self.current_highlighted_segment_id = None
        if not self.segment_manager.segments:
            textarea.setPlainText("No segments loaded.")
            return
        cursor = QTextCursor(textarea.document())
        for seg in self.segment_manager.segments:
            seg['doc_positions'] = (cursor.position(),)
            seg['component_positions'] = {}
            if seg.get("has_timestamps"):
                ts_start_pos = cursor.position()
                ts_str = f"[{self.segment_manager.seconds_to_time_str(seg['start_time'])}] "
                cursor.insertText(ts_str, self.normal_format)
                seg['component_positions']['timestamp'] = (ts_start_pos, cursor.position())
            speaker_label = seg.get("speaker_raw", constants.NO_SPEAKER_LABEL)
            if speaker_label != constants.NO_SPEAKER_LABEL:
                spk_start_pos = cursor.position()
                spk_str = f"{self.segment_manager.speaker_map.get(speaker_label, speaker_label)}: "
                cursor.insertText(spk_str, self.normal_format)
                seg['component_positions']['speaker'] = (spk_start_pos, cursor.position())
            text_start_pos = cursor.position()
            cursor.insertText(seg['text'], self.normal_format)
            seg['component_positions']['text'] = (text_start_pos, cursor.position())
            cursor.insertText('\n', self.normal_format)
            seg['doc_positions'] = (seg['doc_positions'][0], cursor.position())
        if current_selection_id:
            self.select_segment(current_selection_id)
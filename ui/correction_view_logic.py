# ui/correction_view_logic.py
import logging, sys, os
from copy import deepcopy
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QVBoxLayout, QColorDialog, QDialog, 
                               QDialogButtonBox, QLabel, QLineEdit, QGridLayout, QScrollArea, 
                               QWidget, QComboBox, QRadioButton, QHBoxLayout, QPushButton,
                               QSizePolicy)
from PySide6.QtCore import QObject, Slot, Qt, QSize
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QIcon

from core.correction_window_logic import SegmentManager
from core.audio_player import AudioPlayer
from core.undo_redo import UndoManager, ModifyStateCommand
from utils import constants
from ui.timeline_frame import WaveformFrame
from ui.selectable_text_edit import SelectableTextEdit

logger = logging.getLogger(__name__)

class CorrectionViewLogic(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.segment_manager = SegmentManager()
        self.audio_player = AudioPlayer()
        self.undo_manager = UndoManager()
        self.original_text_before_edit = None

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
            if item and item.widget(): item.widget().deleteLater()
        layout.addWidget(self.timeline)
        
        self.connect_signals()
        self.set_controls_enabled(False)
        self._update_text_area_font()
        self._update_undo_redo_buttons_state(False, False)

    def connect_audio_player_signals(self):
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
            
        self.main_window.findChild(QPushButton, "Undo_button").clicked.connect(self.undo_manager.undo)
        self.main_window.findChild(QPushButton, "Redo_Button").clicked.connect(self.undo_manager.redo)
        self.undo_manager.state_changed.connect(self._update_undo_redo_buttons_state)
        self.undo_manager.history_changed.connect(self.render_segments_to_textarea)
        
        self.main_window.correction_text_edit_btn.clicked.connect(self.on_edit_button_clicked)
        self.main_window.edit_speaker_btn.clicked.connect(self.on_edit_speaker_clicked)
        self.main_window.correction_timestamp_edit_btn.clicked.connect(self.on_timestamp_edit_button_clicked)
        self.main_window.save_timestamp_btn.clicked.connect(self.on_save_timestamp_clicked)
        self.main_window.merge_segments_btn.clicked.connect(self.on_merge_button_clicked)
        self.main_window.segment_btn.clicked.connect(self.on_add_split_button_clicked)
        self.main_window.delete_segment_btn.clicked.connect(self.on_delete_segment_clicked)
        self.main_window.correction_browse_transcription_btn.clicked.connect(self.browse_transcription_file)
        self.main_window.correction_browse_audio_btn.clicked.connect(self.browse_audio_file)
        self.main_window.correction_load_files_btn.clicked.connect(self.load_files)
        self.main_window.correction_assign_speakers_btn.clicked.connect(self.open_speaker_assignment_dialog)
        self.main_window.correction_save_changes_btn.clicked.connect(self.save_changes)
        self.main_window.change_highlight_color_btn.clicked.connect(self.open_change_highlight_color_dialog)
        self.main_window.correction_play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.main_window.correction_rewind_btn.clicked.connect(lambda: self.on_seek_button_clicked(is_forward=False))
        self.main_window.correction_forward_btn.clicked.connect(lambda: self.on_seek_button_clicked(is_forward=True))
        self.timeline.seek_requested.connect(self.seek_to_percentage)
        self.timeline.bar_dragged.connect(self.on_timestamp_bar_dragged)
        self.main_window.text_font_combo.currentTextChanged.connect(self._update_text_area_font)
        self.main_window.font_size_combo.currentTextChanged.connect(self._update_text_area_font)
        self.connect_audio_player_signals()
        
    @Slot(bool, bool)
    def _update_undo_redo_buttons_state(self, can_undo, can_redo):
        self.main_window.findChild(QPushButton, "Undo_button").setEnabled(can_undo)
        self.main_window.findChild(QPushButton, "Redo_Button").setEnabled(can_redo)
        
    def _execute_command(self, before_segments, before_map, action_func):
        action_func()
        after_segments = deepcopy(self.segment_manager.segments)
        after_map = deepcopy(self.segment_manager.speaker_map)
        
        command = ModifyStateCommand(self.segment_manager, self, before_segments, after_segments, before_map, after_map)
        self.undo_manager.add_command(command)
        
    @Slot()
    def _update_text_area_font(self):
        font_family = self.main_window.text_font_combo.currentText(); font_size_str = self.main_window.font_size_combo.currentText()
        if not font_family or not font_size_str: return
        try: self.main_window.correction_text_area.setFont(QFont(font_family, int(font_size_str)))
        except ValueError: logger.warning(f"Invalid font size: '{font_size_str}'")

    @Slot()
    def toggle_play_pause(self):
        if not self.audio_player or not self.segment_manager.segments: return
        if self.audio_player.is_playing: self.audio_player.pause()
        else: self.audio_player.play()

    @Slot()
    def load_files(self): self._safe_action(self._load_files_action)

    def _load_files_action(self):
        txt = self.main_window.correction_transcription_entry.text(); audio = self.main_window.correction_audio_entry.text()
        if not txt or not audio: return
        try:
            self.undo_manager.clear()
            self.select_segment(None)
            if self.audio_player: self.audio_player.destroy()
            self.audio_player = AudioPlayer(); self.connect_audio_player_signals()
            with open(txt, 'r', encoding='utf-8') as f: lines = f.readlines()
            self.segment_manager.parse_transcription_lines(lines); self.render_segments_to_textarea()
            if not self.audio_player.load_file(audio): raise IOError("Audio player failed to load file.")
            self.timeline.set_waveform_data(self.audio_player.get_normalized_waveform()); self.timeline.set_duration(self.audio_player.get_duration())
            self.update_audio_progress(0); self.set_controls_enabled(True); self.update_play_button_state(playing=False)
        except Exception as e:
            logger.exception("Load error."); self.set_controls_enabled(False); QMessageBox.critical(self.main_window, "Load Error", str(e))
    
    @Slot()
    def on_delete_segment_clicked(self):
        # DO NOT call exit_all_edit_modes() here. This was the bug.
        
        before_segs = deepcopy(self.segment_manager.segments)
        before_map = deepcopy(self.segment_manager.speaker_map)

        confirmed_action = False
        
        if self.timestamp_editing_segment_id:
            msg = "Are you sure you want to remove the timestamp from this segment?"
            if QMessageBox.question(self.main_window, "Confirm Delete Timestamp", msg) == QMessageBox.Yes:
                self.segment_manager.remove_segment_timestamp(self.timestamp_editing_segment_id)
                self.exit_timestamp_edit_mode(save=False) # Exits the mode internally
                confirmed_action = True
        
        elif self.editing_segment_id:
            msg = "Are you sure you want to clear the text for this segment? The speaker and timestamp will remain."
            if QMessageBox.question(self.main_window, "Confirm Clear Text", msg) == QMessageBox.Yes:
                self.segment_manager.clear_segment_text(self.editing_segment_id)
                self.exit_edit_mode(save=False) # Exits the mode internally
                confirmed_action = True
        
        else:
            # This is the default case, only reached if not in an edit mode.
            self.exit_all_edit_modes() # Safe to call here now.
            target_ids = self.multi_selection_ids if self.multi_selection_ids else ([self.selected_segment_id] if self.selected_segment_id else [])
            if target_ids and QMessageBox.question(self.main_window, "Confirm Delete", f"Are you sure you want to delete {len(target_ids)} segment(s)?") == QMessageBox.Yes:
                for seg_id in sorted(target_ids, key=self.segment_manager.get_segment_index, reverse=True):
                    self.segment_manager.remove_segment(seg_id)
                self._clear_all_selections()
                confirmed_action = True
        
        if confirmed_action:
            self._execute_command(before_segs, before_map, lambda: self.render_segments_to_textarea())

            
    @Slot()
    def on_add_split_button_clicked(self):
        before_segs = deepcopy(self.segment_manager.segments)
        before_map = deepcopy(self.segment_manager.speaker_map)
        
        action_performed = False

        if self.editing_segment_id is not None:
            original_segment = self.segment_manager.get_segment_by_id(self.editing_segment_id)
            if not original_segment or 'component_positions' not in original_segment or 'text' not in original_segment['component_positions']: return
            
            cursor = self.main_window.correction_text_area.textCursor(); absolute_cursor_pos = cursor.position()
            self.segment_manager.update_segment_from_full_line(self.editing_segment_id, self.main_window.correction_text_area.document().findBlockByNumber(self.segment_manager.get_segment_index(self.editing_segment_id)).text())
            text_start_pos = original_segment['component_positions']['text'][0]; split_pos = max(0, absolute_cursor_pos - text_start_pos)
            
            defaults = {"speaker_raw": original_segment.get("speaker_raw"), "has_timestamps": original_segment.get("has_timestamps"), "has_explicit_end_time": original_segment.get("has_explicit_end_time", False)}
            result = self._open_add_split_dialog(is_split_mode=True, defaults=defaults)
            if result:
                if self.segment_manager.split_segment(self.editing_segment_id, split_pos, result):
                    self.exit_edit_mode(save=False)
                    action_performed = True

        elif self.selected_segment_id is not None:
            result = self._open_add_split_dialog(is_split_mode=False)
            if result: 
                new_id = self.segment_manager.add_segment(result, self.selected_segment_id, result['position'])
                if new_id:
                    self._clear_all_selections()
                    self.select_segment(new_id)
                    action_performed = True
        
        if action_performed:
            self._execute_command(before_segs, before_map, self.render_segments_to_textarea)

    def _open_add_split_dialog(self, is_split_mode, defaults={}):
        dialog = QDialog(self.main_window); dialog.setWindowTitle("Split Segment" if is_split_mode else "Add New Segment"); layout = QGridLayout(dialog);
        layout.addWidget(QLabel("New Segment Speaker:"), 0, 0); speaker_combo = QComboBox(); speaker_map = {constants.NO_SPEAKER_LABEL: "(No Speaker)"}
        speaker_map.update({spk: self.segment_manager.speaker_map.get(spk, spk) for spk in sorted(self.segment_manager.unique_speaker_labels)})
        for raw_id, display_name in speaker_map.items(): speaker_combo.addItem(display_name, raw_id)
        default_speaker = defaults.get('speaker_raw', constants.NO_SPEAKER_LABEL)
        speaker_combo.setCurrentIndex(speaker_combo.findData(default_speaker)); layout.addWidget(speaker_combo, 0, 1)
        layout.addWidget(QLabel("New Segment Timestamps:"), 1, 0); ts_combo = QComboBox(); ts_options = {"none": "No Timestamps", "start_only": "Start Time Only", "start_end": "Start and End Times"}
        for key, value in ts_options.items(): ts_combo.addItem(value, key)
        if not is_split_mode: ts_combo.setCurrentIndex(ts_combo.findData('start_only'))
        elif defaults.get('has_explicit_end_time'): ts_combo.setCurrentIndex(ts_combo.findData('start_end'))
        elif defaults.get('has_timestamps'): ts_combo.setCurrentIndex(ts_combo.findData('start_only'))
        else: ts_combo.setCurrentIndex(ts_combo.findData('none'))
        layout.addWidget(ts_combo, 1, 1)
        if not is_split_mode:
            layout.addWidget(QLabel("Position:"), 2, 0); radio_layout = QHBoxLayout(); radio_above = QRadioButton("Above"); radio_below = QRadioButton("Below"); radio_below.setChecked(True); radio_layout.addWidget(radio_above); radio_layout.addWidget(radio_below); layout.addLayout(radio_layout, 2, 1)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); button_box.accepted.connect(dialog.accept); button_box.rejected.connect(dialog.reject); layout.addWidget(button_box, 3, 0, 1, 2)
        if dialog.exec() == QDialog.Accepted:
            ts_type = ts_combo.currentData(); result = {"speaker_raw": speaker_combo.currentData(), "has_timestamps": ts_type != "none", "has_explicit_end_time": ts_type == "start_end"}
            if not is_split_mode: result['position'] = 'above' if radio_above.isChecked() else 'below'
            return result
        return None
        
    def render_segments_to_textarea(self):
        current_selection_id = self.selected_segment_id
        current_multi_ids = list(self.multi_selection_ids)
        
        self.main_window.correction_text_area.clear()
        self.current_highlighted_segment_id = None
        
        if not self.segment_manager.segments: 
            self.main_window.correction_text_area.setPlainText("No segments loaded.")
            return

        cursor = QTextCursor(self.main_window.correction_text_area.document())
        for seg in self.segment_manager.segments:
            seg['doc_positions'] = (cursor.position(), )
            seg['component_positions'] = {}

            if seg.get("has_timestamps"):
                ts_start_pos = cursor.position()
                ts_str = f"[{self.segment_manager.seconds_to_time_str(seg['start_time'])}] "
                if seg.get('has_explicit_end_time') and seg.get('end_time') is not None:
                     ts_str = f"[{self.segment_manager.seconds_to_time_str(seg['start_time'])} - {self.segment_manager.seconds_to_time_str(seg['end_time'])}] "
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
        
        self._clear_all_selections(update_buttons=False)
        if current_selection_id and self.segment_manager.get_segment_by_id(current_selection_id):
             self.select_segment(current_selection_id)
        if current_multi_ids:
            self.multi_selection_ids = [mid for mid in current_multi_ids if self.segment_manager.get_segment_by_id(mid)]
            for mid in self.multi_selection_ids:
                self._apply_format(mid, self.multi_selection_format)
        
        self.update_edit_buttons_state()
            
    def update_edit_buttons_state(self):
        is_text_editing = self.editing_segment_id is not None
        is_ts_editing = self.timestamp_editing_segment_id is not None
        is_selected = self.selected_segment_id is not None
        is_multi_selected = len(self.multi_selection_ids) > 0
        
        self.main_window.delete_segment_btn.setEnabled(
            is_text_editing or is_ts_editing or is_selected or is_multi_selected
        )
        self.main_window.segment_btn.setEnabled(is_text_editing or is_selected)
        self.main_window.merge_segments_btn.setEnabled(len(self.multi_selection_ids) > 1 or (is_selected and self.segment_manager.get_segment_index(self.selected_segment_id) > 0))
        edit_button = self.main_window.correction_text_edit_btn
        if edit_button:
            edit_button.setEnabled((is_selected or is_text_editing) and not is_ts_editing)
            if is_text_editing: edit_button.setIcon(self.main_window.icon_save_edit); edit_button.setToolTip("Commit Changes")
            else: edit_button.setIcon(self.main_window.icon_edit_text); edit_button.setToolTip("Edit Selected Segment")
        ts_edit_button = self.main_window.correction_timestamp_edit_btn
        if ts_edit_button: ts_edit_button.setEnabled((is_selected or is_ts_editing) and not is_text_editing); ts_edit_button.setChecked(is_ts_editing)
        self.main_window.edit_speaker_btn.setEnabled((is_selected or is_multi_selected) and not is_text_editing and not is_ts_editing)
        self.main_window.save_timestamp_btn.setEnabled(is_ts_editing)
        is_action_safe = not is_text_editing and not is_ts_editing
        for w in [self.main_window.correction_load_files_btn, self.main_window.correction_browse_audio_btn, self.main_window.correction_browse_transcription_btn, self.main_window.correction_assign_speakers_btn, self.main_window.change_highlight_color_btn, self.main_window.correction_save_changes_btn]:
            if w: w.setEnabled(is_action_safe)

    def enter_timestamp_edit_mode(self, segment_id):
        self.exit_all_edit_modes(); segment = self.segment_manager.get_segment_by_id(segment_id);
        if not segment or not segment.get('has_timestamps'): return
        self.timestamp_editing_segment_id = segment_id; self.select_segment(segment_id)
        self.main_window.save_timestamp_btn.setVisible(True); self.main_window.correction_timestamp_edit_btn.setIcon(self.main_window.icon_cancel_edit)
        self.main_window.correction_rewind_btn.setText("-1s"); self.main_window.correction_forward_btn.setText("+1s")
        start_time = segment.get('start_time', 0.0); self.audio_player.set_position(start_time); self.timeline.enter_edit_mode(start_time)
        self.update_edit_buttons_state(); self.main_window.correction_text_area.setFocus()

    def exit_timestamp_edit_mode(self, save=False):
        if not self.timestamp_editing_segment_id: return
        id_to_reselect = self.timestamp_editing_segment_id
        
        if save:
            new_start_time = self.timeline.start_bar_pos_secs
            time_str = self.segment_manager.seconds_to_time_str(new_start_time)
            self.segment_manager.update_segment_timestamps(id_to_reselect, time_str, None)
            QMessageBox.information(self.main_window, "Timestamp Saved", f"Segment start time updated to {time_str}")
            self.render_segments_to_textarea()
        
        self.main_window.save_timestamp_btn.setVisible(False); self.main_window.correction_timestamp_edit_btn.setIcon(self.main_window.icon_edit_timestamp)
        self.main_window.correction_rewind_btn.setText("5s"); self.main_window.correction_forward_btn.setText("5s")
        self.timestamp_editing_segment_id = None; self.timeline.exit_edit_mode()
        
        if self.segment_manager.get_segment_by_id(id_to_reselect):
            self.select_segment(id_to_reselect)
        
        self.update_edit_buttons_state()

    def on_seek_button_clicked(self, is_forward: bool):
        is_ts_editing = self.timestamp_editing_segment_id is not None
        offset_value = 1.0 if is_ts_editing else 5.0
        offset = offset_value if is_forward else -offset_value
        self.seek_by_offset(offset)
        
    @Slot(int, Qt.KeyboardModifiers)
    def on_segment_clicked(self, block_number, modifiers):
        is_click_on_valid_segment = 0 <= block_number < len(self.segment_manager.segments)
        
        if self.editing_segment_id or self.timestamp_editing_segment_id:
            clicked_id = self.segment_manager.segments[block_number]['id'] if is_click_on_valid_segment else None
            if self.editing_segment_id == clicked_id or self.timestamp_editing_segment_id == clicked_id:
                return

            self.exit_all_edit_modes(save=True)
            if is_click_on_valid_segment: self.select_segment_by_block(block_number)
            self.update_edit_buttons_state()
            return

        if not is_click_on_valid_segment:
             self._clear_all_selections()
             self.update_edit_buttons_state()
             return

        segment_id = self.segment_manager.segments[block_number]['id']

        is_shift_pressed = (modifiers & Qt.KeyboardModifier.ShiftModifier) == Qt.KeyboardModifier.ShiftModifier
        if is_shift_pressed:
            if self.selected_segment_id and self.selected_segment_id != segment_id:
                 start_index = self.segment_manager.get_segment_index(self.selected_segment_id)
                 end_index = block_number
                 if start_index > end_index: start_index, end_index = end_index, start_index
                 
                 new_multi_ids = [self.segment_manager.segments[i]['id'] for i in range(start_index, end_index + 1)]
                 
                 self._clear_all_selections(update_buttons=False)
                 self.multi_selection_ids = new_multi_ids
                 for sid in self.multi_selection_ids: self._apply_format(sid, self.multi_selection_format)

            elif segment_id not in self.multi_selection_ids:
                 self.multi_selection_ids.append(segment_id)
                 self._apply_format(segment_id, self.multi_selection_format)
            
            else:
                self.multi_selection_ids.remove(segment_id)
                self._apply_format(segment_id, self.normal_format)

        else:
            self._clear_all_selections()
            self.select_segment_by_block(block_number)

        self.update_edit_buttons_state()

    def _clear_all_selections(self, update_buttons=True):
        self._clear_selection();
        for seg_id in self.multi_selection_ids: 
            if self.segment_manager.get_segment_by_id(seg_id):
                self._apply_format(seg_id, self.normal_format)
        self.multi_selection_ids.clear()
        if update_buttons: self.update_edit_buttons_state()

    @Slot()
    def on_merge_button_clicked(self):
        before_segs = deepcopy(self.segment_manager.segments)
        before_map = deepcopy(self.segment_manager.speaker_map)
        
        self.exit_all_edit_modes()
        
        action_made = False
        num_multi_selected = len(self.multi_selection_ids)
        new_target_id = None

        if num_multi_selected > 1:
            new_target_id = self.segment_manager.merge_multiple_segments(self.multi_selection_ids)
            if new_target_id: action_made = True
        elif self.selected_segment_id and num_multi_selected == 0:
            current_id = self.selected_segment_id
            current_index = self.segment_manager.get_segment_index(current_id)
            if current_index > 0:
                previous_id = self.segment_manager.segments[current_index - 1]['id']
                if self.segment_manager.merge_segment_upwards(current_id):
                    new_target_id = previous_id
                    action_made = True
        
        if action_made:
            def action():
                self._clear_all_selections()
                self.render_segments_to_textarea()
                if new_target_id:
                    self.select_segment(new_target_id)
            
            self._execute_command(before_segs, before_map, action)
             
        self.update_edit_buttons_state()
        
    @Slot()
    def on_timestamp_edit_button_clicked(self):
        if self.timestamp_editing_segment_id: self.exit_timestamp_edit_mode(save=False)
        elif self.selected_segment_id: self.enter_timestamp_edit_mode(self.selected_segment_id)
        
    def _apply_format(self, segment_id, text_format, clear_first=False):
        segment = self.segment_manager.get_segment_by_id(segment_id)
        if segment and 'doc_positions' in segment:
            cursor = QTextCursor(self.main_window.correction_text_area.document())
            start, end = segment['doc_positions']
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, 1) # Exclude newline
            cursor.setCharFormat(text_format)
            
    def set_highlight_color(self, color): self.highlight_format.setBackground(color); self.selection_format.setBackground(color.darker(150)); self.multi_selection_format.setBackground(color.lighter(130))
    def _apply_selection(self, segment_id): self._apply_format(segment_id, self.selection_format)
    
    def _apply_highlight(self, segment_id):
        is_multi = segment_id in self.multi_selection_ids
        if segment_id != self.selected_segment_id and not self.editing_segment_id and not is_multi:
            self._apply_format(segment_id, self.highlight_format)
            
    def _clear_selection(self):
        if self.selected_segment_id: 
            is_highlighted = self.selected_segment_id == self.current_highlighted_segment_id
            is_multi = self.selected_segment_id in self.multi_selection_ids
            revert_format = self.normal_format
            if is_highlighted: revert_format = self.highlight_format
            if is_multi: revert_format = self.multi_selection_format
            
            self._apply_format(self.selected_segment_id, revert_format)

        self.selected_segment_id = None
        
    def _clear_highlight(self):
        if self.current_highlighted_segment_id: 
            is_selected = self.current_highlighted_segment_id == self.selected_segment_id
            is_multi = self.current_highlighted_segment_id in self.multi_selection_ids
            revert_format = self.normal_format
            if is_selected: revert_format = self.selection_format
            if is_multi: revert_format = self.multi_selection_format
            
            self._apply_format(self.current_highlighted_segment_id, revert_format)
        
        self.current_highlighted_segment_id = None

    @Slot()
    def on_edit_speaker_clicked(self): 
        target_ids = []
        if self.selected_segment_id and self.selected_segment_id not in self.multi_selection_ids:
            target_ids = [self.selected_segment_id]
        elif self.multi_selection_ids:
            target_ids = list(self.multi_selection_ids)
        
        if not target_ids:
             QMessageBox.information(self.main_window, "No Selection", "Please select one or more segments to change the speaker.")
             return

        first_segment = self.segment_manager.get_segment_by_id(target_ids[0])
        if not first_segment: return

        self._safe_action(self._open_change_speaker_dialog, first_segment, target_ids)

    def _open_change_speaker_dialog(self, segment, target_ids):
        before_segs = deepcopy(self.segment_manager.segments)
        before_map = deepcopy(self.segment_manager.speaker_map)
        
        dialog = QDialog(self.main_window)
        title = f"Change Speaker for {len(target_ids)} Segment(s)"
        dialog.setWindowTitle(title)
        
        layout = QGridLayout(dialog)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel("Assign a speaker to the selected segment(s):"), 0, 0, 1, 2)
        
        combo = QComboBox()
        combo.addItem("(No Speaker)", constants.NO_SPEAKER_LABEL)
        for speaker_id in sorted(list(self.segment_manager.unique_speaker_labels)): 
            display_name = self.segment_manager.speaker_map.get(speaker_id, speaker_id)
            combo.addItem(f"{display_name} ({speaker_id})", speaker_id)
        layout.addWidget(combo, 1, 0, 1, 2)
        
        current_speaker_index = combo.findData(segment.get("speaker_raw", constants.NO_SPEAKER_LABEL))
        if current_speaker_index != -1: combo.setCurrentIndex(current_speaker_index)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        delete_speaker_button = QPushButton(icon=self.main_window.delete_segment_btn.icon())
        delete_speaker_button.setToolTip("Remove speaker assignment from segment(s)")
        delete_speaker_button.setFixedSize(QSize(32, 32))
        delete_speaker_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        def on_accept(speaker_to_set):
            def action():
                for seg_id in target_ids:
                    self.segment_manager.update_segment_speaker(seg_id, speaker_to_set)
                self.render_segments_to_textarea()
            
            self._execute_command(before_segs, before_map, action)
            dialog.accept()

        button_box.accepted.connect(lambda: on_accept(combo.currentData()))
        button_box.rejected.connect(dialog.reject)
        delete_speaker_button.clicked.connect(lambda: on_accept(constants.NO_SPEAKER_LABEL))
        
        layout.addWidget(delete_speaker_button, 2, 0, Qt.AlignLeft)
        layout.addWidget(button_box, 2, 1, Qt.AlignRight)

        dialog.exec()
            
    def select_segment_by_block(self, block_number):
        if 0 <= block_number < len(self.segment_manager.segments): self.select_segment(self.segment_manager.segments[block_number]['id'])

    @Slot(int, int)
    def on_edit_requested(self, block_number, position_in_block):
        if not (0 <= block_number < len(self.segment_manager.segments)): return
        segment = self.segment_manager.segments[block_number]
        block = self.main_window.correction_text_area.document().findBlockByNumber(block_number); absolute_click_pos = block.position() + position_in_block
        if 'component_positions' in segment:
            positions = segment['component_positions']
            if 'speaker' in positions and positions['speaker'][0] <= absolute_click_pos < positions['speaker'][1]:
                self.select_segment(segment['id']); 
                self._safe_action(self._open_change_speaker_dialog, segment, [segment['id']])
                return
            if 'timestamp' in positions and positions['timestamp'][0] <= absolute_click_pos < positions['timestamp'][1]:
                self.enter_timestamp_edit_mode(segment['id']); 
                return
        
        if self.editing_segment_id and self.editing_segment_id != segment['id']: self.exit_edit_mode(save=True)
        self.enter_edit_mode(segment['id'], position_in_block)
        
    def enter_edit_mode(self, segment_id, click_pos_in_block: int = 0):
        if self.editing_segment_id == segment_id or self.timestamp_editing_segment_id: return
        self.exit_all_edit_modes(save=True)
        
        segment_obj = self.segment_manager.get_segment_by_id(segment_id)
        if not segment_obj: return

        self.original_text_before_edit = segment_obj.get('text')
        self.editing_segment_id = segment_id
        
        block_number = self.segment_manager.get_segment_index(segment_id)
        if block_number == -1: return

        if segment_obj.get('text') == constants.EMPTY_SEGMENT_PLACEHOLDER:
            block = self.main_window.correction_text_area.document().findBlockByNumber(block_number)
            if block.isValid() and 'text' in segment_obj.get('component_positions', {}):
                text_start, text_end = segment_obj['component_positions']['text']
                cursor = QTextCursor(block)
                cursor.setPosition(text_start)
                cursor.setPosition(text_end, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()
                click_pos_in_block = cursor.position() - block.position()

        self.main_window.correction_text_area.enter_edit_mode(block_number, click_pos_in_block)
        self.select_segment(segment_id)
        self.update_edit_buttons_state()

    def exit_edit_mode(self, save=False):
        if not self.editing_segment_id: return
        
        segment_id_to_exit = self.editing_segment_id
        
        if save:
            before_segs = deepcopy(self.segment_manager.segments)
            before_map = deepcopy(self.segment_manager.speaker_map)
            
            block_number = self.segment_manager.get_segment_index(segment_id_to_exit)
            if block_number != -1: 
                line_text = self.main_window.correction_text_area.document().findBlockByNumber(block_number).text()
                self.segment_manager.update_segment_from_full_line(segment_id_to_exit, line_text)

            segment_after_update = self.segment_manager.get_segment_by_id(segment_id_to_exit)
            
            if segment_after_update and self.original_text_before_edit != segment_after_update.get('text'):
                self._execute_command(before_segs, before_map, lambda: self.render_segments_to_textarea())

        self.editing_segment_id = None
        self.original_text_before_edit = None
        self.main_window.correction_text_area.exit_edit_mode()
        
        if not save: self.render_segments_to_textarea()
        
        if self.segment_manager.get_segment_by_id(segment_id_to_exit):
            self.select_segment(segment_id_to_exit)
        else:
            self._clear_all_selections()
            
        self.update_edit_buttons_state()

    @Slot()
    def on_edit_button_clicked(self):
        if self.editing_segment_id:
            self.exit_edit_mode(save=True)
        elif self.selected_segment_id:
            self.enter_edit_mode(self.selected_segment_id)

    def select_segment(self, segment_id):
        if self.selected_segment_id and self.selected_segment_id in self.multi_selection_ids:
             self._apply_format(self.selected_segment_id, self.multi_selection_format)
        else:
            self._clear_selection()

        if segment_id: 
            self._apply_selection(segment_id)
            self.selected_segment_id = segment_id
        else: 
            self.selected_segment_id = None
        
        self.update_edit_buttons_state()
        
    @Slot(str, float)
    def on_timestamp_bar_dragged(self, bar_name, new_time):
        if bar_name == "start": self.timeline.set_start_bar_position(new_time)
        elif bar_name == "playhead": self.audio_player.set_position(new_time)
        
    @Slot()
    def on_save_timestamp_clicked(self): 
        before_segs = deepcopy(self.segment_manager.segments)
        before_map = deepcopy(self.segment_manager.speaker_map)
        self._execute_command(before_segs, before_map, lambda: self.exit_timestamp_edit_mode(save=True))
        
    def exit_all_edit_modes(self, save=False): 
        if self.editing_segment_id: self.exit_edit_mode(save)
        if self.timestamp_editing_segment_id: self.exit_timestamp_edit_mode(False)
        
    def _safe_action(self, action_func, *args): 
        self.exit_all_edit_modes(save=True)
        action_func(*args)
        
    @Slot()
    def save_changes(self): self._safe_action(self._save_changes_action)
    
    def _save_changes_action(self):
        if not self.segment_manager.segments: return
        self.undo_manager.clear()
        path, _=QFileDialog.getSaveFileName(self.main_window, "Save Corrected Transcription", "", "Text Files (*.txt)");
        if path:
            try:
                save_data = self.segment_manager.format_segments_for_saving(True, True)
                with open(path, 'w', encoding='utf-8') as f: 
                    f.write('\n'.join(save_data))
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
        # --- THE FIX ---
        file_filter = (
            "All Media Files (*.wav *.mp3 *.aac *.flac *.m4a *.mp4 *.mov *.avi *.mkv);;"
            "Audio Files (*.wav *.mp3 *.aac *.flac *.m4a);;"
            "Video Files (*.mp4 *.mov *.avi *.mkv);;"
            "All Files (*)"
        )
        path, _ = QFileDialog.getOpenFileName(self.main_window, "Select Audio or Video File", "", file_filter);
        if path: self.main_window.correction_audio_entry.setText(path)
        
    @Slot()
    def open_speaker_assignment_dialog(self): self._safe_action(self._open_speaker_assignment_dialog_action)
    
    def _open_speaker_assignment_dialog_action(self):
        if not self.segment_manager.segments: return
        
        before_segs = deepcopy(self.segment_manager.segments)
        before_map = deepcopy(self.segment_manager.speaker_map)
        
        dialog=QDialog(self.main_window); dialog.setWindowTitle("Assign Speaker Names"); dialog.setMinimumWidth(400); layout=QVBoxLayout(dialog); scroll=QScrollArea(); scroll.setWidgetResizable(True); layout.addWidget(scroll); content=QWidget(); form=QGridLayout(content); entries={}
        for i, label in enumerate(sorted(list(self.segment_manager.unique_speaker_labels))):
            form.addWidget(QLabel(f"<b>{label}:</b>"), i, 0); edit=QLineEdit(self.segment_manager.speaker_map.get(label, "")); form.addWidget(edit, i, 1); entries[label]=edit
        sep_row=len(entries); form.addWidget(QLabel("---<br><b>Add New</b>"), sep_row, 0, 1, 2, Qt.AlignCenter); form.addWidget(QLabel("ID:"), sep_row + 1, 0); id_edit=QLineEdit(); form.addWidget(id_edit, sep_row + 1, 1); form.addWidget(QLabel("Name:"), sep_row + 2, 0); name_edit=QLineEdit(); form.addWidget(name_edit, sep_row + 2, 1)
        scroll.setWidget(content); buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            def action():
                for label, edit in entries.items():
                    if edit.text().strip(): self.segment_manager.speaker_map[label]=edit.text().strip()
                    elif label in self.segment_manager.speaker_map: del self.segment_manager.speaker_map[label]
                new_id=id_edit.text().strip().replace(" ", "_").upper();
                if new_id:
                    self.segment_manager.unique_speaker_labels.add(new_id)
                    if name_edit.text().strip(): self.segment_manager.speaker_map[new_id] = name_edit.text().strip()
                self.render_segments_to_textarea()
                self.main_window.correction_text_area.setFocus()
            
            self._execute_command(before_segs, before_map, action)

    @Slot()
    def open_change_highlight_color_dialog(self): self._safe_action(self._open_change_highlight_color_dialog_action)
    def _open_change_highlight_color_dialog_action(self):
        new_color=QColorDialog.getColor(self.highlight_format.background().color(), self.main_window, "Select Highlight Color");
        if new_color.isValid(): self.set_highlight_color(new_color);
        if self.current_highlighted_segment_id: self._apply_highlight(self.current_highlighted_segment_id)
        
    def set_controls_enabled(self, enabled):
        widgets=[self.main_window.correction_play_pause_btn, self.main_window.correction_rewind_btn, self.main_window.correction_forward_btn, self.main_window.correction_assign_speakers_btn, self.main_window.correction_save_changes_btn, self.main_window.correction_timeline_frame, self.main_window.change_highlight_color_btn]
        for w in widgets:
            if w: w.setEnabled(enabled)
        if not enabled:
            for btn in [self.main_window.correction_text_edit_btn, self.main_window.edit_speaker_btn,
                        self.main_window.correction_timestamp_edit_btn, self.main_window.save_timestamp_btn,
                        self.main_window.delete_segment_btn, self.main_window.segment_btn, 
                        self.main_window.merge_segments_btn]:
                 if btn: btn.setEnabled(False)
        else:
             self.update_edit_buttons_state()
             
    @Slot(bool)
    def update_play_button_state(self, playing):
        if playing: self.main_window.correction_play_pause_btn.setText("Pause"); self.main_window.correction_play_pause_btn.setIcon(self.main_window.icon_pause)
        else: self.main_window.correction_play_pause_btn.setText("Play"); self.main_window.correction_play_pause_btn.setIcon(self.main_window.icon_play)
        
    @Slot()
    def on_audio_finished(self): 
        self._clear_highlight(); 
        self.current_highlighted_segment_id=None
        if self.selected_segment_id:
            self._apply_selection(self.selected_segment_id)

    @Slot(float)
    def update_audio_progress(self, current_time):
        duration = self.audio_player.get_duration()
        if duration > 0:
            self.main_window.correction_time_label.setText(f"{self.format_time(current_time)} / {self.format_time(duration)}")
            if hasattr(self.main_window, 'monospace_font'):
                self.main_window.correction_time_label.setFont(self.main_window.monospace_font)
            self.timeline.set_progress(current_time)
            self._update_text_highlight(current_time)

    def _update_text_highlight(self, current_time):
        active_id = None
        if self.audio_player.get_duration() > 0:
            for i, seg in enumerate(self.segment_manager.segments):
                if not seg.get("has_timestamps"): continue
                start_time=seg.get('start_time', -1)
                
                end_time = seg.get('end_time')
                if end_time is None:
                    is_last_segment = (i + 1) >= len(self.segment_manager.segments)
                    if not is_last_segment and self.segment_manager.segments[i + 1].get('has_timestamps'):
                        end_time = self.segment_manager.segments[i+1].get('start_time')
                    else:
                        end_time = self.audio_player.get_duration()
                
                if end_time is not None and start_time <= current_time < end_time:
                    active_id = seg['id']
                    break

        if self.current_highlighted_segment_id != active_id:
            old_highlight_id = self.current_highlighted_segment_id
            self.current_highlighted_segment_id = active_id
            
            if old_highlight_id:
                is_selected = old_highlight_id == self.selected_segment_id
                is_multi = old_highlight_id in self.multi_selection_ids
                if is_selected: self._apply_selection(old_highlight_id)
                elif is_multi: self._apply_format(old_highlight_id, self.multi_selection_format)
                else: self._apply_format(old_highlight_id, self.normal_format)

            if active_id:
                self._apply_highlight(active_id)
    
    @Slot()
    def seek_by_offset(self, offset_seconds): self.audio_player.seek(offset_seconds)
    @Slot(float)
    def seek_to_percentage(self, percentage):
        if self.audio_player.get_duration() > 0: self.audio_player.set_position(percentage * self.audio_player.get_duration())
    @Slot(str, str)
    def load_files_from_paths(self, audio_path: str, txt_path: str):
        """A convenience slot to be called from the main window."""
        if not os.path.exists(audio_path) or not os.path.exists(txt_path):
            QMessageBox.critical(self.main_window, "File Not Found", 
                                 f"Could not find one of the required files:\nAudio: {audio_path}\nText: {txt_path}")
            return
            
        # Set the text of the QLineEdit widgets
        self.main_window.correction_audio_entry.setText(audio_path)
        self.main_window.correction_transcription_entry.setText(txt_path)
        
        # Now, call the existing load function which reads from the line edits
        self.load_files()
    def format_time(self, seconds): 
        m, s = divmod(abs(seconds), 60)
        return f"{int(m):02d}:{s:06.3f}"
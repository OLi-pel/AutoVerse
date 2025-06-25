# ui/correction_view_logic.py
import logging, sys, os
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QVBoxLayout, QColorDialog, QDialog, 
                               QDialogButtonBox, QLabel, QLineEdit, QGridLayout, QScrollArea, QWidget, QTextEdit)
from PySide6.QtCore import QObject, Slot, Qt
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QMouseEvent

current_dir = os.path.dirname(os.path.abspath(__file__)); project_root = os.path.dirname(current_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)
from core.correction_window_logic import SegmentManager; from core.audio_player import AudioPlayer
from utils import constants; from ui.timeline_frame import WaveformFrame; from ui.selectable_text_edit import SelectableTextEdit
logger = logging.getLogger(__name__)

class CorrectionViewLogic(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window; self.segment_manager = SegmentManager()
        self.audio_player = AudioPlayer(); self.selected_segment_id = None
        self.current_highlighted_segment_id = None; self.editing_segment_id = None
        self.normal_format = QTextCharFormat(); self.highlight_format = QTextCharFormat(); self.selection_format = QTextCharFormat()
        self.set_highlight_color(QColor("darkblue")); self.selection_format.setBackground(QColor("#B4D5FF"))
        self.timeline = WaveformFrame(); old_frame = self.main_window.correction_timeline_frame
        layout = old_frame.layout() or QVBoxLayout(old_frame)
        if not old_frame.layout(): old_frame.setLayout(layout)
        layout.setContentsMargins(0,0,0,0)
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        layout.addWidget(self.timeline)
        if self.main_window.correction_text_area: self.main_window.correction_text_area.installEventFilter(self)
        self.connect_signals(); self.set_controls_enabled(False)
        # --- FIX: Removed the incorrect keyword argument ---
        self.update_edit_buttons_state()

    def eventFilter(self, watched, event):
        if watched == self.main_window.correction_text_area and event.type() == QMouseEvent.Type.MouseButtonPress:
            return self.handle_text_area_click(event)
        return super().eventFilter(watched, event)
    
    def connect_signals(self):
        textarea = self.main_window.correction_text_area
        if textarea:
            textarea.segment_clicked.connect(self.on_segment_clicked)
            textarea.edit_requested.connect(self.on_edit_requested)
            textarea.focusOutEvent = lambda event: self.exit_edit_mode(save=True) if self.editing_segment_id else None
        
        self.main_window.correction_browse_transcription_btn.clicked.connect(lambda: self.safe_action(self.browse_transcription_file))
        self.main_window.correction_browse_audio_btn.clicked.connect(lambda: self.safe_action(self.browse_audio_file))
        self.main_window.correction_load_files_btn.clicked.connect(lambda: self.safe_action(self.load_files))
        self.main_window.correction_assign_speakers_btn.clicked.connect(lambda: self.safe_action(self.open_speaker_assignment_dialog))
        if self.main_window.change_highlight_color_btn: self.main_window.change_highlight_color_btn.clicked.connect(lambda: self.safe_action(self.open_change_highlight_color_dialog))
        if self.main_window.correction_text_edit_btn: self.main_window.correction_text_edit_btn.clicked.connect(self.on_edit_button_clicked)
        
        self.main_window.correction_play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.main_window.correction_rewind_btn.clicked.connect(lambda: self.seek_by_offset(-5.0))
        self.main_window.correction_forward_btn.clicked.connect(lambda: self.seek_by_offset(5.0))
        self.timeline.seek_requested.connect(self.seek_to_percentage)
        self.audio_player.progress.connect(self.update_audio_progress)
        self.audio_player.finished.connect(self.on_audio_finished)
        self.audio_player.error.connect(lambda msg: QMessageBox.critical(self.main_window, "Audio Player Error", msg))
        self.audio_player.state_changed.connect(self.update_play_button_state)

    def handle_text_area_click(self, event: QMouseEvent):
        if self.editing_segment_id:
            cursor = self.main_window.correction_text_area.cursorForPosition(event.pos())
            if self.segment_manager.get_segment_index(self.editing_segment_id) != cursor.blockNumber():
                self.exit_edit_mode(save=True)
                return True 
        self.main_window.correction_text_area.mousePressEvent(event)
        return True 

    def safe_action(self, action_func, *args, **kwargs):
        if self.editing_segment_id: self.exit_edit_mode(save=True)
        action_func(*args, **kwargs)

    def enter_edit_mode(self, segment_id, click_pos_in_block: int = 0):
        if self.editing_segment_id: return
        self.editing_segment_id = segment_id
        logger.info(f"Entering edit mode for {segment_id}")
        self.select_segment(segment_id)
        block_number = self.segment_manager.get_segment_index(segment_id)
        if block_number != -1: self.main_window.correction_text_area.enter_edit_mode(block_number)
        
    def exit_edit_mode(self, save=False):
        if not self.editing_segment_id: return
        segment_id_to_exit = self.editing_segment_id
        if save:
            block_number = self.segment_manager.get_segment_index(segment_id_to_exit)
            if block_number != -1:
                new_line_text = self.main_window.correction_text_area.document().findBlockByNumber(block_number).text()
                self.segment_manager.update_segment_from_full_line(segment_id_to_exit, new_line_text)
        
        self.editing_segment_id = None
        self.main_window.correction_text_area.exit_edit_mode()
        self.render_segments_to_textarea()
        self.select_segment(segment_id_to_exit)

    @Slot(int)
    def on_segment_clicked(self, block_number):
        if 0 <= block_number < len(self.segment_manager.segments): self.select_segment(self.segment_manager.segments[block_number]['id'])
        else: self.safe_action(self.select_segment, None)

    @Slot(int, int)
    def on_edit_requested(self, block_number, position_in_block):
        if 0 <= block_number < len(self.segment_manager.segments):
            self.enter_edit_mode(self.segment_manager.segments[block_number]['id'], position_in_block)

    @Slot()
    def on_edit_button_clicked(self):
        if self.editing_segment_id: self.exit_edit_mode(save=True)
        elif self.selected_segment_id: self.enter_edit_mode(self.selected_segment_id)
            
    def select_segment(self, segment_id):
        if self.selected_segment_id == segment_id: return
        self._clear_selection();
        if segment_id: self._apply_selection(segment_id); self.selected_segment_id = segment_id
        self.update_edit_buttons_state()
        
    def update_edit_buttons_state(self):
        is_editing = self.editing_segment_id is not None
        is_selected = self.selected_segment_id is not None
        edit_button = self.main_window.correction_text_edit_btn
        if edit_button:
            edit_button.setEnabled(is_editing or is_selected)
            if is_editing: edit_button.setIcon(self.main_window.icon_save_edit); edit_button.setToolTip("Save Changes")
            else: edit_button.setIcon(self.main_window.icon_edit_text); edit_button.setToolTip("Edit Selected Segment")
        for w in [self.main_window.edit_speaker_btn, self.main_window.correction_timestamp_edit_btn]:
            if w: w.setEnabled(is_selected and not is_editing)
        is_action_safe = not is_editing
        for w in [self.main_window.correction_load_files_btn, self.main_window.correction_browse_audio_btn, 
                  self.main_window.correction_browse_transcription_btn, self.main_window.correction_assign_speakers_btn,
                  self.main_window.change_highlight_color_btn]:
            if w: w.setEnabled(is_action_safe)
    
    # ... Rest of the file remains the same ...
    def _clear_selection(self):
        if self.selected_segment_id:
            is_highlighted = self.selected_segment_id == self.current_highlighted_segment_id
            self._apply_format(self.selected_segment_id, self.highlight_format if is_highlighted else self.normal_format)
        self.selected_segment_id = None
    def _apply_selection(self, segment_id): self._apply_format(segment_id, self.selection_format)
    def _apply_highlight(self, segment_id):
        if segment_id != self.selected_segment_id and not self.editing_segment_id: self._apply_format(segment_id, self.highlight_format)
    def _apply_format(self, segment_id, text_format):
        segment = self.segment_manager.get_segment_by_id(segment_id)
        if segment and 'doc_positions' in segment:
            cursor = QTextCursor(self.main_window.correction_text_area.document()); cursor.setPosition(segment['doc_positions'][0]); cursor.setPosition(segment['doc_positions'][1] -1, QTextCursor.MoveMode.KeepAnchor)
            cursor.setCharFormat(text_format)
    def set_highlight_color(self, color): self.highlight_format.setBackground(color)
    @Slot()
    def open_change_highlight_color_dialog(self): self._open_change_highlight_color_dialog_action()
    def _open_change_highlight_color_dialog_action(self):
        new_color = QColorDialog.getColor(self.highlight_format.background().color(), self.main_window, "Select Highlight Color");
        if new_color.isValid(): self.set_highlight_color(new_color);
        if self.current_highlighted_segment_id: self._apply_highlight(self.current_highlighted_segment_id)
    @Slot()
    def open_speaker_assignment_dialog(self):
        if not self.segment_manager.segments: QMessageBox.information(self.main_window, "No Segments", "Please load a transcription file first."); return
        dialog = QDialog(self.main_window); dialog.setWindowTitle("Assign Speaker Names"); dialog.setMinimumWidth(400); layout = QVBoxLayout(dialog)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); layout.addWidget(scroll); content = QWidget(); form = QGridLayout(content)
        entries = {}
        for i, label in enumerate(sorted(list(self.segment_manager.unique_speaker_labels))):
            form.addWidget(QLabel(f"<b>{label}:</b>"), i, 0); edit = QLineEdit(self.segment_manager.speaker_map.get(label, "")); form.addWidget(edit, i, 1); entries[label] = edit
        sep_row = len(entries); form.addWidget(QLabel("---<br><b>Add New</b>"), sep_row, 0, 1, 2, Qt.AlignCenter)
        form.addWidget(QLabel("ID:"), sep_row + 1, 0); id_edit = QLineEdit(); form.addWidget(id_edit, sep_row + 1, 1)
        form.addWidget(QLabel("Name:"), sep_row + 2, 0); name_edit = QLineEdit(); form.addWidget(name_edit, sep_row + 2, 1)
        scroll.setWidget(content); buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted:
            for label, edit in entries.items():
                if edit.text().strip(): self.segment_manager.speaker_map[label] = edit.text().strip()
                elif label in self.segment_manager.speaker_map: del self.segment_manager.speaker_map[label]
            new_id = id_edit.text().strip().replace(" ", "_").upper();
            if new_id: self.segment_manager.unique_speaker_labels.add(new_id)
            if new_id and name_edit.text().strip(): self.segment_manager.speaker_map[new_id] = name_edit.text().strip()
            self.render_segments_to_textarea()
    def set_controls_enabled(self, enabled):
        widgets = [self.main_window.correction_play_pause_btn, self.main_window.correction_rewind_btn, self.main_window.correction_forward_btn,
                   self.main_window.correction_assign_speakers_btn, self.main_window.correction_save_changes_btn,
                   self.main_window.correction_timeline_frame, self.main_window.change_highlight_color_btn];
        for w in widgets:
            if w: w.setEnabled(enabled)
        self.update_edit_buttons_state()
    def browse_transcription_file(self):
        path, _ = QFileDialog.getOpenFileName(self.main_window, "Select Transcription", "", "Text (*.txt)");
        if path: self.main_window.correction_transcription_entry.setText(path)
    def browse_audio_file(self):
        path, _ = QFileDialog.getOpenFileName(self.main_window, "Select Audio", "", "Audio (*.wav *.mp3)");
        if path: self.main_window.correction_audio_entry.setText(path)
    @Slot()
    def load_files(self):
        self.exit_edit_mode(save=False)
        txt, audio = self.main_window.correction_transcription_entry.text(), self.main_window.correction_audio_entry.text()
        if not txt or not audio: QMessageBox.warning(self.main_window, "Error", "Select files."); return
        try:
            self.select_segment(None);
            with open(txt, 'r', encoding='utf-8') as f: lines = f.readlines()
            self.segment_manager.parse_transcription_lines(lines); self.render_segments_to_textarea()
            if not self.audio_player.load_file(audio): raise IOError("Audio could not be loaded.")
            self.timeline.set_waveform_data(self.audio_player.get_normalized_waveform()); self.timeline.set_duration(self.audio_player.get_duration())
            self.update_audio_progress(0); self.set_controls_enabled(True); self.update_play_button_state(playing=False)
        except Exception as e: logger.exception("Load error."); self.set_controls_enabled(False); QMessageBox.critical(self.main_window, "Load Error", str(e))
    @Slot(bool)
    def update_play_button_state(self, playing):
        if playing: self.main_window.correction_play_pause_btn.setText("Pause"); self.main_window.correction_play_pause_btn.setIcon(self.main_window.icon_pause)
        else: self.main_window.correction_play_pause_btn.setText("Play"); self.main_window.correction_play_pause_btn.setIcon(self.main_window.icon_play)
    @Slot()
    def toggle_play_pause(self):
        if self.audio_player.is_playing: self.audio_player.pause()
        else: self.audio_player.play()
    @Slot()
    def on_audio_finished(self): self._clear_highlight()
    @Slot(float)
    def update_audio_progress(self, current_time):
        duration = self.audio_player.get_duration()
        self.main_window.correction_time_label.setText(f"{self.format_time(current_time)} / {self.format_time(duration)}")
        self.main_window.correction_time_label.setFont(self.main_window.monospace_font)
        self.timeline.set_progress(current_time); self._update_text_highlight(current_time)
    def _update_text_highlight(self, current_time):
        active_id = None
        for i, seg in enumerate(self.segment_manager.segments):
            if not seg.get("has_timestamps"): continue
            start, end = seg.get('start_time', -1), seg.get('end_time') or (self.segment_manager.segments[i+1].get('start_time') if (i+1) < len(self.segment_manager.segments) and self.segment_manager.segments[i+1].get('start_time') is not None else self.audio_player.get_duration())
            if start <= current_time < end: active_id = seg['id']; break
        if self.current_highlighted_segment_id != active_id:
            self._clear_highlight();
            if active_id: self._apply_highlight(active_id)
            self.current_highlighted_segment_id = active_id
    @Slot()
    def seek_by_offset(self, offset_seconds): self.audio_player.seek(offset_seconds)
    @Slot(float)
    def seek_to_percentage(self, percentage): self.audio_player.set_position(percentage * self.audio_player.get_duration())
    def format_time(self, seconds): minutes = int(seconds // 60); return f"{minutes:02d}:{(seconds % 60):06.3f}"
    def render_segments_to_textarea(self):
        textarea = self.main_window.correction_text_area; textarea.clear()
        self.current_highlighted_segment_id = None; self.selected_segment_id = None
        self.update_edit_buttons_state()
        if not self.segment_manager.segments: textarea.setPlainText("No segments loaded."); return
        cursor = QTextCursor(textarea.document())
        for seg in self.segment_manager.segments:
            start_pos = cursor.position(); line = ""
            if seg.get("has_timestamps"): line += f"[{self.segment_manager.seconds_to_time_str(seg['start_time'])}] "
            speaker_label = seg.get("speaker_raw", constants.NO_SPEAKER_LABEL)
            if speaker_label != constants.NO_SPEAKER_LABEL: line += f"{self.segment_manager.speaker_map.get(speaker_label, speaker_label)}: "
            line += seg['text']; cursor.insertText(line + '\n', self.normal_format)
            end_pos = cursor.position(); seg['doc_positions'] = (start_pos, end_pos)
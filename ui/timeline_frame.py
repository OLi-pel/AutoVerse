# ui/timeline_frame.py
from PySide6.QtWidgets import QFrame
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent

class WaveformFrame(QFrame):
    seek_requested = Signal(float)
    # --- NEW: Signal to report when a bar is dragged by the user ---
    bar_dragged = Signal(str, float) # Emits bar_name ("start" or "playhead") and new_time (in seconds)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        self.setMinimumHeight(60)
        
        self._waveform_data = []
        self._duration = 1.0
        self._progress = 0.0

        self.edit_mode_active = False
        self.start_bar_pos_secs = 0.0
        self._dragging_bar = None # None, "start", or "playhead"

        # Colors
        self.wave_color = QColor("#909090")
        self.progress_color = QColor("#0078d4")
        self.cursor_color = QColor("#d13438")
        self.background_color = QColor("#595656")
        self.start_bar_color = QColor(Qt.cyan)
        self.amplitude_scale = 4.5

    def set_waveform_data(self, data):
        self._waveform_data = data; self.update()
    def set_duration(self, duration_seconds):
        self._duration = max(1.0, duration_seconds); self.update()
    def set_progress(self, progress_seconds):
        self._progress = max(0.0, min(progress_seconds, self._duration)); self.update()

    # --- Methods to control edit mode ---
    def enter_edit_mode(self, start_seconds):
        self.edit_mode_active = True
        self.start_bar_pos_secs = start_seconds
        self.update()

    def exit_edit_mode(self):
        self.edit_mode_active = False
        self._dragging_bar = None
        self.update()
        
    def set_start_bar_position(self, seconds):
        if self._duration > 0:
            self.start_bar_pos_secs = max(0.0, min(seconds, self._duration))
            self.update()

    # --- Drawing and Interaction ---
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.background_color)
        if not self._waveform_data or self._duration <= 0: painter.end(); return

        w = self.width(); h = self.height(); h_half = h // 2
        data_len = len(self._waveform_data)
        
        def get_scaled_line_height(sample_value):
            return max(-h_half, min(sample_value * h_half * self.amplitude_scale, h_half))

        # Base waveform
        painter.setPen(QPen(self.wave_color, 1))
        for i in range(w):
            data_index = int((i / w) * data_len)
            if 0 <= data_index < data_len:
                sample = self._waveform_data[data_index]
                line_height = get_scaled_line_height(sample)
                painter.drawLine(i, int(h_half - line_height), i, int(h_half + line_height))

        # Progress overlay
        progress_x = int((self._progress / self._duration) * w)
        painter.setPen(QPen(self.progress_color, 1))
        for i in range(progress_x):
            data_index = int((i / w) * data_len)
            if 0 <= data_index < data_len:
                sample = self._waveform_data[data_index]
                line_height = get_scaled_line_height(sample)
                painter.drawLine(i, int(h_half - line_height), i, int(h_half + line_height))

        # Playhead (always drawn)
        painter.setPen(QPen(self.cursor_color, 2)); painter.drawLine(progress_x, 0, progress_x, h)
        
        # Start bar (only in edit mode)
        if self.edit_mode_active:
            start_x = int((self.start_bar_pos_secs / self._duration) * w)
            painter.setPen(QPen(self.start_bar_color, 2, Qt.DashLine))
            painter.drawLine(start_x, 0, start_x, h)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton: return

        if self.edit_mode_active:
            click_x = event.position().x()
            sensitivity = 8  # Click sensitivity in pixels
            
            # Check proximity to start bar first
            start_x = int((self.start_bar_pos_secs / self._duration) * self.width())
            if abs(click_x - start_x) <= sensitivity:
                self._dragging_bar = "start"
                self._handle_drag(event.position().x()) # Immediately update on click
                return

            # Check proximity to playhead
            playhead_x = int((self._progress / self._duration) * self.width())
            if abs(click_x - playhead_x) <= sensitivity:
                self._dragging_bar = "playhead"
                self._handle_drag(event.position().x()) # Immediately update on click
                return
        else:
            # If not in edit mode, default to seeking
            self._handle_seek(event.position().x())

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton): return
        
        if self._dragging_bar:
            self._handle_drag(event.position().x())
        elif not self.edit_mode_active:
            self._handle_seek(event.position().x())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging_bar = None

    def _handle_drag(self, x_pos):
        if not self._dragging_bar or self._duration <= 0: return
        new_time = max(0.0, min((x_pos / self.width()) * self._duration, self._duration))
        self.bar_dragged.emit(self._dragging_bar, new_time)

    def _handle_seek(self, x_pos):
        if self._duration > 0:
            seek_percentage = max(0.0, min(1.0, x_pos / self.width()))
            self.seek_requested.emit(seek_percentage)
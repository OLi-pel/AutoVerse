# ui/timeline_frame.py
from PySide6.QtWidgets import QFrame
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent

class WaveformFrame(QFrame):
    seek_requested = Signal(float)
    bar_dragged = Signal(str, float)

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
        self._dragging_bar = None

        # --- Updated Colors for Dark Theme ---
        self.wave_color = QColor("#00b7c3")       # Teal/Cyan (Modern tech feel)
        self.progress_color = QColor("#ffffff")   # White for the part already played
        self.cursor_color = QColor("#ffaa00")     # Bright Orange playhead cursor
        self.background_color = QColor("#1e1e1e") # Dark Grey background
        self.start_bar_color = QColor("#ff00ff")  # Magenta for timestamp editing
        
        self.amplitude_scale = 4.5

    def set_waveform_data(self, data):
        self._waveform_data = data; self.update()
    def set_duration(self, duration_seconds):
        self._duration = max(1.0, duration_seconds); self.update()
    def set_progress(self, progress_seconds):
        self._progress = max(0.0, min(progress_seconds, self._duration)); self.update()

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

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self); painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.background_color)
        if not self._waveform_data or self._duration <= 0: painter.end(); return

        w = self.width(); h = self.height(); h_half = h // 2
        data_len = len(self._waveform_data)
        
        def get_scaled_line_height(sample_value):
            return max(-h_half, min(sample_value * h_half * self.amplitude_scale, h_half))

        # Draw the "future" wave (unplayed)
        painter.setPen(QPen(self.wave_color, 1))
        for i in range(w):
            data_index = int((i / w) * data_len)
            if 0 <= data_index < data_len:
                line_height = get_scaled_line_height(self._waveform_data[data_index])
                painter.drawLine(i, int(h_half - line_height), i, int(h_half + line_height))

        # Draw the "past" wave (played) over the top
        progress_x = int((self._progress / self._duration) * w)
        painter.setPen(QPen(self.progress_color, 1))
        for i in range(progress_x):
            data_index = int((i / w) * data_len)
            if 0 <= data_index < data_len:
                line_height = get_scaled_line_height(self._waveform_data[data_index])
                painter.drawLine(i, int(h_half - line_height), i, int(h_half + line_height))

        # Draw Playhead
        painter.setPen(QPen(self.cursor_color, 2)); painter.drawLine(progress_x, 0, progress_x, h)
        
        # Draw Edit Mode Marker (if active)
        if self.edit_mode_active:
            start_x = int((self.start_bar_pos_secs / self._duration) * w)
            painter.setPen(QPen(self.start_bar_color, 2, Qt.DashLine))
            painter.drawLine(start_x, 0, start_x, h)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton: return

        click_x = event.position().x()
        sensitivity = 8
        self._dragging_bar = None
        
        if self.edit_mode_active:
            start_x = int((self.start_bar_pos_secs / self._duration) * self.width())
            if abs(click_x - start_x) <= sensitivity:
                self._dragging_bar = "start"
                self.bar_dragged.emit("start", self._time_from_x(click_x))
                return

        playhead_x = int((self._progress / self._duration) * self.width())
        if abs(click_x - playhead_x) <= sensitivity:
            self._dragging_bar = "playhead"
            self.bar_dragged.emit("playhead", self._time_from_x(click_x))
            return

        self.seek_requested.emit(self._percentage_from_x(click_x))

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.LeftButton) or not self._dragging_bar:
            return
        
        if self._dragging_bar == "start":
            self.bar_dragged.emit("start", self._time_from_x(event.position().x()))
        elif self._dragging_bar == "playhead":
            self.bar_dragged.emit("playhead", self._time_from_x(event.position().x()))

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._dragging_bar = None

    def _percentage_from_x(self, x):
        return max(0.0, min(1.0, x / self.width()))
    
    def _time_from_x(self, x):
        return self._percentage_from_x(x) * self._duration
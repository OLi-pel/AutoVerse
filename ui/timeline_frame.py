# ui/timeline_frame.py
from PySide6.QtWidgets import QFrame
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPainter, QColor, QPen

class WaveformFrame(QFrame):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        self.setMinimumHeight(60)
        
        self._waveform_data = []
        self._duration = 1.0
        self._progress = 0.0

        # --- VISUAL ADJUSTMENTS ---
        self.wave_color = QColor("#909090")      # Slightly darker for better contrast on gray
        self.progress_color = QColor("#0078d4")
        self.cursor_color = QColor("#d13438")
        self.background_color = QColor("#595656") # New gray background color
        self.amplitude_scale = 1.5               # New amplitude scaling factor (1.0 is original)
        # --- END OF ADJUSTMENTS ---

    def set_waveform_data(self, data):
        self._waveform_data = data
        self.update()

    def set_duration(self, duration_seconds):
        self._duration = max(1.0, duration_seconds)
        self.update()

    def set_progress(self, progress_seconds):
        self._progress = max(0.0, min(progress_seconds, self._duration))
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.background_color)

        if not self._waveform_data:
            painter.end()
            return

        w = self.width()
        h = self.height()
        h_half = h // 2

        if w <= 0:
            painter.end()
            return
            
        painter.setPen(QPen(self.wave_color, 1))
        data_len = len(self._waveform_data)
        
        # A helper function to avoid repeating the amplitude logic
        def get_scaled_line_height(sample_value):
            scaled_height = sample_value * h_half * self.amplitude_scale
            # Clamp the height to ensure it never draws outside the widget bounds
            return max(-h_half, min(scaled_height, h_half))

        # Draw base waveform by mapping pixels to data points
        for i in range(w):
            data_index = int((i / w) * data_len)
            if 0 <= data_index < data_len:
                sample = self._waveform_data[data_index]
                line_height = get_scaled_line_height(sample)
                painter.drawLine(i, int(h_half - line_height), i, int(h_half + line_height))

        # Draw progress overlay
        if self._duration > 0:
            progress_x = min(int((self._progress / self._duration) * w), w)
            
            painter.setPen(QPen(self.progress_color, 1))
            for i in range(progress_x):
                data_index = int((i / w) * data_len)
                if 0 <= data_index < data_len:
                    sample = self._waveform_data[data_index]
                    line_height = get_scaled_line_height(sample)
                    painter.drawLine(i, int(h_half - line_height), i, int(h_half + line_height))

            # Draw playback cursor
            painter.setPen(QPen(self.cursor_color, 2))
            cursor_pos = min(progress_x, w - 1)
            painter.drawLine(cursor_pos, 0, cursor_pos, h)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._handle_seek(event.position().x())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._handle_seek(event.position().x())

    def _handle_seek(self, x_pos):
        seek_percentage = max(0.0, min(1.0, x_pos / self.width()))
        self.seek_requested.emit(seek_percentage)
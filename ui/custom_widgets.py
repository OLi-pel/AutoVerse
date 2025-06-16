# ui/custom_widgets.py (New File)

import logging
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QColor, QPen, QBrush

logger = logging.getLogger(__name__)

class AudioTimeline(QWidget):
    """
    A custom widget to display and interact with an audio timeline.
    
    This widget is responsible for drawing:
    - The main playback head position.
    - Draggable bars for setting segment start and end times.
    - Handling mouse clicks and drags to seek audio or move the bars.
    
    Signals:
        seek_requested(float): Emitted when the user clicks on the timeline to
                               seek to a specific position (value is in seconds).
        playback_head_dragged(float): Emitted when the user drags the main
                                       playback head (value is in seconds).
        start_bar_dragged(float): Emitted when the user drags the start time bar.
        end_bar_dragged(float): Emitted when the user drags the end time bar.
        drag_finished(): Emitted when any drag operation is completed.
    """
    # Define signals that will be emitted by this widget
    seek_requested = Signal(float)
    playback_head_dragged = Signal(float)
    start_bar_dragged = Signal(float)
    end_bar_dragged = Signal(float)
    drag_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(30) # Ensure the widget has a reasonable height
        
        # --- State Variables ---
        self._audio_duration_sec = 0.0
        self._current_playback_sec = 0.0
        self._start_bar_sec = None
        self._end_bar_sec = None
        
        # --- Dragging State ---
        self._dragging_bar = None # Can be 'playback', 'start', or 'end'
        self._click_sensitivity = 8 # Pixels of tolerance for clicking on a bar

        # --- Appearance ---
        self.background_color = QColor("#E0E0E0")
        self.playback_bar_color = QColor("#E91E63") # A vibrant pink/red
        self.start_bar_color = QColor("#4CAF50")    # Green
        self.end_bar_color = QColor("#2196F3")      # Blue
        self.bar_width = 3

        # Enable mouse tracking to get mouse move events even when no button is pressed
        self.setMouseTracking(True)
        
    # --- Public Methods to Update State ---

    def set_audio_duration(self, duration_seconds: float):
        """Sets the total duration of the audio file."""
        self._audio_duration_sec = max(0.0, duration_seconds)
        self.update() # Trigger a repaint

    def set_playback_position(self, position_seconds: float):
        """Updates the position of the main playback head."""
        if self._audio_duration_sec > 0:
            self._current_playback_sec = max(0.0, min(position_seconds, self._audio_duration_sec))
        else:
            self._current_playback_sec = 0.0
        self.update()

    def set_selection_bars(self, start_seconds: float | None, end_seconds: float | None):
        """Sets the positions of the start and end selection bars."""
        self._start_bar_sec = start_seconds
        self._end_bar_sec = end_seconds
        self.update()

    # --- Coordinate Conversion ---

    def _time_to_x(self, seconds: float) -> int:
        """Converts a time in seconds to a horizontal pixel coordinate."""
        if self._audio_duration_sec <= 0:
            return 0
        proportion = seconds / self._audio_duration_sec
        return int(proportion * self.width())

    def _x_to_time(self, x_coord: int) -> float:
        """Converts a horizontal pixel coordinate to a time in seconds."""
        if self.width() <= 0:
            return 0.0
        proportion = x_coord / self.width()
        return proportion * self._audio_duration_sec

    # --- Paint Event (Drawing Logic) ---

    def paintEvent(self, event):
        """This method is called by Qt whenever the widget needs to be redrawn."""
        painter = QPainter(self)
        
        # 1. Draw the background
        painter.fillRect(self.rect(), self.background_color)
        
        if self._audio_duration_sec <= 0:
            painter.end()
            return
            
        # 2. Draw the start/end selection range (if applicable)
        if self._start_bar_sec is not None and self._end_bar_sec is not None:
            start_x = self._time_to_x(self._start_bar_sec)
            end_x = self._time_to_x(self._end_bar_sec)
            selection_rect = QRect(QPoint(start_x, 0), QPoint(end_x, self.height()))
            selection_color = self.start_bar_color.lighter(180) # Very light green
            selection_color.setAlpha(100) # Semi-transparent
            painter.fillRect(selection_rect, selection_color)

        # 3. Draw the vertical bars
        pen = QPen()
        pen.setWidth(self.bar_width)

        # Draw start bar
        if self._start_bar_sec is not None:
            pen.setColor(self.start_bar_color)
            painter.setPen(pen)
            start_x = self._time_to_x(self._start_bar_sec)
            painter.drawLine(start_x, 0, start_x, self.height())

        # Draw end bar
        if self._end_bar_sec is not None:
            pen.setColor(self.end_bar_color)
            painter.setPen(pen)
            end_x = self._time_to_x(self._end_bar_sec)
            painter.drawLine(end_x, 0, end_x, self.height())
            
        # Draw playback head (on top)
        pen.setColor(self.playback_bar_color)
        painter.setPen(pen)
        playback_x = self._time_to_x(self._current_playback_sec)
        painter.drawLine(playback_x, 0, playback_x, self.height())
        
        painter.end()
        
    # --- Mouse Events ---

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._audio_duration_sec <= 0:
            return
        
        click_x = event.pos().x()
        
        # Check if the click is near a draggable bar (in order of priority)
        if self._start_bar_sec is not None and abs(click_x - self._time_to_x(self._start_bar_sec)) <= self._click_sensitivity:
            self._dragging_bar = 'start'
        elif self._end_bar_sec is not None and abs(click_x - self._time_to_x(self._end_bar_sec)) <= self._click_sensitivity:
            self._dragging_bar = 'end'
        elif abs(click_x - self._time_to_x(self._current_playback_sec)) <= self._click_sensitivity:
            self._dragging_bar = 'playback'
        else:
            # If not near a bar, it's a seek request
            self._dragging_bar = None
            seek_time = self._x_to_time(click_x)
            self.seek_requested.emit(seek_time)

    def mouseMoveEvent(self, event):
        if self._dragging_bar is not None:
            # If we are dragging a bar, emit the corresponding signal
            drag_time = self._x_to_time(event.pos().x())
            if self._dragging_bar == 'start':
                self.start_bar_dragged.emit(drag_time)
            elif self._dragging_bar == 'end':
                self.end_bar_dragged.emit(drag_time)
            elif self._dragging_bar == 'playback':
                self.playback_head_dragged.emit(drag_time)
        else:
            # Change cursor to hand if hovering over a bar
            pos_x = event.pos().x()
            on_bar = False
            if self._start_bar_sec is not None and abs(pos_x - self._time_to_x(self._start_bar_sec)) <= self._click_sensitivity:
                on_bar = True
            elif self._end_bar_sec is not None and abs(pos_x - self._time_to_x(self._end_bar_sec)) <= self._click_sensitivity:
                on_bar = True
            elif abs(pos_x - self._time_to_x(self._current_playback_sec)) <= self._click_sensitivity:
                on_bar = True
            
            self.setCursor(Qt.CursorShape.PointingHandCursor if on_bar else Qt.CursorShape.ArrowCursor)


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._dragging_bar is not None:
            self._dragging_bar = None
            self.drag_finished.emit()
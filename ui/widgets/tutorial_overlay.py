# ui/widgets/tutorial_overlay.py

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QApplication
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QMouseEvent

class TutorialOverlay(QWidget):
    next_clicked = Signal()
    prev_clicked = Signal()
    exit_clicked = Signal()
    target_clicked = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setParent(parent)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.hide()

        self.target_widget = None
        self.highlight_rect = QRect()
        self.allow_interaction = False

        self.panel = QFrame(self)
        self.panel.setFrameStyle(QFrame.Box | QFrame.StyledPanel)
        self.panel.setStyleSheet("""
            QFrame { background-color: #3c3c3c; border: 1px solid #555; border-radius: 8px; }
            QLabel { color: #e0e0e0; }
        """)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setSpacing(10)
        panel_layout.setContentsMargins(15, 15, 15, 15)

        self.title_label = QLabel()
        self.title_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.title_label.setWordWrap(True)

        self.instruction_label = QLabel()
        self.instruction_label.setFont(QFont("Arial", 11))
        self.instruction_label.setWordWrap(True)

        self.step_label = QLabel()
        self.step_label.setAlignment(Qt.AlignCenter)
        self.step_label.setStyleSheet("color: #909090;")

        button_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.exit_button = QPushButton("Exit Tutorial")

        button_style = """
            QPushButton { background-color: #555; border: 1px solid #666; color: #ddd; padding: 8px 12px; border-radius: 4px; }
            QPushButton:hover { background-color: #666; }
            QPushButton:pressed { background-color: #444; }
            QPushButton:disabled { color: #888; background-color: #404040; }
        """
        self.prev_button.setStyleSheet(button_style)
        self.next_button.setStyleSheet(button_style + "QPushButton { background-color: #0078d7; }")
        self.exit_button.setStyleSheet(button_style)

        button_layout.addWidget(self.exit_button, 0, Qt.AlignLeft)
        button_layout.addStretch()
        button_layout.addWidget(self.prev_button)
        button_layout.addWidget(self.next_button)

        panel_layout.addWidget(self.title_label)
        panel_layout.addWidget(self.instruction_label)
        panel_layout.addSpacing(10)
        panel_layout.addWidget(self.step_label)
        panel_layout.addLayout(button_layout)

        self.next_button.clicked.connect(self.next_clicked.emit)
        self.prev_button.clicked.connect(self.prev_clicked.emit)
        self.exit_button.clicked.connect(self.exit_clicked.emit)

    def show_step(self, target_widget, title, text, current_step, total_steps, is_action_step=False, allow_interaction=False):
        self.target_widget = target_widget
        self.allow_interaction = allow_interaction
        self.title_label.setText(title)
        self.instruction_label.setText(text)
        self.step_label.setText(f"Step {current_step} of {total_steps}")
        self.prev_button.setEnabled(current_step > 1)
        self.next_button.setText("Finish" if current_step == total_steps else "Next")

        is_passive = not is_action_step and not self.target_widget
        self.next_button.setEnabled(is_passive or allow_interaction)
        self.next_button.setVisible(not is_action_step or allow_interaction)

        # --- THIS IS THE FIX ---
        if is_action_step and not allow_interaction:
            self.step_label.setText(f"Step {current_step} of {total_steps}\n(Click the highlighted button to continue)")
        elif allow_interaction:
            self.step_label.setText(f"Step {current_step} of {total_steps}\n(Try interacting with the highlighted area, then click Next)")
        # --- END OF FIX ---

        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        full_path, cutout_path = QPainterPath(), QPainterPath()
        full_path.addRect(self.rect())
        self.highlight_rect = QRect()
        if self.target_widget and self.target_widget.isVisible():
            global_pos = self.target_widget.mapToGlobal(QPoint(0, 0))
            overlay_pos = self.mapFromGlobal(global_pos)
            padding = 5
            self.highlight_rect = QRect(overlay_pos.x() - padding, overlay_pos.y() - padding, self.target_widget.width() + (padding * 2), self.target_widget.height() + (padding * 2))
            cutout_path.addRoundedRect(self.highlight_rect, 5, 5)
        overlay_path = full_path.subtracted(cutout_path)
        painter.fillPath(overlay_path, QBrush(QColor(0, 0, 0, 150)))
        if not self.highlight_rect.isNull():
            pen = QPen(QColor(30, 144, 255, 200), 3)
            painter.setPen(pen)
            painter.drawPath(cutout_path)
            self._position_panel(self.highlight_rect)
            self.panel.setVisible(True)
        else:
            self.panel.adjustSize()
            self.panel.move(int((self.width() - self.panel.width()) / 2), int((self.height() - self.panel.height()) / 2))
            self.panel.setVisible(True)

    def _position_panel(self, target_rect):
        self.panel.adjustSize()
        panel_width, panel_height = self.panel.width(), self.panel.height()
        y_pos = target_rect.bottom() + 10
        if y_pos + panel_height > self.height():
            y_pos = target_rect.top() - panel_height - 10
        x_pos = target_rect.center().x() - (panel_width / 2)
        if x_pos < 10: x_pos = 10
        if x_pos + panel_width > self.width() - 10:
            x_pos = self.width() - panel_width - 10
        self.panel.move(int(x_pos), int(y_pos))

    def resizeEvent(self, event):
        self.setGeometry(self.parent().rect())
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if self.panel.geometry().contains(event.pos()):
            super().mousePressEvent(event)
            return

        if self.highlight_rect.contains(event.pos()):
            if self.allow_interaction:
                self.pass_through_event(event)
            else:
                self.target_clicked.emit()
            event.accept()
            return

        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.allow_interaction and self.highlight_rect.contains(event.pos()):
            self.pass_through_event(event)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.allow_interaction and self.highlight_rect.contains(event.pos()):
            self.pass_through_event(event)
        else:
            super().mouseReleaseEvent(event)

    def pass_through_event(self, event: QMouseEvent):
        if not self.target_widget:
            return

        self.hide()
        widget_at_pos = QApplication.widgetAt(event.globalPosition().toPoint())
        if widget_at_pos:
            new_event = QMouseEvent(
                event.type(),
                widget_at_pos.mapFromGlobal(event.globalPosition().toPoint()),
                event.globalPosition(),
                event.button(),
                event.buttons(),
                event.modifiers()
            )
            QApplication.postEvent(widget_at_pos, new_event)
        self.show()
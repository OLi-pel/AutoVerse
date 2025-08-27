# ui/widgets/tutorial_overlay.py

from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QApplication
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QMouseEvent, QRegion

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
        self.secondary_widgets = []
        self.panel_position_hint = None
        self.interactive_rects = []
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

    def show_step(self, target_widget, title, text, current_step, total_steps,
                  secondary_widgets=None, panel_position_hint=None,
                  is_action_step=False, allow_interaction=False, disable_prev_button=False,
                  highlight_secondary_widgets=None):
        self.target_widget = target_widget
        self.secondary_widgets = secondary_widgets if secondary_widgets else []
        self.highlight_secondary_widgets = highlight_secondary_widgets if highlight_secondary_widgets else []
        self.panel_position_hint = panel_position_hint
        self.allow_interaction = allow_interaction
        self.title_label.setText(title)
        self.instruction_label.setText(text)
        self.step_label.setText(f"Step {current_step} of {total_steps}")

        self.prev_button.setEnabled(current_step > 1 and not disable_prev_button)
        self.next_button.setText("Finish" if current_step == total_steps else "Next")

        is_passive = not is_action_step and not self.target_widget
        self.next_button.setEnabled(is_passive or allow_interaction)
        self.next_button.setVisible(not is_action_step or allow_interaction)

        if is_action_step and not allow_interaction:
            self.step_label.setText(f"Step {current_step} of {total_steps}\n(Click the highlighted element to continue)")
        elif allow_interaction:
            self.step_label.setText(f"Step {current_step} of {total_steps}\n(Try interacting with the highlighted areas, then click Next)")

        # Ensure the tutorial overlay is visible
        self.raise_()
        self.update()
        self._update_mouse_mask()

    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        full_path = QPainterPath()
        full_path.addRect(self.rect())

        cutout_path = QPainterPath()
        highlight_path = QPainterPath()

        self.interactive_rects = []

        all_widgets = []
        if self.target_widget:
            all_widgets.append((self.target_widget, True, True))
        for widget in self.secondary_widgets:
            all_widgets.append((widget, False, False))
        if hasattr(self, 'highlight_secondary_widgets'):
            for widget in self.highlight_secondary_widgets:
                all_widgets.append((widget, False, True))

        for widget, is_primary, should_highlight in all_widgets:
            if widget and widget.isVisible():
                global_pos = widget.mapToGlobal(QPoint(0, 0))
                overlay_pos = self.mapFromGlobal(global_pos)
                padding = 5 if is_primary else 2
                rect = QRect(
                    overlay_pos.x() - padding,
                    overlay_pos.y() - padding,
                    widget.width() + (padding * 2),
                    widget.height() + (padding * 2)
                )
                self.interactive_rects.append(rect)
                rounded_rect_path = QPainterPath()
                rounded_rect_path.addRoundedRect(rect, 5, 5)
                cutout_path.addPath(rounded_rect_path)

                if should_highlight:
                    highlight_path.addPath(rounded_rect_path)

        overlay_path = full_path.subtracted(cutout_path)
        painter.fillPath(overlay_path, QBrush(QColor(0, 0, 0, 150)))

        if not highlight_path.isEmpty():
            pen = QPen(QColor(30, 144, 255, 200), 3)
            painter.setPen(pen)
            painter.drawPath(highlight_path)
            self._position_panel()
            self.panel.setVisible(True)
        else:
            self.panel.adjustSize()
            self.panel.move(int((self.width() - self.panel.width()) / 2), int((self.height() - self.panel.height()) / 2))
            self.panel.setVisible(True)

        self._update_mouse_mask()

    def _position_panel(self):
        # This is the original, simple positioning logic that does not try to be "smart".
        # It relies on hints and a basic default, preventing the layout issues from before.
        self.panel.adjustSize()
        panel_width, panel_height = self.panel.width(), self.panel.height()
        
        primary_rect = self.interactive_rects[0] if self.interactive_rects else QRect()

        y_pos = primary_rect.bottom() + 10
        if y_pos + panel_height > self.height():
            y_pos = primary_rect.top() - panel_height - 10
        
        x_pos = primary_rect.center().x() - (panel_width / 2)
        
        if self.panel_position_hint:
            if self.panel_position_hint == "above_timeline" and self.target_widget:
                global_pos = self.target_widget.mapToGlobal(QPoint(0,0))
                overlay_pos = self.mapFromGlobal(global_pos)
                y_pos = overlay_pos.y() - panel_height - 10
                x_pos = (self.width() - panel_width) / 2
            elif self.panel_position_hint == "center_top":
                 y_pos, x_pos = 20, (self.width() - panel_width) / 2
            elif self.panel_position_hint == "bottom_right":
                # For bottom_right, position more conservatively to avoid z-index issues
                # Move it further from the edges and higher up to avoid tab content
                y_pos = self.height() - panel_height - 60  # More space from bottom
                x_pos = self.width() - panel_width - 40    # More space from right
                
                # Additional safety: ensure the panel is fully visible
                if y_pos < 20:  # Don't go too high
                    y_pos = 20
                if x_pos < 20:  # Don't go too far left
                    x_pos = 20
                    
                # If still too close to edges, use center positioning as fallback
                if y_pos + panel_height > self.height() - 40 or x_pos + panel_width > self.width() - 40:
                    y_pos = (self.height() - panel_height) // 2
                    x_pos = (self.width() - panel_width) // 2

        if x_pos < 10: x_pos = 10
        if x_pos + panel_width > self.width() - 10:
            x_pos = self.width() - panel_width - 10
        
        self.panel.move(int(x_pos), int(y_pos))

    def show(self):
        """Override show to ensure proper setup"""
        super().show()
        # Ensure we cover the entire parent window
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.raise_()

    def resizeEvent(self, event):
        self.setGeometry(self.parent().rect())
        super().resizeEvent(event)
        if self.isVisible():
            self.update()

    def hideEvent(self, event):
        self.clearMask()
        super().hideEvent(event)

    def _is_pos_interactive(self, pos: QPoint) -> bool:
        return any(rect.contains(pos) for rect in self.interactive_rects)

    def _update_mouse_mask(self):
        # ALWAYS create holes for interactive areas when interaction is allowed
        # This ensures double-clicks work on ALL interactive steps, not just ones with secondary widgets
        if self.allow_interaction:
            # Create holes for ALL interactive areas (target + secondary widgets)
            full_region = QRegion(self.rect())
            interactive_region = QRegion()
            
            # Add holes for all interactive rectangles
            for rect in self.interactive_rects:
                interactive_region = interactive_region.united(QRegion(rect))
            
            # Always keep the panel area solid (never create holes in the panel)
            panel_region = QRegion(self.panel.geometry())
            interactive_region = interactive_region.subtracted(panel_region)
            
            # The final mask is the entire overlay minus the interactive holes
            final_mask = full_region.subtracted(interactive_region)
            self.setMask(final_mask)
        else:
            # When interaction is not allowed, the whole overlay is solid
            self.clearMask()

    def mousePressEvent(self, event: QMouseEvent):
        # Handle clicks on the panel
        if self.panel.geometry().contains(event.pos()):
            super().mousePressEvent(event)
            return

        # Handle clicks on interactive areas (only when masking is not active)
        if not self.allow_interaction and self._is_pos_interactive(event.pos()):
            if self.interactive_rects and self.interactive_rects[0].contains(event.pos()):
                self.target_clicked.emit()
        
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        # Handle double-clicks on the panel
        if self.panel.geometry().contains(event.pos()):
            super().mouseDoubleClickEvent(event)
            return
        
        # When allow_interaction is True, double-clicks should pass through via masking
        # No need for manual forwarding since the mask creates holes
        
        event.accept()
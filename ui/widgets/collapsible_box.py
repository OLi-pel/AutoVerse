# ui/widgets/collapsible_box.py

from PySide6.QtCore import (Qt, QParallelAnimationGroup, QPropertyAnimation, QAbstractAnimation, Slot, QSize, QEasingCurve)
from PySide6.QtWidgets import (QWidget, QToolButton, QFrame, QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout)

class CollapsibleBox(QWidget):
    def __init__(self, title="", summary="", parent=None, is_compact=False):
        super(CollapsibleBox, self).__init__(parent)

        # --- Header Section ---
        self.header_frame = QFrame()
        self.header_frame.setObjectName("HeaderFrame")
        
        self.toggle_button = QToolButton(self.header_frame)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                border: none;
                background-color: transparent;
                color: #e0e0e0;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 10);
                border-radius: 4px;
            }
        """)

        self.title_label = QLabel(title, self.header_frame)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        
        self.summary_label = QLabel(summary, self.header_frame)
        self.summary_label.setObjectName("SummaryLabel")
        self.summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.summary_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Header Layout
        header_layout = QHBoxLayout(self.header_frame)
        # Revert to simpler margins
        header_layout.setContentsMargins(5, 5, 5, 5) 
        header_layout.setSpacing(5)
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.summary_label)

        # --- Content Section ---
        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        self.box_layout = QVBoxLayout(self.content_area)
        
        if is_compact:
            self.toggle_button.setIconSize(QSize(8, 8))
            self.title_label.setStyleSheet("font-size: 12px; font-weight: normal;")
            self.box_layout.setContentsMargins(15, 0, 0, 5)
            self.box_layout.setSpacing(5)
        else:
            self.box_layout.setContentsMargins(10, 10, 10, 10)
            self.box_layout.setSpacing(10)

        # --- Animation Setup ---
        self.toggle_animation = QParallelAnimationGroup(self)
        self.content_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.content_animation.setDuration(250)
        self.content_animation.setEasingCurve(QEasingCurve.InOutQuad) 
        self.toggle_animation.addAnimation(self.content_animation)
        
        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.header_frame)
        main_layout.addWidget(self.content_area)

        self.toggle_button.clicked.connect(self._toggle_collapsible)
        self.is_expanded = False

    @Slot(bool)
    def _toggle_collapsible(self, checked):
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.is_expanded = checked
        
        if self.toggle_animation.state() == QAbstractAnimation.State.Running:
            self.toggle_animation.stop()

        content_height = self.content_area.sizeHint().height()
        self.content_animation.setStartValue(self.content_area.maximumHeight())
        self.content_animation.setEndValue(content_height if checked else 0)

        self.toggle_animation.start()

    def setContentLayout(self, layout):
        while self.box_layout.count():
            child = self.box_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.box_layout.addLayout(layout)
        self.content_animation.setEndValue(layout.sizeHint().height())

    def addWidget(self, widget):
        self.box_layout.addWidget(widget)

    def expand(self):
      if not self.is_expanded:
        self.toggle_button.setChecked(True)
        self._toggle_collapsible(True)

    def collapse(self):
      if self.is_expanded:
        self.toggle_button.setChecked(False)
        self._toggle_collapsible(False)
    
    def set_summary_text(self, text):
      self.summary_label.setText(text)
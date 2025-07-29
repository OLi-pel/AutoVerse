# ui/widgets/collapsible_box.py

from PySide6.QtCore import (Qt, QParallelAnimationGroup, QPropertyAnimation, QAbstractAnimation, Slot, QSize)
from PySide6.QtWidgets import (QWidget, QToolButton, QFrame, QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout)

class CollapsibleBox(QWidget):
    def __init__(self, title="", summary="", parent=None, is_compact=False):
        super(CollapsibleBox, self).__init__(parent)

        self.toggle_button = QToolButton()
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        self.title_label = QLabel(title)
        self.title_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        
        self.summary_label = QLabel(summary)
        self.summary_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.summary_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.summary_label.setStyleSheet("color: #707070;")

        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.content_area.setMinimumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.box_layout = QVBoxLayout(self.content_area)
        
        # --- Style Changes based on is_compact flag ---
        if is_compact:
            self.toggle_button.setStyleSheet("QToolButton { border: none; font-weight: normal; font-size: 9pt; }")
            # --- THE FIX for the icon size ---
            self.toggle_button.setIconSize(QSize(8, 8))
            self.toggle_button.setMaximumSize(18, 18)
            self.title_label.setStyleSheet("font-weight: normal; font-size: 9pt;")
            self.box_layout.setContentsMargins(15, 2, 5, 2)
            self.box_layout.setSpacing(2)
        else:
            self.toggle_button.setStyleSheet("QToolButton { border: none; font-weight: bold; }")
            self.title_label.setStyleSheet("font-weight: bold;")
            self.box_layout.setContentsMargins(15, 5, 5, 5)
            self.box_layout.setSpacing(5)

        # Animation Setup
        self.toggle_animation = QParallelAnimationGroup(self)
        self.content_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.content_animation.setDuration(300)
        self.toggle_animation.addAnimation(self.content_animation)
        
        # Header Layout
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(5)
        header_layout.addWidget(self.toggle_button)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.summary_label)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(header_layout)
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
# ui/selectable_text_edit.py
from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QTextCursor

class SelectableTextEdit(QTextEdit):
    segment_clicked = Signal(int, Qt.KeyboardModifiers)
    edit_requested = Signal(int, int)
    edit_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # We start with NoTextInteraction to prevent the native selection highlight.
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.is_in_edit_mode = False

    def mousePressEvent(self, event: QMouseEvent):
        # --- THE CORRECT FIX ---
        # 1. Manually set focus to this widget. This is what makes the
        #    rest of the UI (like the Play button) responsive after a click.
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        
        # 2. DO NOT call super().mousePressEvent(). This is what prevents the
        #    unwanted native selection from being drawn.

        # 3. Always emit our custom signal so the controller can handle selection.
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            self.segment_clicked.emit(cursor.blockNumber(), event.modifiers())

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if not self.is_in_edit_mode and event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            self.edit_requested.emit(cursor.blockNumber(), cursor.positionInBlock())
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if self.is_in_edit_mode and event.key() == Qt.Key_Escape:
            self.edit_cancelled.emit()
            event.accept()
        else:
            super().keyPressEvent(event)
            
    def enter_edit_mode(self, block_number: int, position_in_block: int = 0):
        self.is_in_edit_mode = True
        self.setReadOnly(False)
        # Restore full text editor features ONLY while in edit mode.
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        
        block = self.document().findBlockByNumber(block_number)
        if block.isValid():
            cursor = QTextCursor(block)
            cursor.setPosition(block.position() + position_in_block)
            self.setTextCursor(cursor)
        self.setFocus()

    def exit_edit_mode(self):
        self.is_in_edit_mode = False
        self.setReadOnly(True)
        # Revert to no native interactions to prevent the visual bug.
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
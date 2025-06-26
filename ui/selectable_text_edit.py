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
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.is_in_edit_mode = False

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            # Emit the block number AND the state of the keyboard (e.g., if Shift is held)
            self.segment_clicked.emit(cursor.blockNumber(), event.modifiers())

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        # A double-click is an explicit request to edit
        if not self.is_in_edit_mode and event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            self.edit_requested.emit(cursor.blockNumber(), cursor.positionInBlock())
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        # NEW: Handle the Escape key to cancel editing
        if self.is_in_edit_mode and event.key() == Qt.Key_Escape:
            self.edit_cancelled.emit()
            event.accept() # We've handled this event
        else:
            # For all other keys, use the default behavior
            super().keyPressEvent(event)
            
    def enter_edit_mode(self, block_number: int, position_in_block: int = 0):
        self.is_in_edit_mode = True
        self.setReadOnly(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        
        block = self.document().findBlockByNumber(block_number)
        if block.isValid():
            cursor = QTextCursor(block)
            cursor.setPosition(block.position() + position_in_block)
            self.setTextCursor(cursor)
        self.setFocus() # Crucial for receiving key events and focusOutEvent

    def exit_edit_mode(self):
        self.is_in_edit_mode = False
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
# ui/selectable_text_edit.py
from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QMouseEvent, QTextCursor

class SelectableTextEdit(QTextEdit):
    segment_clicked = Signal(int)
    # --- FIX: Restore the position argument to the signal ---
    edit_requested = Signal(int, int) # block_number, position_in_block

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.is_in_edit_mode = False

    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)
        if not self.is_in_edit_mode and event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            self.segment_clicked.emit(cursor.blockNumber())

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if not self.is_in_edit_mode and event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            # --- FIX: Emit the position_in_block as well ---
            self.edit_requested.emit(cursor.blockNumber(), cursor.positionInBlock())
        else:
            super().mouseDoubleClickEvent(event)
            
    def enter_edit_mode(self, block_number: int, position_in_block: int = 0):
        self.is_in_edit_mode = True
        self.setReadOnly(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        
        block = self.document().findBlockByNumber(block_number)
        if block.isValid():
            cursor = QTextCursor(block)
            # Use the position from the double-click to place the cursor
            cursor.setPosition(block.position() + position_in_block)
            self.setTextCursor(cursor)
        self.setFocus()

    def exit_edit_mode(self):
        self.is_in_edit_mode = False
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
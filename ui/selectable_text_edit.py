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
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.is_in_edit_mode = False
        self.editing_block_number = -1

    def mousePressEvent(self, event: QMouseEvent):
        # --- THE DEFINITIVE FIX ---
        if self.is_in_edit_mode:
            # Determine which text block the user clicked on
            cursor = self.cursorForPosition(event.pos())
            clicked_block_number = cursor.blockNumber()

            # If the click is on a DIFFERENT block, exit edit mode and select the new block
            if clicked_block_number != self.editing_block_number:
                # We need to signal the controller to handle this state change
                # We can re-use the segment_clicked signal for this.
                # The controller will see this and exit edit mode first.
                self.segment_clicked.emit(clicked_block_number, event.modifiers())
                # It's important to stop further processing of this click event here
                event.accept()
                return
            else:
                # If the click is within the block we are currently editing,
                # let the base class handle it to move the cursor.
                super().mousePressEvent(event)
                return

        # If we are NOT in edit mode, do our standard segment selection
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            self.segment_clicked.emit(cursor.blockNumber(), event.modifiers())
        else:
            super().mousePressEvent(event)

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
        self.editing_block_number = block_number
        self.setReadOnly(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        
        block = self.document().findBlockByNumber(block_number)
        if block.isValid():
            cursor = QTextCursor(block)
            cursor.setPosition(block.position() + position_in_block)
            self.setTextCursor(cursor)
        self.setFocus()

    def exit_edit_mode(self):
        self.is_in_edit_mode = False
        self.editing_block_number = -1
        self.setReadOnly(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
# ui/selectable_text_edit.py
from PySide6.QtWidgets import QTextEdit
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QTextCursor

class SelectableTextEdit(QTextEdit):
    segment_clicked = Signal(int, int)
    edit_requested = Signal(int, int)
    edit_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        # Explicitly remove Editable flag for read-only mode
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        self.is_in_edit_mode = False
        self.editing_block_number = -1

    def mousePressEvent(self, event: QMouseEvent):
        if self.is_in_edit_mode:
            cursor = self.cursorForPosition(event.pos())
            clicked_block_number = cursor.blockNumber()

            if clicked_block_number != self.editing_block_number:
                # Use int() to safely get the value across different PySide6 versions
                modifiers_int = int(event.modifiers().value)
                self.segment_clicked.emit(clicked_block_number, modifiers_int)
                event.accept()
                return
            else:
                super().mousePressEvent(event)
                return

        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            modifiers_int = int(event.modifiers().value)
            self.segment_clicked.emit(cursor.blockNumber(), modifiers_int)

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if not self.is_in_edit_mode and event.button() == Qt.LeftButton:
            cursor = self.cursorForPosition(event.pos())
            self.edit_requested.emit(cursor.blockNumber(), cursor.positionInBlock())
        else:
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        # --- DEFENSIVE FIX FOR MACOS ---
        # If we think we are in edit mode, but the widget thinks it's ReadOnly,
        # the keystroke will fail (bonk sound). We force it to be writable here.
        if self.is_in_edit_mode and self.isReadOnly():
            self.setReadOnly(False)
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        # -------------------------------

        if self.is_in_edit_mode and event.key() == Qt.Key_Escape:
            self.edit_cancelled.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def enter_edit_mode(self, block_number: int, position_in_block: int = 0):
        self.is_in_edit_mode = True
        self.editing_block_number = block_number
        
        # --- ROBUST MODE SWITCHING ---
        # 1. Set ReadOnly to False first
        self.setReadOnly(False)
        # 2. Force the flags. TextEditorInteraction includes TextEditable.
        # We set it explicitly to overwrite any previous state.
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        # -----------------------------

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
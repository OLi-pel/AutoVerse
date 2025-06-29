# core/undo_redo.py
import logging
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

class Command:
    """Abstract base class for a command."""
    def __init__(self, segment_manager, main_controller):
        self.segment_manager = segment_manager
        self.main_controller = main_controller

    def execute(self):
        raise NotImplementedError

    def undo(self):
        raise NotImplementedError
    
    def redo(self):
        # Default redo is just to execute the command again
        self.execute()

class ModifyStateCommand(Command):
    """
    A generic command for actions that modify the entire state of 
    segments or the speaker map. This is useful for complex operations 
    like merge, split, delete, add, and speaker assignment.
    """
    def __init__(self, segment_manager, main_controller, before_segments, after_segments, before_map, after_map):
        super().__init__(segment_manager, main_controller)
        self._before_segments = before_segments
        self._after_segments = after_segments
        self._before_map = before_map
        self._after_map = after_map

    def execute(self):
        """Applies the 'after' state."""
        self.segment_manager.segments = self._after_segments
        self.segment_manager.speaker_map = self._after_map
        # Re-derive unique labels from the restored map and segments
        self.segment_manager.unique_speaker_labels = set(self.segment_manager.speaker_map.keys())
        for seg in self.segment_manager.segments:
            if seg['speaker_raw'] not in ['SPEAKER_NONE_INTERNAL']:
                 self.segment_manager.unique_speaker_labels.add(seg['speaker_raw'])

    def undo(self):
        """Applies the 'before' state."""
        self.segment_manager.segments = self._before_segments
        self.segment_manager.speaker_map = self._before_map
        # Re-derive unique labels
        self.segment_manager.unique_speaker_labels = set(self.segment_manager.speaker_map.keys())
        for seg in self.segment_manager.segments:
            if seg['speaker_raw'] not in ['SPEAKER_NONE_INTERNAL']:
                 self.segment_manager.unique_speaker_labels.add(seg['speaker_raw'])

class UndoManager(QObject):
    """Manages the undo and redo stacks."""
    
    # Signal emitted when undo/redo stacks change, enabling/disabling buttons
    state_changed = Signal(bool, bool) # can_undo, can_redo
    
    # Signal to notify the UI it needs to refresh its views
    history_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._undo_stack = []
        self._redo_stack = []
        logger.info("UndoManager initialized.")

    def add_command(self, command: Command):
        """Adds a new command to the stack after executing it."""
        # When a new action is performed, the redo stack must be cleared
        if self._redo_stack:
            logger.debug("New command added, clearing redo stack.")
            self._redo_stack.clear()
        
        self._undo_stack.append(command)
        logger.debug(f"Added command to undo stack. Stack size: {len(self._undo_stack)}")
        self._emit_state_change()

    def undo(self):
        """
        Performs an undo operation if there are commands on the undo stack.
        """
        if not self._undo_stack:
            logger.warning("Undo called on empty stack.")
            return

        command = self._undo_stack.pop()
        logger.info(f"Undoing command: {type(command).__name__}")
        command.undo()
        self._redo_stack.append(command)

        self.history_changed.emit() # Tell the UI to update
        self._emit_state_change()

    def redo(self):
        """
        Performs a redo operation if there are commands on the redo stack.
        """
        if not self._redo_stack:
            logger.warning("Redo called on empty stack.")
            return

        command = self._redo_stack.pop()
        logger.info(f"Redoing command: {type(command).__name__}")
        command.redo() # `redo` often just calls `execute` again
        self._undo_stack.append(command)

        self.history_changed.emit() # Tell the UI to update
        self._emit_state_change()

    def clear(self):
        """Clears both the undo and redo stacks completely."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        logger.info("Undo/Redo history cleared.")
        self._emit_state_change()

    def _emit_state_change(self):
        """Emits a signal indicating the current undo/redo availability."""
        can_undo = len(self._undo_stack) > 0
        can_redo = len(self._redo_stack) > 0
        self.state_changed.emit(can_undo, can_redo)
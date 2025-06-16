# utils/streams.py (New File)
import io
import re
from PySide6.QtCore import QObject, Signal

# --- Step 1: Create a dedicated QObject for emitting signals ---
class ProgressSignalEmitter(QObject):
    """
    A simple QObject subclass whose only purpose is to emit a signal
    with an integer payload. This avoids metaclass conflicts.
    """
    # Define a signal that will carry an integer (the percentage)
    progress_updated = Signal(int)

    def emit_progress(self, percentage: int):
        """Emits the progress_updated signal."""
        self.progress_updated.emit(percentage)


# --- Step 2: Create the stream class that USES the emitter ---
class TqdmSignalStream(io.TextIOBase):
    """
    A file-like object that intercepts writes (like from tqdm) and uses an
    emitter to send a Qt signal with the progress percentage.
    It inherits only from io.TextIOBase to act as a stream.
    """
    # Regex to find one or more digits followed by a '%' sign
    _progress_regex = re.compile(r"(\d+)%")

    def __init__(self):
        super().__init__()
        # Create an instance of our dedicated signal emitter
        self.emitter = ProgressSignalEmitter()

    def write(self, text: str) -> int:
        """
        This method is called whenever a library (like tqdm) tries to
        write to this stream.
        """
        # Search for the percentage pattern in the text
        match = self._progress_regex.search(text)
        if match:
            # If a match is found, extract the number and emit the signal
            percentage = int(match.group(1))
            self.emitter.emit_progress(percentage)
            
        # The write method must return the number of characters written.
        return len(text)

    def readable(self) -> bool:
        return False

    def seekable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def flush(self):
        # This can be a no-op for our purpose
        pass

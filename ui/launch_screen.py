# ui/launch_screen.py (PySide6 Version)

import sys
import logging
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QProgressBar, 
                               QVBoxLayout)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

# Initialize logger for this module
logger = logging.getLogger(__name__)

class LaunchScreen(QWidget):
    """
    A launch screen window implemented with PySide6 (Qt).
    This window displays a loading message and a progress bar while the main
    application initializes in the background.
    """
    def __init__(self, parent=None):
        """
        Initializes the launch screen widget.
        """
        super().__init__(parent)
        
        # --- Window Properties ---
        self.setWindowTitle("Transcription Oli - Loading...")
        # Set the window to be a frameless splash screen.
        self.setWindowFlags(Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(400, 200) # A fixed size for a simple launch screen

        # --- Widget Creation ---
        # Main title label
        self.title_label = QLabel("Transcription Oli")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        self.title_label.setFont(font)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Label to display loading status messages
        self.loading_label = QLabel("Initializing...")
        font = QFont()
        font.setPointSize(12)
        self.loading_label.setFont(font)
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Set to indeterminate (busy) mode
        self.progress_bar.setTextVisible(False)

        # --- Layout ---
        # QVBoxLayout arranges widgets vertically.
        layout = QVBoxLayout()
        layout.addStretch() # Add stretchable space to push content to the center
        layout.addWidget(self.title_label)
        layout.addWidget(self.loading_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch() # Add more stretchable space at the bottom

        self.setLayout(layout)
        
        logger.info("PySide6 LaunchScreen initialized.")

    def update_text(self, text: str):
        """
        Updates the loading status message text.
        This method can be called from another thread via signals if needed,
        but for simple startup, direct calls before showing are fine.
        """
        self.loading_label.setText(text)
        logger.debug(f"Launch screen text updated to: '{text}'")
        # In Qt, changes are typically batched and drawn in the next event loop cycle.
        # For immediate updates, you can call QApplication.processEvents(),
        # but it's often not necessary.

    def center_on_screen(self):
        """
        Centers the launch screen on the primary monitor.
        """
        if self.parent():
            # Center on the parent widget if one is provided
            parent_geo = self.parent().geometry()
            self.move(parent_geo.center() - self.rect().center())
        else:
            # Otherwise, center on the screen
            screen = QApplication.primaryScreen().geometry()
            self.move(screen.center() - self.rect().center())

    def show_and_process(self):
        """
        A convenience method to show the screen and ensure it's displayed immediately.
        """
        self.center_on_screen()
        self.show()
        # Process any pending events to make sure the window is drawn.
        QApplication.processEvents()

# --- Example Usage (for testing this file directly) ---
if __name__ == '__main__':
    # This block allows you to run this file by itself to see how the launch screen looks.
    # It demonstrates how it will be integrated into the main application.

    # Every Qt application needs one QApplication instance.
    app = QApplication(sys.argv)

    # Create the launch screen
    launch_screen = LaunchScreen()
    launch_screen.show_and_process()

    # --- Simulate a loading process ---
    def update_step_1():
        launch_screen.update_text("Loading transcription models...")

    def update_step_2():
        launch_screen.update_text("Initializing diarization pipeline...")
    
    def update_step_3():
        launch_screen.update_text("Finalizing UI...")

    def do_close():
        launch_screen.close()
        # In a real app, you would show your main window here before closing.
        # app.quit() # Uncomment to make the test app exit after closing.

    # Use QTimer to simulate work being done without blocking the UI.
    QTimer.singleShot(1500, update_step_1)
    QTimer.singleShot(3000, update_step_2)
    QTimer.singleShot(4500, update_step_3)
    QTimer.singleShot(6000, do_close)
    
    # Start the Qt event loop.
    sys.exit(app.exec())
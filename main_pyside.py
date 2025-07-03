# main_pyside.py

import sys
import multiprocessing
import os
import logging
import ssl      
import certifi
from queue import Empty
import platform # --- NEW IMPORT
import requests # --- NEW IMPORT
import tempfile # --- NEW IMPORT
import subprocess # --- NEW IMPORT
import shutil # --- NEW IMPORT
from packaging.version import Version # --- NEW IMPORT

# Keep only the most essential, safe imports at the global level
# QApplication must be imported here for the app instance to be created.
from PySide6.QtWidgets import QApplication

def configure_ssl_for_bundle():
    """
    On macOS, PyInstaller bundles are isolated from system certificates.
    This function programmatically tells Python's SSL module to use the
    certificate bundle provided by the `certifi` package.
    """
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        try:
            # Get the path to the certifi certificate bundle
            cert_path = certifi.where()
            
            # Set the SSL_CERT_FILE environment variable for this process
            # This is the primary method used by 'requests', 'urllib3', etc.
            os.environ['SSL_CERT_FILE'] = cert_path
            
            # Also configure the default SSL context for lower-level libraries
            ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=cert_path)
            
            logging.info(f"SSL Context configured to use certifi bundle at: {cert_path}")

        except Exception as e:
            logging.error(f"CRITICAL: Failed to configure SSL certificates for bundle. Network requests may fail. Error: {e}")

# --- NEW HELPER FUNCTION ---
def _get_bundled_ffmpeg_path():
    """Checks if the app is a PyInstaller bundle and returns the path to ffmpeg."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        exe_name = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
        return os.path.join(sys._MEIPASS, 'bin', exe_name)
    return None # Return None if not bundled


def run_app():
    """
    Contains all application logic and imports.
    """
    # --- [THE FIX] Added 'Qt' to this import line ---
    from PySide6.QtCore import QObject, Slot, QTimer, QThread, Signal, Qt
    # ----------------------------------------------------

    from PySide6.QtWidgets import QFileDialog, QMessageBox, QLineEdit, QPushButton, QComboBox, QFrame, QCheckBox, QProgressBar, QLabel, QTextEdit, QWidget, QTabWidget, QGroupBox
    from PySide6.QtGui import QIcon, QFontMetrics, QFont, QFontDatabase
    from PySide6.QtUiTools import QUiLoader

    from utils.logging_setup import setup_logging
    from utils import constants
    from utils.config_manager import ConfigManager
    from ui.correction_view_logic import CorrectionViewLogic
    from core.app_worker import processing_worker_function
    from core.audio_processor import AudioProcessor
    from ui.selectable_text_edit import SelectableTextEdit

    setup_logging()
    logger = logging.getLogger(__name__)


    # --- UPDATE CHECKER THREAD ---
    class UpdateChecker(QThread):
        update_available = Signal(str, str, str) # version, release_notes, download_url

        def __init__(self, owner, repo):
            super().__init__()
            self.owner = owner
            self.repo = repo
            self.current_os_string = self._get_os_string()
            if not self.current_os_string:
                logger.warning("Auto-updates not supported on this OS.")
                return
            self.asset_name = f"AutoVerse-{self.current_os_string}-App.zip"

        def _get_os_string(self):
            system = platform.system()
            if system == "Windows": return "Windows"
            if system == "Darwin": return "macOS"
            return None
        
        def run(self):
            if not self.current_os_string:
                return
            try:
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
                logger.info(f"Checking for updates at: {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                latest_release = response.json()
                latest_version_str = latest_release.get("tag_name", "v0.0.0").lstrip('v')
                
                if Version(latest_version_str) > Version(constants.APP_VERSION):
                    logger.info(f"Update found! Current: {constants.APP_VERSION}, Latest: {latest_version_str}")
                    download_url = ""
                    for asset in latest_release.get("assets", []):
                        if asset.get("name") == self.asset_name:
                            download_url = asset.get("browser_download_url")
                            break
                    
                    if download_url:
                        self.update_available.emit(
                            latest_version_str, 
                            latest_release.get("body", "No release notes available."),
                            download_url
                        )
                    else:
                        logger.warning(f"Update {latest_version_str} found, but asset '{self.asset_name}' was not present.")
            except requests.RequestException as e:
                logger.warning(f"Could not check for updates (network issue): {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred during update check: {e}", exc_info=True)


    # --- DOWNLOADER THREAD ---
    class Downloader(QThread):
        download_progress = Signal(int)
        download_finished = Signal(bool, str)

        def __init__(self, url):
            super().__init__()
            self.url = url

        def run(self):
            try:
                logger.info(f"Starting download from: {self.url}")
                response = requests.get(self.url, stream=True, timeout=15)
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_file:
                    file_path = temp_file.name
                
                downloaded_size = 0
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress = int((downloaded_size / total_size) * 100) if total_size > 0 else 0
                        self.download_progress.emit(progress)

                logger.info(f"Download complete. File saved to: {file_path}")
                self.download_finished.emit(True, file_path)

            except requests.RequestException as e:
                logger.error(f"Download failed: {e}", exc_info=True)
                self.download_finished.emit(False, "")
            except Exception as e:
                logger.error(f"An unexpected error occurred during download: {e}", exc_info=True)
                self.download_finished.emit(False, "")

    class MainApplication(QObject):
        def __init__(self, app_instance):
            super().__init__()
            self.app = app_instance
            
            loader = QUiLoader()
            loader.registerCustomWidget(SelectableTextEdit)

            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            ui_file_path = os.path.join(base_path, "ui", "main_window.ui")
            
            self.window = loader.load(ui_file_path, None)
            self.window.setWindowTitle(f"AutoVerse v{constants.APP_VERSION}")
            
            if not self.window:
                logger.critical(f"Failed to load UI file: {ui_file_path}")
                sys.exit(1)
            
            self.config_manager = ConfigManager(constants.DEFAULT_CONFIG_FILE)
            self.is_processing = False
            
            self._promote_widgets()
            self._setup_fonts()
            self._setup_icons()
            
            self.correction_logic = CorrectionViewLogic(self.window)
            
            self.app.aboutToQuit.connect(self.cleanup)

            self.audio_file_paths = []
            self.process = None
            self.queue = None
            self.last_single_file_result_path = None

            self.timer = QTimer()
            self.timer.timeout.connect(self.check_queue)
            
            self.connect_signals()
            self.load_initial_settings()
            
            # --- [THE FIX] UPDATE LOGIC IS NOW CORRECTLY INDENTED INSIDE __init__ ---
            if getattr(sys, 'frozen', False):
                logger.info("Application is frozen, initializing update check.")
                # IMPORTANT: Replace with your GitHub username and repository name if needed
                self.update_checker = UpdateChecker(owner="OLi-pel", repo="AutoVerse")
                self.update_checker.update_available.connect(self.prompt_for_update)
                self.update_checker.start()
            else:
                logger.info("Application not frozen. Skipping update check.")
            # --------------------------------------------------------------------

            self.window.show()
                
        def cleanup(self):
            logger.info("Application quitting. Cleaning up...")
            if self.process and self.process.is_alive():
                logger.warning("Terminating active process due to application quit.")
                self.process.terminate()
                self.process.join(1)
            if hasattr(self, 'correction_logic') and hasattr(self.correction_logic, 'audio_player'):
                self.correction_logic.audio_player.destroy()
            logger.info("Cleanup finished.")

        # --- ALL UPDATE METHODS CORRECTLY DEFINED IN THE CLASS ---
        @Slot(str, str, str)
        def prompt_for_update(self, version, notes, url):
            msg_box = QMessageBox(self.window)
            msg_box.setWindowTitle(f"Update Available: v{version}")
            msg_box.setText(f"A new version of AutoVerse is available (<b>v{version}</b>). You have v{constants.APP_VERSION}.<br><br>Would you like to download and install it now?")
            msg_box.setInformativeText(f"<b>Release Notes:</b><hr>{notes}")
            msg_box.setTextFormat(Qt.RichText)
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)
            
            if msg_box.exec() == QMessageBox.Yes:
                self.start_download(url)

        def start_download(self, url):
            self.window.status_label.setText("Downloading update...")
            self.downloader = Downloader(url)
            self.downloader.download_progress.connect(self.window.progress_bar.setValue)
            self.downloader.download_finished.connect(self.on_download_finished)
            self.downloader.start()

        @Slot(bool, str)
        def on_download_finished(self, success, file_path):
            if not success:
                QMessageBox.critical(self.window, "Download Error", "Failed to download the update. Please try again later or visit the GitHub page to download it manually.")
                self.window.status_label.setText("Update download failed.")
                self.window.progress_bar.setValue(0)
                return
            
            self.window.status_label.setText("Download complete. Starting update...")
            self.window.progress_bar.setValue(100)
            self.trigger_updater(file_path)

        def trigger_updater(self, zip_path):
            """Prepares and launches the external updater script."""
            try:
                # --- [THE FIX for App Translocation] ---
                # Instead of guessing with _MEIPASS, get the path relative to the main executable.
                # On both platforms, the updater is bundled in the same directory as the main app executable.
                current_executable_path = os.path.dirname(sys.executable)
                updater_in_bundle = os.path.join(current_executable_path, 'updater.exe' if sys.platform == 'win32' else 'updater')
                # ---------------------------------------------
                
                # This part remains the same: copy updater to a temp dir to run it from
                temp_dir = tempfile.gettempdir()
                temp_updater_path = os.path.join(temp_dir, os.path.basename(updater_in_bundle))
                shutil.copy2(updater_in_bundle, temp_updater_path)

                install_dir = ""
                main_executable_name = ""

                if sys.platform == 'darwin': # macOS
                    # install_dir is the directory that CONTAINS AutoVerse.app
                    install_dir = os.path.abspath(os.path.join(current_executable_path, '..', '..', '..'))
                    main_executable_name = "AutoVerse.app"
                else: # Windows
                    # install_dir is the directory containing AutoVerse.exe
                    install_dir = current_executable_path
                    main_executable_name = "AutoVerse.exe"

                args = [temp_updater_path, zip_path, install_dir, main_executable_name]

                logger.info(f"Launching updater from '{temp_updater_path}'")
                logger.info(f"Updater arguments: {args}")

                subprocess.Popen(args)
                self.app.quit() 

            except Exception as e:
                logger.error(f"Failed to launch updater: {e}", exc_info=True)
                QMessageBox.critical(self.window, "Update Error", f"Could not launch the updater script: {e}. Please update manually.")
        
        def _promote_widgets(self):
            self.window.audio_file_entry = self.window.findChild(QLineEdit, "audio_file_entry")
            self.window.browse_button = self.window.findChild(QPushButton, "browse_button")
            self.window.model_dropdown = self.window.findChild(QComboBox, "model_dropdown")
            self.window.diarization_checkbutton = self.window.findChild(QCheckBox, "diarization_checkbutton")
            self.window.auto_merge_checkbutton = self.window.findChild(QCheckBox, "auto_merge_checkbutton")
            self.window.timestamps_checkbutton_2 = self.window.findChild(QCheckBox, "timestamps_checkbutton_2")
            self.window.end_times_checkbutton = self.window.findChild(QCheckBox, "end_times_checkbutton")
            self.window.huggingface_token_frame = self.window.findChild(QGroupBox, "huggingface_token_frame")
            self.window.huggingface_token_entry = self.window.findChild(QLineEdit, "huggingface_token_entry")
            self.window.save_token_button = self.window.findChild(QPushButton, "save_token_button")
            self.window.start_processing_button = self.window.findChild(QPushButton, "start_processing_button")
            self.window.status_label = self.window.findChild(QLabel, "status_label")
            self.window.progress_bar = self.window.findChild(QProgressBar, "progress_bar")
            self.window.output_text_area = self.window.findChild(QTextEdit, "output_text_area")
            self.window.correction_button = self.window.findChild(QPushButton, "correction_button")
            self.window.main_tab_widget = self.window.findChild(QTabWidget, "tabWidget")
            self.window.correction_transcription_entry = self.window.findChild(QLineEdit, "correction_transcription_entry")
            self.window.correction_browse_transcription_btn = self.window.findChild(QPushButton, "correction_browse_transcription_btn")
            self.window.correction_audio_entry = self.window.findChild(QLineEdit, "correction_audio_entry")
            self.window.correction_browse_audio_btn = self.window.findChild(QPushButton, "correction_browse_audio_btn")
            self.window.correction_load_files_btn = self.window.findChild(QPushButton, "correction_load_files_btn")
            self.window.correction_assign_speakers_btn = self.window.findChild(QPushButton, "correction_assign_speakers_btn")
            self.window.correction_save_changes_btn = self.window.findChild(QPushButton, "correction_save_changes_btn")
            self.window.correction_play_pause_btn = self.window.findChild(QPushButton, "correction_play_pause_btn")
            self.window.correction_rewind_btn = self.window.findChild(QPushButton, "correction_rewind_btn")
            self.window.correction_forward_btn = self.window.findChild(QPushButton, "correction_forward_btn")
            self.window.correction_timeline_frame = self.window.findChild(QWidget, "correction_timeline_frame")
            self.window.correction_time_label = self.window.findChild(QLabel, "correction_time_label")
            self.window.correction_text_area = self.window.findChild(SelectableTextEdit, "correction_text_area")
            self.window.edit_speaker_btn = self.window.findChild(QPushButton, "edit_speaker_btn")
            self.window.correction_text_edit_btn = self.window.findChild(QPushButton, "correction_text_edit_btn")
            self.window.correction_timestamp_edit_btn = self.window.findChild(QPushButton, "correction_timestamp_edit_btn")
            self.window.segment_btn = self.window.findChild(QPushButton, "segment_btn")
            self.window.save_timestamp_btn = self.window.findChild(QPushButton, "save_timestamp_btn")
            self.window.change_highlight_color_btn = self.window.findChild(QPushButton, "change_highlight_color_btn")
            self.window.delete_segment_btn = self.window.findChild(QPushButton, "delete_segment_btn")
            self.window.merge_segments_btn = self.window.findChild(QPushButton, "merge_segments_btn")
            self.window.text_font_combo = self.window.findChild(QComboBox, "text_font")
            self.window.font_size_combo = self.window.findChild(QComboBox, "Police_size")

        def _setup_fonts(self):
            font_id = QFontDatabase.font("Monaco", "Roman", 12)
            if font_id == -1: self.window.monospace_font = QFont("Monospace", 12)
            else: self.window.monospace_font = QFont("Monaco")
            self.window.monospace_font.setStyleHint(QFont.StyleHint.Monospace)

        def _setup_icons(self):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            icon_dir = os.path.join(base_dir, 'assets', 'icons')
            icon_map = { self.window.browse_button: "folder-open.png", self.window.save_token_button: "disk.png", self.window.correction_button: "next.png", self.window.correction_browse_transcription_btn: "folder-open.png", self.window.correction_browse_audio_btn: "folder-open.png", self.window.correction_save_changes_btn: "disk.png", self.window.correction_load_files_btn: "sort-down.png", self.window.correction_rewind_btn: "rewind.png", self.window.correction_forward_btn: "forward.png", self.window.correction_assign_speakers_btn: "user-add.png", self.window.findChild(QPushButton, "Undo_button"): "undo.png", self.window.findChild(QPushButton, "Redo_Button"): "redo.png", self.window.findChild(QCheckBox, "show_tips_checkbox"): "interrogation.png", self.window.change_highlight_color_btn: "palette.png", self.window.edit_speaker_btn: "user-pen.png", self.window.correction_text_edit_btn: "pencil.png", self.window.correction_timestamp_edit_btn: "stopwatch.png", self.window.segment_btn: "multiple.png", self.window.save_timestamp_btn: "disk.png", self.window.merge_segments_btn: "merge.png", self.window.delete_segment_btn: "trash.png"}
            for widget, filename in icon_map.items():
                if widget:
                    icon_path = os.path.join(icon_dir, filename)
                    if os.path.exists(icon_path): widget.setIcon(QIcon(icon_path))
                    else: logger.warning(f"Icon not found: {icon_path}")
            
            self.window.icon_play = QIcon(os.path.join(icon_dir, "play.png"))
            self.window.icon_abort = QIcon(os.path.join(icon_dir, "stop.png")) 
            self.window.icon_pause = QIcon(os.path.join(icon_dir, "pause.png"))
            self.window.icon_edit_text = QIcon(os.path.join(icon_dir, "pencil.png"))
            self.window.icon_save_edit = QIcon(os.path.join(icon_dir, "sign-out-alt.png"))
            self.window.icon_edit_timestamp = QIcon(os.path.join(icon_dir, "stopwatch.png"))
            self.window.icon_cancel_edit = self.window.icon_save_edit
            self.window.start_processing_button.setIcon(self.window.icon_play)
            self.window.correction_play_pause_btn.setIcon(self.window.icon_play)

        def connect_signals(self):
            self.window.browse_button.clicked.connect(self.select_files)
            self.window.start_processing_button.clicked.connect(self.start_or_abort_processing)
            self.window.save_token_button.clicked.connect(self.save_huggingface_token)
            self.window.diarization_checkbutton.stateChanged.connect(self.toggle_advanced_options)
            self.window.correction_button.clicked.connect(self.go_to_correction)

        def toggle_advanced_options(self, state):
            is_checked = (state == 2)
            if self.window.huggingface_token_frame: self.window.huggingface_token_frame.setVisible(is_checked)
            if self.window.auto_merge_checkbutton: self.window.auto_merge_checkbutton.setEnabled(is_checked)
            if not is_checked: self.window.auto_merge_checkbutton.setChecked(False)

        def set_ui_for_processing(self, is_processing):
            self.window.findChild(QGroupBox, "Audio_file_frame").setEnabled(not is_processing)
            self.window.findChild(QGroupBox, "Processing_options_frame").setEnabled(not is_processing)
            self.window.start_processing_button.setEnabled(True) 
            self.window.main_tab_widget.setTabEnabled(1, not is_processing)
            
            if is_processing:
                self.window.start_processing_button.setText("Abort")
                self.window.start_processing_button.setIcon(self.window.icon_abort)
            else:
                self.window.start_processing_button.setText("Start Processing")
                self.window.start_processing_button.setIcon(self.window.icon_play)
            
            self.is_processing = is_processing
        
        def get_processing_options(self):
            return {"model_key": self.window.model_dropdown.currentText(), "enable_diarization": self.window.diarization_checkbutton.isChecked(), "auto_merge": self.window.auto_merge_checkbutton.isChecked(), "include_timestamps": self.window.timestamps_checkbutton_2.isChecked(), "include_end_times": self.window.end_times_checkbutton.isChecked(), "hf_token": self.window.huggingface_token_entry.text().strip()}

        def load_initial_settings(self):
            self.window.correction_button.setEnabled(False)
            self.window.model_dropdown.addItems(["tiny", "base", "small", "medium", "large (recommended)", "turbo"])
            self.window.model_dropdown.setCurrentText("large (recommended)")
            if self.window.huggingface_token_frame: self.window.huggingface_token_frame.hide()
            token = self.config_manager.load_huggingface_token()
            if token: self.window.huggingface_token_entry.setText(token)
            
            font_sizes = ["8", "9", "10", "11", "12", "14", "16", "18", "24", "36"]
            self.window.font_size_combo.addItems(font_sizes)
            self.window.font_size_combo.setCurrentText("12")

            db = QFontDatabase()
            font_families = db.families()
            self.window.text_font_combo.addItems(font_families)
            
            default_font = "Monaco" if "Monaco" in font_families else "Courier New" if "Courier New" in font_families else "Monospace"
            self.window.text_font_combo.setCurrentText(default_font)

            if self.window.correction_play_pause_btn:
                button = self.window.correction_play_pause_btn
                font_metrics = QFontMetrics(button.font())
                text_width = font_metrics.boundingRect("Pause ").width()
                padding = 40 
                button.setFixedWidth(text_width + padding)
                
            logger.info("Initial settings loaded.")

        def save_huggingface_token(self):
            token = self.window.huggingface_token_entry.text().strip()
            self.config_manager.save_huggingface_token(token)
            self.config_manager.set_use_auth_token(bool(token))
            QMessageBox.information(self.window, "Token Saved", "Hugging Face token has been saved." if token else "Hugging Face token has been cleared.")

        @Slot()
        def select_files(self):
            from PySide6.QtWidgets import QFileDialog
            if self.is_processing: return
            file_filter = ("All Media Files (*.wav *.mp3 *.aac *.flac *.m4a *.mp4 *.mov *.avi *.mkv);;Audio Files (*.wav *.mp3 *.aac *.flac *.m4a);;Video Files (*.mp4 *.mov *.avi *.mkv);;All Files (*)")
            paths, _ = QFileDialog.getOpenFileNames(self.window, "Select Audio or Video Files", "", file_filter)
            if paths:
                self.audio_file_paths = paths
                self.window.audio_file_entry.setText(paths[0] if len(paths) == 1 else f"{len(paths)} files selected")
                self.window.correction_button.setEnabled(False)

        @Slot()
        def start_or_abort_processing(self):
            if self.is_processing and self.process:
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(timeout=1)
                self.timer.stop()
                self.process = None
                self.window.status_label.setText("Processing aborted by user.")
                self.window.progress_bar.setValue(0)
                self.set_ui_for_processing(False)
                return

            if not self.audio_file_paths:
                QMessageBox.critical(self.window, "Error", "Please select one or more audio/video files first.")
                return

            destination_folder = None
            if len(self.audio_file_paths) > 1:
                destination_folder = QFileDialog.getExistingDirectory(self.window, "Select Destination Folder for Transcriptions")
                if not destination_folder:
                    self.window.status_label.setText("Batch processing cancelled.")
                    return

            self.set_ui_for_processing(True)
            self.window.progress_bar.setValue(0)
            self.window.output_text_area.clear()
            
            options = self.get_processing_options()
            cache_dir = os.path.join(os.path.expanduser('~'), 'AutoVerse_Cache')
            
            ffmpeg_path = _get_bundled_ffmpeg_path()
            if ffmpeg_path:
                logger.info(f"Main process identified bundled ffmpeg: {ffmpeg_path}")

            self.queue = multiprocessing.Queue()
            self.process = multiprocessing.Process(
                target=processing_worker_function, 
                args=(self.queue, self.audio_file_paths, options, cache_dir, destination_folder, ffmpeg_path), 
                daemon=True
            )
            self.process.start()
            self.timer.start(100)

        def check_queue(self):
            try:
                msg_type, data = self.queue.get_nowait()
                if msg_type == constants.MSG_TYPE_PROGRESS:
                    self.window.progress_bar.setValue(data)
                elif msg_type == constants.MSG_TYPE_STATUS:
                    self.window.status_label.setText(data)
                elif msg_type == constants.MSG_TYPE_BATCH_FILE_START:
                    file_info = data
                    status = f"Processing file {file_info[constants.KEY_BATCH_CURRENT_IDX]} of {file_info[constants.KEY_BATCH_TOTAL_FILES]}: {file_info[constants.KEY_BATCH_FILENAME]}"
                    self.window.status_label.setText(status)
                    self.window.progress_bar.setValue(0)
                elif msg_type == constants.MSG_TYPE_BATCH_COMPLETED:
                    self.timer.stop()
                    if self.process:
                        self.process.join()
                        self.process = None
                    self.handle_batch_results(data)
            
            except Empty:
                if self.is_processing and (not self.process or not self.process.is_alive()):
                    self.timer.stop()
                    self.process = None
                    self.set_ui_for_processing(False)
                    if "aborted" not in self.window.status_label.text():
                        QMessageBox.critical(self.window, "Error", "Processing stopped unexpectedly.")
                        self.window.status_label.setText("Error: Processing stopped unexpectedly.")

        def handle_batch_results(self, final_payload):
            results = final_payload[constants.KEY_BATCH_ALL_RESULTS]
            summary = []
            successful_count = 0
            error_count = 0
            
            if len(results) == 1:
                result = results[0]
                self.window.progress_bar.setValue(100)
                if result.status == constants.STATUS_SUCCESS:
                    output_text = "\n".join(result.data) if isinstance(result.data, list) else str(result.data)
                    self.window.output_text_area.setPlainText(output_text)
                    self.prompt_and_save_single_result(result)
                else:
                    msg = result.message or "An unknown error occurred."
                    self.window.status_label.setText(f"Error: {msg[:100]}...")
                    self.window.output_text_area.setPlainText(f"An error occurred:\n{msg}")
                    QMessageBox.critical(self.window, "Processing Error", msg)
            else: 
                for result in results:
                    file_name = os.path.basename(result.source_file)
                    if result.status == constants.STATUS_SUCCESS:
                        successful_count += 1
                        summary.append(f"SUCCESS: '{file_name}' saved to '{os.path.basename(result.output_path)}'")
                    else:
                        error_count += 1
                        summary.append(f"ERROR: '{file_name}' - {result.message}")
                self.window.output_text_area.setPlainText("\n".join(summary))
                final_status_msg = f"Batch finished. {successful_count} successful, {error_count} failed."
                self.window.status_label.setText(final_status_msg)
                QMessageBox.information(self.window, "Batch Processing Complete", final_status_msg)
            
            self.set_ui_for_processing(False)
        
        def prompt_and_save_single_result(self, result):
            if hasattr(result, 'output_path') and result.output_path:
                self.last_single_file_result_path = result.output_path
                self.window.correction_button.setEnabled(True)
                self.window.status_label.setText(f"Transcription saved to {os.path.basename(result.output_path)}")
                return

            base_name, _ = os.path.splitext(os.path.basename(result.source_file))
            model_name = self.get_processing_options()["model_key"].split(" ")[0]
            default_fn = os.path.join(os.getcwd(), f"{base_name}_{model_name}_transcription.txt")
            save_path, _ = QFileDialog.getSaveFileName(self.window, "Save Transcription As", default_fn, "Text Files (*.txt)")
            
            if save_path:
                try:
                    AudioProcessor.save_to_txt(save_path, result.data, result.is_plain_text_output)
                    self.window.status_label.setText(f"Transcription saved to {os.path.basename(save_path)}")
                    QMessageBox.information(self.window, "Success", f"Transcription saved to {save_path}")
                    self.last_single_file_result_path = save_path
                    self.window.correction_button.setEnabled(True)
                except Exception as e:
                    QMessageBox.critical(self.window, "Save Error", f"Could not save file: {e}")
                    self.window.correction_button.setEnabled(False)
            else:
                self.window.status_label.setText("Save cancelled by user.")
                self.window.correction_button.setEnabled(False)

        @Slot()
        def go_to_correction(self):
            if not self.last_single_file_result_path or not self.audio_file_paths:
                QMessageBox.warning(self.window, "Error", "Cannot find the necessary file paths.")
                return
                
            audio_path = self.audio_file_paths[0]
            txt_path = self.last_single_file_result_path
            self.correction_logic.load_files_from_paths(audio_path=audio_path, txt_path=txt_path)
            self.window.main_tab_widget.setCurrentIndex(1)

    # --- Start of main execution ---
    app = QApplication(sys.argv)
    main_app = MainApplication(app)
    sys.exit(app.exec())

if __name__ == "__main__":
    configure_ssl_for_bundle()
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn', force=True)
    run_app()
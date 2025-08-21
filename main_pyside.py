# main_pyside.py

import sys
import multiprocessing
import os
import logging
import ssl
import certifi
from queue import Empty
import platform
import requests
import tempfile
import subprocess
import shutil
import webbrowser
from packaging.version import Version

from PySide6.QtWidgets import QApplication

def configure_ssl_for_bundle():
    """
    On macOS, PyInstaller bundles are isolated from system certificates.
    This function programmatically tells Python's SSL module to use the
    certificate bundle provided by the `certifi` package.
    """
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        try:
            cert_path = certifi.where()
            os.environ['SSL_CERT_FILE'] = cert_path
            ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=cert_path)
            logging.info(f"SSL Context configured to use certifi bundle at: {cert_path}")
        except Exception as e:
            logging.error(f"CRITICAL: Failed to configure SSL certificates for bundle. Network requests may fail. Error: {e}")

def _get_bundled_ffmpeg_path():
    """Checks if the app is a PyInstaller bundle and returns the path to ffmpeg."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        exe_name = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
        return os.path.join(sys._MEIPASS, 'bin', exe_name)
    return None

def run_app():
    """
    Contains all application logic and imports.
    """
    import time
    from PySide6.QtCore import QObject, Slot, QTimer, QThread, Signal, Qt
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QDialogButtonBox, QFileDialog, QMessageBox, QLineEdit, 
                                 QPushButton, QComboBox, QFrame, QCheckBox, QProgressBar, QLabel, 
                                 QTextEdit, QWidget, QTabWidget, QGroupBox, QSpacerItem, QSizePolicy)
    from PySide6.QtGui import QIcon, QFontMetrics, QFont, QFontDatabase, QPixmap
    from PySide6.QtUiTools import QUiLoader

    from utils.logging_setup import setup_logging
    from utils import constants
    from utils.config_manager import ConfigManager
    from ui.correction_view_logic import CorrectionViewLogic
    from core.app_worker import processing_worker_function
    from core.audio_processor import AudioProcessor
    from ui.selectable_text_edit import SelectableTextEdit
    from ui.widgets.collapsible_box import CollapsibleBox
    from utils import tips_data

    setup_logging()
    logger = logging.getLogger(__name__)

    class HuggingFaceTokenDialog(QDialog):
        def __init__(self, current_token, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Hugging Face Token Setup")
            self.token = current_token
            self.setMinimumWidth(550)
            
            main_layout = QVBoxLayout(self)
            
            info_group = QGroupBox("Why is this needed?")
            info_layout = QVBoxLayout()
            info_label = QLabel(
                "To identify different speakers, AutoVerse needs to download free AI models "
                "from a service called Hugging Face.\n\n"
                "A 'read-only' access token proves you have accepted their terms. "
                "<b>This is a one-time setup.</b>"
            )
            info_label.setWordWrap(True)
            info_layout.addWidget(info_label)
            info_group.setLayout(info_layout)
            main_layout.addWidget(info_group)
            
            steps_group = QGroupBox("Setup Steps")
            steps_layout = QGridLayout()
            steps_layout.setSpacing(10)
            
            steps_layout.addWidget(QLabel("<b>1. Create Account</b>"), 0, 0)
            steps_layout.addWidget(QLabel("Log in or create a free Hugging Face account."), 0, 1)
            btn_step1 = QPushButton("Open Hugging Face")
            btn_step1.clicked.connect(lambda: webbrowser.open("https://huggingface.co/join"))
            steps_layout.addWidget(btn_step1, 0, 2)

            steps_layout.addWidget(QLabel("<b>2. Accept Terms</b>"), 1, 0)
            steps_layout.addWidget(QLabel("Visit BOTH links and click 'Agree and access repository'."), 1, 1)
            btn_layout_s2 = QHBoxLayout()
            btn_s2a = QPushButton("Model 1")
            btn_s2b = QPushButton("Model 2")
            btn_s2a.clicked.connect(lambda: webbrowser.open("https://huggingface.co/pyannote/segmentation-3.0"))
            btn_s2b.clicked.connect(lambda: webbrowser.open("https://huggingface.co/pyannote/speaker-diarization-3.1"))
            btn_layout_s2.addWidget(btn_s2a)
            btn_layout_s2.addWidget(btn_s2b)
            steps_layout.addLayout(btn_layout_s2, 1, 2)
            
            steps_layout.addWidget(QLabel("<b>3. Generate Token</b>"), 2, 0)
            steps_layout.addWidget(QLabel("Create a new token with the <b>'read'</b> role."), 2, 1)
            btn_step3 = QPushButton("Get Your Token")
            btn_step3.clicked.connect(lambda: webbrowser.open("https://huggingface.co/settings/tokens"))
            steps_layout.addWidget(btn_step3, 2, 2)

            steps_layout.addWidget(QLabel("<b>4. Paste Token</b>"), 3, 0)
            self.token_entry = QLineEdit()
            self.token_entry.setPlaceholderText("Paste your token here (it starts with 'hf_...')")
            self.token_entry.setText(current_token) 
            steps_layout.addWidget(self.token_entry, 3, 1, 1, 2)
            
            steps_group.setLayout(steps_layout)
            main_layout.addWidget(steps_group)

            button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            self.save_button = button_box.button(QDialogButtonBox.Save)
            self.save_button.setText("Save and Continue")
            
            self.token_entry.textChanged.connect(self.validate_token)
            button_box.accepted.connect(self.on_accept)
            button_box.rejected.connect(self.reject)
            main_layout.addWidget(button_box)
            self.validate_token()

        def validate_token(self):
            text = self.token_entry.text()
            self.save_button.setEnabled(text.strip().startswith("hf_"))

        def on_accept(self):
            self.token = self.token_entry.text().strip()
            self.accept()

    class WelcomeDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Welcome to AutoVerse!")
            self.choice = None
            self.setModal(True)
            self.setFixedSize(450, 270)
            
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            icon_dir = os.path.join(base_dir, 'assets', 'icons')

            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(15)

            welcome_label = QLabel("What would you like to do?")
            welcome_label.setAlignment(Qt.AlignCenter)
            welcome_label.setStyleSheet("QLabel { font-size: 20px; margin-bottom: 10px; }")
            layout.addWidget(welcome_label)

            self.transcribe_button = QPushButton(" Transcribe a New Audio/Video File")
            fallback_transcribe_icon = QIcon(os.path.join(icon_dir, 'folder-open.png'))
            self.transcribe_button.setIcon(QIcon.fromTheme("document-new", fallback_transcribe_icon))
            self.transcribe_button.setMinimumHeight(60)
            self.transcribe_button.setStyleSheet("QPushButton { font-size: 16px; text-align: left; padding-left: 10px; }")
            self.transcribe_button.clicked.connect(self.select_transcribe)
            layout.addWidget(self.transcribe_button)

            self.edit_button = QPushButton(" Edit an Existing Transcript")
            fallback_edit_icon = QIcon(os.path.join(icon_dir, 'pencil.png'))
            self.edit_button.setIcon(QIcon.fromTheme("document-edit", fallback_edit_icon))
            self.edit_button.setMinimumHeight(60)
            self.edit_button.setStyleSheet("QPushButton { font-size: 16px; text-align: left; padding-left: 10px; }")
            self.edit_button.clicked.connect(self.select_edit)
            layout.addWidget(self.edit_button)

            layout.addStretch(1)

            self.dont_show_again_checkbox = QCheckBox("Don't show this again")
            self.dont_show_again_checkbox.setStyleSheet("QCheckBox { font-size: 12px; }")
            layout.addWidget(self.dont_show_again_checkbox, 0, Qt.AlignRight)

        def select_transcribe(self):
            self.choice = 'transcribe'
            self.accept()

        def select_edit(self):
            self.choice = 'edit'
            self.accept()
    
    def get_true_application_path():
        if not (getattr(sys, 'frozen', False) and sys.platform == 'darwin'):
            return None
        try:
            executable_path = os.path.realpath(sys.executable)
            current_path = os.path.dirname(executable_path)
            for _ in range(6):
                if current_path.endswith('.app'):
                    return current_path
                parent_path = os.path.dirname(current_path)
                if parent_path == current_path:
                    break
                current_path = parent_path
        except Exception as e:
            try:
                logging.error(f"Error while trying to determine application path: {e}")
            except:
                pass
        return None

    class UpdateChecker(QThread):
        update_available = Signal(str, str, str)
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
            self._setup_main_workflow_layout()
            self._setup_nested_collapsible_options()

            self.correction_logic = CorrectionViewLogic(self.window)
            self.tip_widgets = {
                self.window.audio_file_entry: "audio_file_browse", self.window.browse_button: "audio_file_browse", self.window.model_dropdown: "transcription_model_dropdown", self.window.identify_speakers_checkbutton: "enable_diarization_checkbox", self.window.auto_merge_checkbutton: "auto_merge_checkbutton", self.window.timestamps_checkbutton_2: "include_timestamps_checkbox", self.window.end_times_checkbutton: "include_end_times_checkbox", self.window.huggingface_token_entry: "huggingface_token_entry", self.window.save_token_button: "save_huggingface_token_button", self.window.start_processing_button: "start_processing_button", self.window.status_label: "status_label", self.window.progress_bar: "progress_bar", self.window.output_text_area: "output_text_area", self.window.correction_button: "correction_window_button", self.window.show_tips_checkbox: "show_tips_checkbox_main",
            }
            self._setup_fonts()
            self._setup_icons()
            self.app.aboutToQuit.connect(self.cleanup)
            self.audio_file_paths = []
            self.process = None
            self.queue = None
            self.last_single_file_result_path = None
        
            self.current_step_start_time = None
            self.original_status_text = ""

            self.timer = QTimer()
            self.timer.timeout.connect(self.check_queue)
            self.connect_signals()
            self.load_initial_settings()
            
            if getattr(sys, 'frozen', False):
                logger.info("Application is frozen, initializing update check.")
                self.update_checker = UpdateChecker(owner="OLi-pel", repo="AutoVerse")
                self.update_checker.update_available.connect(self.prompt_for_update)
                self.update_checker.start()
            else:
                logger.info("Application not frozen. Skipping update check.")
            
            if self.config_manager.get_show_welcome_wizard():
                welcome_dialog = WelcomeDialog(self.window)
                if welcome_dialog.exec() == QDialog.Accepted:
                    self.config_manager.set_show_welcome_wizard(not welcome_dialog.dont_show_again_checkbox.isChecked())
                    if welcome_dialog.choice == 'transcribe':
                        self.window.show()
                    elif welcome_dialog.choice == 'edit':
                        self.window.main_tab_widget.setCurrentIndex(1)
                        self.window.show()
                else:
                    self.config_manager.set_show_welcome_wizard(not welcome_dialog.dont_show_again_checkbox.isChecked())
                    self.window.show()
            else:
                self.window.show()
        
        def _setup_main_workflow_layout(self):
            transcription_tab = self.window.findChild(QWidget, "tab")
            transcription_tab_layout = transcription_tab.layout().findChild(QVBoxLayout)

            # Create Collapsible Boxes
            self.step1_box = CollapsibleBox("Step 1: Select Audio/Video File(s)", "")
            self.step2_box = CollapsibleBox("Step 2: Configure Processing Options", "Select file(s) to continue.")
            self.step3_box = CollapsibleBox("Step 3: Start Processing & View Output", "Configure options to continue.")

            # == STEP 1 MIGRATION ==
            step1_new_content_layout = QVBoxLayout()
            original_step1_layout = self.window.Audio_file_frame.layout()
            while original_step1_layout.count():
                item = original_step1_layout.takeAt(0)
                step1_new_content_layout.addItem(item)
            self.step1_box.setContentLayout(step1_new_content_layout)

            # == STEP 2 MIGRATION (Restoring Horizontal Layout) ==
            # --- THE FIX for horizontal alignment ---
            # Get the original group boxes
            model_frame = self.window.findChild(QGroupBox, "Model_selection_frame")
            speaker_frame = self.window.Speaker_options_frame
            timestamps_frame = self.window.Timestamps_options_frame
            
            # Set their size policy to allow vertical expansion
            model_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            speaker_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            timestamps_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

            # Create a new HORIZONTAL layout for the contents of Step 2
            step2_content_hlayout = QHBoxLayout()
            step2_content_hlayout.addWidget(model_frame)
            step2_content_hlayout.addWidget(speaker_frame)
            step2_content_hlayout.addWidget(timestamps_frame)
            
            # Put the horizontal layout inside a main vertical layout for this step
            self.step2_new_content_layout = QVBoxLayout()
            self.step2_new_content_layout.addLayout(step2_content_hlayout)
            self.step2_box.setContentLayout(self.step2_new_content_layout)
            
            # == STEP 3 MIGRATION ==
            step3_content_layout = QVBoxLayout()
            step3_content_layout.addWidget(self.window.status_and_play_frame)
            step3_content_layout.addWidget(self.window.Output_area_frame)
            self.step3_box.setContentLayout(step3_content_layout)

            # Hide the now-empty original containers
            self.window.Audio_file_frame.setParent(None)
            self.window.Processing_options_frame.setParent(None)
            
            # Clear original main layout and add new collapsible boxes
            while transcription_tab_layout.count():
                child = transcription_tab_layout.takeAt(0)
                if child.widget(): child.widget().setParent(None)
            
            transcription_tab_layout.addWidget(self.step1_box)
            transcription_tab_layout.addWidget(self.step2_box)
            transcription_tab_layout.addWidget(self.step3_box)

            # Add workflow buttons
            self.change_files_button = QPushButton("Change Selection")
            step1_new_content_layout.addWidget(self.change_files_button)
            
            self.proceed_button = QPushButton("Continue to Processing")
            button_container_layout = QHBoxLayout()
            button_container_layout.addStretch()
            button_container_layout.addWidget(self.proceed_button)
            button_container_layout.addStretch()
            self.step2_new_content_layout.addLayout(button_container_layout)
            
            transcription_tab_layout.addStretch(1)

        def _setup_nested_collapsible_options(self):
            # --- Auto-Merge nested under Speaker Detection ---
            speaker_frame_layout = self.window.Speaker_options_frame.layout()
            self.others_speaker_box = CollapsibleBox("Others", is_compact=True)
            self.others_speaker_box.addWidget(self.window.auto_merge_checkbutton)
            speaker_frame_layout.addWidget(self.others_speaker_box)
            self.others_speaker_box.collapse()

            # --- End Times nested under Timestamps ---
            timestamp_frame_layout = self.window.Timestamps_options_frame.layout()
            self.others_timestamp_box = CollapsibleBox("Others", is_compact=True)
            self.others_timestamp_box.addWidget(self.window.end_times_checkbutton)
            timestamp_frame_layout.addWidget(self.others_timestamp_box)
            self.others_timestamp_box.collapse()

        def _apply_tips_state(self, is_enabled):
            self.window.statusBar().setVisible(is_enabled)
            for widget, tip_key in self.tip_widgets.items():
                if not widget: continue
                if is_enabled: widget.setStatusTip(tips_data.get_tip("main_window", tip_key) or "")
                else: widget.setStatusTip("")

        @Slot(int)
        def on_tips_toggled(self, state):
            is_enabled = (state == Qt.Checked.value)
            self._apply_tips_state(is_enabled)
            self.correction_logic.set_tips_enabled(is_enabled)
            self.config_manager.set_main_window_show_tips(is_enabled)
            logger.info(f"Tips display set to: {is_enabled} and preference saved.")
                
        def cleanup(self):
            logger.info("Application quitting. Cleaning up...")
            if self.process and self.process.is_alive():
                logger.warning("Terminating active process due to application quit.")
                self.process.terminate()
                self.process.join(1)
            if hasattr(self, 'correction_logic'):
                if hasattr(self.correction_logic, 'cleanup'):
                    self.correction_logic.cleanup()
                elif hasattr(self.correction_logic, 'audio_player'):
                    self.correction_logic.audio_player.destroy()
            logger.info("Cleanup finished.")

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
            try:
                script_path = ""
                script_content = ""

                if sys.platform == 'darwin':
                    final_app_path = "/Applications/AutoVerse.app"
                    old_app_path = get_true_application_path()
                    log_file_path = os.path.join(os.path.expanduser("~"), "autoverse_updater.log")
                    
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.sh', encoding='utf-8') as f:
                        script_path = f.name
                        script_content = f'''#!/bin/bash

# AutoVerse macOS Updater Script
# Log file: {log_file_path}

exec > >(tee -a "{log_file_path}") 2>&1

echo "=== AutoVerse macOS Updater Started ==="
echo "Date: $(date)"
echo "Zip Path: {zip_path}"
echo "Final App Path: {final_app_path}"
echo "Old App Path: {old_app_path or 'None'}"
echo ""

# Wait for main app to close
echo "Step 1: Waiting for AutoVerse to close..."
sleep 3

# Terminate any remaining processes
echo "Step 2: Terminating any remaining AutoVerse processes..."
pkill -f "AutoVerse" 2>/dev/null || true
sleep 2

# Create backup
echo "Step 3: Creating backup of current installation..."
BACKUP_DIR="{final_app_path}_backup_$(date +%Y%m%d_%H%M%S)"
if [ -d "{final_app_path}" ]; then
    cp -R "{final_app_path}" "$BACKUP_DIR"
    echo "Backup created at: $BACKUP_DIR"
else
    echo "No existing installation found to backup"
fi

# Extract update
echo "Step 4: Extracting new version..."
TEMP_DIR=$(mktemp -d)
echo "Temporary directory: $TEMP_DIR"

if ! unzip -q "{zip_path}" -d "$TEMP_DIR"; then
    echo "ERROR: Failed to extract zip file"
    echo "Cleaning up..."
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Find the .app bundle
echo "Step 5: Searching for application bundle..."
SOURCE_APP_PATH=$(find "$TEMP_DIR" -name "*.app" -type d -print -quit)

# Check for nested zip if no .app found
if [ -z "$SOURCE_APP_PATH" ]; then
    echo "No .app found, checking for nested zip..."
    NESTED_ZIP=$(find "$TEMP_DIR" -name "*.zip" -print -quit)
    if [ -n "$NESTED_ZIP" ]; then
        echo "Found nested zip: $NESTED_ZIP"
        NESTED_TEMP=$(mktemp -d)
        if unzip -q "$NESTED_ZIP" -d "$NESTED_TEMP"; then
            SOURCE_APP_PATH=$(find "$NESTED_TEMP" -name "*.app" -type d -print -quit)
            if [ -n "$SOURCE_APP_PATH" ]; then
                # Move the .app to the main temp directory
                mv "$SOURCE_APP_PATH" "$TEMP_DIR/"
                SOURCE_APP_PATH="$TEMP_DIR/$(basename "$SOURCE_APP_PATH")"
            fi
        fi
        rm -rf "$NESTED_TEMP"
    fi
fi

if [ -z "$SOURCE_APP_PATH" ] || [ ! -d "$SOURCE_APP_PATH" ]; then
    echo "ERROR: Could not find a valid .app bundle in the archive"
    echo "Contents of temp directory:"
    ls -la "$TEMP_DIR"
    echo "Cleaning up..."
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo "Found application bundle at: $SOURCE_APP_PATH"

# Install new version
echo "Step 6: Installing new version..."
if [ -d "{final_app_path}" ]; then
    echo "Removing old version..."
    rm -rf "{final_app_path}"
fi

echo "Moving new version to /Applications..."
if mv "$SOURCE_APP_PATH" "{final_app_path}"; then
    echo "Successfully installed new version"
else
    echo "ERROR: Failed to install new version"
    echo "Attempting to restore backup..."
    if [ -d "$BACKUP_DIR" ]; then
        mv "$BACKUP_DIR" "{final_app_path}"
        echo "Backup restored"
    fi
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Clean up old installation if different location
if [ -n "{old_app_path}" ] && [ -d "{old_app_path}" ] && [ "{old_app_path}" != "{final_app_path}" ]; then
    echo "Step 7: Cleaning up old installation at {old_app_path}..."
    rm -rf "{old_app_path}"
    echo "Old installation removed"
fi

# Relaunch application
echo "Step 8: Relaunching AutoVerse..."
if [ -d "{final_app_path}" ]; then
    open "{final_app_path}"
    echo "AutoVerse relaunched successfully"
else
    echo "ERROR: Application not found after installation"
    exit 1
fi

# Cleanup
echo "Step 9: Cleaning up temporary files..."
rm -rf "$TEMP_DIR"
rm -f "{zip_path}"

# Remove successful backup (keep only on error)
if [ -d "$BACKUP_DIR" ]; then
    rm -rf "$BACKUP_DIR"
    echo "Backup removed (update successful)"
fi

echo ""
echo "=== Update completed successfully! ==="
echo "Date: $(date)"
echo "Log saved to: {log_file_path}"
echo ""
echo "This window will close in 5 seconds..."
sleep 5

# Remove this script
rm -- "$0"
'''
                        f.write(script_content)

                    os.chmod(script_path, 0o755)
                    
                    applescript = f'''
                    tell application "Terminal"
                        activate
                        do script "'{script_path}'"
                    end tell
                    '''
                    
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.scpt', encoding='utf-8') as f:
                        applescript_path = f.name
                        f.write(applescript)
                    
                    subprocess.Popen(['osascript', applescript_path])
                
                elif sys.platform == 'win32':
                    install_dir = os.path.dirname(sys.executable)
                    relaunch_path = os.path.join(install_dir, "AutoVerse.exe")
                    
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ps1', encoding='utf-8-sig') as f:
                        script_path = f.name
                        log_file_path = os.path.join(os.path.expanduser("~"), "autoverse_updater.log")
                        
                        script_content = (
                            f'Start-Transcript -Path "{log_file_path}" -Append -Force\n'
                            'Write-Host "--- AutoVerse Updater Script Starting ---"\n'
                            f'$installDir = "{install_dir}"\n'
                            f'$zipPath = "{zip_path}"\n'
                            f'$relaunchPath = "{relaunch_path}"\n\n'
                            
                            'Write-Host "Waiting for AutoVerse to close..."\n'
                            'Start-Sleep -Seconds 3\n\n'
                            
                            'try {\n'
                            '    Write-Host "Step 1: Terminating any remaining AutoVerse processes..."\n'
                            '    Get-Process -Name "AutoVerse" -ErrorAction SilentlyContinue | Stop-Process -Force\n'
                            '    Start-Sleep -Seconds 2\n\n'
                            
                            '    Write-Host "Step 2: Creating backup of current installation..."\n'
                            '    $backupDir = "$installDir" + "_backup_" + (Get-Date -Format "yyyyMMdd_HHmmss")\n'
                            '    if (Test-Path $installDir) {\n'
                            '        Copy-Item -Path $installDir -Destination $backupDir -Recurse -Force\n'
                            '        Write-Host "Backup created at: $backupDir"\n'
                            '    }\n\n'
                            
                            '    Write-Host "Step 3: Extracting new version..."\n'
                            '    $tempExtractDir = "$env:TEMP\\AutoVerse_Update_" + (Get-Date -Format "yyyyMMdd_HHmmss")\n'
                            '    Expand-Archive -Path $zipPath -DestinationPath $tempExtractDir -Force\n\n'
                            
                            '    Write-Host "Step 4: Finding extracted files..."\n'
                            '    $extractedFiles = Get-ChildItem -Path $tempExtractDir -Recurse -File\n'
                            '    if ($extractedFiles.Count -eq 0) {\n'
                            '        throw "No files found in extracted archive"\n'
                            '    }\n\n'
                            
                            '    Write-Host "Step 5: Updating application files..."\n'
                            '    foreach ($file in $extractedFiles) {\n'
                            '        $relativePath = $file.FullName.Substring($tempExtractDir.Length + 1)\n'
                            '        $destPath = Join-Path $installDir $relativePath\n'
                            '        $destDir = Split-Path $destPath -Parent\n'
                            '        if (!(Test-Path $destDir)) {\n'
                            '            New-Item -ItemType Directory -Path $destDir -Force | Out-Null\n'
                            '        }\n'
                            '        Copy-Item -Path $file.FullName -Destination $destPath -Force\n'
                            '    }\n\n'
                            
                            '    Write-Host "Step 6: Cleaning up temporary files..."\n'
                            '    Remove-Item -Path $tempExtractDir -Recurse -Force\n'
                            '    Remove-Item -Path $zipPath -Force\n\n'
                            
                            '    Write-Host "Step 7: Relaunching AutoVerse..."\n'
                            '    if (Test-Path $relaunchPath) {\n'
                            '        Start-Process -FilePath $relaunchPath\n'
                            '        Write-Host "Update completed successfully!"\n'
                            '    } else {\n'
                            '        Write-Error "Relaunch failed. Executable not found at: $relaunchPath"\n'
                            '        Write-Host "You can manually start AutoVerse from: $installDir"\n'
                            '    }\n'
                            '} catch {\n'
                            '    Write-Host "--- UPDATE ERROR ---" -ForegroundColor Red\n'
                            '    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Yellow\n'
                            '    Write-Host "Attempting to restore from backup..." -ForegroundColor Cyan\n'
                            '    if (Test-Path $backupDir) {\n'
                            '        Remove-Item -Path $installDir -Recurse -Force -ErrorAction SilentlyContinue\n'
                            '        Move-Item -Path $backupDir -Destination $installDir -Force\n'
                            '        Write-Host "Backup restored. Please try updating manually."\n'
                            '    }\n'
                            '    Write-Host "Press Enter to exit..."\n'
                            '    Read-Host\n'
                            '} finally {\n'
                            '    Write-Host "Cleaning up..."\n'
                            '    Remove-Item -Path $tempExtractDir -Recurse -Force -ErrorAction SilentlyContinue\n'
                            '    Remove-Item -Path $zipPath -Force -ErrorAction SilentlyContinue\n'
                            '    Stop-Transcript\n'
                            '    Start-Sleep -Seconds 2\n'
                            '}\n'
                        )
                        f.write(script_content)
                    
                    command_list = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-NoProfile", "-WindowStyle", "Normal", "-File", script_path]
                    subprocess.Popen(command_list, creationflags=subprocess.CREATE_NEW_CONSOLE)

                logger.info(f"Update script written to '{script_path}'. Launching execution.")
                self.app.quit()

            except Exception as e:
                logger.error(f"Failed to create or launch updater script: {e}", exc_info=True)
                QMessageBox.critical(self.window, "Update Error", f"Could not create the update script: {e}. Please update manually.")
        
        def _promote_widgets(self):
            self.window.audio_file_entry = self.window.findChild(QLineEdit, "audio_file_entry")
            self.window.browse_button = self.window.findChild(QPushButton, "browse_button")
            self.window.model_dropdown = self.window.findChild(QComboBox, "model_dropdown")
            self.window.identify_speakers_checkbutton = self.window.findChild(QCheckBox, "identify_speakers_checkbutton")
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
            self.window.show_tips_checkbox = self.window.findChild(QCheckBox, "show_tips_checkbox")

            self.window.Audio_file_frame = self.window.findChild(QGroupBox, "Audio_file_frame")
            self.window.Processing_options_frame = self.window.findChild(QGroupBox, "Processing_options_frame")
            self.window.status_and_play_frame = self.window.findChild(QGroupBox, "status_and_play_frame")
            self.window.Output_area_frame = self.window.findChild(QGroupBox, "Output_area_frame")
            
            self.window.Speaker_options_frame = self.window.findChild(QGroupBox, "Speaker_options_frame")
            self.window.Timestamps_options_frame = self.window.findChild(QGroupBox, "Timestamps_options_frame")

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
            icon_map = { self.window.browse_button: "folder-open.png", self.window.save_token_button: "disk.png", self.window.correction_button: "next.png", self.window.correction_browse_transcription_btn: "folder-open.png", self.window.correction_browse_audio_btn: "folder-open.png", self.window.correction_save_changes_btn: "disk.png", self.window.correction_load_files_btn: "sort-down.png", self.window.correction_rewind_btn: "rewind.png", self.window.correction_forward_btn: "forward.png", self.window.correction_assign_speakers_btn: "user-add.png", self.window.findChild(QPushButton, "Undo_button"): "undo.png", self.window.findChild(QPushButton, "Redo_Button"): "redo.png", self.window.findChild(QCheckBox, "show_tips_checkbox"): "interrogation.png", self.window.change_highlight_color_btn: "palette.png", self.window.edit_speaker_btn: "user-pen.png", self.window.correction_text_edit_btn: "pencil.png", self.window.correction_timestamp_edit_btn: "stopwatch.png", self.window.segment_btn: "multiple.png", self.window.save_timestamp_btn: "disk.png", self.window.merge_segments_btn: "merge.png", self.window.delete_segment_btn: "trash.png", self.change_files_button: "undo.png", self.proceed_button: "next.png"}
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
            self.change_files_button.clicked.connect(self._return_to_file_selection)
            self.proceed_button.clicked.connect(self._proceed_to_processing_step)
            self.window.start_processing_button.clicked.connect(self.start_or_abort_processing)
            self.window.save_token_button.clicked.connect(self.show_hf_token_dialog)
            self.window.identify_speakers_checkbutton.stateChanged.connect(self.toggle_speaker_options)
            self.window.timestamps_checkbutton_2.stateChanged.connect(self.toggle_timestamp_options)
            self.window.correction_button.clicked.connect(self.go_to_correction)
            self.window.show_tips_checkbox.stateChanged.connect(self.on_tips_toggled)
        
        @Slot(int)
        def toggle_timestamp_options(self, state):
            is_checked = (state == Qt.CheckState.Checked.value)
            self.others_timestamp_box.setEnabled(is_checked)
            if not is_checked:
                self.others_timestamp_box.collapse()
                self.window.end_times_checkbutton.setChecked(False)

        @Slot(int)
        def toggle_speaker_options(self, state):
            is_checked = (state == Qt.CheckState.Checked.value)
            
            self.others_speaker_box.setEnabled(is_checked)
            if not is_checked:
                self.others_speaker_box.collapse()
                self.window.auto_merge_checkbutton.setChecked(False)

            self.window.save_token_button.setVisible(is_checked)
            if is_checked:
                if not self.config_manager.load_huggingface_token():
                    self.show_hf_token_dialog(is_mandatory=True)
        
        @Slot()
        def show_hf_token_dialog(self, is_mandatory=False):
            current_token = self.config_manager.load_huggingface_token()
            dialog = HuggingFaceTokenDialog(current_token, self.window)

            if dialog.exec() == QDialog.Accepted:
                if dialog.token != current_token:
                    self.window.huggingface_token_entry.setText(dialog.token)
                    self.config_manager.save_huggingface_token(dialog.token)
                    self.config_manager.set_use_auth_token(bool(dialog.token))
                    QMessageBox.information(self.window, "Token Saved", "Hugging Face token has been saved successfully.")
            elif is_mandatory:
                self.window.identify_speakers_checkbutton.setChecked(False)
                logger.warning("Mandatory Hugging Face token setup was cancelled.")
        
        def set_ui_for_processing(self, is_processing):
            self.step1_box.setEnabled(not is_processing)
            self.step2_box.setEnabled(not is_processing)
            self.step3_box.setEnabled(True) 

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
            return {
                constants.OPTION_MODEL: self.window.model_dropdown.currentText(), 
                constants.OPTION_DIARIZE: self.window.identify_speakers_checkbutton.isChecked(), 
                constants.OPTION_AUTO_MERGE: self.window.auto_merge_checkbutton.isChecked(), 
                constants.OPTION_TIMESTAMPS: self.window.timestamps_checkbutton_2.isChecked(), 
                constants.OPTION_END_TIMES: self.window.end_times_checkbutton.isChecked(), 
                "hf_token": self.window.huggingface_token_entry.text().strip()
            }
        
        def load_initial_settings(self):
            # Visual Setup
            self.window.huggingface_token_frame.hide()
            self.window.save_token_button.setText("Manage Token")
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            key_icon_path = os.path.join(base_dir, 'assets', 'icons', 'key.png')
            if os.path.exists(key_icon_path):
                 self.window.save_token_button.setIcon(QIcon(key_icon_path))
            
            self.window.correction_button.setEnabled(False)

            self.window.model_dropdown.addItems(["tiny", "base", "small", "medium", "large (recommended)", "turbo"])
            
            saved_options = self.config_manager.load_processing_options()
            self.window.model_dropdown.setCurrentText(saved_options.get(constants.OPTION_MODEL, "large (recommended)"))
            self.window.identify_speakers_checkbutton.setChecked(saved_options.get(constants.OPTION_DIARIZE, False))
            self.window.auto_merge_checkbutton.setChecked(saved_options.get(constants.OPTION_AUTO_MERGE, False))
            self.window.timestamps_checkbutton_2.setChecked(saved_options.get(constants.OPTION_TIMESTAMPS, True))
            self.window.end_times_checkbutton.setChecked(saved_options.get(constants.OPTION_END_TIMES, False))

            token = self.config_manager.load_huggingface_token()
            if token: self.window.huggingface_token_entry.setText(token)
            
            # --- THE BUG FIX ---
            is_diarize_checked = self.window.identify_speakers_checkbutton.isChecked()
            diarize_check_state = Qt.CheckState.Checked.value if is_diarize_checked else Qt.CheckState.Unchecked.value
            self.toggle_speaker_options(diarize_check_state)

            is_ts_checked = self.window.timestamps_checkbutton_2.isChecked()
            ts_check_state = Qt.CheckState.Checked.value if is_ts_checked else Qt.CheckState.Unchecked.value
            self.toggle_timestamp_options(ts_check_state)
            
            # Initial UI state for accordion workflow
            self._set_workflow_step(1)
            
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
            show_tips = self.config_manager.get_main_window_show_tips()
            self.window.show_tips_checkbox.setChecked(show_tips)
            self._apply_tips_state(show_tips)
            self.correction_logic.set_tips_enabled(show_tips)
            logger.info(f"Loaded tips preference on startup: {show_tips}")
            
        @Slot()
        def select_files(self):
            if self.is_processing: return
            file_filter = ("All Media Files (*.wav *.mp3 *.aac *.flac *.m4a *.mp4 *.mov *.avi *.mkv);;Audio Files (*.wav *.mp3 *.aac *.flac *.m4a);;Video Files (*.mp4 *.mov *.avi *.mkv);;All Files (*)")
            paths, _ = QFileDialog.getOpenFileNames(self.window, "Select Audio or Video Files", "", file_filter)
            
            if paths:
                self.audio_file_paths = paths
                summary = f"{len(paths)} file(s) selected: {os.path.basename(paths[0])}"
                if len(paths) > 1: summary += ", ..."
                self.step1_box.set_summary_text(summary)
                self.window.correction_button.setEnabled(False)
                self._set_workflow_step(2)

        def _set_workflow_step(self, step_number):
            if step_number == 1:
                self.step1_box.expand()
                self.step2_box.collapse()
                self.step3_box.collapse()
                
                self.step2_box.setEnabled(False)
                self.step3_box.setEnabled(False)
                self.step2_box.set_summary_text("Select file(s) to continue.")
                self.step3_box.set_summary_text("Configure options to continue.")

                self.change_files_button.hide()
            
            elif step_number == 2:
                self.step1_box.collapse()
                self.step2_box.expand()
                self.step3_box.collapse()

                self.step2_box.setEnabled(True)
                self.step3_box.setEnabled(False)
                self.step2_box.set_summary_text("")
                self.step3_box.set_summary_text("Configure options to continue.")
                
                self.change_files_button.show()
                self.window.browse_button.hide() # Browse is inside the now-open box
            
            elif step_number == 3:
                self.step1_box.collapse()
                self.step2_box.collapse()
                self.step3_box.expand()
                
                self.step2_box.setEnabled(True)
                self.step3_box.setEnabled(True)
                
                options = self.get_processing_options()
                model = options[constants.OPTION_MODEL]
                diarize = "Diarization" if options[constants.OPTION_DIARIZE] else "No Diarization"
                self.step2_box.set_summary_text(f"{model}, {diarize}")
                self.step3_box.set_summary_text("")
                self.start_or_abort_processing()
                
        @Slot()
        def _return_to_file_selection(self):
            if self.is_processing:
                QMessageBox.warning(self.window, "Processing Active", "Cannot change file selection while processing is active.")
                return
            self._set_workflow_step(1)

        @Slot()
        def _proceed_to_processing_step(self):
            # Save the current options before proceeding
            self.config_manager.save_processing_options(self.get_processing_options())
            logger.info("Processing options saved.")
            
            self._set_workflow_step(3)

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
                self._set_workflow_step(1)
                return
            
            if not self.config_manager.get_has_shown_performance_notice():
                QMessageBox.information(self.window, "First-Time Processing Notice",
                    "The first time you run a model, AutoVerse may need to download a few gigabytes of AI model files from the internet.\n\n"
                    "---\n\n"
                    "<b>Smart Time Estimates</b>\n\n"
                    "For future runs, AutoVerse will provide an Estimated Time Remaining (ETR). This estimate will automatically learn from your computer's performance and become more accurate over time.\n\n"
                    "This is a one-time message."
                )
                self.config_manager.set_has_shown_performance_notice(True)

            destination_folder = None
            if len(self.audio_file_paths) > 1:
                destination_folder = QFileDialog.getExistingDirectory(self.window, "Select Destination Folder for Transcriptions")
                if not destination_folder:
                    self.window.status_label.setText("Batch processing cancelled.")
                    self._set_workflow_step(2)
                    return

            self.set_ui_for_processing(True)
            self.window.progress_bar.setValue(0)
            self.window.output_text_area.clear()
            
            options = self.get_processing_options()
            cache_dir = os.path.join(os.path.expanduser('~'), 'AutoVerse_Cache')
            ffmpeg_path = _get_bundled_ffmpeg_path()
            if ffmpeg_path: logger.info(f"Main process identified bundled ffmpeg: {ffmpeg_path}")

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
                    self.window.progress_bar.setValue(0)
                    self.current_step_start_time = time.time()
                    self.original_status_text = data
                elif msg_type == constants.MSG_TYPE_REALTIME_PROGRESS:
                    percentage = data
                    self.window.progress_bar.setValue(percentage)
                    if self.current_step_start_time is not None and percentage > 2:
                        elapsed_time = time.time() - self.current_step_start_time
                        total_predicted_time = (elapsed_time / percentage) * 100
                        remaining_time = total_predicted_time - elapsed_time
                        if remaining_time > 0:
                            self.window.status_label.setText(f"{self.original_status_text} (ETR: ~{self._format_etr(remaining_time)})")
                elif msg_type == constants.MSG_TYPE_SAVE_PERFORMANCE_FACTOR:
                    model_key, new_factor = data
                    logger.info(f"Received new performance factor for '{model_key}': {new_factor:.4f}. Saving.")
                    self.config_manager.save_performance_factor(model_key, new_factor)
                elif msg_type == constants.MSG_TYPE_BATCH_FILE_START:
                    file_info = data
                    status = f"Processing file {file_info[constants.KEY_BATCH_CURRENT_IDX]} of {file_info[constants.KEY_BATCH_TOTAL_FILES]}: {file_info[constants.KEY_BATCH_FILENAME]}"
                    self.window.status_label.setText(status)
                    self.window.progress_bar.setValue(0)
                elif msg_type == constants.MSG_TYPE_BATCH_COMPLETED:
                    self.current_step_start_time = None
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
        
        def _format_etr(self, seconds: float) -> str:
            if seconds < 60:
                return f"{int(seconds)}s"
            else:
                mins = int(seconds / 60)
                secs = int(seconds % 60)
                return f"{mins}m {secs:02d}s"

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
            model_name = self.get_processing_options()[constants.OPTION_MODEL].split(" ")[0]
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

    app = QApplication(sys.argv)
    main_app = MainApplication(app)
    sys.exit(app.exec())

if __name__ == "__main__":
    configure_ssl_for_bundle()
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn', force=True)
    run_app()
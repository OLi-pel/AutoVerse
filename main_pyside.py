



import sys
import multiprocessing
import os
import collections
import logging
import ctypes
import site
import shutil

# --- [FIX]: WINDOWS FROZEN BUILD DLL INJECTION ---
if sys.platform == 'win32':
    # 1. Standard Environment fixes
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    
    # Graphics compatibility for older hardware
    os.environ["QT_API"] = "pyside6"
    os.environ["QSG_RHI_BACKEND"] = "opengl"

    if getattr(sys, 'frozen', False):
        try:
            # 2. Locate the Bundle Directory
            # PyInstaller 6+ '_internal' folder or legacy sys._MEIPASS
            base_dir = os.path.dirname(sys.executable)
            if hasattr(sys, '_MEIPASS'):
                base_dir = sys._MEIPASS
            elif os.path.exists(os.path.join(base_dir, '_internal')):
                base_dir = os.path.join(base_dir, '_internal')

            torch_lib_path = os.path.join(base_dir, 'torch', 'lib')

            # 3. Add directories to DLL Search Path (Python 3.8+)
            # We must add BOTH the torch/lib folder AND the base directory
            # (where vcruntime140.dll usually lives)
            if hasattr(os, 'add_dll_directory'):
                try:
                    os.add_dll_directory(torch_lib_path)
                except Exception:
                    pass
                try:
                    os.add_dll_directory(base_dir)
                except Exception:
                    pass

            # Legacy PATH update
            os.environ['PATH'] = torch_lib_path + os.pathsep + base_dir + os.pathsep + os.environ['PATH']

            # 4. CRITICAL: Manually Pre-load Dependencies in Order
            # We attempt to load the VCRuntime first, then OpenMP, then Torch.
            dlls_to_preload = [
                (base_dir, 'vcruntime140.dll'),
                (base_dir, 'vcruntime140_1.dll'), # Critical for Exception Handling in c10.dll
                (base_dir, 'msvcp140.dll'),
                (torch_lib_path, 'libiomp5md.dll'),  # OpenMP
                (torch_lib_path, 'mkl_intel_thread.dll'),
                (torch_lib_path, 'fbgemm.dll'),
                (torch_lib_path, 'asmjit.dll'), # Often required by fbgemm/c10
                (torch_lib_path, 'c10.dll'),
                (torch_lib_path, 'torch_cpu.dll')
            ]

            for folder, dll_name in dlls_to_preload:
                dll_path = os.path.join(folder, dll_name)
                if os.path.exists(dll_path):
                    try:
                        ctypes.CDLL(dll_path, mode=ctypes.RTLD_GLOBAL)
                    except Exception as e:
                        # Print debug but don't stop; some might already be loaded
                        print(f"--- [DEBUG] Pre-loading {dll_name} failed: {e}")
                            
        except Exception as e:
            print(f"--- [DEBUG] Critical Error during DLL setup: {e}")

# --- End of Windows Fix ---

try:
    import torch
    import torchaudio
    if not hasattr(torchaudio, 'list_audio_backends'):
        setattr(torchaudio, 'list_audio_backends', lambda: ['soundfile', 'ffmpeg'])
    if not hasattr(torchaudio, 'get_audio_backend'):
        setattr(torchaudio, 'get_audio_backend', lambda: 'soundfile')
    if not hasattr(torchaudio, 'AudioMetaData'):
        try:
            from torchaudio.backend.common import AudioMetaData # type: ignore
            setattr(torchaudio, 'AudioMetaData', AudioMetaData)
        except ImportError:
            AudioMetaData = collections.namedtuple('AudioMetaData', ['sample_rate', 'num_frames', 'num_channels', 'bits_per_sample', 'encoding'])
            setattr(torchaudio, 'AudioMetaData', AudioMetaData)
except Exception as e:
    print(f"--- [DEBUG] Warning during early torch import: {e}")

import ssl
import certifi
from queue import Empty
import platform
import requests
import webbrowser
from packaging.version import Version

from PySide6.QtWidgets import QApplication

def configure_ssl_for_bundle():
    """Configures SSL for PyInstaller bundles."""
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        try:
            cert_path = certifi.where()
            os.environ['SSL_CERT_FILE'] = cert_path
            ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=cert_path)
        except Exception as e:
            print(f"CRITICAL: Failed to configure SSL certificates for bundle. Error: {e}")

def _get_bundled_ffmpeg_path():
    """Checks if the app is a PyInstaller bundle OR running from source and returns ffmpeg path."""
    if getattr(sys, 'frozen', False):
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(sys.executable)
            # Check for _internal folder (PyInstaller 6+ onedir mode)
            internal_dir = os.path.join(base_dir, '_internal')
            if os.path.exists(internal_dir) and os.path.exists(os.path.join(internal_dir, 'bin')):
                base_dir = internal_dir
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    exe_name = 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg'
    potential_path = os.path.join(base_dir, 'bin', exe_name)
    
    if os.path.exists(potential_path):
        return potential_path
    
    return shutil.which('ffmpeg')

def apply_modern_theme(app):
    app.setStyle("Fusion")
    dark_qss = """
    QWidget { background-color: #1e1e1e; color: #d4d4d4; font-family: "Segoe UI", "Helvetica Neue", "Arial", sans-serif; font-size: 14px; }
    QGroupBox { border: 1px solid #3e3e3e; border-radius: 6px; margin-top: 20px; background-color: transparent; padding-top: 10px; }
    QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0px 5px; background-color: transparent; color: #e0e0e0; font-weight: bold; }
    QLabel, QCheckBox, QRadioButton { background-color: transparent; }
    QLineEdit, QTextEdit, QPlainTextEdit { background-color: #3c3c3c; border: 1px solid #3e3e3e; border-radius: 4px; padding: 4px; color: #d4d4d4; selection-background-color: #264f78; }
    QLineEdit:focus, QTextEdit:focus { border: 1px solid #007acc; }
    QPushButton { background-color: #3c3c3c; border: 1px solid #3e3e3e; border-radius: 4px; padding: 6px 12px; color: #ffffff; }
    QPushButton:hover { background-color: #4c4c4c; }
    QPushButton:pressed { background-color: #2c2c2c; }
    QPushButton:disabled { background-color: #252526; color: #666666; border: 1px solid #2d2d2d; }
    QPushButton#correction_save_changes_btn, QPushButton#start_processing_button { background-color: #007acc; border: 1px solid #007acc; }
    QPushButton#correction_save_changes_btn:hover, QPushButton#start_processing_button:hover { background-color: #0062a3; }
    QTabWidget::pane { border: 1px solid #3e3e3e; background-color: #1e1e1e; }
    QTabBar::tab { background-color: #2d2d2d; color: #999999; padding: 8px 16px; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
    QTabBar::tab:selected { background-color: #1e1e1e; color: #ffffff; border-top: 2px solid #007acc; }
    QTabBar::tab:hover { background-color: #3e3e3e; }
    QCheckBox { spacing: 8px; }
    QCheckBox::indicator { width: 18px; height: 18px; background-color: #3c3c3c; border: 1px solid #555555; border-radius: 3px; }
    QCheckBox::indicator:checked { background-color: #007acc; border: 1px solid #007acc; image: url(assets/icons/check.png); }
    QScrollBar:vertical { border: none; background: #1e1e1e; width: 12px; margin: 0px; }
    QScrollBar::handle:vertical { background: #424242; min-height: 20px; border-radius: 6px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QProgressBar { border: 1px solid #3e3e3e; border-radius: 4px; text-align: center; background-color: #252526; }
    QProgressBar::chunk { background-color: #007acc; border-radius: 3px; }
    QStatusBar { background-color: #007acc; color: white; }
    """
    app.setStyleSheet(dark_qss)

def run_app():
    if sys.platform == 'win32':
        multiprocessing.freeze_support()

    import time
    from PySide6.QtCore import QObject, Slot, QTimer, QThread, Signal, Qt
    from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QDialogButtonBox, QFileDialog, QMessageBox, QLineEdit, 
                                 QPushButton, QComboBox, QFrame, QCheckBox, QProgressBar, QLabel, 
                                 QTextEdit, QWidget, QTabWidget, QGroupBox, QSpacerItem, QSizePolicy, QScrollArea)
    from PySide6.QtGui import QIcon, QFontMetrics, QFont, QFontDatabase, QPixmap
    from PySide6.QtUiTools import QUiLoader

    from utils.logging_setup import setup_logging
    from utils import constants
    from utils import translations 
    from utils.config_manager import ConfigManager
    from ui.correction_view_logic import CorrectionViewLogic
    from ui.settings_logic import SettingsLogic
    from core.app_worker import processing_worker_function
    from core.audio_processor import AudioProcessor
    from ui.selectable_text_edit import SelectableTextEdit
    from utils import tips_data
    from core.tutorial_manager import TutorialManager
    from ui.widgets.tutorial_overlay import TutorialOverlay

    setup_logging()
    logger = logging.getLogger(__name__)

    class HuggingFaceTokenDialog(QDialog):
        def __init__(self, current_token, lang="Français", parent=None):
            super().__init__(parent)
            self.setWindowTitle(translations.get_text("hf_dialog_title", lang))
            self.token = current_token
            self.setMinimumWidth(550)
            main_layout = QVBoxLayout(self)
            info_group = QGroupBox(translations.get_text("hf_group_why", lang))
            info_layout = QVBoxLayout()
            info_label = QLabel(translations.get_text("hf_label_why", lang))
            info_label.setWordWrap(True)
            info_layout.addWidget(info_label)
            info_group.setLayout(info_layout)
            main_layout.addWidget(info_group)
            steps_group = QGroupBox(translations.get_text("hf_group_steps", lang))
            steps_layout = QGridLayout()
            steps_layout.setSpacing(10)
            steps_layout.addWidget(QLabel(translations.get_text("hf_step1", lang)), 0, 0)
            steps_layout.addWidget(QLabel(translations.get_text("hf_step1_desc", lang)), 0, 1)
            btn_step1 = QPushButton(translations.get_text("hf_btn_step1", lang))
            btn_step1.clicked.connect(lambda: webbrowser.open("https://huggingface.co/join"))
            steps_layout.addWidget(btn_step1, 0, 2)
            steps_layout.addWidget(QLabel(translations.get_text("hf_step2", lang)), 1, 0)
            steps_layout.addWidget(QLabel(translations.get_text("hf_step2_desc", lang)), 1, 1)
            btn_layout_s2 = QHBoxLayout()
            btn_s2a = QPushButton(translations.get_text("hf_btn_model1", lang))
            btn_s2b = QPushButton(translations.get_text("hf_btn_model2", lang))
            btn_s2a.clicked.connect(lambda: webbrowser.open("https://huggingface.co/pyannote/segmentation-3.0"))
            btn_s2b.clicked.connect(lambda: webbrowser.open("https://huggingface.co/pyannote/speaker-diarization-3.1"))
            btn_layout_s2.addWidget(btn_s2a)
            btn_layout_s2.addWidget(btn_s2b)
            steps_layout.addLayout(btn_layout_s2, 1, 2)
            steps_layout.addWidget(QLabel(translations.get_text("hf_step3", lang)), 2, 0)
            steps_layout.addWidget(QLabel(translations.get_text("hf_step3_desc", lang)), 2, 1)
            btn_step3 = QPushButton(translations.get_text("hf_btn_step3", lang))
            btn_step3.clicked.connect(lambda: webbrowser.open("https://huggingface.co/settings/tokens"))
            steps_layout.addWidget(btn_step3, 2, 2)
            steps_layout.addWidget(QLabel(translations.get_text("hf_step4", lang)), 3, 0)
            self.token_entry = QLineEdit()
            self.token_entry.setPlaceholderText(translations.get_text("hf_placeholder", lang))
            self.token_entry.setText(current_token) 
            steps_layout.addWidget(self.token_entry, 3, 1, 1, 2)
            steps_group.setLayout(steps_layout)
            main_layout.addWidget(steps_group)
            button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
            self.save_button = button_box.button(QDialogButtonBox.Save)
            self.save_button.setText(translations.get_text("hf_btn_save", lang))
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
        def __init__(self, lang="Français", parent=None):
            super().__init__(parent)
            self.setWindowTitle(translations.get_text("welcome_title", lang))
            self.choice = None
            self.setModal(True)
            self.setFixedSize(500, 320)
            if hasattr(sys, '_MEIPASS'): base_dir = sys._MEIPASS
            else: base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            icon_dir = os.path.join(base_dir, 'assets', 'icons')
            layout = QVBoxLayout(self)
            layout.setContentsMargins(30, 30, 30, 30)
            layout.setSpacing(15)
            welcome_label = QLabel(translations.get_text("welcome_label", lang))
            welcome_label.setAlignment(Qt.AlignCenter)
            welcome_label.setStyleSheet("QLabel { font-size: 22px; font-weight: bold; margin-bottom: 10px; border: none; }")
            layout.addWidget(welcome_label)
            self.launch_button = QPushButton(translations.get_text("btn_launch_app", lang))
            self.launch_button.setIcon(QIcon.fromTheme("media-playback-start", QIcon(os.path.join(icon_dir, 'forward.png'))))
            self.launch_button.setMinimumHeight(70)
            self.launch_button.setCursor(Qt.PointingHandCursor)
            launch_desc = translations.get_text("btn_launch_desc", lang)
            self.launch_button.setText(f"{translations.get_text('btn_launch_app', lang)}\n{launch_desc}")
            self.launch_button.setStyleSheet("""QPushButton { font-size: 16px; text-align: left; padding: 10px 20px; border: 1px solid #555; border-radius: 8px; background-color: #333; color: white; } QPushButton:hover { background-color: #444; border-color: #777; }""")
            self.launch_button.clicked.connect(self.select_launch)
            layout.addWidget(self.launch_button)
            self.tutorial_button = QPushButton(translations.get_text("btn_tutorial", lang))
            self.tutorial_button.setIcon(QIcon(os.path.join(icon_dir, 'interrogation.png')))
            self.tutorial_button.setMinimumHeight(70)
            self.tutorial_button.setCursor(Qt.PointingHandCursor)
            tut_desc = translations.get_text("btn_tutorial_desc", lang)
            self.tutorial_button.setText(f"{translations.get_text('btn_tutorial', lang)}\n{tut_desc}")
            self.tutorial_button.setStyleSheet("""QPushButton { font-size: 16px; text-align: left; padding: 10px 20px; background-color: #0078d7; color: white; border: 1px solid #005a9e; border-radius: 8px; } QPushButton:hover { background-color: #106ebe; }""")
            self.tutorial_button.clicked.connect(self.select_tutorial)
            layout.addWidget(self.tutorial_button)
            layout.addStretch(1)
            self.dont_show_again_checkbox = QCheckBox(translations.get_text("chk_dont_show", lang))
            self.dont_show_again_checkbox.setStyleSheet("QCheckBox { font-size: 12px; margin-top: 10px; border: none; }")
            layout.addWidget(self.dont_show_again_checkbox, 0, Qt.AlignRight)
        def select_launch(self):
            self.choice = 'launch'
            self.accept()
        def select_tutorial(self):
            self.choice = 'tutorial'
            self.accept()

    class UpdateChecker(QThread):
        update_available = Signal(str, str, str)
        no_update_signal = Signal()
        error_signal = Signal(str)
        def __init__(self, owner, repo, manual_check=False):
            super().__init__()
            self.owner = owner; self.repo = repo; self.manual_check = manual_check
        def run(self):
            try:
                url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
                logger.info(f"Checking for updates at: {url}")
                response = requests.get(url, timeout=10); response.raise_for_status()
                latest_release = response.json(); latest_version_str = latest_release.get("tag_name", "v0.0.0").lstrip('v'); release_url = latest_release.get("html_url", url)
                if Version(latest_version_str) > Version(constants.APP_VERSION):
                    logger.info(f"Update found! Current: {constants.APP_VERSION}, Latest: {latest_version_str}")
                    self.update_available.emit(latest_version_str, latest_release.get("body", "No release notes available."), release_url)
                else:
                    if self.manual_check: self.no_update_signal.emit()
            except requests.RequestException as e:
                logger.warning(f"Could not check for updates (network issue): {e}")
                if self.manual_check: self.error_signal.emit(str(e))
            except Exception as e:
                logger.error(f"An unexpected error occurred during update check: {e}", exc_info=True)
                if self.manual_check: self.error_signal.emit(str(e))

    class MainApplication(QObject):
        def __init__(self, app_instance):
            super().__init__()
            self.app = app_instance
            loader = QUiLoader()
            loader.registerCustomWidget(SelectableTextEdit)
            if hasattr(sys, '_MEIPASS'): base_path = sys._MEIPASS
            else: base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            ui_file_path = os.path.join(base_path, "ui", "main_window.ui")
            self.window = loader.load(ui_file_path, None)
            if not self.window: logger.critical(f"Failed to load UI file: {ui_file_path}"); sys.exit(1)
            self.config_manager = ConfigManager(constants.DEFAULT_CONFIG_FILE)
            self.current_language = self.config_manager.get_language()
            self.window.setWindowTitle(translations.get_text("window_title", self.current_language, constants.APP_VERSION))
            self.is_processing = False; self.current_step = 1
            self._promote_widgets()
            self._setup_main_workflow_layout()
            self._setup_nested_options()
            self._setup_settings_tab_layout()
            self.correction_logic = CorrectionViewLogic(self.window, self)
            self.settings_logic = SettingsLogic(self.window, self)
            self.tip_widgets = {self.window.audio_file_entry: "audio_file_browse", self.window.browse_button: "audio_file_browse", self.window.identify_speakers_checkbutton: "enable_diarization_checkbox", self.window.auto_merge_checkbutton: "auto_merge_checkbutton", self.window.timestamps_checkbutton_2: "include_timestamps_checkbox", self.window.end_times_checkbutton: "include_end_times_checkbox", self.window.huggingface_token_entry: "huggingface_token_entry", self.window.save_token_button: "save_huggingface_token_button", self.window.start_processing_button: "start_processing_button", self.window.status_label: "status_label", self.window.progress_bar: "progress_bar", self.window.output_text_area: "output_text_area", self.window.correction_button: "correction_window_button", self.window.show_tips_checkbox: "show_tips_checkbox_main"}
            self._setup_fonts(); self._setup_icons()
            self.tutorial_overlay = TutorialOverlay(self.window); self.tutorial_manager = TutorialManager(self, self.tutorial_overlay); self._setup_tutorial_menu()
            self.app.aboutToQuit.connect(self.cleanup)
            self.audio_file_paths = []; self.process = None; self.queue = None; self.last_single_file_result_path = None
            self.current_step_start_time = None; self.original_status_text = ""
            self.timer = QTimer(); self.timer.timeout.connect(self.check_queue)
            self.connect_signals(); self.load_initial_settings(); self.retranslateUi()
            QTimer.singleShot(0, self.run_startup_logic)

        def retranslateUi(self):
            lang = self.current_language
            self.window.setWindowTitle(translations.get_text("window_title", lang, constants.APP_VERSION))
            self.window.main_tab_widget.setTabText(0, translations.get_text("tab_transcription", lang))
            self.window.main_tab_widget.setTabText(1, translations.get_text("tab_correction", lang))
            self.window.main_tab_widget.setTabText(2, translations.get_text("tab_settings", lang))
            self.window.Audio_file_frame.setTitle(translations.get_text("step1_title", lang))
            self.window.findChild(QLabel, "label").setText(translations.get_text("lbl_file_path", lang))
            self.window.Processing_options_frame.setTitle(translations.get_text("step2_title", lang))
            self.window.Speaker_options_frame.setTitle(translations.get_text("grp_speaker", lang))
            self.window.identify_speakers_checkbutton.setText(translations.get_text("chk_identify_speakers", lang))
            self.window.save_token_button.setText(translations.get_text("btn_manage_token", lang))
            self.window.auto_merge_checkbutton.setText(translations.get_text("chk_auto_merge", lang))
            self.window.Timestamps_options_frame.setTitle(translations.get_text("grp_timestamps", lang))
            self.window.timestamps_checkbutton_2.setText(translations.get_text("chk_timestamps", lang))
            self.window.end_times_checkbutton.setText(translations.get_text("chk_end_times", lang))
            self.window.huggingface_token_frame.setTitle(translations.get_text("grp_huggingface", lang))
            if hasattr(self, 'step3_group'): self.step3_group.setTitle(translations.get_text("step3_title", lang))
            self.window.Output_area_frame.setTitle(translations.get_text("grp_output", lang))
            self.window.status_label.setText(translations.get_text("lbl_status_inactive", lang))
            if not self.is_processing:
                self.window.start_processing_button.setText(translations.get_text("btn_start_processing", lang))
            else:
                self.window.start_processing_button.setText(translations.get_text("btn_abort", lang))
            self.window.correction_button.setText(translations.get_text("btn_correction_tab", lang))
            self.window.findChild(QGroupBox, "Load_objects_frame").setTitle(translations.get_text("grp_load_files", lang))
            self.window.findChild(QLabel, "label_3").setText(translations.get_text("lbl_transcription_file", lang))
            self.window.findChild(QLabel, "label_4").setText(translations.get_text("lbl_audio_file", lang))
            self.window.correction_load_files_btn.setText(translations.get_text("btn_load_files", lang))
            self.window.correction_save_changes_btn.setText(translations.get_text("btn_save_changes", lang))
            self.window.findChild(QGroupBox, "Audio_player_frame").setTitle(translations.get_text("grp_audio_player", lang))
            if not (hasattr(self.correction_logic, 'audio_player') and self.correction_logic.audio_player.is_playing):
                 self.window.correction_play_pause_btn.setText(translations.get_text("btn_play", lang))
            else:
                 self.window.correction_play_pause_btn.setText(translations.get_text("btn_pause", lang))
            self.window.findChild(QGroupBox, "appearance_group").setTitle(translations.get_text("grp_appearance", lang))
            self.window.findChild(QLabel, "label_lang").setText(translations.get_text("lbl_language", lang))
            self.window.findChild(QGroupBox, "application_group").setTitle(translations.get_text("grp_application", lang))
            self.window.findChild(QLabel, "label_updates").setText(translations.get_text("lbl_updates", lang))
            self.window.findChild(QPushButton, "settings_check_updates_btn").setText(translations.get_text("btn_check_updates", lang))
            self.window.findChild(QPushButton, "settings_reset_tutorials_btn").setText(translations.get_text("btn_reset_tutorials", lang))
            self.window.findChild(QPushButton, "settings_clear_cache_btn").setText(translations.get_text("btn_clear_cache", lang))
            self.window.findChild(QPushButton, "settings_reset_app_btn").setText(translations.get_text("btn_reset_app", lang))
            self._apply_tips_state(self.window.show_tips_checkbox.isChecked())
            if hasattr(self, 'correction_logic'): self.correction_logic.update_tips_language(lang)

        def run_startup_logic(self):
            if getattr(sys, 'frozen', False):
                logger.info("Application is frozen, initializing update check.")
                self.check_for_updates_automatic()
            else:
                logger.info("Application not frozen. Skipping update check.")
            last_seen_version = self.config_manager.get_last_seen_version()
            if Version(constants.APP_VERSION) > Version(last_seen_version):
                logger.info(f"New version detected ({last_seen_version} -> {constants.APP_VERSION}). Forcing welcome wizard.")
                self.config_manager.set_show_welcome_wizard(True)
                self.config_manager.set_last_seen_version(constants.APP_VERSION)
            
            user_choice = None
            if self.config_manager.get_show_welcome_wizard():
                try:
                    welcome_dialog = WelcomeDialog(self.current_language, self.window)
                    if welcome_dialog.exec() == QDialog.Accepted:
                        self.config_manager.set_show_welcome_wizard(not welcome_dialog.dont_show_again_checkbox.isChecked())
                        user_choice = welcome_dialog.choice
                    else: 
                        self.config_manager.set_show_welcome_wizard(not welcome_dialog.dont_show_again_checkbox.isChecked())
                except Exception as e:
                    logger.error(f"Failed to show welcome wizard: {e}")
            
            self.window.show()
            if user_choice == 'tutorial': 
                QTimer.singleShot(100, lambda: self.tutorial_manager.start_tutorial("main_tutorial"))

        def check_for_updates_automatic(self):
            self.update_checker = UpdateChecker(owner="OLi-pel", repo="AutoVerse", manual_check=False)
            self.update_checker.update_available.connect(self.prompt_for_update)
            self.update_checker.start()

        def check_for_updates_manual(self):
            self.manual_update_checker = UpdateChecker(owner="OLi-pel", repo="AutoVerse", manual_check=True)
            self.manual_update_checker.update_available.connect(self.prompt_for_update)
            lang = self.current_language
            self.manual_update_checker.no_update_signal.connect(lambda: QMessageBox.information(self.window, translations.get_text("update_uptodate_title", lang), translations.get_text("update_uptodate_msg", lang)))
            self.manual_update_checker.error_signal.connect(lambda msg: QMessageBox.warning(self.window, "Update Error", f"Could not check for updates: {msg}"))
            self.manual_update_checker.start()

        def _setup_tutorial_menu(self):
            menu_bar = self.window.menuBar(); help_menu = menu_bar.addMenu("&Help"); start_tutorial_action = help_menu.addAction("Start Tutorial")
            if hasattr(sys, '_MEIPASS'): base_dir = sys._MEIPASS
            else: base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            start_tutorial_action.setIcon(QIcon(os.path.join(base_dir, 'assets', 'icons', "interrogation.png")))
            start_tutorial_action.triggered.connect(lambda: self.tutorial_manager.start_tutorial("main_tutorial"))

        def _setup_main_workflow_layout(self):
            transcription_tab = self.window.findChild(QWidget, "tab")
            widgets_to_keep = [self.window.Audio_file_frame, self.window.Processing_options_frame, self.window.status_and_play_frame, self.window.Output_area_frame]
            for w in widgets_to_keep: 
                if w: w.setParent(None)
            old_layout = transcription_tab.layout()
            if old_layout: QWidget().setLayout(old_layout)
            transcription_tab_layout = QVBoxLayout(transcription_tab); transcription_tab_layout.setSpacing(15); transcription_tab_layout.setContentsMargins(15, 15, 15, 15)
            transcription_tab_layout.addWidget(self.window.Audio_file_frame)
            speaker_frame = self.window.Speaker_options_frame; timestamps_frame = self.window.Timestamps_options_frame; token_frame = self.window.huggingface_token_frame
            if speaker_frame: speaker_frame.setParent(None)
            if timestamps_frame: timestamps_frame.setParent(None)
            if token_frame: token_frame.setParent(None)
            old_proc_layout = self.window.Processing_options_frame.layout()
            if old_proc_layout: QWidget().setLayout(old_proc_layout)
            step2_main_layout = QVBoxLayout(self.window.Processing_options_frame); step2_grid = QGridLayout(); step2_grid.setSpacing(15)
            step2_grid.addWidget(speaker_frame, 0, 0); step2_grid.addWidget(timestamps_frame, 0, 1); step2_grid.addWidget(token_frame, 1, 0, 1, 2); step2_main_layout.addLayout(step2_grid)
            transcription_tab_layout.addWidget(self.window.Processing_options_frame)
            self.step3_group = QGroupBox(); step3_layout = QVBoxLayout(self.step3_group)
            if self.window.status_and_play_frame: step3_layout.addWidget(self.window.status_and_play_frame)
            if self.window.Output_area_frame: step3_layout.addWidget(self.window.Output_area_frame)
            transcription_tab_layout.addWidget(self.step3_group); transcription_tab_layout.addStretch(1)

        def _setup_nested_options(self): pass
        def _setup_settings_tab_layout(self): 
            settings_tab = self.window.findChild(QWidget, "tab_3"); layout = settings_tab.layout(); 
            if not layout: return
            pass

        def _apply_tips_state(self, is_enabled):
            self.window.statusBar().setVisible(is_enabled)
            for widget, tip_key in self.tip_widgets.items():
                if not widget: continue
                if is_enabled: tip_text = tips_data.get_tip(tip_key, self.current_language); widget.setStatusTip(tip_text or "")
                else: widget.setStatusTip("")

        @Slot(int)
        def on_tips_toggled(self, state):
            is_enabled = (state == Qt.Checked.value); self._apply_tips_state(is_enabled); self.correction_logic.set_tips_enabled(is_enabled)
            self.config_manager.set_main_window_show_tips(is_enabled); logger.info(f"Tips display set to: {is_enabled} and preference saved.")

        def cleanup(self):
            logger.info("Application quitting. Cleaning up...")
            if self.process and self.process.is_alive(): logger.warning("Terminating active process due to application quit."); self.process.terminate(); self.process.join(1)
            if hasattr(self, 'correction_logic'):
                if hasattr(self.correction_logic, 'cleanup'): self.correction_logic.cleanup()
                elif hasattr(self.correction_logic, 'audio_player'): self.correction_logic.audio_player.destroy()
            if hasattr(self, 'tutorial_overlay'): self.tutorial_overlay.hide()
            logger.info("Cleanup finished.")

        @Slot(str, str, str)
        def prompt_for_update(self, version, notes, url):
            msg_box = QMessageBox(self.window); msg_box.setWindowTitle(f"Update Available: v{version}")
            msg_box.setText(f"A new version of AutoVerse is available (<b>v{version}</b>). You have v{constants.APP_VERSION}.<br><br>Would you like to view the release page?")
            msg_box.setInformativeText(f"<b>Release Notes:</b><hr>{notes}"); msg_box.setTextFormat(Qt.RichText)
            open_btn = msg_box.addButton("Open Release Page", QMessageBox.AcceptRole); ignore_btn = msg_box.addButton("Ignore", QMessageBox.RejectRole)
            msg_box.setDefaultButton(open_btn); msg_box.exec()
            if msg_box.clickedButton() == open_btn: webbrowser.open(url)

        def _promote_widgets(self):
            self.window.audio_file_entry = self.window.findChild(QLineEdit, "audio_file_entry"); self.window.browse_button = self.window.findChild(QPushButton, "browse_button")
            self.window.identify_speakers_checkbutton = self.window.findChild(QCheckBox, "identify_speakers_checkbutton"); self.window.auto_merge_checkbutton = self.window.findChild(QCheckBox, "auto_merge_checkbutton")
            self.window.timestamps_checkbutton_2 = self.window.findChild(QCheckBox, "timestamps_checkbutton_2"); self.window.end_times_checkbutton = self.window.findChild(QCheckBox, "end_times_checkbutton")
            self.window.huggingface_token_frame = self.window.findChild(QGroupBox, "huggingface_token_frame"); self.window.huggingface_token_entry = self.window.findChild(QLineEdit, "huggingface_token_entry")
            self.window.save_token_button = self.window.findChild(QPushButton, "save_token_button"); self.window.start_processing_button = self.window.findChild(QPushButton, "start_processing_button")
            self.window.status_label = self.window.findChild(QLabel, "status_label"); self.window.progress_bar = self.window.findChild(QProgressBar, "progress_bar")
            self.window.output_text_area = self.window.findChild(QTextEdit, "output_text_area"); self.window.correction_button = self.window.findChild(QPushButton, "correction_button")
            self.window.main_tab_widget = self.window.findChild(QTabWidget, "tabWidget"); self.window.show_tips_checkbox = self.window.findChild(QCheckBox, "show_tips_checkbox")
            self.window.Audio_file_frame = self.window.findChild(QGroupBox, "Audio_file_frame"); self.window.Processing_options_frame = self.window.findChild(QGroupBox, "Processing_options_frame")
            self.window.status_and_play_frame = self.window.findChild(QGroupBox, "status_and_play_frame"); self.window.Output_area_frame = self.window.findChild(QGroupBox, "Output_area_frame")
            self.window.Speaker_options_frame = self.window.findChild(QGroupBox, "Speaker_options_frame"); self.window.Timestamps_options_frame = self.window.findChild(QGroupBox, "Timestamps_options_frame")
            self.window.correction_transcription_entry = self.window.findChild(QLineEdit, "correction_transcription_entry"); self.window.correction_browse_transcription_btn = self.window.findChild(QPushButton, "correction_browse_transcription_btn")
            self.window.correction_audio_entry = self.window.findChild(QLineEdit, "correction_audio_entry"); self.window.correction_browse_audio_btn = self.window.findChild(QPushButton, "correction_browse_audio_btn")
            self.window.correction_load_files_btn = self.window.findChild(QPushButton, "correction_load_files_btn"); self.window.correction_assign_speakers_btn = self.window.findChild(QPushButton, "correction_assign_speakers_btn")
            self.window.correction_save_changes_btn = self.window.findChild(QPushButton, "correction_save_changes_btn"); self.window.correction_play_pause_btn = self.window.findChild(QPushButton, "correction_play_pause_btn")
            self.window.correction_rewind_btn = self.window.findChild(QPushButton, "correction_rewind_btn"); self.window.correction_forward_btn = self.window.findChild(QPushButton, "correction_forward_btn")
            self.window.correction_timeline_frame = self.window.findChild(QWidget, "correction_timeline_frame"); self.window.correction_time_label = self.window.findChild(QLabel, "correction_time_label")
            self.window.correction_text_area = self.window.findChild(SelectableTextEdit, "correction_text_area"); self.window.edit_speaker_btn = self.window.findChild(QPushButton, "edit_speaker_btn")
            self.window.correction_text_edit_btn = self.window.findChild(QPushButton, "correction_text_edit_btn"); self.window.correction_timestamp_edit_btn = self.window.findChild(QPushButton, "correction_timestamp_edit_btn")
            self.window.segment_btn = self.window.findChild(QPushButton, "segment_btn"); self.window.save_timestamp_btn = self.window.findChild(QPushButton, "save_timestamp_btn")
            self.window.change_highlight_color_btn = self.window.findChild(QPushButton, "change_highlight_color_btn"); self.window.delete_segment_btn = self.window.findChild(QPushButton, "delete_segment_btn")
            self.window.merge_segments_btn = self.window.findChild(QPushButton, "merge_segments_btn"); self.window.text_font_combo = self.window.findChild(QComboBox, "text_font"); self.window.font_size_combo = self.window.findChild(QComboBox, "Police_size")

        def _setup_fonts(self):
            font_families = QFontDatabase.families()
            if "Monaco" in font_families:
                self.window.monospace_font = QFont("Monaco", 12)
            else:
                self.window.monospace_font = QFont("Monospace", 12)
            self.window.monospace_font.setStyleHint(QFont.StyleHint.Monospace)
            
            self.window.text_font_combo.addItems(font_families)
            default_font = "Monaco" if "Monaco" in font_families else "Courier New" if "Courier New" in font_families else "Monospace"
            self.window.text_font_combo.setCurrentText(default_font)

        def _setup_icons(self):
            if hasattr(sys, '_MEIPASS'): base_dir = sys._MEIPASS
            else: base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            icon_dir = os.path.join(base_dir, 'assets', 'icons'); self.window.icon_dir = icon_dir
            icon_map = { self.window.browse_button: "folder-open.png", self.window.save_token_button: "disk.png", self.window.correction_button: "next.png", self.window.correction_browse_transcription_btn: "folder-open.png", self.window.correction_browse_audio_btn: "folder-open.png", self.window.correction_save_changes_btn: "disk.png", self.window.correction_load_files_btn: "sort-down.png", self.window.correction_rewind_btn: "rewind.png", self.window.correction_forward_btn: "forward.png", self.window.correction_assign_speakers_btn: "user-add.png", self.window.findChild(QPushButton, "Undo_button"): "undo.png", self.window.findChild(QPushButton, "Redo_Button"): "redo.png", self.window.findChild(QCheckBox, "show_tips_checkbox"): "interrogation.png", self.window.change_highlight_color_btn: "palette.png", self.window.edit_speaker_btn: "user-pen.png", self.window.correction_text_edit_btn: "pencil.png", self.window.correction_timestamp_edit_btn: "stopwatch.png", self.window.segment_btn: "multiple.png", self.window.save_timestamp_btn: "disk.png", self.window.merge_segments_btn: "merge.png", self.window.delete_segment_btn: "trash.png"}
            for widget, filename in icon_map.items():
                if widget:
                    icon_path = os.path.join(icon_dir, filename)
                    if os.path.exists(icon_path): widget.setIcon(QIcon(icon_path))
                    else: logger.warning(f"Icon not found: {icon_path}")
            self.window.icon_play = QIcon(os.path.join(icon_dir, "play.png")); self.window.icon_abort = QIcon(os.path.join(icon_dir, "stop.png")); self.window.icon_pause = QIcon(os.path.join(icon_dir, "pause.png"))
            self.window.icon_edit_text = QIcon(os.path.join(icon_dir, "pencil.png")); self.window.icon_save_edit = QIcon(os.path.join(icon_dir, "sign-out-alt.png"))
            self.window.icon_edit_timestamp = QIcon(os.path.join(icon_dir, "stopwatch.png")); self.window.icon_cancel_edit = self.window.icon_save_edit
            self.window.start_processing_button.setIcon(self.window.icon_play); self.window.correction_play_pause_btn.setIcon(self.window.icon_play)

        def connect_signals(self):
            self.window.browse_button.clicked.connect(self.select_files)
            self.window.start_processing_button.clicked.connect(self.start_or_abort_processing)
            self.window.save_token_button.clicked.connect(self.show_hf_token_dialog)
            self.window.identify_speakers_checkbutton.stateChanged.connect(self.toggle_speaker_options)
            self.window.timestamps_checkbutton_2.stateChanged.connect(self.toggle_timestamp_options)
            self.window.correction_button.clicked.connect(self.go_to_correction)
            self.window.show_tips_checkbox.stateChanged.connect(self.on_tips_toggled)
        
        @Slot(int)
        def toggle_timestamp_options(self, state):
            is_checked = (state == Qt.CheckState.Checked.value); self.window.end_times_checkbutton.setEnabled(is_checked)
            if not is_checked: self.window.end_times_checkbutton.setChecked(False)

        @Slot(int)
        def toggle_speaker_options(self, state):
            is_checked = (state == Qt.CheckState.Checked.value)
            if is_checked:
                if not self.config_manager.load_huggingface_token():
                    self.show_hf_token_dialog(is_mandatory=True)
                    if not self.config_manager.load_huggingface_token():
                        self.window.identify_speakers_checkbutton.blockSignals(True)
                        self.window.identify_speakers_checkbutton.setChecked(False)
                        self.window.identify_speakers_checkbutton.blockSignals(False)
                        return
            self.window.auto_merge_checkbutton.setEnabled(is_checked)
            if not is_checked:
                self.window.auto_merge_checkbutton.setChecked(False)
            self.window.save_token_button.setVisible(is_checked)
        
        @Slot()
        def show_hf_token_dialog(self, is_mandatory=False):
            current_token = self.config_manager.load_huggingface_token(); dialog = HuggingFaceTokenDialog(current_token, self.current_language, self.window)
            if dialog.exec() == QDialog.Accepted:
                if dialog.token != current_token:
                    self.window.huggingface_token_entry.setText(dialog.token); self.config_manager.save_huggingface_token(dialog.token); self.config_manager.set_use_auth_token(bool(dialog.token))
                    QMessageBox.information(self.window, "Token Saved", translations.get_text("msg_token_saved", self.current_language))
        
        def set_ui_for_processing(self, is_processing):
            self.window.Audio_file_frame.setEnabled(not is_processing); self.window.Processing_options_frame.setEnabled(not is_processing)
            self.window.start_processing_button.setEnabled(True); self.window.main_tab_widget.setTabEnabled(1, not is_processing); self.window.main_tab_widget.setTabEnabled(2, not is_processing)
            lang = self.current_language
            if is_processing: self.window.start_processing_button.setText(translations.get_text("btn_abort", lang)); self.window.start_processing_button.setIcon(self.window.icon_abort)
            else: self.window.start_processing_button.setText(translations.get_text("btn_start_processing", lang)); self.window.start_processing_button.setIcon(self.window.icon_play)
            self.is_processing = is_processing
        
        def get_processing_options(self):
            return {
                constants.OPTION_MODEL: "large", constants.OPTION_DIARIZE: self.window.identify_speakers_checkbutton.isChecked(), 
                constants.OPTION_AUTO_MERGE: self.window.auto_merge_checkbutton.isChecked(), constants.OPTION_TIMESTAMPS: self.window.timestamps_checkbutton_2.isChecked(), 
                constants.OPTION_END_TIMES: self.window.end_times_checkbutton.isChecked(), "hf_token": self.window.huggingface_token_entry.text().strip()
            }
        
        def load_initial_settings(self):
            self.window.huggingface_token_frame.hide(); self.window.save_token_button.setText(translations.get_text("btn_manage_token", self.current_language))
            if hasattr(sys, '_MEIPASS'): base_dir = sys._MEIPASS
            else: base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
            key_icon_path = os.path.join(base_dir, 'assets', 'icons', 'key.png')
            if os.path.exists(key_icon_path): self.window.save_token_button.setIcon(QIcon(key_icon_path))
            self.window.correction_button.setEnabled(False)
            saved_options = self.config_manager.load_processing_options()
            
            diar_enabled_in_config = saved_options.get(constants.OPTION_DIARIZE, False)
            if diar_enabled_in_config:
                if not self.config_manager.load_huggingface_token():
                    diar_enabled_in_config = False
            
            self.window.identify_speakers_checkbutton.setChecked(diar_enabled_in_config)
            
            self.window.auto_merge_checkbutton.setChecked(saved_options.get(constants.OPTION_AUTO_MERGE, False))
            self.window.timestamps_checkbutton_2.setChecked(saved_options.get(constants.OPTION_TIMESTAMPS, True)); self.window.end_times_checkbutton.setChecked(saved_options.get(constants.OPTION_END_TIMES, False))
            token = self.config_manager.load_huggingface_token()
            if token: self.window.huggingface_token_entry.setText(token)
            
            self.toggle_speaker_options(Qt.CheckState.Checked.value if self.window.identify_speakers_checkbutton.isChecked() else Qt.CheckState.Unchecked.value)
            
            is_ts_checked = self.window.timestamps_checkbutton_2.isChecked(); ts_check_state = Qt.CheckState.Checked.value if is_ts_checked else Qt.CheckState.Unchecked.value; self.toggle_timestamp_options(ts_check_state)
            font_sizes = ["8", "9", "10", "11", "12", "14", "16", "18", "24", "36"]; self.window.font_size_combo.addItems(font_sizes); self.window.font_size_combo.setCurrentText("12")
            if self.window.correction_play_pause_btn: button = self.window.correction_play_pause_btn; font_metrics = QFontMetrics(button.font()); text_width = font_metrics.boundingRect("Pause ").width(); padding = 40; button.setFixedWidth(text_width + padding)
            logger.info("Initial settings loaded."); show_tips = self.config_manager.get_main_window_show_tips(); self.window.show_tips_checkbox.setChecked(show_tips); self._apply_tips_state(show_tips); self.correction_logic.set_tips_enabled(show_tips); logger.info(f"Loaded tips preference on startup: {show_tips}")
            
        @Slot()
        def select_files(self):
            if self.is_processing: return
            file_filter = ("All Media Files (*.wav *.mp3 *.aac *.flac *.m4a *.mp4 *.mov *.avi *.mkv);;Audio Files (*.wav *.mp3 *.aac *.flac *.m4a);;Video Files (*.mp4 *.mov *.avi *.mkv);;All Files (*)")
            paths, _ = QFileDialog.getOpenFileNames(self.window, "Select Audio or Video Files", "", file_filter)
            if paths:
                self.audio_file_paths = paths; self.window.correction_button.setEnabled(False)
                summary = translations.get_text("step1_summary_selected", self.current_language, len(paths), os.path.basename(paths[0]))
                if len(paths) > 1: summary += ", ..."
                if len(paths) == 1: self.window.audio_file_entry.setText(paths[0])
                else: self.window.audio_file_entry.setText(f"{len(paths)} files selected")

        @Slot()
        def start_or_abort_processing(self):
            if self.is_processing and self.process:
                if self.process.is_alive(): self.process.terminate(); self.process.join(timeout=1)
                self.timer.stop(); self.process = None; self.window.status_label.setText(translations.get_text("msg_processing_aborted", self.current_language))
                self.window.progress_bar.setValue(0); self.set_ui_for_processing(False)
                if self.tutorial_manager.paused_state: QTimer.singleShot(200, self.tutorial_manager.resume_tutorial)
                return
            if self.tutorial_manager.is_active: self.tutorial_manager.pause_tutorial()
            if not self.audio_file_paths: QMessageBox.critical(self.window, "Error", translations.get_text("msg_select_file_error", self.current_language)); return
            destination_folder = None
            if len(self.audio_file_paths) > 1:
                destination_folder = QFileDialog.getExistingDirectory(self.window, "Select Destination Folder for Transcriptions")
                if not destination_folder: self.window.status_label.setText(translations.get_text("msg_batch_cancel", self.current_language)); return
            
            ffmpeg_path = _get_bundled_ffmpeg_path()
            if not ffmpeg_path:
                QMessageBox.critical(self.window, "FFmpeg Missing", 
                                     "FFmpeg could not be found.\n\n"
                                     "Since you are running from source code, you must install FFmpeg manually:\n"
                                     "1. Download ffmpeg.exe from gyan.dev\n"
                                     "2. Create a 'bin' folder in the project root\n"
                                     "3. Place ffmpeg.exe inside 'bin/'")
                return
            
            logger.info(f"Main process identified ffmpeg: {ffmpeg_path}")
            
            self.config_manager.save_processing_options(self.get_processing_options()); self.set_ui_for_processing(True); self.window.progress_bar.setValue(0); self.window.output_text_area.clear()
            options = self.get_processing_options(); cache_dir = os.path.join(os.path.expanduser('~'), 'AutoVerse_Cache')
            
            self.queue = multiprocessing.Queue(); self.process = multiprocessing.Process(target=processing_worker_function, args=(self.queue, self.audio_file_paths, options, cache_dir, destination_folder, ffmpeg_path), daemon=True); self.process.start(); self.timer.start(100)

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
                    whisper_percentage = data
                    mapped_percentage = int((whisper_percentage * 0.6) + 30)
                    self.window.progress_bar.setValue(mapped_percentage)
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
                        pass 
                    if self.tutorial_manager.paused_state:
                        QTimer.singleShot(200, self.tutorial_manager.resume_tutorial)
        
        def _format_etr(self, seconds: float) -> str:
            if seconds < 60: return f"{int(seconds)}s"
            else: mins = int(seconds / 60); secs = int(seconds % 60); return f"{mins}m {secs:02d}s"

        def handle_batch_results(self, final_payload):
            if not isinstance(final_payload, dict) or constants.KEY_BATCH_ALL_RESULTS not in final_payload:
                logger.error(f"Invalid payload in handle_batch_results: {final_payload}")
                self.window.status_label.setText("Error: Received invalid data from worker.")
                self.set_ui_for_processing(False)
                return

            results = final_payload[constants.KEY_BATCH_ALL_RESULTS]; summary = []; successful_count = 0; error_count = 0
            if len(results) == 1:
                result = results[0]; self.window.progress_bar.setValue(100)
                if result.status == constants.STATUS_SUCCESS: output_text = "\n".join(result.data) if isinstance(result.data, list) else str(result.data); self.window.output_text_area.setPlainText(output_text); self.prompt_and_save_single_result(result)
                else: msg = result.message or "An unknown error occurred."; self.window.status_label.setText(f"Error: {msg[:100]}..."); self.window.output_text_area.setPlainText(f"An error occurred:\n{msg}"); QMessageBox.critical(self.window, "Processing Error", msg)
            else: 
                for result in results:
                    file_name = os.path.basename(result.source_file)
                    if result.status == constants.STATUS_SUCCESS: successful_count += 1; summary.append(f"SUCCESS: '{file_name}' saved to '{os.path.basename(result.output_path)}'")
                    else: error_count += 1; summary.append(f"ERROR: '{file_name}' - {result.message}")
                self.window.output_text_area.setPlainText("\n".join(summary)); final_status_msg = f"Batch finished. {successful_count} successful, {error_count} failed."; self.window.status_label.setText(final_status_msg); QMessageBox.information(self.window, "Batch Processing Complete", final_status_msg)
            self.set_ui_for_processing(False)
            if self.tutorial_manager.paused_state: QTimer.singleShot(200, self.tutorial_manager.resume_tutorial)
        
        def prompt_and_save_single_result(self, result):
            if hasattr(result, 'output_path') and result.output_path: self.last_single_file_result_path = result.output_path; self.window.correction_button.setEnabled(True); self.window.status_label.setText(translations.get_text("msg_save_success", self.current_language, os.path.basename(result.output_path))); return
            base_name, _ = os.path.splitext(os.path.basename(result.source_file)); model_name = "large"; default_fn = os.path.join(os.getcwd(), f"{base_name}_{model_name}_transcription.txt"); save_path, _ = QFileDialog.getSaveFileName(self.window, "Save Transcription As", default_fn, "Text Files (*.txt)")
            if save_path:
                try: AudioProcessor.save_to_txt(save_path, result.data, result.is_plain_text_output); self.window.status_label.setText(translations.get_text("msg_save_success", self.current_language, os.path.basename(save_path))); QMessageBox.information(self.window, "Success", translations.get_text("msg_save_success", self.current_language, save_path)); self.last_single_file_result_path = save_path; self.window.correction_button.setEnabled(True)
                except Exception as e: QMessageBox.critical(self.window, "Save Error", translations.get_text("msg_save_error", self.current_language, e)); self.window.correction_button.setEnabled(False)
            else: self.window.status_label.setText("Save cancelled by user."); self.window.correction_button.setEnabled(False)

        @Slot()
        def go_to_correction(self):
            if not self.last_single_file_result_path or not self.audio_file_paths: QMessageBox.warning(self.window, "Error", "Cannot find the necessary file paths."); return
            audio_path = self.audio_file_paths[0]; txt_path = self.last_single_file_result_path; self.correction_logic.load_files_from_paths(audio_path=audio_path, txt_path=txt_path); self.window.main_tab_widget.setCurrentIndex(1)

    app = QApplication(sys.argv)
    apply_modern_theme(app)
    main_app = MainApplication(app)
    sys.exit(app.exec())

if __name__ == "__main__":
    configure_ssl_for_bundle()
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn', force=True)
    run_app()
# ui/settings_logic.py
import logging
import os
import shutil
import sys
from PySide6.QtWidgets import (QWidget, QComboBox, QPushButton, QMessageBox, 
                               QApplication, QStyleFactory)
from PySide6.QtCore import QObject, Slot, Qt
from PySide6.QtGui import QPalette, QColor

from utils import constants

logger = logging.getLogger(__name__)

class SettingsLogic(QObject):
    def __init__(self, main_window, main_app):
        super().__init__()
        self.main_window = main_window
        self.main_app = main_app
        self.config_manager = main_app.config_manager
        
        # UI Elements
        self.theme_combo = self.main_window.findChild(QComboBox, "settings_theme_combo")
        self.language_combo = self.main_window.findChild(QComboBox, "settings_language_combo")
        self.check_updates_btn = self.main_window.findChild(QPushButton, "settings_check_updates_btn")
        self.reset_tutorials_btn = self.main_window.findChild(QPushButton, "settings_reset_tutorials_btn")
        self.clear_cache_btn = self.main_window.findChild(QPushButton, "settings_clear_cache_btn")
        self.reset_app_btn = self.main_window.findChild(QPushButton, "settings_reset_app_btn")
        
        self._init_ui_state()
        self._connect_signals()

    def _init_ui_state(self):
        # Load saved settings
        current_theme = self.config_manager.get_theme()
        index = self.theme_combo.findText(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
            
        current_lang = self.config_manager.get_language()
        index = self.language_combo.findText(current_lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        # Apply the theme immediately
        self.apply_theme(current_theme)

    def _connect_signals(self):
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        self.language_combo.currentTextChanged.connect(self.on_language_changed)
        self.check_updates_btn.clicked.connect(self.on_check_updates_clicked)
        self.reset_tutorials_btn.clicked.connect(self.on_reset_tutorials_clicked)
        self.clear_cache_btn.clicked.connect(self.on_clear_cache_clicked)
        self.reset_app_btn.clicked.connect(self.on_reset_app_clicked)

    @Slot(str)
    def on_theme_changed(self, theme_name):
        self.config_manager.set_theme(theme_name)
        self.apply_theme(theme_name)
        QMessageBox.information(self.main_window, "Theme Changed", 
                              f"Theme set to {theme_name}.")

    def apply_theme(self, theme_name):
        app = QApplication.instance()
        
        if theme_name == "Dark":
            app.setStyle("Fusion")
            dark_palette = QPalette()
            dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.WindowText, Qt.white)
            dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
            dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
            dark_palette.setColor(QPalette.ToolTipText, Qt.white)
            dark_palette.setColor(QPalette.Text, Qt.white)
            dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ButtonText, Qt.white)
            dark_palette.setColor(QPalette.BrightText, Qt.red)
            dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(dark_palette)
            app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")
        
        elif theme_name == "Light":
            app.setStyle("Fusion")
            app.setPalette(QApplication.style().standardPalette())
            app.setStyleSheet("")
            
        else: # System
            # Reset to default style (usually windowsvista on Windows, macos on Mac)
            if sys.platform == 'win32':
                if 'windowsvista' in QStyleFactory.keys():
                    app.setStyle('windowsvista')
            elif sys.platform == 'darwin':
                 if 'macos' in QStyleFactory.keys():
                    app.setStyle('macos')
            
            # Reset palette to default
            app.setPalette(QApplication.style().standardPalette())
            app.setStyleSheet("")

    @Slot(str)
    def on_language_changed(self, lang_name):
        self.config_manager.set_language(lang_name)
        QMessageBox.information(self.main_window, "Language Changed", 
                                "Please restart the application for language changes to take full effect.\n\n"
                                "(Note: Only English is fully supported in this version. "
                                "This is a placeholder for future translations.)")

    @Slot()
    def on_check_updates_clicked(self):
        # Trigger the check in the main app
        if hasattr(self.main_app, 'check_for_updates_manual'):
            self.main_app.check_for_updates_manual()
        else:
            QMessageBox.information(self.main_window, "Updates", 
                                    "Update checking is handled automatically at startup in frozen builds.")

    @Slot()
    def on_reset_tutorials_clicked(self):
        self.config_manager.reset_all_tutorials()
        QMessageBox.information(self.main_window, "Tutorials Reset", 
                                "All tutorials have been reset. They will appear again when you next use the relevant features.")

    @Slot()
    def on_clear_cache_clicked(self):
        reply = QMessageBox.question(self.main_window, "Clear Cache", 
                                   "This will delete downloaded models and temporary audio files. "
                                   "Models will need to be re-downloaded next time you use them.\n\n"
                                   "Are you sure?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            cache_dir = os.path.join(os.path.expanduser('~'), 'AutoVerse_Cache')
            if os.path.exists(cache_dir):
                try:
                    shutil.rmtree(cache_dir)
                    QMessageBox.information(self.main_window, "Success", "Cache cleared successfully.")
                except Exception as e:
                    QMessageBox.critical(self.main_window, "Error", f"Could not clear cache: {e}")
            else:
                QMessageBox.information(self.main_window, "Info", "Cache directory was already empty or not found.")

    @Slot()
    def on_reset_app_clicked(self):
        reply = QMessageBox.critical(self.main_window, "Reset Application", 
                                   "This will delete all your preferences, the Hugging Face token, "
                                   "and logs. The application will close.\n\n"
                                   "This action cannot be undone. Are you sure?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # Delete config file
                if os.path.exists(constants.DEFAULT_CONFIG_FILE):
                    os.remove(constants.DEFAULT_CONFIG_FILE)
                
                # We don't delete the entire APP_USER_DATA_DIR because it might contain
                # logs or other things useful for debugging, but let's clear the specific files.
                # Just config is usually enough to "reset" the user experience.
                
                QMessageBox.information(self.main_window, "Reset Complete", 
                                      "Application has been reset. It will now close.")
                QApplication.quit()
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to reset: {e}")
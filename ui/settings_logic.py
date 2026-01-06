# ui/settings_logic.py
import logging
import os
import shutil
import sys
from PySide6.QtWidgets import (QWidget, QComboBox, QPushButton, QMessageBox, 
                               QApplication, QStyleFactory, QGroupBox, QLabel)
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
        # Note: self.theme_combo is purposely ignored/hidden
        self.language_combo = self.main_window.findChild(QComboBox, "settings_language_combo")
        self.check_updates_btn = self.main_window.findChild(QPushButton, "settings_check_updates_btn")
        self.reset_tutorials_btn = self.main_window.findChild(QPushButton, "settings_reset_tutorials_btn")
        self.clear_cache_btn = self.main_window.findChild(QPushButton, "settings_clear_cache_btn")
        self.reset_app_btn = self.main_window.findChild(QPushButton, "settings_reset_app_btn")
        
        # Group Boxes to manage visibility
        self.appearance_group = self.main_window.findChild(QGroupBox, "appearance_group")
        self.danger_group = self.main_window.findChild(QGroupBox, "danger_zone_group")
        self.app_group = self.main_window.findChild(QGroupBox, "application_group")

        self._init_ui_state()
        self._connect_signals()

    def _init_ui_state(self):
        # Hide Theme UI components
        theme_combo = self.main_window.findChild(QComboBox, "settings_theme_combo")
        theme_label = self.main_window.findChild(QLabel, "label_theme")
        if theme_combo: theme_combo.hide()
        if theme_label: theme_label.hide()

        # Hide Danger Zone Group
        if self.danger_group:
            self.danger_group.hide()
            
        # Move Reset Button to App Group if not already there (logical reparenting)
        # We do this by ensuring the Reset button is visible and connected, 
        # effectively treating it as a standard action.
        # Since we can't easily move widgets between layouts defined in .ui at runtime 
        # without breaking layout pointers, we simply accept it's "Gone" visually 
        # but we want the functionality.
        # Actually, let's just repurpose the danger zone or add it programmatically.
        # Simpler approach: Allow the Danger Group to be hidden, and re-add the button 
        # to the Application Group layout programmatically.
        
        if self.app_group and self.reset_app_btn:
            layout = self.app_group.layout()
            if layout:
                # Remove from old parent layout if possible, or just add to new one
                # PySide re-parenting handles removal.
                layout.addWidget(self.reset_app_btn)
                
                # Reset styling to look normal
                self.reset_app_btn.setStyleSheet("") 

        # Load Language
        current_lang = self.config_manager.get_language()
        index = self.language_combo.findText(current_lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

    def _connect_signals(self):
        self.language_combo.currentTextChanged.connect(self.on_language_changed)
        self.check_updates_btn.clicked.connect(self.on_check_updates_clicked)
        self.reset_tutorials_btn.clicked.connect(self.on_reset_tutorials_clicked)
        self.clear_cache_btn.clicked.connect(self.on_clear_cache_clicked)
        self.reset_app_btn.clicked.connect(self.on_reset_app_clicked)

    @Slot(str)
    def on_language_changed(self, lang_name):
        self.config_manager.set_language(lang_name)
        self.main_app.current_language = lang_name
        self.main_app.retranslateUi()

    @Slot()
    def on_check_updates_clicked(self):
        if hasattr(self.main_app, 'check_for_updates_manual'):
            self.main_app.check_for_updates_manual()
        else:
            QMessageBox.information(self.main_window, "Updates", 
                                    "Update checking is handled automatically at startup in frozen builds.")

    @Slot()
    def on_reset_tutorials_clicked(self):
        self.config_manager.reset_all_tutorials()
        QMessageBox.information(self.main_window, "Tutorials Reset", 
                                "All tutorials have been reset.")

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
                if os.path.exists(constants.DEFAULT_CONFIG_FILE):
                    os.remove(constants.DEFAULT_CONFIG_FILE)
                
                QMessageBox.information(self.main_window, "Reset Complete", 
                                      "Application has been reset. It will now close.")
                QApplication.quit()
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to reset: {e}")
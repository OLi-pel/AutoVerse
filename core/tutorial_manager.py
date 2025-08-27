# core/tutorial_manager.py

import json
import logging
import os
import sys
from PySide6.QtWidgets import QWidget, QCheckBox, QComboBox
from PySide6.QtCore import QTimer, Qt

logger = logging.getLogger(__name__)

class TutorialManager:
    def __init__(self, main_app, overlay):
        self.main_app = main_app
        self.overlay = overlay
        self.tutorials = {}
        self.current_tutorial_name = None
        self.current_tutorial = None
        self.current_step_index = -1
        self.active_connection = None
        self.current_target_widget = None
        self.is_active = False
        self.paused_state = None

        self._load_tutorials()
        
        self.overlay.next_clicked.connect(self.next_step)
        self.overlay.prev_clicked.connect(self.prev_step)
        self.overlay.exit_clicked.connect(self.exit_tutorial)
        self.overlay.target_clicked.connect(self._on_target_clicked)

    def _load_tutorials(self):
        try:
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            project_root = os.path.dirname(base_path)
            config_path = os.path.join(project_root, 'tutorials.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                self.tutorials = json.load(f)
            logger.info("Tutorials loaded successfully.")
        except Exception as e:
            logger.error(f"Error loading tutorials: {e}")
            self.tutorials = {}

    def start_tutorial(self, tutorial_name):
        if self.is_active: return
        if tutorial_name not in self.tutorials: return
        
        # --- THIS IS THE NEW LINE TO ENSURE CORRECT STARTING TAB ---
        self.main_app.window.main_tab_widget.setCurrentIndex(0)
        
        # Reset UI to initial state before starting tutorial
        self._reset_ui_for_tutorial()
        
        self.is_active = True
        self.current_tutorial_name = tutorial_name
        self.current_tutorial = self.tutorials[tutorial_name]
        self.current_step_index = 0
        self.show_step(self.current_step_index)
        self.overlay.show()

    def _reset_ui_for_tutorial(self):
        """Reset UI to initial state for tutorial"""
        # Clear any loaded files
        self.main_app.audio_file_paths = []
        self.main_app.last_single_file_result_path = None
        
        # Reset UI elements to initial state
        self.main_app.window.output_text_area.clear()
        self.main_app.window.status_label.setText("Ready")
        self.main_app.window.progress_bar.setValue(0)
        self.main_app.window.correction_button.setEnabled(False)
        
        # Clear step1 summary text
        self.main_app.step1_box.set_summary_text("")
        
        # Reset to first workflow step
        self.main_app._set_workflow_step(1)

    def show_step(self, index):
        if not self.current_tutorial or not (0 <= index < len(self.current_tutorial)):
            self.exit_tutorial()
            return

        step_data = self.current_tutorial[index]
        logger.info(f"Showing tutorial step {index + 1}: {step_data.get('title', 'No title')}")
        
        if "pre_action" in step_data: self._execute_action(step_data["pre_action"])
        
        target_widget_name = step_data.get("target_widget")
        self.current_target_widget = self.main_app.window.findChild(QWidget, target_widget_name)
        
        if not self.current_target_widget:
            logger.warning(f"Target widget '{target_widget_name}' not found for step {index + 1}")
        else:
            logger.info(f"Target widget '{target_widget_name}' found. Visible: {self.current_target_widget.isVisible()}, Enabled: {self.current_target_widget.isEnabled()}")

        validation = step_data.get("validation", {})
        validation_type = validation.get("type")
        is_action_step = validation_type in ["action_click", "file_selected"]
        is_passive = step_data.get("type") == "passive"
        allow_interaction = validation_type == "interactive_widget" and validation.get("allow_interaction", False)

        self.overlay.show_step(
            target_widget=self.current_target_widget,
            title=step_data.get("title", ""), text=step_data.get("text", ""),
            current_step=index + 1, total_steps=len(self.current_tutorial),
            is_action_step=is_action_step, allow_interaction=allow_interaction
        )
        
        # Ensure overlay is visible and force a repaint
        if not self.overlay.isVisible():
            self.overlay.show()
        self.overlay.update()
        self.overlay.raise_()
        
        if is_passive: self.overlay.next_button.setEnabled(True)
        self._setup_validation(validation)

    def _execute_action(self, action_data):
        target_name = action_data.get("target")
        method_name = action_data.get("method")
        if not target_name or not method_name: return
        target_obj = getattr(self.main_app, target_name, None)
        if not target_obj: return
        method_to_call = getattr(target_obj, method_name, None)
        if callable(method_to_call): QTimer.singleShot(100, method_to_call)

    def _setup_validation(self, validation):
        self._clear_validation()
        if not self.current_target_widget: return
        
        validation_type = validation.get("type")
        
        if validation_type == "checked":
            signal = self.current_target_widget.stateChanged
            connection = signal.connect(
                lambda state: self.overlay.next_button.setEnabled(state == Qt.Checked.value)
            )
            self.active_connection = (signal, connection)
            if self.current_target_widget.isChecked():
                self.overlay.next_button.setEnabled(True)

        elif validation_type == "value_changed":
            if isinstance(self.current_target_widget, QComboBox):
                expected_value = validation.get("value")
                signal = self.current_target_widget.currentTextChanged
                connection = signal.connect(
                    lambda text: self.overlay.next_button.setEnabled(expected_value in text)
                )
                self.active_connection = (signal, connection)
                if expected_value in self.current_target_widget.currentText():
                    self.overlay.next_button.setEnabled(True)
                    
        elif validation_type == "manual_next":
            # Just enable the next button - no validation required
            self.overlay.next_button.setEnabled(True)
        elif validation_type == "interactive_widget":
            # Enable the next button for interactive widgets
            self.overlay.next_button.setEnabled(True)

    def _on_target_clicked(self):
        if not self.current_target_widget: return
        
        validation = self.current_tutorial[self.current_step_index].get("validation", {})
        validation_type = validation.get("type")
        action_name = validation.get("action")

        if validation_type == "file_selected" and action_name == "select_files":
            self.overlay.hide()
            self.main_app.select_files() 
            if self.main_app.audio_file_paths:
                # Automatically advance to next step when files are selected
                # Use longer delay to ensure the workflow step change and UI updates complete first
                QTimer.singleShot(300, self.next_step)
            else:
                self.overlay.show()
        elif validation_type == "action_click":
            action_method = getattr(self.main_app, action_name, None)
            if callable(action_method):
                action_method()
                if action_name not in ["start_or_abort_processing", "_proceed_to_processing_step"]:
                    self.next_step()
            else:
                logger.error(f"Action '{action_name}' not found on main app.")
        elif validation_type == "interactive_widget":
            # For interactive widgets, don't intercept the click - let it pass through
            # The overlay should allow interaction with the target widget
            logger.info(f"Interactive widget clicked: {self.current_target_widget.__class__.__name__}")
            # Don't advance automatically - user needs to click Next when ready
            return
        else:
            # Only try to click if the widget has a click method (buttons, etc.)
            if hasattr(self.current_target_widget, 'click'):
                self.current_target_widget.click()
            else:
                # For non-clickable widgets, just advance to next step
                logger.info(f"Widget {self.current_target_widget.__class__.__name__} is not clickable, advancing to next step")
                self.next_step()

    def next_step(self):
        self._clear_validation()
        if self.current_tutorial and self.current_step_index < len(self.current_tutorial) - 1:
            self.current_step_index += 1
            self.show_step(self.current_step_index)
        else:
            self.exit_tutorial()
    
    def should_auto_start_tutorial(self, tutorial_name):
        """Check if a tutorial should be automatically started for first-time users"""
        if not hasattr(self.main_app, 'config_manager'):
            return False
            
        if tutorial_name == "transcription":
            return not self.main_app.config_manager.get_transcription_tutorial_completed()
        elif tutorial_name == "correction":
            return not self.main_app.config_manager.get_correction_tutorial_completed()
        
        return False

    def prev_step(self):
        self._clear_validation()
        if self.current_tutorial and self.current_step_index > 0:
            self.current_step_index -= 1
            self.show_step(self.current_step_index)

    def pause_tutorial(self):
        if not self.is_active: return
        next_step_index = self.current_step_index
        step_data = self.current_tutorial[self.current_step_index]
        
        if step_data.get("validation", {}).get("type") == "action_click":
            action_name = step_data.get("validation", {}).get("action")
            if action_name == "_proceed_to_processing_step":
                # Skip the "Start Processing" step and go directly to "View Your Transcript"
                next_step_index += 2
            else:
                next_step_index += 1

        self.paused_state = { "name": self.current_tutorial_name, "step": next_step_index }
        
        # Hide tutorial without clearing paused state
        self._clear_validation()
        self.current_tutorial = None
        self.current_step_index = -1
        self.is_active = False
        self.overlay.hide()
        
        logger.info(f"Tutorial paused. Will resume at step {next_step_index}.")

    def resume_tutorial(self):
        if not self.paused_state: return
        
        name, step = self.paused_state["name"], self.paused_state["step"]
        
        self.is_active = True
        self.current_tutorial_name, self.current_tutorial = name, self.tutorials[name]
        self.current_step_index = step
        
        self.show_step(self.current_step_index)
        self.overlay.show()
        
        self.paused_state = None
        logger.info(f"Tutorial resumed at step {step}.")

    def exit_tutorial(self):
        # Mark tutorial as completed if we reached the end
        if self.current_tutorial_name and self.current_tutorial and self.current_step_index >= len(self.current_tutorial) - 1:
            self._mark_tutorial_completed(self.current_tutorial_name)
        
        self._clear_validation()
        self.current_tutorial = None
        self.current_step_index = -1
        self.is_active = False
        self.paused_state = None
        self.overlay.hide()
    
    def _mark_tutorial_completed(self, tutorial_name):
        """Mark a tutorial as completed in the config"""
        if hasattr(self.main_app, 'config_manager'):
            if tutorial_name == "transcription":
                self.main_app.config_manager.set_transcription_tutorial_completed(True)
                logger.info("Transcription tutorial marked as completed")
            elif tutorial_name == "correction":
                self.main_app.config_manager.set_correction_tutorial_completed(True)
                logger.info("Correction tutorial marked as completed")

    def _clear_validation(self):
        if self.active_connection:
            try:
                signal, connection_object = self.active_connection
                signal.disconnect(connection_object)
            except (TypeError, RuntimeError) as e:
                logger.debug(f"Could not disconnect signal: {e}")
            self.active_connection = None
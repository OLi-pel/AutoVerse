# core/tutorial_manager.py

import json
import logging
import os
import sys
from PySide6.QtWidgets import QWidget, QCheckBox, QComboBox
from PySide6.QtCore import QTimer, Qt, QObject

logger = logging.getLogger(__name__)

class TutorialManager(QObject):
    def __init__(self, main_app, overlay):
        super().__init__()
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
        self._selection_timer = None

        # Simple timer for occasional overlay maintenance (much less aggressive)
        self._raise_timer = QTimer(self)
        self._raise_timer.timeout.connect(self._ensure_overlay_on_top)

        self._load_tutorials()
        
        self.overlay.next_clicked.connect(self.next_step)
        self.overlay.prev_clicked.connect(self.prev_step)
        self.overlay.exit_clicked.connect(self.exit_tutorial)
        self.overlay.target_clicked.connect(self._on_target_clicked)

    def _ensure_overlay_on_top(self):
        """Gentle maintenance to keep overlay visible."""
        if self.overlay and self.overlay.isVisible():
            # Simple raise - no aggressive repainting
            self.overlay.raise_()
            # Also ensure the panel stays visible
            if hasattr(self.overlay, 'panel') and self.overlay.panel:
                self.overlay.panel.raise_()

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
        
        self.main_app.window.main_tab_widget.setCurrentIndex(0)
        self._start_tutorial_flow(tutorial_name)
    
    def _start_tutorial_flow(self, tutorial_name):
        self._reset_ui_for_tutorial()
        
        self.is_active = True
        self.current_tutorial_name = tutorial_name
        self.current_tutorial = self.tutorials[tutorial_name]
        self.current_step_index = 0
        self.show_step(self.current_step_index)
        self.overlay.show()
        
        # Start a gentle timer for occasional maintenance
        self._raise_timer.start(500) # Check every 500ms - much less aggressive

    def _reset_ui_for_tutorial(self):
        if hasattr(self.main_app, 'correction_logic'):
            self.main_app.correction_logic.undo_manager.clear()
            self.main_app.correction_logic._clear_all_selections()
        
        self.main_app.audio_file_paths = []
        self.main_app.last_single_file_result_path = None
        self.main_app.window.output_text_area.clear()
        self.main_app.window.status_label.setText("Ready")
        self.main_app.window.progress_bar.setValue(0)
        self.main_app.window.correction_button.setEnabled(False)
        self.main_app.step1_box.set_summary_text("")
        self.main_app._set_workflow_step(1)

    def _find_widget(self, name):
        if not name: return None
        widget = self.main_app.window.findChild(QWidget, name)
        if not widget:
            if name == 'correction_timeline_frame' and hasattr(self.main_app.correction_logic, 'timeline'):
                return self.main_app.correction_logic.timeline
            logger.warning(f"Could not find widget with name: '{name}'")
        return widget
        
    def show_step(self, index):
        if not self.current_tutorial or not (0 <= index < len(self.current_tutorial)):
            self.exit_tutorial()
            return

        step_data = self.current_tutorial[index]
        logger.info(f"Showing tutorial step {index + 1}: {step_data.get('title', 'No title')}")
        
        if "pre_action" in step_data: self._execute_action(step_data["pre_action"])
        
        self.current_target_widget = self._find_widget(step_data.get("target_widget"))
        secondary_widgets = [self._find_widget(name) for name in step_data.get("secondary_widgets", [])]
        secondary_widgets = [w for w in secondary_widgets if w is not None]
        
        highlight_widgets = [self._find_widget(name) for name in step_data.get("highlight_widgets", [])]
        highlight_widgets = [w for w in highlight_widgets if w is not None]

        validation = step_data.get("validation", {})
        validation_type = validation.get("type")
        is_action_step = validation_type in ["action_click", "file_selected"]
        is_passive = step_data.get("type") == "passive"
        allow_interaction = validation.get("allow_interaction", False) or validation_type == "wait_for_selection"
        disable_prev_button = step_data.get("disable_prev", False)

        self.overlay.show_step(
            target_widget=self.current_target_widget,
            title=step_data.get("title", ""), text=step_data.get("text", ""),
            current_step=index + 1, total_steps=len(self.current_tutorial),
            secondary_widgets=secondary_widgets,
            panel_position_hint=step_data.get("panel_position_hint"),
            is_action_step=is_action_step, allow_interaction=allow_interaction,
            disable_prev_button=disable_prev_button,
            highlight_secondary_widgets=highlight_widgets
        )
        
        if not self.overlay.isVisible(): self.overlay.show()
        self.overlay.update()
        
        # Ensure the timer is running when showing steps
        if not self._raise_timer.isActive():
            self._raise_timer.start(500)
        
        # Simple raise for all tabs
        self.overlay.raise_()
        
        if is_passive: self.overlay.next_button.setEnabled(True)
        self._setup_validation(validation)

    def _execute_action(self, action_data):
        target_name = action_data.get("target")
        method_name = action_data.get("method")
        if not target_name or not method_name: return
        
        target_obj = getattr(self.main_app, target_name, None)
        if target_name == "correction_logic":
            target_obj = getattr(self.main_app, 'correction_logic', None)
            
        if not target_obj: return
        method_to_call = getattr(target_obj, method_name, None)
        if callable(method_to_call): QTimer.singleShot(100, method_to_call)

    def _setup_validation(self, validation):
        self._clear_validation()
        if not self.current_target_widget and validation.get("type") not in ["wait_for_selection", "manual_next"]:
             return
        
        validation_type = validation.get("type")
        
        if validation_type == "checked":
            signal = self.current_target_widget.stateChanged
            connection = signal.connect(lambda state: self.overlay.next_button.setEnabled(state == Qt.Checked.value))
            self.active_connection = (signal, connection)
            if self.current_target_widget.isChecked():
                self.overlay.next_button.setEnabled(True)
        
        elif validation_type == "wait_for_selection":
            def check_selection():
                logic = self.main_app.correction_logic
                has_selection = logic.selected_segment_id or logic.multi_selection_ids
                if has_selection:
                    if self._selection_timer: self._selection_timer.stop()
                    self.next_step()
            
            self._selection_timer = QTimer(self)
            self._selection_timer.timeout.connect(check_selection)
            self._selection_timer.start(200)

        elif validation_type in ["manual_next", "interactive_widget"]:
            self.overlay.next_button.setEnabled(True)

    def _on_target_clicked(self):
        if not self.current_target_widget: return
        
        validation = self.current_tutorial[self.current_step_index].get("validation", {})
        action_name = validation.get("action")
        auto_advances = validation.get("auto_advances", False)

        if validation.get("type") == "file_selected":
            self.overlay.hide()
            self.main_app.select_files() 
            if self.main_app.audio_file_paths:
                QTimer.singleShot(300, self.next_step)
            else:
                self.overlay.show()
        elif validation.get("type") == "action_click":
            action_method = getattr(self.main_app, action_name, None)
            if not action_method and hasattr(self.main_app, 'correction_logic'):
                action_method = getattr(self.main_app.correction_logic, action_name, None)

            if callable(action_method):
                action_method()
                if auto_advances:
                    QTimer.singleShot(100, self.next_step)
            else:
                logger.error(f"Action '{action_name}' not found.")
        else:
            if hasattr(self.current_target_widget, 'click'):
                self.current_target_widget.click()
            if auto_advances:
                self.next_step()

    def next_step(self):
        self._clear_validation()
        if self.current_tutorial and self.current_step_index < len(self.current_tutorial) - 1:
            self.current_step_index += 1
            self.show_step(self.current_step_index)
        else:
            self.exit_tutorial()

    def prev_step(self):
        self._clear_validation()
        if self.current_tutorial and self.current_step_index > 0:
            self.current_step_index -= 1
            self.show_step(self.current_step_index)
            
    def pause_tutorial(self):
        if not self.is_active: return
        next_step_index = self.current_step_index + 1
        
        self.paused_state = { "name": self.current_tutorial_name, "step": next_step_index }
        self.exit_tutorial(is_pause=True) # Use exit logic to clean up
        logger.info(f"Tutorial paused. Will resume at step index {next_step_index}.")

    def resume_tutorial(self):
        if not self.paused_state: return
        name, step = self.paused_state["name"], self.paused_state["step"]
        self.is_active = True
        self.current_tutorial_name, self.current_tutorial = name, self.tutorials[name]
        self.current_step_index = step
        self.show_step(self.current_step_index)
        self.overlay.show()
        self._raise_timer.start(500) # Restart timer on resume
        self.paused_state = None
        logger.info(f"Tutorial resumed at step index {step}.")

    def exit_tutorial(self, is_pause=False):
        if not is_pause and self.current_tutorial_name and self.current_tutorial and self.current_step_index >= len(self.current_tutorial) - 1:
            self._mark_tutorial_completed(self.current_tutorial_name)
        
        self._raise_timer.stop() # --- FIX: Stop the timer on exit ---
        self._clear_validation()
        self.current_tutorial, self.current_step_index, self.is_active = None, -1, False
        if not is_pause:
            self.paused_state = None
        self.overlay.hide()

    def _mark_tutorial_completed(self, tutorial_name):
        if hasattr(self.main_app, 'config_manager'):
            if tutorial_name == "main_tutorial":
                self.main_app.config_manager.set_transcription_tutorial_completed(True)
                self.main_app.config_manager.set_correction_tutorial_completed(True)
                logger.info(f"Main tutorial marked as completed.")

    def _clear_validation(self):
        if self._selection_timer:
            self._selection_timer.stop()
            self._selection_timer = None
        if self.active_connection:
            try:
                signal, connection = self.active_connection
                signal.disconnect(connection)
            except (TypeError, RuntimeError): pass
            self.active_connection = None
# ui/correction_window.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import logging
import os
import queue
import math # For clamping values and copysign

try:
    from utils import constants
    from core.correction_window_logic import SegmentManager
    from .correction_window_ui import CorrectionWindowUI, ToolTip 
    from .correction_window_callbacks import CorrectionCallbackHandler
    from .audio_player import AudioPlayer
    from utils.tips_data import get_tip 
except ImportError:
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from utils import constants
    from core.correction_window_logic import SegmentManager
    from ui.correction_window_ui import CorrectionWindowUI, ToolTip
    from ui.correction_window_callbacks import CorrectionCallbackHandler
    from ui.audio_player import AudioPlayer
    from utils.tips_data import get_tip


logger = logging.getLogger(__name__)

class CorrectionWindow:
    def __init__(self, parent_root,
                 config_manager_instance, 
                 initial_show_tips_state,   
                 initial_include_timestamps=True,
                 initial_include_end_times=False):
        self.parent_root = parent_root
        self.config_manager = config_manager_instance 
        self.window = tk.Toplevel(parent_root)
        self.window.title("Transcription Correction Tool")
        self.window.geometry("900x700")

        self.segment_manager = SegmentManager(parent_window_for_dialogs=self.window)
        self.audio_player = None
        self.audio_player_update_queue = None

        self.callback_handler = CorrectionCallbackHandler(self)

        self.show_tips_var_corr = tk.BooleanVar(value=initial_show_tips_state)
        self.tips_widgets_corr = {} 

        self.ui = CorrectionWindowUI(
            parent_tk_window=self.window,
            browse_transcription_callback=self.callback_handler.browse_transcription_file,
            browse_audio_callback=self.callback_handler.browse_audio_file,
            load_files_callback=self.callback_handler.load_files,
            assign_speakers_callback=self.callback_handler.open_assign_speakers_dialog,
            save_changes_callback=self.callback_handler.save_changes,
            toggle_play_pause_callback=self._toggle_play_pause,
            seek_audio_callback=self._handle_seek_button_click,
            jump_to_segment_start_callback=self._jump_to_segment_start_action,
            text_area_double_click_callback=self.callback_handler.handle_text_area_double_click,
            text_area_right_click_callback=self.callback_handler.handle_text_area_right_click,
            text_area_left_click_edit_mode_callback=self.callback_handler.handle_text_area_left_click_edit_mode,
            on_speaker_click_callback=self.callback_handler.on_speaker_click,
            on_merge_click_callback=self.callback_handler.on_merge_click,
            show_tips_var_ref=self.show_tips_var_corr,
            toggle_tips_callback_ref=self._on_toggle_tips_corr,
            on_save_start_time_callback=self._handle_save_start_time_click,
            on_toggle_end_time_callback=self._handle_toggle_end_time_click,
            on_save_times_callback=self._handle_save_times_click,
            on_cancel_timestamp_edit_callback=self._handle_cancel_timestamp_edit_click
        )

        self.output_include_timestamps = initial_include_timestamps
        self.output_include_end_times = initial_include_end_times

        self.currently_highlighted_text_seg_id = None
        self.text_edit_mode_active = False
        self.editing_segment_id = None
        self.text_content_start_index_in_edit = None

        self.is_timestamp_editing_active = False
        self.segment_id_for_timestamp_edit = None
        self.start_timestamp_bar_value_seconds = 0.0
        self.end_timestamp_bar_value_seconds = 0.0 
        self.is_end_time_bar_active = False
        self.dragging_bar = None 
        
        self.dragging_main_playback_bar = False
        self.was_playing_before_drag = False

        self.main_playback_bar_id = None
        self.start_selection_bar_id = None
        self.end_selection_bar_id = None
        
        self.right_clicked_segment_id = None
        self._setup_context_menu()

        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        self.window.bind('<Control-s>', lambda e: self.callback_handler.save_changes())
        self.window.bind('<Escape>', self._handle_escape_key)
        self.window.after(100, self._poll_audio_player_queue)
        
        if hasattr(self.ui, 'audio_timeline_canvas'):
            self.ui.audio_timeline_canvas.bind("<Configure>", self._on_canvas_resize)
            self.ui.audio_timeline_canvas.bind("<ButtonPress-1>", self._on_timeline_canvas_press)
            self.ui.audio_timeline_canvas.bind("<B1-Motion>", self._on_timeline_canvas_drag)
            self.ui.audio_timeline_canvas.bind("<ButtonRelease-1>", self._on_timeline_canvas_release)
        
        self._on_toggle_tips_corr() 
        logger.info("CorrectionWindow fully initialized.")

    def _add_tooltip_for_widget_corr(self, widget, tip_key: str, wraplength=250):
        if not widget: return
        tip_text = get_tip("correction_window", tip_key)
        if widget in self.tips_widgets_corr:
            self.tips_widgets_corr[widget].unbind()
            del self.tips_widgets_corr[widget]
        if self.show_tips_var_corr.get() and tip_text:
            if not widget.winfo_ismapped(): return
            try:
                bbox = widget.bbox("insert")
                if bbox is None:
                    if not isinstance(widget, (tk.Canvas, ttk.Label, ttk.Button, ttk.Checkbutton)): 
                        return
            except tk.TclError:
                return 
                
            tooltip = ToolTip(widget, tip_text, wraplength=wraplength) 
            self.tips_widgets_corr[widget] = tooltip

    def _on_toggle_tips_corr(self):
        show = self.show_tips_var_corr.get()
        self.config_manager.set_correction_window_show_tips(show) 
        logger.info(f"Correction window tips toggled: {'On' if show else 'Off'}")
        if show: self._setup_correction_window_tooltips()
        else:
            for widget, tooltip_instance in list(self.tips_widgets_corr.items()):
                tooltip_instance.unbind()
            self.tips_widgets_corr.clear()

    def _setup_correction_window_tooltips(self):
        if not hasattr(self.ui, 'tips_checkbox_corr'): return
        self._add_tooltip_for_widget_corr(self.ui.tips_checkbox_corr, "show_tips_checkbox_corr")
        self._add_tooltip_for_widget_corr(self.ui.browse_transcription_button, "transcription_file_browse_corr")
        self._add_tooltip_for_widget_corr(self.ui.browse_audio_button, "audio_file_browse_corr")
        self._add_tooltip_for_widget_corr(self.ui.load_files_button, "load_files_button_corr")
        self._add_tooltip_for_widget_corr(self.ui.assign_speakers_button, "assign_speakers_button_corr")
        self._add_tooltip_for_widget_corr(self.ui.save_changes_button, "save_changes_button_corr")
        self._add_tooltip_for_widget_corr(self.ui.play_pause_button, "play_pause_button_corr")
        self._add_tooltip_for_widget_corr(self.ui.rewind_button, "rewind_button_corr")
        self._add_tooltip_for_widget_corr(self.ui.forward_button, "forward_button_corr")
        self._add_tooltip_for_widget_corr(self.ui.jump_to_segment_button, "jump_to_segment_button_corr")
        self._add_tooltip_for_widget_corr(self.ui.audio_timeline_canvas, "audio_progress_bar_corr") 
        self._add_tooltip_for_widget_corr(self.ui.current_time_label, "time_labels_corr")
        self._add_tooltip_for_widget_corr(self.ui.transcription_text, "transcription_text_area_corr", wraplength=350)
        self._add_tooltip_for_widget_corr(self.ui.save_start_time_button, "save_start_time_button_tip") 
        self._add_tooltip_for_widget_corr(self.ui.toggle_end_time_button, "toggle_end_time_button_tip") 
        self._add_tooltip_for_widget_corr(self.ui.save_times_button, "save_times_button_tip") 
        self._add_tooltip_for_widget_corr(self.ui.cancel_timestamp_edit_button, "cancel_timestamp_edit_button_tip") 

    def _setup_context_menu(self):
        self.context_menu = tk.Menu(self.ui.transcription_text, tearoff=0)
        self.context_menu.add_command(label="Edit Segment Text", command=self.callback_handler.edit_segment_text_action_from_menu)
        self.context_menu.add_command(label="Edit Timestamps", command=self.callback_handler.edit_segment_timestamps_action_menu)
        self.context_menu.add_command(label="Add New Segment", command=self.callback_handler.add_new_segment_action_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Remove Segment", command=self.callback_handler.remove_segment_action_from_menu)
        self.context_menu.add_command(label="Change Speaker for this Segment", command=self.callback_handler.change_segment_speaker_action_menu)

    def configure_and_show_context_menu(self, event):
        is_segment_selected = bool(self.right_clicked_segment_id)
        can_edit_text = is_segment_selected and not self.is_timestamp_editing_active 
        can_edit_ts = is_segment_selected and not self.text_edit_mode_active
        can_remove = is_segment_selected and not self.is_any_edit_mode_active()
        can_change_speaker = is_segment_selected and not self.is_any_edit_mode_active()
        self.context_menu.entryconfig("Add New Segment", state=tk.NORMAL)
        self.context_menu.entryconfig("Edit Segment Text", state=tk.NORMAL if can_edit_text else tk.DISABLED)
        self.context_menu.entryconfig("Edit Timestamps", state=tk.NORMAL if can_edit_ts else tk.DISABLED)
        self.context_menu.entryconfig("Remove Segment", state=tk.NORMAL if can_remove else tk.DISABLED)
        self.context_menu.entryconfig("Change Speaker for this Segment", state=tk.NORMAL if can_change_speaker else tk.DISABLED)
        try: self.context_menu.tk_popup(event.x_root, event.y_root)
        except tk.TclError: self.context_menu.tk_popup(self.window.winfo_pointerx(), self.window.winfo_pointery())

    def is_any_edit_mode_active(self) -> bool:
        return self.text_edit_mode_active or self.is_timestamp_editing_active

    def _exit_all_edit_modes(self, save_changes: bool = True):
        if self.text_edit_mode_active: self._exit_text_edit_mode(save_changes=save_changes)
        if self.is_timestamp_editing_active: self._exit_timestamp_edit_mode(save_changes=save_changes) 
        if hasattr(self.ui, 'tips_checkbox_corr'): self.ui.tips_checkbox_corr.config(state=tk.NORMAL)

    def _handle_escape_key(self, event=None):
        if self.text_edit_mode_active:
            self._exit_text_edit_mode(save_changes=False); return "break"
        elif self.is_timestamp_editing_active:
            self._handle_cancel_timestamp_edit_click(); return "break"
        return None

    def _load_files_core_logic(self, transcription_path: str, audio_path: str):
        logger.info(f"Core load: TXT='{transcription_path}', AUDIO='{audio_path}'")
        self._exit_all_edit_modes(save_changes=False) 
        try:
            if self.audio_player: self.audio_player.stop_resources(); self.audio_player = None
            if self.audio_player_update_queue:
                while not self.audio_player_update_queue.empty(): self.audio_player_update_queue.get_nowait()
                self.audio_player_update_queue = None
            with open(transcription_path, 'r', encoding='utf-8') as f: lines = f.readlines()
            if not self.segment_manager.parse_transcription_lines(lines):
                 self._disable_audio_controls(); return
            self._render_segments_to_text_area()
            self.audio_player = AudioPlayer(audio_path, on_error_callback=self._handle_audio_player_error)
            if not self.audio_player.is_ready(): self._disable_audio_controls(); return
            self.audio_player_update_queue = self.audio_player.get_update_queue()
            self._redraw_audio_timeline()
            self._update_time_labels_display()
            widgets_to_enable = [
                self.ui.play_pause_button, self.ui.rewind_button, self.ui.forward_button,
                self.ui.audio_timeline_canvas, self.ui.save_changes_button
            ]
            if hasattr(self.ui, 'tips_checkbox_corr'): widgets_to_enable.append(self.ui.tips_checkbox_corr)
            self.ui.set_widgets_state(widgets_to_enable, tk.NORMAL)
            self.ui.assign_speakers_button.config(state=tk.NORMAL) # Always enable Assign Speakers button
            self.ui.load_files_button.config(text="Reload Files")
            self.ui.set_play_pause_button_text("Play")
            logger.info("Files loaded successfully (core logic), timeline drawn.")
        except Exception as e:
            logger.exception("Error during _load_files_core_logic.")
            messagebox.showerror("Load Error", f"Unexpected error during file loading: {e}", parent=self.window)
            self._disable_audio_controls()

    def _save_changes_core_logic(self):
        self._exit_all_edit_modes(save_changes=True) 
        formatted_lines = self.segment_manager.format_segments_for_saving(
            self.output_include_timestamps, self.output_include_end_times
        )
        if not formatted_lines: messagebox.showwarning("Nothing to Save", "No valid segments found to save.", parent=self.window); return
        content_to_save = "\n".join(formatted_lines) + "\n"
        initial_filename = "corrected_transcription.txt"
        if self.ui.get_transcription_file_path():
            try:
                base, ext = os.path.splitext(os.path.basename(self.ui.get_transcription_file_path()))
                initial_filename = f"{base}_corrected{ext if ext else '.txt'}"
            except Exception: pass
        save_path = filedialog.asksaveasfilename(
            initialfile=initial_filename, defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            parent=self.window, title="Save Corrected Transcription As"
        )
        if not save_path: logger.info("Save operation cancelled."); return
        try:
            with open(save_path, 'w', encoding='utf-8') as f: f.write(content_to_save)
            messagebox.showinfo("Saved Successfully", f"Corrected transcription saved to:\n{save_path}", parent=self.window)
            logger.info(f"Changes saved to {save_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file: {e}", parent=self.window)
            logger.exception(f"Error during _save_changes_core_logic to {save_path}")

    def _open_assign_speakers_dialog_core_logic(self):
        # This is the single source of truth for opening the dialog now.
        self._exit_all_edit_modes(save_changes=True)
        dialog = tk.Toplevel(self.window); dialog.title("Assign Speaker Names"); dialog.transient(self.window); dialog.grab_set()
        main_frame = ttk.Frame(dialog, padding="10"); main_frame.pack(expand=True, fill=tk.BOTH)
        ttk.Label(main_frame, text="Assign custom names to raw speaker labels or add new speakers:").pack(anchor="w", pady=(0,5))

        canvas_frame = ttk.Frame(main_frame); canvas_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(canvas_frame, highlightthickness=0); scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        inner_frame = ttk.Frame(canvas)
        inner_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"), width=e.width))
        canvas.create_window((0,0), window=inner_frame, anchor="nw"); canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def _on_mousewheel_dialog(event): canvas.yview_scroll(-1*(event.delta // 120), "units")
        dialog.bind_all("<MouseWheel>", _on_mousewheel_dialog) 

        add_new_speaker_frame = ttk.Frame(inner_frame); add_new_speaker_frame.pack(fill=tk.X, pady=(5,10), padx=5)
        ttk.Label(add_new_speaker_frame, text="Add New Speaker:").pack(side=tk.LEFT, padx=(0,2))
        new_raw_id_var = tk.StringVar(); ttk.Entry(add_new_speaker_frame, textvariable=new_raw_id_var, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Label(add_new_speaker_frame, text="Display Name:").pack(side=tk.LEFT, padx=(5,2))
        new_display_name_var = tk.StringVar(); ttk.Entry(add_new_speaker_frame, textvariable=new_display_name_var, width=15).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        ttk.Separator(inner_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        entries = {}
        if not self.segment_manager.unique_speaker_labels:
             ttk.Label(inner_frame, text="No existing speaker labels found.").pack(pady=10)
        for raw_label in sorted(list(self.segment_manager.unique_speaker_labels)):
            row_frame = ttk.Frame(inner_frame); row_frame.pack(fill=tk.X, expand=True, padx=5) 
            ttk.Label(row_frame, text=f"{raw_label}:", width=20).pack(side=tk.LEFT, padx=5, pady=3) 
            entry = ttk.Entry(row_frame); entry.insert(0, self.segment_manager.speaker_map.get(raw_label, "")); entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, pady=3)
            entries[raw_label] = entry
        
        btn_frame = ttk.Frame(main_frame); btn_frame.pack(fill=tk.X, pady=(10,0), side=tk.BOTTOM) 
        def on_save_dialog():
            for raw_label, entry_widget in entries.items():
                custom_name = entry_widget.get().strip()
                if custom_name: self.segment_manager.speaker_map[raw_label] = custom_name 
                elif raw_label in self.segment_manager.speaker_map: del self.segment_manager.speaker_map[raw_label] 
            new_raw_id = new_raw_id_var.get().strip(); new_display_name = new_display_name_var.get().strip()
            if new_raw_id: 
                if new_raw_id not in self.segment_manager.unique_speaker_labels: self.segment_manager.unique_speaker_labels.add(new_raw_id)
                if new_display_name: self.segment_manager.speaker_map[new_raw_id] = new_display_name
                elif new_raw_id in self.segment_manager.speaker_map and not new_display_name: del self.segment_manager.speaker_map[new_raw_id]
            self._render_segments_to_text_area(); dialog.unbind_all("<MouseWheel>"); dialog.destroy()
        
        ttk.Button(btn_frame, text="Save", command=on_save_dialog).pack(side=tk.RIGHT, padx=5) 
        ttk.Button(btn_frame, text="Cancel", command=lambda: (dialog.unbind_all("<MouseWheel>"), dialog.destroy())).pack(side=tk.RIGHT) 
        self._center_dialog(dialog, min_width=580, base_height=350)
        dialog.wait_window()

    def _change_segment_speaker_dialog_logic(self, segment_id: str):
        self._exit_all_edit_modes(save_changes=True)
        segment = self.segment_manager.get_segment_by_id(segment_id)
        if not segment: return

        choices = {raw: self.segment_manager.speaker_map.get(raw, raw) for raw in self.segment_manager.unique_speaker_labels}
        if constants.NO_SPEAKER_LABEL not in choices:
            choices[constants.NO_SPEAKER_LABEL] = "(No Speaker / Unknown)"
        
        menu = tk.Menu(self.window, tearoff=0)
        
        def set_speaker(raw_label):
            self.segment_manager.update_segment_speaker(segment_id, raw_label)
            self._render_segments_to_text_area()

        for raw, display in sorted(choices.items(), key=lambda item: item[1]): 
            menu.add_command(label=display, command=lambda rl=raw: set_speaker(rl))

        menu.add_separator()
        menu.add_command(label="Add/Edit Speaker List...", command=self.callback_handler.open_assign_speakers_dialog)

        try: 
            menu.tk_popup(self.window.winfo_pointerx(), self.window.winfo_pointery())
        except tk.TclError: 
            menu.tk_popup(self.window.winfo_rootx()+100, self.window.winfo_rooty()+100)

    def _add_new_segment_dialog_logic(self, reference_segment_id_for_positioning: str | None, split_char_index: int | None = None):
        self._exit_all_edit_modes(save_changes=True) 

        dialog = tk.Toplevel(self.window)
        dialog_title = "Split Segment" if split_char_index is not None else "Add New Segment"
        dialog.title(dialog_title); dialog.transient(self.window); dialog.grab_set(); dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding="15"); frame.pack(expand=True, fill=tk.BOTH)

        # --- Reusable function to populate the speaker dropdown ---
        def populate_speaker_dropdown(dropdown_widget, string_var):
            speaker_choices = {constants.NO_SPEAKER_LABEL: "(No Speaker / Unknown)"}
            for raw_label in sorted(list(self.segment_manager.unique_speaker_labels)):
                speaker_choices[raw_label] = self.segment_manager.speaker_map.get(raw_label, raw_label)
            
            speaker_display_names = list(speaker_choices.values())
            dropdown_widget['values'] = speaker_display_names
            if speaker_display_names:
                string_var.set(speaker_display_names[0])
            return {v: k for k, v in speaker_choices.items()} # Return reverse map

        # --- Dialog UI Elements ---
        if split_char_index is None and reference_segment_id_for_positioning:
            position_var = tk.StringVar(value="below")
            ttk.Label(frame, text="Position relative to selected:").grid(row=0, column=0, sticky="w", pady=2)
            pos_frame = ttk.Frame(frame)
            ttk.Radiobutton(pos_frame, text="Above", variable=position_var, value="above").pack(side=tk.LEFT)
            ttk.Radiobutton(pos_frame, text="Below", variable=position_var, value="below").pack(side=tk.LEFT, padx=5)
            pos_frame.grid(row=0, column=1, columnspan=2, sticky="w", pady=2)
        elif split_char_index is None and not reference_segment_id_for_positioning: 
             ttk.Label(frame, text="Adding new segment to the end.").grid(row=0, column=0, columnspan=3, sticky="w", pady=2)

        ttk.Label(frame, text="New Segment Timestamp Type:").grid(row=1, column=0, sticky="w", pady=2)
        ts_type_var = tk.StringVar(value="No Timestamps") 
        ts_type_options = ["No Timestamps", "Start Time Only", "Start and End Times"]
        ts_type_dropdown = ttk.Combobox(frame, textvariable=ts_type_var, values=ts_type_options, state="readonly", width=25)
        ts_type_dropdown.set(ts_type_options[0]); ts_type_dropdown.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(frame, text="New Segment Speaker:").grid(row=2, column=0, sticky="w", pady=2)
        speaker_var = tk.StringVar()
        speaker_dropdown = ttk.Combobox(frame, textvariable=speaker_var, state="readonly", width=25)
        speaker_raw_map = populate_speaker_dropdown(speaker_dropdown, speaker_var) # Initial population
        speaker_dropdown.grid(row=2, column=1, sticky="ew", pady=2)

        def open_speaker_manager_and_refresh_dropdown():
            # Open the main dialog
            self.callback_handler.open_assign_speakers_dialog()
            # Repopulate the dropdown in this dialog after the main one closes
            nonlocal speaker_raw_map
            speaker_raw_map = populate_speaker_dropdown(speaker_dropdown, speaker_var)

        ttk.Button(frame, text="...", command=open_speaker_manager_and_refresh_dropdown, width=3).grid(row=2, column=2, padx=(2,0), pady=2, sticky="w")
        
        feedback_label = ttk.Label(frame, text="", foreground="red"); feedback_label.grid(row=3, column=0, columnspan=3, pady=(5,0), sticky="w")
        btn_frame = ttk.Frame(frame); btn_frame.grid(row=4, column=0, columnspan=3, pady=(10,0))

        def on_ok_add_segment():
            ts_type_map = {"No Timestamps": "none", "Start Time Only": "start_only", "Start and End Times": "start_end"}
            actual_ts_type = ts_type_map.get(ts_type_var.get(), "none")
            actual_speaker_raw = speaker_raw_map.get(speaker_var.get(), constants.NO_SPEAKER_LABEL)

            if split_char_index is not None: 
                original_seg_id = reference_segment_id_for_positioning 
                if not original_seg_id: feedback_label.config(text="Error: Original segment for split not identified."); return
                _, new_seg_id = self.segment_manager.split_segment(
                    original_segment_id=original_seg_id, text_split_index=split_char_index,
                    new_segment_speaker=actual_speaker_raw, new_segment_ts_type=actual_ts_type
                )
                if new_seg_id:
                    self._render_segments_to_text_area()
                    messagebox.showinfo("Segment Split", f"Segment split. New segment created.", parent=self.window) 
                    dialog.destroy()
                else: feedback_label.config(text="Error: Failed to split segment.")
            else: 
                new_segment_data = {
                    "text": "", "speaker_raw": actual_speaker_raw, "start_time": 0.0, "end_time": None,
                    "has_timestamps": actual_ts_type != "none", "has_explicit_end_time": actual_ts_type == "start_end"
                }
                position_to_insert = position_var.get() if reference_segment_id_for_positioning else "end"
                new_seg_id = self.segment_manager.add_segment(
                    new_segment_data, reference_segment_id=reference_segment_id_for_positioning, position=position_to_insert
                )
                if new_seg_id:
                    self._render_segments_to_text_area()
                    messagebox.showinfo("Segment Added", f"New segment added. Please edit its text.", parent=self.window) 
                    dialog.destroy()
                else: feedback_label.config(text="Error: Failed to add new segment.")

        ttk.Button(btn_frame, text="OK", command=on_ok_add_segment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        self._center_dialog(dialog, min_width=450)
        dialog.wait_window()

    def _enter_timestamp_edit_mode(self, segment_id: str):
        if self.text_edit_mode_active: 
            self._exit_text_edit_mode(save_changes=True)
        if self.is_timestamp_editing_active and self.segment_id_for_timestamp_edit != segment_id:
            self._exit_timestamp_edit_mode(save_changes=True) 
        elif self.is_timestamp_editing_active and self.segment_id_for_timestamp_edit == segment_id:
            logger.debug(f"Already in timestamp edit mode for segment {segment_id}. Re-initializing bars.")
            
        target_segment = self.segment_manager.get_segment_by_id(segment_id)
        if not target_segment: logger.warning(f"Enter TS Edit: Segment {segment_id} not found."); return
        if not self.audio_player or not self.audio_player.is_ready():
            messagebox.showwarning("Audio Error", "Audio player not ready. Cannot edit timestamps.", parent=self.window); return

        self.is_timestamp_editing_active = True
        self.segment_id_for_timestamp_edit = segment_id
        
        self.start_timestamp_bar_value_seconds = target_segment.get("start_time", 0.0)
        if target_segment.get("has_timestamps", False) and self.start_timestamp_bar_value_seconds is None: self.start_timestamp_bar_value_seconds = 0.0
        
        current_is_end_time_active = target_segment.get("has_explicit_end_time", False)
        self.is_end_time_bar_active = current_is_end_time_active 
        self.ui.toggle_end_time_var.set(self.is_end_time_bar_active) 
        
        if self.is_end_time_bar_active and target_segment.get("end_time") is not None:
            self.end_timestamp_bar_value_seconds = target_segment.get("end_time")
        else: 
            self.end_timestamp_bar_value_seconds = self.start_timestamp_bar_value_seconds + 1.0 
            audio_duration = self.audio_player.total_frames / self.audio_player.frame_rate if self.audio_player.frame_rate > 0 else float('inf')
            self.end_timestamp_bar_value_seconds = min(self.end_timestamp_bar_value_seconds, audio_duration)
            if not self.is_end_time_bar_active : 
                 self.end_timestamp_bar_value_seconds = self.start_timestamp_bar_value_seconds

        self._configure_ui_for_timestamp_edit_mode(True) 
        self._update_timestamp_bar_labels()
        self._redraw_audio_timeline()
        
        self.ui.rewind_button.config(text="<< 1s")
        self.ui.forward_button.config(text="1s >>")

        if target_segment.get("has_timestamps", False):
             self.ui.jump_to_segment_button.pack(side=tk.LEFT, padx=(5,0), before=self.ui.audio_timeline_canvas)
        else: self.ui.jump_to_segment_button.pack_forget()
        logger.info(f"Entered interactive timestamp edit mode for segment: {segment_id}")

    def _exit_timestamp_edit_mode(self, save_changes: bool = False):
        if not self.is_timestamp_editing_active: return
        logger.info(f"Exiting interactive timestamp edit mode for {self.segment_id_for_timestamp_edit}. Save: {save_changes}")
        
        exited_segment_id = self.segment_id_for_timestamp_edit 
        
        self.is_timestamp_editing_active = False
        self.segment_id_for_timestamp_edit = None
        self.dragging_bar = None
        
        self._configure_ui_for_timestamp_edit_mode(False) 

        self._redraw_audio_timeline() 
        
        self.ui.rewind_button.config(text="<< 5s")
        self.ui.forward_button.config(text="5s >>")

        self.ui.jump_to_segment_button.pack_forget()
        
        if save_changes: 
            self._render_segments_to_text_area()
            if exited_segment_id: self._scroll_to_segment_if_visible(exited_segment_id)

    def _configure_ui_for_timestamp_edit_mode(self, enter_mode: bool):
        if enter_mode:
            self.ui.timestamp_edit_controls_frame.pack(after=self.ui.audio_timeline_canvas.master, fill=tk.X, pady=(2,0))
            self.ui.toggle_end_time_button.config(state=tk.NORMAL)
            self.ui.toggle_end_time_var.set(self.is_end_time_bar_active)

            for widget in self.ui.timestamp_edit_controls_frame.winfo_children():
                widget.pack_forget()

            if self.is_end_time_bar_active:
                self.ui.timestamp_start_time_label.pack(side=tk.LEFT, padx=(5,10), pady=2)
                self.ui.timestamp_end_time_label.pack(side=tk.LEFT, padx=(0,10), pady=2)
                self.ui.save_times_button.pack(side=tk.LEFT, padx=5, pady=2)
            else:
                self.ui.timestamp_start_time_label.pack(side=tk.LEFT, padx=(5,10), pady=2)
                self.ui.save_start_time_button.pack(side=tk.LEFT, padx=5, pady=2)
            
            self.ui.toggle_end_time_button.pack(side=tk.LEFT, padx=5, pady=2)
            self.ui.cancel_timestamp_edit_button.pack(side=tk.RIGHT, padx=5, pady=2) 

            self._toggle_global_ui_for_edit_mode(disable=True, keep_playback_controls_enabled=True)
        else:
            self.ui.timestamp_edit_controls_frame.pack_forget()
            self._toggle_global_ui_for_edit_mode(disable=False)

    def _update_timestamp_bar_labels(self):
        if not self.is_timestamp_editing_active: return
        start_str = self.segment_manager.seconds_to_time_str(self.start_timestamp_bar_value_seconds)
        self.ui.update_specific_timestamp_label(self.ui.timestamp_start_time_label, "Start", start_str)
        
        if self.is_end_time_bar_active and self.ui.timestamp_end_time_label.winfo_ismapped():
            end_str = self.segment_manager.seconds_to_time_str(self.end_timestamp_bar_value_seconds)
            self.ui.update_specific_timestamp_label(self.ui.timestamp_end_time_label, "End", end_str)
        elif not self.is_end_time_bar_active: 
             self.ui.update_specific_timestamp_label(self.ui.timestamp_end_time_label, "End", "")

    def _redraw_audio_timeline(self, event=None):
        if not hasattr(self.ui, 'audio_timeline_canvas') or not self.ui.audio_timeline_canvas.winfo_exists(): return
        canvas = self.ui.audio_timeline_canvas; canvas.delete("all") 
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width <= 1 or height <= 1 : return 
        audio_duration_sec = 0
        if self.audio_player and self.audio_player.is_ready() and self.audio_player.frame_rate > 0:
            audio_duration_sec = self.audio_player.total_frames / self.audio_player.frame_rate
        if audio_duration_sec <= 0: return 
        if self.audio_player and self.audio_player.is_ready():
            current_time_sec = self.audio_player.current_frame / self.audio_player.frame_rate if self.audio_player.frame_rate > 0 else 0
            playback_x = self._time_to_x(current_time_sec, width, audio_duration_sec)
            self.main_playback_bar_id = canvas.create_line(playback_x, 0, playback_x, height, 
                                                           fill=self.ui.main_playback_bar_color, width=self.ui.main_playback_bar_width, tags="playback_bar")
        if self.is_timestamp_editing_active:
            start_bar_x = self._time_to_x(self.start_timestamp_bar_value_seconds, width, audio_duration_sec)
            self.start_selection_bar_id = canvas.create_line(start_bar_x, 0, start_bar_x, height,
                                                             fill=self.ui.start_bar_color, width=self.ui.draggable_bar_width, tags="start_bar")
            if self.is_end_time_bar_active:
                end_bar_x = self._time_to_x(self.end_timestamp_bar_value_seconds, width, audio_duration_sec)
                self.end_selection_bar_id = canvas.create_line(end_bar_x, 0, end_bar_x, height,
                                                               fill=self.ui.end_bar_color, width=self.ui.draggable_bar_width, tags="end_bar")
            else: self.end_selection_bar_id = None
        else: self.start_selection_bar_id = None; self.end_selection_bar_id = None

    def _time_to_x(self, seconds: float, canvas_width: int, audio_duration_seconds: float) -> int:
        if audio_duration_seconds <= 0: return 0
        clamped_seconds = max(0, min(seconds, audio_duration_seconds))
        proportion = clamped_seconds / audio_duration_seconds
        return int(proportion * canvas_width)

    def _x_to_time(self, x_coord: int, canvas_width: int, audio_duration_seconds: float) -> float:
        if canvas_width <= 0 or audio_duration_seconds <=0: return 0.0
        clamped_x = max(0, min(x_coord, canvas_width))
        proportion = clamped_x / canvas_width
        return proportion * audio_duration_seconds
    
    def _on_canvas_resize(self, event):
        self._redraw_audio_timeline()

    def _on_timeline_canvas_press(self, event):
        if not self.audio_player or not self.audio_player.is_ready(): return

        canvas = self.ui.audio_timeline_canvas
        width = canvas.winfo_width()
        audio_duration_sec = self.audio_player.total_frames / self.audio_player.frame_rate if self.audio_player.frame_rate > 0 else 0
        if audio_duration_sec <=0: return

        click_x = event.x
        click_sensitivity = 5 
        
        if self.is_timestamp_editing_active:
            start_bar_x = self._time_to_x(self.start_timestamp_bar_value_seconds, width, audio_duration_sec)
            if abs(click_x - start_bar_x) <= click_sensitivity:
                self.dragging_bar = "start"; logger.debug("Dragging start bar"); return

            if self.is_end_time_bar_active:
                end_bar_x = self._time_to_x(self.end_timestamp_bar_value_seconds, width, audio_duration_sec)
                if abs(click_x - end_bar_x) <= click_sensitivity:
                    self.dragging_bar = "end"; logger.debug("Dragging end bar"); return
        
        current_time_sec = self.audio_player.current_frame / self.audio_player.frame_rate if self.audio_player.frame_rate > 0 else 0
        playback_x = self._time_to_x(current_time_sec, width, audio_duration_sec)
        if abs(click_x - playback_x) <= click_sensitivity:
            self.dragging_main_playback_bar = True
            self.was_playing_before_drag = self.audio_player.playing
            if self.was_playing_before_drag:
                self.audio_player.pause()
            logger.debug("Dragging main playback bar")
            return

        self.dragging_bar = None
        self.dragging_main_playback_bar = False
        seek_time_seconds = self._x_to_time(click_x, width, audio_duration_sec)
        if self.audio_player.frame_rate > 0:
            self.audio_player.set_pos_frames(int(seek_time_seconds * self.audio_player.frame_rate))
        logger.debug(f"Canvas clicked for main audio seek to: {seek_time_seconds:.3f}s")

    def _on_timeline_canvas_drag(self, event):
        if not self.audio_player or not self.audio_player.is_ready(): return
        
        canvas = self.ui.audio_timeline_canvas
        width = canvas.winfo_width()
        audio_duration_sec = self.audio_player.total_frames / self.audio_player.frame_rate if self.audio_player.frame_rate > 0 else 0
        if audio_duration_sec <=0: return

        drag_x = event.x
        clamped_drag_x = max(0, min(drag_x, width))
        new_time = self._x_to_time(clamped_drag_x, width, audio_duration_sec)
        new_time = max(0.0, min(new_time, audio_duration_sec))

        if self.is_timestamp_editing_active and self.dragging_bar is not None:
            if self.dragging_bar == "start":
                self.start_timestamp_bar_value_seconds = new_time
                if self.is_end_time_bar_active and self.end_timestamp_bar_value_seconds < self.start_timestamp_bar_value_seconds:
                    self.end_timestamp_bar_value_seconds = self.start_timestamp_bar_value_seconds
            elif self.dragging_bar == "end":
                self.end_timestamp_bar_value_seconds = new_time
                if self.start_timestamp_bar_value_seconds > self.end_timestamp_bar_value_seconds:
                    self.start_timestamp_bar_value_seconds = self.end_timestamp_bar_value_seconds
            
            self._update_timestamp_bar_labels()
            self._redraw_audio_timeline()
        elif self.dragging_main_playback_bar:
            if self.audio_player.frame_rate > 0:
                self.audio_player.set_pos_frames(int(new_time * self.audio_player.frame_rate))

    def _on_timeline_canvas_release(self, event):
        if self.dragging_bar: 
            logger.debug(f"Finished dragging {self.dragging_bar} bar.")
            self.dragging_bar = None
        
        if self.dragging_main_playback_bar:
            logger.debug("Finished dragging main playback bar.")
            self.dragging_main_playback_bar = False
            if self.was_playing_before_drag:
                self.audio_player.play()
            self.was_playing_before_drag = False
    
    def _handle_save_start_time_click(self):
        if not self.is_timestamp_editing_active or not self.segment_id_for_timestamp_edit:
            logger.warning("Save Start Time: Not in edit mode or no segment ID.")
            return
        new_start_str = self.segment_manager.seconds_to_time_str(self.start_timestamp_bar_value_seconds)
        success, msg = self.segment_manager.update_segment_timestamps(
            self.segment_id_for_timestamp_edit, new_start_str, None 
        )
        if success:
            logger.info(f"Segment {self.segment_id_for_timestamp_edit} start time updated to {new_start_str}.")
            if msg: messagebox.showwarning("Timestamp Warning", msg, parent=self.window)
            self._exit_timestamp_edit_mode(save_changes=True)
        else:
            logger.error(f"Failed to save start time for {self.segment_id_for_timestamp_edit}: {msg}")
            messagebox.showerror("Save Error", msg or "Failed to save start time.", parent=self.window)

    def _handle_toggle_end_time_click(self):
        self.is_end_time_bar_active = self.ui.toggle_end_time_var.get()
        logger.info(f"_handle_toggle_end_time_click: End time bar active: {self.is_end_time_bar_active}")
        
        self._configure_ui_for_timestamp_edit_mode(True) 
        self._update_timestamp_bar_labels()
        self._redraw_audio_timeline()

    def _handle_save_times_click(self):
        if not self.is_timestamp_editing_active or not self.segment_id_for_timestamp_edit or \
           not self.is_end_time_bar_active:
            logger.warning("Save Times: Not in correct edit mode or no segment ID or end time bar not active.")
            return

        new_start_str = self.segment_manager.seconds_to_time_str(self.start_timestamp_bar_value_seconds)
        new_end_str = self.segment_manager.seconds_to_time_str(self.end_timestamp_bar_value_seconds)
        success, msg = self.segment_manager.update_segment_timestamps(
            self.segment_id_for_timestamp_edit, new_start_str, new_end_str
        )
        if success:
            logger.info(f"Segment {self.segment_id_for_timestamp_edit} start/end times updated to S={new_start_str}, E={new_end_str}.")
            if msg: messagebox.showwarning("Timestamp Warning", msg, parent=self.window)
            self._exit_timestamp_edit_mode(save_changes=True)
        else:
            logger.error(f"Failed to save times for {self.segment_id_for_timestamp_edit}: {msg}")
            messagebox.showerror("Save Error", msg or "Failed to save start and end times.", parent=self.window)

    def _handle_cancel_timestamp_edit_click(self):
        logger.info("_handle_cancel_timestamp_edit_click: Cancelling timestamp edit.")
        self._exit_timestamp_edit_mode(save_changes=False)

    def _render_segments_to_text_area(self):
        if self.text_edit_mode_active: self._exit_text_edit_mode(save_changes=False) 
        
        self.ui.transcription_text.config(state=tk.NORMAL); self.ui.transcription_text.delete("1.0", tk.END)
        self.currently_highlighted_text_seg_id = None 
        if not self.segment_manager.segments:
            self.ui.transcription_text.insert(tk.END, "No transcription data loaded or all lines were unparsable.")
            self.ui.transcription_text.config(state=tk.DISABLED); return
        for idx, seg in enumerate(self.segment_manager.segments):
            line_start_idx_str = self.ui.transcription_text.index(tk.END + "-1c linestart") 
            has_ts, has_explicit_end, has_speaker = seg.get("has_timestamps", False), seg.get("has_explicit_end_time", False), seg['speaker_raw'] != constants.NO_SPEAKER_LABEL
            display_speaker = self.segment_manager.speaker_map.get(seg['speaker_raw'], seg['speaker_raw']) if has_speaker else ""
            prefix, merge_tuple = "  ", () 
            if idx > 0 and has_speaker and self.segment_manager.segments[idx-1].get("speaker_raw") == seg["speaker_raw"] and seg['speaker_raw'] != constants.NO_SPEAKER_LABEL:
                prefix, merge_tuple = "+ ", ("merge_tag_style", seg['id']) 
            if not has_ts and not has_speaker: prefix = ""; merge_tuple = () 
            self.ui.transcription_text.insert(tk.END, prefix, merge_tuple)
            ts_area_start_idx_str, ts_tag_for_double_click = self.ui.transcription_text.index(tk.END), seg.get("timestamp_tag_id") 
            if has_ts:
                start_str = self.segment_manager.seconds_to_time_str(seg['start_time'])
                ts_str_display = f"[{start_str} - {self.segment_manager.seconds_to_time_str(seg['end_time'])}] " if has_explicit_end and seg['end_time'] is not None else f"[{start_str}] "
                self.ui.transcription_text.insert(tk.END, ts_str_display, ("timestamp_tag_style", seg['id'], ts_tag_for_double_click))
            ts_area_end_idx_str = self.ui.transcription_text.index(tk.END) 
            if ts_tag_for_double_click: self.ui.transcription_text.tag_add(ts_tag_for_double_click, ts_area_start_idx_str, ts_area_end_idx_str)
            if has_speaker: self.ui.transcription_text.insert(tk.END, display_speaker, ("speaker_tag_style", seg['id'])); self.ui.transcription_text.insert(tk.END, ": ")
            text_to_display, current_text_tags = seg['text'], ["inactive_text_default", seg.get("text_tag_id")] 
            if not text_to_display: text_to_display, current_text_tags = constants.EMPTY_SEGMENT_PLACEHOLDER, ["placeholder_text_style", seg.get("text_tag_id")] 
            text_content_actual_start_idx_str = self.ui.transcription_text.index(tk.END) 
            self.ui.transcription_text.insert(tk.END, text_to_display, tuple(filter(None, current_text_tags))) 
            text_content_actual_end_idx_str = self.ui.transcription_text.index(tk.END)
            if seg.get("text_tag_id"): self.ui.transcription_text.tag_add(seg.get("text_tag_id"), text_content_actual_start_idx_str, text_content_actual_end_idx_str)
            self.ui.transcription_text.insert(tk.END, "\n") 
            self.ui.transcription_text.tag_add(seg['id'], line_start_idx_str, self.ui.transcription_text.index(tk.END + "-1c lineend"))
        self.ui.transcription_text.config(state=tk.DISABLED)

    def _toggle_global_ui_for_edit_mode(self, disable: bool, keep_playback_controls_enabled: bool = False):
        new_state = tk.DISABLED if disable else tk.NORMAL
        
        general_controls_to_toggle = [
            self.ui.browse_transcription_button, self.ui.browse_audio_button,
            self.ui.load_files_button, self.ui.save_changes_button,
            self.ui.assign_speakers_button
        ]
        if hasattr(self.ui, 'tips_checkbox_corr'):
            general_controls_to_toggle.append(self.ui.tips_checkbox_corr)
        
        self.ui.set_widgets_state(general_controls_to_toggle, new_state)

        if not keep_playback_controls_enabled: 
            standard_audio_controls = [
                self.ui.play_pause_button, self.ui.rewind_button, self.ui.forward_button,
                self.ui.audio_timeline_canvas
            ]
            self.ui.set_widgets_state(standard_audio_controls, new_state)
        else:
            standard_audio_controls_to_enable = [
                 self.ui.play_pause_button, self.ui.rewind_button, self.ui.forward_button,
                 self.ui.audio_timeline_canvas
            ]
            self.ui.set_widgets_state(standard_audio_controls_to_enable, tk.NORMAL)

    def _enter_text_edit_mode(self, segment_id_to_edit: str):
        if self.is_any_edit_mode_active(): self._exit_all_edit_modes(save_changes=True)
        target_segment = self.segment_manager.get_segment_by_id(segment_id_to_edit)
        if not target_segment: return
        self.text_edit_mode_active, self.editing_segment_id, self.text_content_start_index_in_edit = True, segment_id_to_edit, None 
        self.ui.transcription_text.config(state=tk.NORMAL)
        self._toggle_global_ui_for_edit_mode(disable=True, keep_playback_controls_enabled=True) 
        text_tag_id = target_segment.get("text_tag_id")
        if not text_tag_id: self._exit_text_edit_mode(save_changes=False); return
        try:
            ranges = self.ui.transcription_text.tag_ranges(text_tag_id)
            if not ranges: self._exit_text_edit_mode(save_changes=False); return
            edit_start_index, edit_end_index = ranges[0], ranges[1]
            current_text_in_widget = self.ui.transcription_text.get(edit_start_index, edit_end_index)
            if current_text_in_widget == constants.EMPTY_SEGMENT_PLACEHOLDER:
                self.ui.transcription_text.delete(edit_start_index, edit_end_index); edit_end_index = edit_start_index 
            self.ui.transcription_text.tag_remove("placeholder_text_style", edit_start_index, edit_end_index)
            self.ui.transcription_text.tag_remove("inactive_text_default", edit_start_index, edit_end_index)
            self.ui.transcription_text.tag_add("editing_active_segment_text", edit_start_index, edit_end_index) 
            self.text_content_start_index_in_edit, _ = edit_start_index, self.ui.transcription_text.focus_set()
            self.ui.transcription_text.mark_set(tk.INSERT, edit_start_index); self.ui.transcription_text.see(edit_start_index)
        except tk.TclError as e: self._exit_text_edit_mode(save_changes=False); return
        if target_segment.get("has_timestamps", False):
             self.ui.jump_to_segment_button.pack(side=tk.LEFT, padx=(5,0), before=self.ui.audio_timeline_canvas)
        else: self.ui.jump_to_segment_button.pack_forget()
        logger.info(f"Entered text edit mode for segment: {self.editing_segment_id}")

    def _exit_text_edit_mode(self, save_changes: bool = True):
        if not self.text_edit_mode_active or not self.editing_segment_id: return
        logger.debug(f"Exiting text edit mode for segment: {self.editing_segment_id}. Save changes: {save_changes}")
        text_updated, original_segment_obj = False, self.segment_manager.get_segment_by_id(self.editing_segment_id) 
        if save_changes and original_segment_obj:
            true_start_of_text_content = self.text_content_start_index_in_edit
            if true_start_of_text_content:
                try:
                    text_content_end_index_on_line = self.ui.transcription_text.index(f"{true_start_of_text_content} lineend")
                    modified_text = self.ui.transcription_text.get(true_start_of_text_content, text_content_end_index_on_line).strip()
                    final_text_to_save = "" if modified_text == constants.EMPTY_SEGMENT_PLACEHOLDER or not modified_text else modified_text
                    if self.segment_manager.update_segment_text(self.editing_segment_id, final_text_to_save): text_updated = True
                except Exception as e: logger.exception(f"Error updating segment text for {self.editing_segment_id}: {e}")
            else: logger.warning(f"Segment {self.editing_segment_id} missing cached start_index_in_edit on exit.")
        try: self.ui.transcription_text.tag_remove("editing_active_segment_text", "1.0", tk.END)
        except tk.TclError: logger.warning("TclError removing 'editing_active_segment_text' globally.")
        self.ui.jump_to_segment_button.pack_forget(); self._toggle_global_ui_for_edit_mode(disable=False) 
        editing_segment_id_before_clear = self.editing_segment_id 
        self.text_edit_mode_active, self.editing_segment_id, self.text_content_start_index_in_edit = False, None, None 
        logger.info(f"Exited text edit mode for segment {editing_segment_id_before_clear}. Text updated status: {text_updated}")
        self._render_segments_to_text_area() 
        if editing_segment_id_before_clear: self._scroll_to_segment_if_visible(editing_segment_id_before_clear)

    def _get_segment_id_from_text_index(self, text_index_str: str) -> str | None:
        tags_at_index = self.ui.transcription_text.tag_names(text_index_str)
        for tag_prefix in ["text_content_seg_", "ts_content_seg_"]:
            for tag in tags_at_index:
                if tag.startswith(tag_prefix):
                    base_id = "seg_" + tag.split("_seg_")[-1]
                    if any(s["id"] == base_id for s in self.segment_manager.segments): return base_id
        for tag in tags_at_index:
            if tag.startswith("seg_") and tag.count('_') == 1 and any(s["id"] == tag for s in self.segment_manager.segments): return tag
        return None

    def _poll_audio_player_queue(self):
        if self.audio_player_update_queue:
            try:
                while not self.audio_player_update_queue.empty():
                    message_content = self.audio_player_update_queue.get_nowait()
                    msg_type = message_content[0]
                    if msg_type == 'initialized': 
                        self._redraw_audio_timeline(); self._update_time_labels_display()
                    elif msg_type == 'progress':
                        if self.audio_player and self.audio_player.is_ready():
                            self._update_time_labels_display(); self._redraw_audio_timeline() 
                            if not self.is_any_edit_mode_active(): 
                                current_s = self.audio_player.current_frame / self.audio_player.frame_rate if self.audio_player.frame_rate > 0 else 0
                                self._highlight_current_segment(current_s)
                    elif msg_type in ['started', 'resumed']: self.ui.set_play_pause_button_text("Pause")
                    elif msg_type == 'paused': self.ui.set_play_pause_button_text("Play")
                    elif msg_type == 'finished':
                        self.ui.set_play_pause_button_text("Play")
                        if self.audio_player and self.audio_player.is_ready(): self._redraw_audio_timeline(); self._update_time_labels_display()
                    elif msg_type == 'stopped': self.ui.set_play_pause_button_text("Play"); self._redraw_audio_timeline() 
                    elif msg_type == 'error': self._handle_audio_player_error(message_content[1]) 
                    self.audio_player_update_queue.task_done()
            except queue.Empty: pass 
            except Exception as e: logger.exception("Error processing audio player queue.")
        if hasattr(self, 'window') and self.window.winfo_exists(): self.window.after(50, self._poll_audio_player_queue) 

    def _toggle_play_pause(self):
        if not self.audio_player or not self.audio_player.is_ready(): 
            messagebox.showinfo("Audio Not Ready", "Please load an audio file.", parent=self.window); return
        if self.audio_player.playing: self.audio_player.pause()
        else: self.audio_player.play() 

    def _seek_audio(self, delta_seconds: float): 
        """Internal method to seek audio by a specific delta."""
        if not self.audio_player or not self.audio_player.is_ready() or self.audio_player.frame_rate <= 0: return
        target_frame = int((self.audio_player.current_frame / self.audio_player.frame_rate + delta_seconds) * self.audio_player.frame_rate)
        self.audio_player.set_pos_frames(target_frame)

    def _handle_seek_button_click(self, base_delta_seconds: int):
        """Handles clicks from Rewind/Forward buttons, adjusting delta if in TS edit mode."""
        if self.is_timestamp_editing_active:
            actual_delta = 1.0 * math.copysign(1, base_delta_seconds) 
        else:
            actual_delta = float(base_delta_seconds) 
        self._seek_audio(actual_delta)
    
    def _update_time_labels_display(self):
        if not self.audio_player or not self.audio_player.is_ready(): self.ui.update_time_labels_display("--:--.---", "--:--.---"); return
        current_s = self.audio_player.current_frame / self.audio_player.frame_rate if self.audio_player.frame_rate > 0 else 0.0
        total_s = self.audio_player.total_frames / self.audio_player.frame_rate if self.audio_player.frame_rate > 0 else 0.0
        self.ui.update_time_labels_display(self.segment_manager.seconds_to_time_str(current_s), self.segment_manager.seconds_to_time_str(total_s))

    def _highlight_current_segment(self, current_playback_seconds: float):
        if self.is_any_edit_mode_active(): return 
        newly_highlighted_id = None
        for i, seg in enumerate(self.segment_manager.segments):
            if not seg.get("has_timestamps") or seg["start_time"] is None: continue
            start_s = seg["start_time"] 
            effective_end_s = seg["end_time"] if seg.get("has_explicit_end_time") and seg["end_time"] is not None else \
                              (self.segment_manager.segments[i+1]["start_time"] if (i + 1) < len(self.segment_manager.segments) and self.segment_manager.segments[i+1].get("has_timestamps") and self.segment_manager.segments[i+1]["start_time"] is not None else \
                              (self.audio_player.total_frames / self.audio_player.frame_rate if self.audio_player and self.audio_player.is_ready() and self.audio_player.frame_rate > 0 else float('inf')))
            if effective_end_s is not None and start_s <= current_playback_seconds < effective_end_s: newly_highlighted_id = seg['id']; break 
        if self.currently_highlighted_text_seg_id != newly_highlighted_id:
            if self.currently_highlighted_text_seg_id and (old_seg := self.segment_manager.get_segment_by_id(self.currently_highlighted_text_seg_id)): self._apply_text_highlight(old_seg.get("text_tag_id"), False) 
            if newly_highlighted_id and (new_seg := self.segment_manager.get_segment_by_id(newly_highlighted_id)): self._apply_text_highlight(new_seg.get("text_tag_id"), True, True)
            self.currently_highlighted_text_seg_id = newly_highlighted_id

    def _apply_text_highlight(self, text_tag_id: str | None, active: bool, scroll_to: bool = False):
        if not text_tag_id: return 
        try:
            ranges = self.ui.transcription_text.tag_ranges(text_tag_id)
            if ranges:
                tags_to_remove = ["active_text_highlight", "inactive_text_default", "placeholder_text_style"]
                for tag in tags_to_remove: self.ui.transcription_text.tag_remove(tag, ranges[0], ranges[1])
                tag_to_add = "active_text_highlight" if active else ("placeholder_text_style" if self.ui.transcription_text.get(ranges[0], ranges[1]) == constants.EMPTY_SEGMENT_PLACEHOLDER else "inactive_text_default")
                self.ui.transcription_text.tag_add(tag_to_add, ranges[0], ranges[1])
                if active and scroll_to: self.ui.transcription_text.see(ranges[0])
        except tk.TclError: logger.warning(f"TclError applying highlight for tag {text_tag_id}.")

    def _jump_to_segment_start_action(self):
        segment_id_to_jump = self.editing_segment_id if self.text_edit_mode_active else (self.segment_id_for_timestamp_edit if self.is_timestamp_editing_active else None)
        if not segment_id_to_jump: return
        segment = self.segment_manager.get_segment_by_id(segment_id_to_jump)
        if not segment or not self.audio_player or not self.audio_player.is_ready() or not segment.get("has_timestamps", False) or segment.get("start_time") is None: 
            if segment and (not segment.get("has_timestamps", False) or segment.get("start_time") is None): messagebox.showwarning("Playback Warning", "Segment has no valid start timestamp.", parent=self.window)
            return
        target_time = max(0, segment["start_time"] - 1.0) 
        if self.audio_player.frame_rate > 0: self.audio_player.set_pos_frames(int(target_time * self.audio_player.frame_rate))

    def _handle_audio_player_error(self, error_message):
        logger.error(f"AudioPlayer reported error: {error_message}")
        messagebox.showerror("Audio Player Error", error_message, parent=self.window)
        self._disable_audio_controls()
        if self.audio_player: self.audio_player.stop_resources(); self.audio_player = None
        self.ui.set_play_pause_button_text("Play")

    def _disable_audio_controls(self):
        widgets = [self.ui.play_pause_button, self.ui.rewind_button, self.ui.forward_button, self.ui.audio_timeline_canvas]
        if hasattr(self.ui, 'tips_checkbox_corr'): widgets.append(self.ui.tips_checkbox_corr)
        self.ui.set_widgets_state(widgets, tk.DISABLED); self._redraw_audio_timeline()
        if hasattr(self.ui, 'jump_to_segment_button') and self.ui.jump_to_segment_button.winfo_exists(): self.ui.jump_to_segment_button.pack_forget()

    def _center_dialog(self, dialog_window, min_width=300, base_height=200, height_per_item=30, num_items=0):
        dialog_window.update_idletasks(); desired_height = base_height + (num_items * height_per_item)
        max_dialog_height = int(self.window.winfo_height() * 0.8); dialog_height = max(150, min(desired_height, max_dialog_height)) 
        dialog_width = min_width; dialog_window.minsize(min_width, 150); dialog_window.geometry(f"{dialog_width}x{dialog_height}")
        dialog_window.update_idletasks(); d_width, d_height = dialog_window.winfo_width(), dialog_window.winfo_height()
        parent_x, parent_y = self.window.winfo_rootx(), self.window.winfo_rooty()
        parent_width, parent_height = self.window.winfo_width(), self.window.winfo_height()
        x, y = parent_x + (parent_width // 2) - (d_width // 2), parent_y + (parent_height // 2) - (d_height // 2)
        dialog_window.geometry(f"+{max(0,x)}+{max(0,y)}"); dialog_window.lift()

    def _scroll_to_segment_if_visible(self, segment_id: str):
        segment_to_see = self.segment_manager.get_segment_by_id(segment_id)
        if segment_to_see:
            for tag_key in ["id", "text_tag_id"]:
                tag_val = segment_to_see.get(tag_key)
                if tag_val:
                    try:
                        if ranges := self.ui.transcription_text.tag_ranges(tag_val): self.ui.transcription_text.see(ranges[0]); return
                    except tk.TclError: logger.warning(f"TclError scrolling to tag {tag_val}.")
            logger.warning(f"Could not find tag for segment {segment_id} to scroll.")

    def _on_close(self):
        logger.info("CorrectionWindow: Close requested.")
        if self.is_any_edit_mode_active():
            if self.is_timestamp_editing_active:
                 if not messagebox.askyesno("Unsaved Edit", "You are editing timestamps. Exiting now will discard changes. Are you sure?", parent=self.window, icon=messagebox.WARNING): return
                 self._exit_timestamp_edit_mode(save_changes=False) 
            elif self.text_edit_mode_active: 
                if not messagebox.askyesno("Unsaved Edit", "You are editing text. Exiting now will discard changes. Are you sure?", parent=self.window, icon=messagebox.WARNING): return
                self._exit_text_edit_mode(save_changes=False)
        self._exit_all_edit_modes(save_changes=False)
        for widget, tooltip_instance in list(self.tips_widgets_corr.items()): tooltip_instance.unbind()
        self.tips_widgets_corr.clear()
        if self.audio_player: self.audio_player.stop_resources()
        self.audio_player, self.audio_player_update_queue = None, None
        try:
            if hasattr(self, 'window') and self.window.winfo_exists(): self.window.unbind_all("<MouseWheel>")
        except tk.TclError: pass
        if hasattr(self, 'window') and self.window.winfo_exists(): self.window.destroy()





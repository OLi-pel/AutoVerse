# ui/correction_window_ui.py
import tkinter as tk
from tkinter import ttk
import logging

# Import for tips data
from utils.tips_data import get_tip # Assuming tips_data.py is in utils

logger = logging.getLogger(__name__)

# --- ToolTip Class (copied from main_window.py for this step) ---
# Ideally, this would be in a shared utility file.
class ToolTip:
    """
    Create a tooltip for a given widget with show/hide delays to prevent flickering.
    """
    def __init__(self, widget, text, wraplength=200, show_delay=500, hide_delay=100):
        self.widget = widget
        self.text = text
        self.wraplength = wraplength
        self.show_delay = show_delay  # milliseconds
        self.hide_delay = hide_delay  # milliseconds
        self.tooltip_window = None
        self._show_after_id = None
        self._hide_after_id = None

        self._enter_binding = self.widget.bind("<Enter>", self.schedule_show_tooltip)
        self._leave_binding = self.widget.bind("<Leave>", self.schedule_hide_tooltip)
        # Also hide if the widget is destroyed (e.g., window closes)
        self._destroy_binding = self.widget.bind("<Destroy>", self.force_hide_tooltip)


    def schedule_show_tooltip(self, event=None):
        # If a hide is scheduled, cancel it because mouse re-entered
        if self._hide_after_id:
            self.widget.after_cancel(self._hide_after_id)
            self._hide_after_id = None
        
        # If a show is already scheduled, or tooltip is already visible, do nothing
        if self._show_after_id or self.tooltip_window:
            return
            
        # Schedule to show
        self._show_after_id = self.widget.after(self.show_delay, self._show_tooltip_actual)

    def _show_tooltip_actual(self):
        self._show_after_id = None # Clear the after ID as it has now run
        if self.tooltip_window or not self.text: # Do not show if already visible or no text
            return

        # Check if widget still exists
        try:
            if not self.widget.winfo_exists():
                return
        except tk.TclError: # Widget might have been destroyed
            return

        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = ttk.Label(self.tooltip_window, text=self.text, justify=tk.LEFT,
                          background="#FFFFE0", relief="solid", borderwidth=1,
                          wraplength=self.wraplength, padding=(5,2))
        label.pack(ipadx=1)

    def schedule_hide_tooltip(self, event=None):
        # If a show is scheduled, cancel it because mouse left before it could show
        if self._show_after_id:
            self.widget.after_cancel(self._show_after_id)
            self._show_after_id = None
            
        # If a hide is already scheduled, or tooltip is not visible, do nothing
        if self._hide_after_id or not self.tooltip_window:
            return

        # Schedule to hide
        self._hide_after_id = self.widget.after(self.hide_delay, self._hide_tooltip_actual)

    def _hide_tooltip_actual(self):
        self._hide_after_id = None # Clear the after ID
        if self.tooltip_window:
            # Check if widget still exists before trying to access Toplevel parent
            try:
                if not self.widget.winfo_exists():
                    if self.tooltip_window.winfo_exists():
                        self.tooltip_window.destroy()
                    self.tooltip_window = None
                    return
            except tk.TclError:
                if self.tooltip_window and self.tooltip_window.winfo_exists():
                    self.tooltip_window.destroy()
                self.tooltip_window = None
                return

            if self.tooltip_window.winfo_exists():
                self.tooltip_window.destroy()
            self.tooltip_window = None
            
    def force_hide_tooltip(self, event=None):
        """Immediately hides the tooltip and cancels any pending actions. Used for <Destroy> or explicit unbind."""
        if self._show_after_id:
            self.widget.after_cancel(self._show_after_id)
            self._show_after_id = None
        if self._hide_after_id:
            self.widget.after_cancel(self._hide_after_id)
            self._hide_after_id = None
        if self.tooltip_window and self.tooltip_window.winfo_exists():
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def update_text(self, new_text):
        self.text = new_text
        # If tooltip is visible, hide it. It will re-appear with new text on next valid hover.
        if self.tooltip_window:
            self.force_hide_tooltip()

    def unbind(self):
        self.force_hide_tooltip() # Hide and cancel timers
        
        # Check if widget still exists before trying to unbind
        try:
            if self.widget.winfo_exists():
                if self._enter_binding:
                    self.widget.unbind("<Enter>", self._enter_binding)
                if self._leave_binding:
                    self.widget.unbind("<Leave>", self._leave_binding)
                if self._destroy_binding:
                    self.widget.unbind("<Destroy>", self._destroy_binding)
        except tk.TclError:
            # Widget might have already been destroyed
            pass
        finally:
            self._enter_binding = None
            self._leave_binding = None
            self._destroy_binding = None

class CorrectionWindowUI:
    def __init__(self, parent_tk_window,
                 browse_transcription_callback, browse_audio_callback,
                 load_files_callback, assign_speakers_callback, save_changes_callback,
                 toggle_play_pause_callback, seek_audio_callback, # REMOVED: on_progress_bar_seek_callback
                 jump_to_segment_start_callback,
                 text_area_double_click_callback, text_area_right_click_callback, text_area_left_click_edit_mode_callback,
                 on_speaker_click_callback, on_merge_click_callback,
                 # Add show_tips_var and its command from CorrectionWindow
                 show_tips_var_ref, toggle_tips_callback_ref,
                 # NEW Callbacks for timestamp editing buttons
                 on_save_start_time_callback, on_toggle_end_time_callback,
                 on_save_times_callback, on_cancel_timestamp_edit_callback
                 ):
        """
        Initializes and lays out the UI elements for the CorrectionWindow.
        Callbacks are passed in from the main CorrectionWindow class.
        show_tips_var_ref is a tk.BooleanVar() instance from CorrectionWindow.
        toggle_tips_callback_ref is the method in CorrectionWindow to call when the checkbox is toggled.
        """
        self.window = parent_tk_window

        # --- StringVars for Entry fields ---
        self.transcription_file_path_var = tk.StringVar()
        self.audio_file_path_var = tk.StringVar()
        # self.audio_progress_var = tk.DoubleVar() # REMOVED: No longer using ttk.Scale for progress

        # --- Colors and Styles ---
        self.text_area_font_family = 'Helvetica'
        self.text_area_font_size = 12
        self.text_area_base_font = (self.text_area_font_family, self.text_area_font_size)
        self.text_area_italic_font = (self.text_area_font_family, self.text_area_font_size, 'italic')
        self.text_area_bold_font = (self.text_area_font_family, self.text_area_font_size, 'bold')
        
        self.text_area_bg_color = "white"
        self.text_area_fg_color = "black"
        self.editing_segment_bg_color = "#E0E0FF"
        self.timestamp_fg_color = "#555555"
        self.active_highlight_bg = "yellow"
        self.active_highlight_fg = "black"
        self.editing_timestamp_bg_color = "lightblue" # Can be used for canvas elements too
        self.placeholder_text_fg_color = "grey"

        # Colors for new draggable bars on canvas
        self.start_bar_color = "blue"
        self.end_bar_color = "green"
        self.main_playback_bar_color = "red"
        self.timeline_bg_color = "#DDDDDD" # Background for the canvas timeline area
        self.draggable_bar_width = 3 # Pixel width for draggable bars
        self.main_playback_bar_width = 2 # Pixel width for main playback bar

        # --- Main layout ---
        main_container_frame = ttk.Frame(self.window, padding="5")
        main_container_frame.pack(expand=True, fill=tk.BOTH)

        # --- Header Frame for Tips Checkbox ---
        header_frame_corr = ttk.Frame(main_container_frame)
        header_frame_corr.pack(fill=tk.X, side=tk.TOP, pady=(0, 5))
        header_frame_corr.columnconfigure(0, weight=1) 

        self.tips_checkbox_corr = ttk.Checkbutton(
            header_frame_corr,
            text="Show Tips",
            variable=show_tips_var_ref, 
            command=toggle_tips_callback_ref 
        )
        self.tips_checkbox_corr.pack(side=tk.RIGHT, padx=5)
        

        # --- Top Controls Frame (File Browse, Load, Assign, Save) ---
        top_controls_frame = ttk.Frame(main_container_frame)
        top_controls_frame.pack(fill=tk.X, side=tk.TOP, pady=(0, 5))

        ttk.Label(top_controls_frame, text="Transcription File:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.transcription_entry = ttk.Entry(top_controls_frame, textvariable=self.transcription_file_path_var, width=40)
        self.transcription_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_transcription_button = ttk.Button(top_controls_frame, text="Browse...", command=browse_transcription_callback)
        self.browse_transcription_button.grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(top_controls_frame, text="Audio File:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.audio_entry = ttk.Entry(top_controls_frame, textvariable=self.audio_file_path_var, width=40)
        self.audio_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.browse_audio_button = ttk.Button(top_controls_frame, text="Browse...", command=browse_audio_callback)
        self.browse_audio_button.grid(row=1, column=2, padx=5, pady=5)

        self.load_files_button = ttk.Button(top_controls_frame, text="Load Files", command=load_files_callback)
        self.load_files_button.grid(row=0, column=3, rowspan=2, padx=(10,5), pady=5, sticky="nswe")

        self.assign_speakers_button = ttk.Button(top_controls_frame, text="Assign Speakers", command=assign_speakers_callback, state=tk.DISABLED)
        self.assign_speakers_button.grid(row=0, column=4, padx=5, pady=5, sticky="ew")

        self.save_changes_button = ttk.Button(top_controls_frame, text="Save Changes", command=save_changes_callback, state=tk.DISABLED)
        self.save_changes_button.grid(row=1, column=4, padx=5, pady=5, sticky="ew")

        top_controls_frame.columnconfigure(1, weight=1)
        top_controls_frame.columnconfigure(3, minsize=100)
        top_controls_frame.columnconfigure(4, minsize=120)

        # --- Audio Controls Frame ---
        # This frame will now contain the standard playback buttons, the new canvas,
        # and a sub-frame for the new timestamp editing buttons/labels that can be shown/hidden.
        audio_controls_outer_frame = ttk.Frame(main_container_frame)
        audio_controls_outer_frame.pack(fill=tk.X, side=tk.TOP, pady=(0,5))

        # Sub-frame for standard playback controls and the timeline canvas
        standard_playback_and_canvas_frame = ttk.Frame(audio_controls_outer_frame)
        standard_playback_and_canvas_frame.pack(fill=tk.X, pady=(0,2)) # Reduced bottom padding

        self.play_pause_button = ttk.Button(standard_playback_and_canvas_frame, text="Play", command=toggle_play_pause_callback, state=tk.DISABLED)
        self.play_pause_button.pack(side=tk.LEFT, padx=2)
        self.rewind_button = ttk.Button(standard_playback_and_canvas_frame, text="<< 5s", command=lambda: seek_audio_callback(-5), state=tk.DISABLED)
        self.rewind_button.pack(side=tk.LEFT, padx=2)
        self.forward_button = ttk.Button(standard_playback_and_canvas_frame, text="5s >>", command=lambda: seek_audio_callback(5), state=tk.DISABLED)
        self.forward_button.pack(side=tk.LEFT, padx=2)
        
        self.jump_to_segment_button = ttk.Button(standard_playback_and_canvas_frame, text="|< Jump to Seg Start (-1s)", command=jump_to_segment_start_callback)
        # Not packed initially, shown/hidden by CorrectionWindow logic. It used to be packed before audio_progress_bar.
        # Now it can be packed by CorrectionWindow when text edit mode is active next to the canvas or other relevant place.
        
        # NEW: Audio Timeline Canvas (replaces ttk.Scale)
        # Define a reasonable height for the canvas to draw the timeline and markers
        self.audio_timeline_canvas_height = 40 # pixels
        self.audio_timeline_canvas = tk.Canvas(standard_playback_and_canvas_frame, height=self.audio_timeline_canvas_height, bg=self.timeline_bg_color, highlightthickness=0)
        self.audio_timeline_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        # Event bindings for this canvas (<Button-1>, <B1-Motion>, etc.) will be done in CorrectionWindow

        self.current_time_label = ttk.Label(standard_playback_and_canvas_frame, text="00:00.000 / 00:00.000")
        self.current_time_label.pack(side=tk.LEFT, padx=5)

        # NEW: Frame for timestamp editing controls (buttons and labels under bars)
        # This frame will be packed/unpacked by CorrectionWindow logic below the canvas or wherever appropriate.
        self.timestamp_edit_controls_frame = ttk.Frame(audio_controls_outer_frame)
        # Do not pack it here initially. CorrectionWindow will pack it when needed (e.g., below standard_playback_and_canvas_frame).

        # Labels to show time under draggable bars. These will be packed into timestamp_edit_controls_frame.
        # Their exact positioning relative to the canvas (above them) will be managed by how CorrectionWindow packs this frame
        # and potentially by adding spacer labels or specific grid layouts within timestamp_edit_controls_frame.
        self.timestamp_start_time_label = ttk.Label(self.timestamp_edit_controls_frame, text="Start: 00:00.000", foreground=self.start_bar_color)
        self.timestamp_start_time_label.pack(side=tk.LEFT, padx=(5,15), pady=2) 

        self.timestamp_end_time_label = ttk.Label(self.timestamp_edit_controls_frame, text="End: 00:00.000", foreground=self.end_bar_color)
        # self.timestamp_end_time_label.pack(side=tk.LEFT, padx=(0,15), pady=2) # Packed by CW when visible

        # Buttons for timestamp editing - also packed into timestamp_edit_controls_frame
        # Their order might be important.
        self.save_start_time_button = ttk.Button(self.timestamp_edit_controls_frame, text="Save Start", command=on_save_start_time_callback)
        # self.save_start_time_button.pack(side=tk.LEFT, padx=5, pady=2) # Packed by CW

        self.toggle_end_time_var = tk.BooleanVar(value=False) 
        self.toggle_end_time_button = ttk.Checkbutton(self.timestamp_edit_controls_frame, text="Set End Time", variable=self.toggle_end_time_var, command=on_toggle_end_time_callback)
        # self.toggle_end_time_button.pack(side=tk.LEFT, padx=5, pady=2) # Packed by CW

        self.save_times_button = ttk.Button(self.timestamp_edit_controls_frame, text="Save Start & End", command=on_save_times_callback)
        # self.save_times_button.pack(side=tk.LEFT, padx=5, pady=2) # Packed by CW
        
        # Add a spacer or use a different frame for cancel if it needs to be on the right
        self.cancel_timestamp_edit_button = ttk.Button(self.timestamp_edit_controls_frame, text="Cancel Edit", command=on_cancel_timestamp_edit_callback)
        # self.cancel_timestamp_edit_button.pack(side=tk.RIGHT, padx=5, pady=2) # Example packing, might be last

        # --- Transcription Text Area ---
        text_area_frame = ttk.Frame(main_container_frame)
        text_area_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        self.transcription_text = tk.Text(text_area_frame, wrap=tk.WORD, height=15, width=80, undo=True,
                                          background=self.text_area_bg_color,
                                          foreground=self.text_area_fg_color,
                                          insertbackground=self.text_area_fg_color,
                                          font=self.text_area_base_font)
        self.text_scrollbar = ttk.Scrollbar(text_area_frame, orient=tk.VERTICAL, command=self.transcription_text.yview)
        self.transcription_text.configure(yscrollcommand=self.text_scrollbar.set)
        self.text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.transcription_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._configure_text_tags()

        self.transcription_text.tag_bind("speaker_tag_style", "<Button-1>", on_speaker_click_callback)
        self.transcription_text.tag_bind("merge_tag_style", "<Button-1>", on_merge_click_callback)
        self.transcription_text.tag_bind("merge_tag_style", "<Enter>", lambda e: self.transcription_text.config(cursor="hand2"))
        self.transcription_text.tag_bind("merge_tag_style", "<Leave>", lambda e: self.transcription_text.config(cursor=""))

        self.transcription_text.bind("<Button-3>", text_area_right_click_callback)
        self.transcription_text.bind("<Double-1>", text_area_double_click_callback)
        self.transcription_text.bind("<Button-1>", text_area_left_click_edit_mode_callback)

        self.transcription_text.config(state=tk.DISABLED)

        logger.info("CorrectionWindowUI elements created with new canvas and timestamp edit controls.")

    def _configure_text_tags(self):
        """Configures all necessary tags for the transcription text area."""
        self.transcription_text.tag_configure("speaker_tag_style")
        self.transcription_text.tag_configure("merge_tag_style", foreground="#008000", underline=True, font=self.text_area_bold_font)
        self.transcription_text.tag_configure("timestamp_tag_style", foreground=self.timestamp_fg_color)
        self.transcription_text.tag_configure("no_timestamp_tag_style", foreground=self.timestamp_fg_color, font=self.text_area_italic_font)
        
        self.transcription_text.tag_configure("active_text_highlight", foreground=self.active_highlight_fg, background=self.active_highlight_bg)
        self.transcription_text.tag_configure("inactive_text_default", foreground=self.text_area_fg_color, background=self.text_area_bg_color)
        self.transcription_text.tag_configure("editing_active_segment_text", background=self.editing_segment_bg_color)
        self.transcription_text.tag_configure("editing_active_timestamp", background=self.editing_timestamp_bg_color)
        
        self.transcription_text.tag_configure("placeholder_text_style",
                                              font=self.text_area_italic_font,
                                              foreground=self.placeholder_text_fg_color)
        logger.debug("Text area tags configured in CorrectionWindowUI.")

    def set_play_pause_button_text(self, text: str):
        if hasattr(self, 'play_pause_button') and self.play_pause_button.winfo_exists():
            self.play_pause_button.config(text=text)

    def update_time_labels_display(self, current_time_str: str, total_time_str: str):
        """Updates the main current/total time display next to the canvas."""
        if hasattr(self, 'current_time_label') and self.current_time_label.winfo_exists():
            self.current_time_label.config(text=f"{current_time_str} / {total_time_str}")
    
    def update_specific_timestamp_label(self, label_widget: ttk.Label, prefix: str, time_str: str):
        """Updates specific labels like those under draggable bars."""
        if label_widget and hasattr(label_widget, 'winfo_exists') and label_widget.winfo_exists():
            label_widget.config(text=f"{prefix}: {time_str}")


    def update_audio_progress_bar_display(self, value: float, max_value: float | None = None):
        """
        This method is now effectively OBSOLETE for direct progress bar update
        as the ttk.Scale has been replaced by a tk.Canvas.
        The canvas will be drawn by CorrectionWindow logic.
        This method can be removed or repurposed if there's a new variable to set.
        For now, we'll make it a no-op to avoid errors if called.
        """
        # logger.debug(f"CorrectionWindowUI.update_audio_progress_bar_display called (now Canvas): V={value}, Max={max_value}")
        pass # ttk.Scale no longer exists

    def set_widgets_state(self, widgets: list, state: str):
        for widget in widgets:
            if widget and hasattr(widget, 'winfo_exists') and widget.winfo_exists():
                try: 
                    widget.config(state=state)
                except tk.TclError:
                    logger.warning(f"Could not set state for widget {widget}. It might be during teardown.")


    def get_transcription_file_path(self) -> str:
        return self.transcription_file_path_var.get()

    def get_audio_file_path(self) -> str:
        return self.audio_file_path_var.get()

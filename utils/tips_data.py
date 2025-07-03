# utils/tips_data.py

MAIN_WINDOW_TIPS = {
    "audio_file_browse": "Click the folder icon to select one or more audio/video files (.mp3, .mp4, etc.) for processing.",
    "transcription_model_dropdown": "Choose the AI model. 'Large' is the most accurate but slowest. 'Small' is a good balance for general use.",
    "enable_diarization_checkbox": "Check this to automatically identify and label different speakers. Requires a Hugging Face token.",
    "include_timestamps_checkbox": "Check to include start timestamps (e.g., [00:00.000]) for each segment.",
    "include_end_times_checkbox": "Check to also include end timestamps (e.g., [00:00.000 - 00:01.500]). Requires 'Include Timestamps' to be checked.",
    "auto_merge_checkbutton": "When using speaker diarization, this automatically joins consecutive segments from the same speaker.",
    "huggingface_token_entry": "Paste your Hugging Face 'read' access token here. This is required for speaker diarization.",
    "save_huggingface_token_button": "Saves your Hugging Face token so you don't have to enter it again next time.",
    "start_processing_button": "Begins processing the selected file(s). Click again to abort a process that is running.",
    "status_label": "Displays the current status of the application (e.g., Idle, Processing, Downloading).",
    "progress_bar": "Shows the progress of a current task like downloading or transcribing.",
    "output_text_area": "Displays the final transcription for a single file, or a summary for a batch process.",
    "correction_window_button": "After processing a single file, click here to open it in the powerful Correction Tab for editing.",
    "show_tips_checkbox_main": "Uncheck this box to hide these helpful tips from appearing in the status bar."
}

CORRECTION_WINDOW_TIPS = {
    # File Management
    "correction_browse_transcription_btn": "Browse for the .txt transcription file you want to edit.",
    "correction_browse_audio_btn": "Browse for the corresponding audio/video file for the transcription.",
    "correction_load_files_btn": "Load the selected audio and text files into the correction editor.",
    "correction_save_changes_btn": "Save all changes made in the editor to a new .txt file.",

    # Playback Controls
    "correction_play_pause_btn": "Play or pause the audio. Keyboard shortcut: Spacebar.",
    "correction_rewind_btn": "Seek backward by 5 seconds (or 1 second in timestamp edit mode).",
    "correction_forward_btn": "Seek forward by 5 seconds (or 1 second in timestamp edit mode).",
    "correction_timeline_frame": "The audio waveform. Click anywhere to jump to that point in the audio.",
    "correction_time_label": "Shows the current playback time and the total duration of the audio.",

    # Main Editing Toolbar
    "Undo_button": "Undo your last action (e.g., text edit, merge, speaker change).",
    "Redo_Button": "Redo an action you have just undone.",
    "edit_speaker_btn": "Change the speaker for the currently selected segment(s).",
    "correction_text_edit_btn": "Toggle edit mode for the selected segment's text. Click again to save.",
    "correction_timestamp_edit_btn": "Enter a special mode to visually edit the start time of a segment on the waveform.",
    "save_timestamp_btn": "Save the new timestamp you have set in timestamp edit mode.",
    "segment_btn": "With a segment selected, click to add a new segment above or below it. In text edit mode, it splits the current segment.",
    "merge_segments_btn": "Merge the selected segment with the one above it. You can also merge multiple selected segments together.",
    "delete_segment_btn": "Delete the selected segment(s), or clear text/timestamps if in an edit mode.",

    # Speaker and Text Formatting
    "correction_assign_speakers_btn": "Open a dialog to manage all speaker labels (e.g., rename SPEAKER_00 to 'Alice').",
    "text_font_combo": "Change the display font for the correction text editor.",
    "Police_size": "Change the display font size for the correction text editor.",
    "change_highlight_color_btn": "Change the color used for highlighting segments.",

    # The Text Area Itself
    "correction_text_area": "The main editor. Double-click a segment to edit its text. Click to select, Shift+Click to multi-select."
}

# Combined dictionary and helper function remain a good practice
ALL_TIPS = {
    "main_window": MAIN_WINDOW_TIPS,
    "correction_window": CORRECTION_WINDOW_TIPS
}

def get_tip(window_name: str, widget_key: str) -> str | None:
    """
    Retrieves a tip for a given window and widget key.
    Example: get_tip("main_window", "enable_diarization_checkbox")
    """
    if window_name in ALL_TIPS and widget_key in ALL_TIPS[window_name]:
        return ALL_TIPS[window_name][widget_key]
    return None

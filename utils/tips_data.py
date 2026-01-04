# utils/tips_data.py

TIPS = {
    "English": {
        # --- Main Window ---
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
        "show_tips_checkbox_main": "Uncheck this box to hide these helpful tips from appearing in the status bar.",

        # --- Correction Window ---
        "correction_browse_transcription_btn": "Browse for the .txt transcription file you want to edit.",
        "correction_browse_audio_btn": "Browse for the corresponding audio/video file for the transcription.",
        "correction_load_files_btn": "Load the selected audio and text files into the correction editor.",
        "correction_save_changes_btn": "Save all changes made in the editor to a new .txt file.",
        "correction_play_pause_btn": "Play or pause the audio. Keyboard shortcut: Spacebar.",
        "correction_rewind_btn": "Seek backward by 5 seconds (or 1 second in timestamp edit mode).",
        "correction_forward_btn": "Seek forward by 5 seconds (or 1 second in timestamp edit mode).",
        "correction_timeline_frame": "The audio waveform. Click anywhere to jump to that point in the audio.",
        "correction_time_label": "Shows the current playback time and the total duration of the audio.",
        "Undo_button": "Undo your last action (e.g., text edit, merge, speaker change).",
        "Redo_Button": "Redo an action you have just undone.",
        "edit_speaker_btn": "Change the speaker for the currently selected segment(s).",
        "correction_text_edit_btn": "Toggle edit mode for the selected segment's text. Click again to save.",
        "correction_timestamp_edit_btn": "Enter a special mode to visually edit the start time of a segment on the waveform.",
        "save_timestamp_btn": "Save the new timestamp you have set in timestamp edit mode.",
        "segment_btn": "With a segment selected, click to add a new segment above or below it. In text edit mode, it splits the current segment.",
        "merge_segments_btn": "Merge the selected segment with the one above it. You can also merge multiple selected segments together.",
        "delete_segment_btn": "Delete the selected segment(s), or clear text/timestamps if in an edit mode.",
        "correction_assign_speakers_btn": "Open a dialog to manage all speaker labels (e.g., rename SPEAKER_00 to 'Alice').",
        "text_font_combo": "Change the display font for the correction text editor.",
        "Police_size": "Change the display font size for the correction text editor.",
        "change_highlight_color_btn": "Change the color used for highlighting segments.",
        "correction_text_area": "The main editor. Double-click a segment to edit its text. Click to select, Shift+Click to multi-select."
    },
    
    "Français": {
        # --- Main Window ---
        "audio_file_browse": "Cliquez sur l'icône dossier pour sélectionner un ou plusieurs fichiers audio/vidéo (.mp3, .mp4, etc.) à traiter.",
        "transcription_model_dropdown": "Choisissez le modèle IA. 'Large' est le plus précis mais le plus lent. 'Small' est un bon équilibre.",
        "enable_diarization_checkbox": "Cochez pour identifier et étiqueter automatiquement les différents locuteurs. Nécessite un token Hugging Face.",
        "include_timestamps_checkbox": "Cochez pour inclure les horodatages de début (ex: [00:00.000]) pour chaque segment.",
        "include_end_times_checkbox": "Cochez pour inclure aussi les heures de fin. Nécessite que 'Inclure Horodatages' soit coché.",
        "auto_merge_checkbutton": "Avec la détection de locuteurs, fusionne automatiquement les segments consécutifs du même locuteur.",
        "huggingface_token_entry": "Collez votre token d'accès 'read' Hugging Face ici. Requis pour la détection de locuteurs.",
        "save_huggingface_token_button": "Sauvegarde votre token Hugging Face pour ne pas avoir à le ressaisir.",
        "start_processing_button": "Lance le traitement du/des fichier(s). Cliquez à nouveau pour annuler un processus en cours.",
        "status_label": "Affiche l'état actuel de l'application (ex: Inactif, Traitement, Téléchargement).",
        "progress_bar": "Affiche la progression de la tâche en cours.",
        "output_text_area": "Affiche la transcription finale pour un fichier unique, ou un résumé pour un traitement par lot.",
        "correction_window_button": "Après le traitement d'un fichier, cliquez ici pour l'ouvrir dans l'onglet Correction.",
        "show_tips_checkbox_main": "Décochez cette case pour masquer ces conseils dans la barre d'état.",

        # --- Correction Window ---
        "correction_browse_transcription_btn": "Parcourir pour trouver le fichier transcription .txt à éditer.",
        "correction_browse_audio_btn": "Parcourir pour trouver le fichier audio/vidéo correspondant.",
        "correction_load_files_btn": "Charger les fichiers audio et texte sélectionnés dans l'éditeur.",
        "correction_save_changes_btn": "Sauvegarder toutes les modifications dans un nouveau fichier .txt.",
        "correction_play_pause_btn": "Lecture ou pause de l'audio. Raccourci clavier : Espace.",
        "correction_rewind_btn": "Reculer de 5 secondes (ou 1 seconde en mode édition de temps).",
        "correction_forward_btn": "Avancer de 5 secondes (ou 1 seconde en mode édition de temps).",
        "correction_timeline_frame": "La forme d'onde audio. Cliquez n'importe où pour sauter à ce point.",
        "correction_time_label": "Affiche le temps de lecture actuel et la durée totale.",
        "Undo_button": "Annuler la dernière action (ex: édition texte, fusion, changement locuteur).",
        "Redo_Button": "Rétablir une action que vous venez d'annuler.",
        "edit_speaker_btn": "Changer le locuteur pour le(s) segment(s) sélectionné(s).",
        "correction_text_edit_btn": "Activer le mode édition pour le texte du segment. Cliquez à nouveau pour sauver.",
        "correction_timestamp_edit_btn": "Entrer dans un mode spécial pour éditer visuellement l'heure de début sur la forme d'onde.",
        "save_timestamp_btn": "Sauvegarder le nouvel horodatage défini.",
        "segment_btn": "Ajouter un nouveau segment au-dessus ou en-dessous. En mode édition, divise le segment actuel.",
        "merge_segments_btn": "Fusionner le segment sélectionné avec celui du dessus. Fonctionne aussi avec une sélection multiple.",
        "delete_segment_btn": "Supprimer le(s) segment(s) sélectionné(s), ou effacer texte/temps en mode édition.",
        "correction_assign_speakers_btn": "Ouvrir un dialogue pour gérer tous les noms de locuteurs (ex: renommer SPEAKER_00 en 'Alice').",
        "text_font_combo": "Changer la police d'affichage de l'éditeur.",
        "Police_size": "Changer la taille de police de l'éditeur.",
        "change_highlight_color_btn": "Changer la couleur de surbrillance des segments.",
        "correction_text_area": "L'éditeur principal. Double-cliquez pour éditer. Clic pour sélectionner, Shift+Clic pour sélection multiple."
    }
}

def get_tip(widget_key: str, lang: str = "English") -> str | None:
    """
    Retrieves a tip for a widget key in the specified language.
    Defaults to English if language or key not found.
    """
    lang_dict = TIPS.get(lang, TIPS["English"])
    return lang_dict.get(widget_key, TIPS["English"].get(widget_key, None))
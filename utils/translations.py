# utils/translations.py

TRANSLATIONS = {
    "English": {
        # --- Main Window ---
        "window_title": "AutoVerse v{}",
        "tab_transcription": "Transcription Service",
        "tab_correction": "Correction Window",
        "tab_settings": "Settings",
        
        # Step 1
        "step1_title": "Step 1: Select Audio/Video File(s)",
        "step1_summary_empty": "",
        "step1_summary_selected": "{} file(s) selected: {}",
        "grp_audio_file": "Audio File(s)",
        "lbl_file_path": "File Path(s):",
        "btn_change_selection": "Change Selection",
        
        # Step 2
        "step2_title": "Step 2: Configure Processing Options",
        "step2_summary_default": "Select file(s) to continue.",
        "step2_summary_config": "{}, {}",
        "grp_processing_options": "Processing Options",
        "grp_model": "Model Selection",
        "grp_speaker": "Speaker Detection",
        "chk_identify_speakers": "Identify Different Speakers",
        "btn_manage_token": "Manage Token",
        "chk_auto_merge": "Auto-Merge",
        "grp_timestamps": "Timestamps",
        "chk_timestamps": "Include Timestamps",
        "chk_end_times": "Include End Times",
        "grp_huggingface": "Hugging Face Token",
        "btn_continue": "Continue to Processing",
        "collapsible_others": "Others",

        # Step 3
        "step3_title": "Step 3: Start Processing & View Output",
        "step3_summary_default": "Configure options to continue.",
        "grp_output": "Output Text Area",
        "lbl_status_inactive": "Status: inactive",
        "btn_start_processing": "Start Processing",
        "btn_abort": "Abort",
        "btn_correction_tab": "Head to Correction Tab",
        
        # --- Correction Window ---
        "grp_load_files": "Load Files",
        "lbl_transcription_file": "Transcription File:",
        "lbl_audio_file": "Audio File:",
        "btn_load_files": "Load Files",
        "btn_save_changes": "Save Changes",
        "grp_audio_player": "Audio Player",
        "btn_play": "Play",
        "btn_pause": "Pause",
        
        # --- Settings Window ---
        "grp_appearance": "Appearance & Language",
        "lbl_theme": "Theme:",
        "lbl_language": "Language:",
        "grp_application": "Application Settings",
        "lbl_updates": "Updates:",
        "btn_check_updates": "Check for Updates",
        "btn_reset_tutorials": "Reset Tutorials",
        "btn_clear_cache": "Clear Cache",
        "grp_danger": "Danger Zone",
        "lbl_delete_desc": "Reset all application settings, tokens, and history.",
        "btn_reset_app": "Reset Application Data",

        # --- Dialogs & Messages ---
        "welcome_title": "Welcome to AutoVerse!",
        "welcome_label": "What would you like to do?",
        "btn_transcribe_new": " Transcribe a New Audio/Video File",
        "btn_edit_existing": " Edit an Existing Transcript",
        "btn_tutorial": " Start the Interactive Tutorial",
        "chk_dont_show": "Don't show this again",
        "hf_dialog_title": "Hugging Face Token Setup",
        "hf_group_why": "Why is this needed?",
        "hf_label_why": "To identify different speakers, AutoVerse needs to download free AI models from Hugging Face.\n\nA 'read-only' access token proves you have accepted their terms. <b>This is a one-time setup.</b>",
        "hf_group_steps": "Setup Steps",
        "hf_step1": "<b>1. Create Account</b>",
        "hf_step1_desc": "Log in or create a free Hugging Face account.",
        "hf_btn_step1": "Open Hugging Face",
        "hf_step2": "<b>2. Accept Terms</b>",
        "hf_step2_desc": "Visit BOTH links and click 'Agree and access repository'.",
        "hf_btn_model1": "Model 1",
        "hf_btn_model2": "Model 2",
        "hf_step3": "<b>3. Generate Token</b>",
        "hf_step3_desc": "Create a new token with the <b>'read'</b> role.",
        "hf_btn_step3": "Get Your Token",
        "hf_step4": "<b>4. Paste Token</b>",
        "hf_placeholder": "Paste your token here (it starts with 'hf_...')",
        "hf_btn_save": "Save and Continue",
        "msg_token_saved": "Hugging Face token has been saved successfully.",
        "msg_processing_aborted": "Processing aborted by user.",
        "msg_select_file_error": "Please select one or more audio/video files first.",
        "msg_batch_cancel": "Batch processing cancelled.",
        "msg_save_success": "Transcription saved to {}",
        "msg_save_error": "Could not save file: {}",
        "msg_confirm_delete": "Delete {} segment(s)?",
        "msg_confirm_clear": "Clear text content?",
        "msg_confirm_ts_delete": "Remove timestamp?",
        "dialog_split_title": "Split Segment",
        "dialog_add_title": "Add New Segment",
        "lbl_new_speaker": "New Segment Speaker:",
        "lbl_new_ts": "New Segment Timestamps:",
        "ts_opt_none": "No Timestamps",
        "ts_opt_start": "Start Time Only",
        "ts_opt_start_end": "Start and End Times",
        "lbl_position": "Position:",
        "radio_above": "Above",
        "radio_below": "Below",
        "dialog_speaker_title": "Assign Speaker Names",
        "lbl_add_new": "---<br><b>Add New</b>",
        "lbl_id": "ID:",
        "lbl_name": "Name:",
        "dialog_change_spk_title": "Change Speaker for {} Segment(s)",
        "lbl_assign_spk": "Assign a speaker:",
        "no_speaker": "(No Speaker)",
        
        # --- Update Checker ---
        "update_available_title": "Update Available: v{}",
        "update_available_msg": "A new version of AutoVerse is available (<b>v{}</b>). You have v{}.<br><br>Would you like to view the release page?",
        "update_uptodate_title": "Updates",
        "update_uptodate_msg": "You are up to date!",
        
        # --- Tutorials ---
        "tut_step_of": "Step {} of {}",
        "tut_next": "Next",
        "tut_finish": "Finish",
        "tut_prev": "Previous",
        "tut_exit": "Exit Tutorial",
    },
    
    "Français": {
        # --- Main Window ---
        "window_title": "AutoVerse v{}",
        "tab_transcription": "Service de Transcription",
        "tab_correction": "Fenêtre de Correction",
        "tab_settings": "Paramètres",
        
        # Step 1
        "step1_title": "Étape 1 : Sélectionner fichier(s) Audio/Vidéo",
        "step1_summary_empty": "",
        "step1_summary_selected": "{} fichier(s) sélectionné(s) : {}",
        "grp_audio_file": "Fichier(s) Audio",
        "lbl_file_path": "Chemin(s) :",
        "btn_change_selection": "Changer la sélection",
        
        # Step 2
        "step2_title": "Étape 2 : Options de Traitement",
        "step2_summary_default": "Sélectionnez un fichier pour continuer.",
        "step2_summary_config": "{}, {}",
        "grp_processing_options": "Options de Traitement",
        "grp_model": "Sélection du Modèle",
        "grp_speaker": "Détection des Locuteurs",
        "chk_identify_speakers": "Identifier les différents locuteurs",
        "btn_manage_token": "Gérer le Token",
        "chk_auto_merge": "Fusion Auto",
        "grp_timestamps": "Horodatages",
        "chk_timestamps": "Inclure Horodatages",
        "chk_end_times": "Inclure Heures de Fin",
        "grp_huggingface": "Token Hugging Face",
        "btn_continue": "Continuer vers le Traitement",
        "collapsible_others": "Autres",

        # Step 3
        "step3_title": "Étape 3 : Lancer le Traitement & Voir le Résultat",
        "step3_summary_default": "Configurez les options pour continuer.",
        "grp_output": "Zone de Texte de Sortie",
        "lbl_status_inactive": "Statut : inactif",
        "btn_start_processing": "Lancer le Traitement",
        "btn_abort": "Annuler",
        "btn_correction_tab": "Aller à l'onglet Correction",
        
        # --- Correction Window ---
        "grp_load_files": "Charger les Fichiers",
        "lbl_transcription_file": "Fichier Transcription :",
        "lbl_audio_file": "Fichier Audio :",
        "btn_load_files": "Charger Fichiers",
        "btn_save_changes": "Sauvegarder",
        "grp_audio_player": "Lecteur Audio",
        "btn_play": "Lecture",
        "btn_pause": "Pause",
        
        # --- Settings Window ---
        "grp_appearance": "Apparence & Langue",
        "lbl_theme": "Thème :",
        "lbl_language": "Langue :",
        "grp_application": "Paramètres de l'Application",
        "lbl_updates": "Mises à jour :",
        "btn_check_updates": "Vérifier les Mises à jour",
        "btn_reset_tutorials": "Réinitialiser les Tutoriels",
        "btn_clear_cache": "Vider le Cache",
        "grp_danger": "Zone de Danger",
        "lbl_delete_desc": "Réinitialiser tous les paramètres et l'historique.",
        "btn_reset_app": "Réinitialiser l'Application",

        # --- Dialogs & Messages ---
        "welcome_title": "Bienvenue sur AutoVerse !",
        "welcome_label": "Que souhaitez-vous faire ?",
        "btn_transcribe_new": " Transcrire un nouveau fichier Audio/Vidéo",
        "btn_edit_existing": " Éditer une transcription existante",
        "btn_tutorial": " Démarrer le Tutoriel Interactif",
        "chk_dont_show": "Ne plus afficher ceci",
        "hf_dialog_title": "Configuration Token Hugging Face",
        "hf_group_why": "Pourquoi est-ce nécessaire ?",
        "hf_label_why": "Pour identifier les locuteurs, AutoVerse doit télécharger des modèles IA gratuits depuis Hugging Face.\n\nUn token d'accès 'read' (lecture) prouve que vous avez accepté leurs conditions. <b>Ceci est une configuration unique.</b>",
        "hf_group_steps": "Étapes de Configuration",
        "hf_step1": "<b>1. Créer un Compte</b>",
        "hf_step1_desc": "Connectez-vous ou créez un compte gratuit Hugging Face.",
        "hf_btn_step1": "Ouvrir Hugging Face",
        "hf_step2": "<b>2. Accepter les Conditions</b>",
        "hf_step2_desc": "Visitez les DEUX liens et cliquez sur 'Agree and access repository'.",
        "hf_btn_model1": "Modèle 1",
        "hf_btn_model2": "Modèle 2",
        "hf_step3": "<b>3. Générer un Token</b>",
        "hf_step3_desc": "Créez un nouveau token avec le rôle <b>'read'</b>.",
        "hf_btn_step3": "Obtenir votre Token",
        "hf_step4": "<b>4. Coller le Token</b>",
        "hf_placeholder": "Collez votre token ici (commence par 'hf_...')",
        "hf_btn_save": "Sauvegarder et Continuer",
        "msg_token_saved": "Le token Hugging Face a été sauvegardé avec succès.",
        "msg_processing_aborted": "Traitement annulé par l'utilisateur.",
        "msg_select_file_error": "Veuillez d'abord sélectionner un ou plusieurs fichiers audio/vidéo.",
        "msg_batch_cancel": "Traitement par lot annulé.",
        "msg_save_success": "Transcription sauvegardée dans {}",
        "msg_save_error": "Impossible de sauvegarder le fichier : {}",
        "msg_confirm_delete": "Supprimer {} segment(s) ?",
        "msg_confirm_clear": "Effacer le contenu du texte ?",
        "msg_confirm_ts_delete": "Supprimer l'horodatage ?",
        "dialog_split_title": "Diviser le Segment",
        "dialog_add_title": "Ajouter un Segment",
        "lbl_new_speaker": "Locuteur du Nouveau Segment :",
        "lbl_new_ts": "Horodatage du Nouveau Segment :",
        "ts_opt_none": "Aucun Horodatage",
        "ts_opt_start": "Heure de Début Uniquement",
        "ts_opt_start_end": "Heure de Début et Fin",
        "lbl_position": "Position :",
        "radio_above": "Au-dessus",
        "radio_below": "En-dessous",
        "dialog_speaker_title": "Assigner des Noms aux Locuteurs",
        "lbl_add_new": "---<br><b>Ajouter Nouveau</b>",
        "lbl_id": "ID :",
        "lbl_name": "Nom :",
        "dialog_change_spk_title": "Changer Locuteur pour {} Segment(s)",
        "lbl_assign_spk": "Assigner un locuteur :",
        "no_speaker": "(Aucun Locuteur)",
        
        # --- Update Checker ---
        "update_available_title": "Mise à jour Disponible : v{}",
        "update_available_msg": "Une nouvelle version d'AutoVerse est disponible (<b>v{}</b>). Vous avez la v{}.<br><br>Voulez-vous voir la page de la version ?",
        "update_uptodate_title": "Mises à jour",
        "update_uptodate_msg": "Vous êtes à jour !",
        
        # --- Tutorials ---
        "tut_step_of": "Étape {} sur {}",
        "tut_next": "Suivant",
        "tut_finish": "Terminer",
        "tut_prev": "Précédent",
        "tut_exit": "Quitter le Tutoriel",
    }
}

def get_text(key, lang="Français", *args):
    """Retrieves the translation for a key in the specified language."""
    # Fallback to English if language not found
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS["English"])
    text = lang_dict.get(key, TRANSLATIONS["English"].get(key, key))
    if args:
        try:
            return text.format(*args)
        except IndexError:
            return text
    return text
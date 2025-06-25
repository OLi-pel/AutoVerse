# main.py
import os
import sys

# This block should be at the very top of your main.py file.
if getattr(sys, 'frozen', False):
    # In a bundled app without a console, sys.stdout and sys.stderr can be None.
    # We redirect them to a null output stream to prevent crashes from any library
    # that tries to write to them.
    _devnull = open(os.devnull, 'w')
    if sys.stdout is None:
        sys.stdout = _devnull
    if sys.stderr is None:
        sys.stderr = _devnull

    # The 'tqdm' library, used by 'whisper' for download progress bars, is a known 
    # cause of this crash. We patch it to ensure it writes to our safe output stream.
    try:
        from tqdm import tqdm
        from functools import partial
        # We replace the original tqdm class with a partial function that has 
        # the 'file' argument preset to our safe (and null) stdout.
        tqdm = partial(tqdm, file=sys.stdout)
    except ImportError:
        # tqdm might not be installed in all development environments.
        pass
    except Exception as e:
        # If the patch fails, this will attempt to write to the (now safe) stderr.
        print(f"Error applying tqdm patch: {e}", file=sys.stderr)

# --- OLD CACHE LOGIC REMOVED FROM HERE ---

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import queue
import logging
import multiprocessing

# --- Add the bundled ffmpeg to the PATH ---
if getattr(sys, 'frozen', False):
    bundle_dir = sys._MEIPASS
    ffmpeg_path = os.path.join(bundle_dir, 'bin')
    os.environ["PATH"] += os.pathsep + ffmpeg_path

from utils import constants
from utils.logging_setup import setup_logging
from utils.config_manager import ConfigManager
from core.audio_processor import AudioProcessor
from ui.main_window import UI
from ui.correction_window import CorrectionWindow
from ui.launch_screen import LaunchScreen


setup_logging()
logger = logging.getLogger(__name__)

app_instance = None

class MainApp:
    def __init__(self, root_tk_param):
        global app_instance
        app_instance = self
        self.root = root_tk_param

        self.config_manager = ConfigManager(constants.DEFAULT_CONFIG_FILE)
        logger.info(f"ConfigManager initialized with path: {constants.DEFAULT_CONFIG_FILE}")

        self.audio_processor = None
        self.processing_thread = None
        self.audio_file_paths = []
        self.correction_window_instance = None
        self.last_successful_audio_path = None
        self.last_successful_transcription_path = None

        self.error_display_queue = queue.Queue()
        self.ui_update_queue = queue.Queue()
        self.completion_queue = queue.Queue()
        
        self.ui = None
        self.launch_screen_ref = None
        self._completion_poller_id = None

    def _setup_main_ui_elements(self):
        logger.info("MainApp: Setting up main UI elements (without final geometry).")
        self.root.title("Audio Transcription and Diarization")

        style = ttk.Style(self.root)
        available_themes = style.theme_names()
        logger.info(f"Available themes: {available_themes}")
        try:
            if 'clam' in available_themes: style.theme_use('clam'); logger.info("Applied 'clam' theme.")
            elif 'alt' in available_themes: style.theme_use('alt'); logger.info("Applied 'alt' theme.")
            else: logger.info("No preferred built-in themes found, using default.")
        except tk.TclError as e: logger.error(f"Failed to apply a built-in ttk theme: {e}")
        
        try:
            theme_bg_color = style.lookup('TFrame', 'background')
            self.root.configure(background=theme_bg_color)
        except tk.TclError: logger.warning("Could not look up TFrame background for MainApp root.")

        self.root.after(200, self._poll_error_display_queue)
        self.root.after(100, self._check_ui_update_queue)

        initial_main_show_tips = self.config_manager.get_main_window_show_tips()
        logger.info(f"Initial 'Show Tips' state for Main Window: {initial_main_show_tips}")

        self.ui = UI(self.root,
                     start_processing_callback=self.start_processing,
                     select_audio_file_callback=self.select_audio_files,
                     open_correction_window_callback=self.open_correction_window,
                     config_manager_instance=self.config_manager,
                     initial_show_tips_state=initial_main_show_tips
                     )
        self.ui.set_save_token_callback(self.save_huggingface_token)
        self._load_and_display_saved_token()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        logger.info("MainApp: Basic UI framework setup complete (final geometry/state pending).")

    def _load_models_in_background(self):
        logger.info("MainApp: Starting model loading in background thread.")
        success = False
        error_for_finalize = None
        try:
            initial_diarization_enabled = self.config_manager.get_use_auth_token()
            initial_auto_merge_enabled = False

            if hasattr(self, 'ui') and self.ui:
                initial_diarization_enabled = self.ui.enable_diarization_var.get()
                initial_auto_merge_enabled = self.ui.auto_merge_var.get() if initial_diarization_enabled else False

            success = self._ensure_audio_processor_initialized(
                is_initial_setup=True,
                initial_model_key="base", # Use 'base' for faster startup
                initial_diarization_enabled_from_ui=initial_diarization_enabled,
                initial_auto_merge_enabled_from_ui=initial_auto_merge_enabled
            )
            logger.info(f"Model loading thread: _ensure_audio_processor_initialized returned {success}")
            self.completion_queue.put((success, error_for_finalize))
            logger.info(f"Model loading thread: Put success={success} on completion_queue.")
        except Exception as e:
            logger.error(f"Exception in model loading thread: {e}", exc_info=True)
            error_for_finalize = str(e)
            success = False
            self.completion_queue.put((success, error_for_finalize))
            logger.info(f"Model loading thread: Put success={success} (due to exception) on completion_queue.")


    def _finalize_startup_on_main_thread(self, models_loaded_ok, error_msg=None):
        logger.critical(f"--- CRITICAL: ENTERING _finalize_startup_on_main_thread. models_loaded_ok={models_loaded_ok}, error_msg='{error_msg}' ---")

        if self.launch_screen_ref and self.launch_screen_ref.winfo_exists():
            logger.info("Launch screen exists, attempting to close.")
            try:
                self.launch_screen_ref.attributes('-topmost', False)
                self.launch_screen_ref.close()
                logger.info("Launch screen closed.")
            except Exception as e:
                logger.error(f"Error closing launch screen: {e}", exc_info=True)
            self.launch_screen_ref = None
        elif self.launch_screen_ref:
            logger.warning("Launch screen reference exists but winfo_exists() is false.")
        else:
            logger.warning("Launch screen reference is None at finalize time.")

        if models_loaded_ok:
            if self.root and self.root.winfo_exists():
                logger.info("Essential models loaded OK. Preparing to show main window.")
                try:
                    logger.info("Applying final geometry/zoom state...")
                    self.root.state('zoomed')
                except tk.TclError:
                    logger.warning("Failed to set 'zoomed' state, using geometry fallback.")
                    screen_width = self.root.winfo_screenwidth()
                    screen_height = self.root.winfo_screenheight()
                    self.root.geometry(f"{screen_width}x{screen_height}+0+0")
                
                logger.info("Deiconifying main window...")
                self.root.deiconify()
                logger.info("Lifting main window...")
                self.root.lift()
                logger.info("Forcing focus to main window...")
                self.root.focus_force()
                self.root.update_idletasks()
                logger.info("MainApp: Application fully initialized and displayed.")
            else:
                logger.error("Root window does not exist at finalization after successful model load!")
        else:
            logger.error(f"Essential model loading failed. Error: {error_msg}")
            full_error_message = f"Failed to initialize essential application models (transcription): {error_msg or 'Unknown error'}.\nPlease check logs and setup."
            msg_parent = self.root if self.root and self.root.winfo_exists() else None
            if msg_parent:
                messagebox.showerror("Application Startup Error", full_error_message, parent=msg_parent)
            else:
                logger.critical(f"Cannot show messagebox (no parent): {full_error_message}")

            if self.root and self.root.winfo_exists():
                logger.info("Destroying root window due to essential model loading failure.")
                self.root.destroy()
        logger.info(f"--- EXITING _finalize_startup_on_main_thread ---")


    def _check_completion_queue(self):
        try:
            while not self.completion_queue.empty():
                success, err_msg = self.completion_queue.get_nowait()
                logger.info(f"MainThread: Got completion signal from queue. Success: {success}, Error: {err_msg}")
                self._finalize_startup_on_main_thread(success, err_msg)
                if self._completion_poller_id:
                    self.root.after_cancel(self._completion_poller_id)
                    self._completion_poller_id = None
                return
            
            if self.root and self.root.winfo_exists() and self._completion_poller_id:
                 self._completion_poller_id = self.root.after(100, self._check_completion_queue)

        except queue.Empty:
            if self.root and self.root.winfo_exists() and self._completion_poller_id:
                 self._completion_poller_id = self.root.after(100, self._check_completion_queue)
        except Exception as e:
            logger.error(f"Error in _check_completion_queue: {e}", exc_info=True)
            self._finalize_startup_on_main_thread(False, f"Error during startup sequence: {e}")
            if self.root and self.root.winfo_exists() and self._completion_poller_id:
                self.root.after_cancel(self._completion_poller_id)
                self._completion_poller_id = None


    def start_initialization_sequence(self, launch_screen):
        self.launch_screen_ref = launch_screen
        self._setup_main_ui_elements()

        if self.launch_screen_ref and hasattr(self.launch_screen_ref, 'loading_label_text'):
            self.launch_screen_ref.loading_label_text.set("Loading models, please wait...")
            if self.launch_screen_ref.winfo_exists():
                 self.launch_screen_ref.update_idletasks()
        
        if self.root and self.root.winfo_exists():
            self._completion_poller_id = self.root.after(100, self._check_completion_queue)

        model_loader_thread = threading.Thread(
            target=self._load_models_in_background,
            daemon=True
        )
        model_loader_thread.start()

    def _on_closing(self):
        logger.info("Application closing sequence initiated.")
        if self.processing_thread and self.processing_thread.is_alive():
            if messagebox.askyesno("Processing Active",
                                   "Audio processing is currently active. Exiting now may lead to incomplete results or errors. Are you sure you want to exit?",
                                   parent=self.root):
                logger.warning("User chose to exit while processing was active.")
            else:
                logger.info("User cancelled exit due to active processing.")
                return

        if self.correction_window_instance and hasattr(self.correction_window_instance, 'window') and self.correction_window_instance.window.winfo_exists():
            logger.info("Closing correction window as part of main app shutdown.")
            if hasattr(self.correction_window_instance, '_on_close') and callable(self.correction_window_instance._on_close):
                self.correction_window_instance._on_close()
            else:
                try:
                    self.correction_window_instance.window.destroy()
                except Exception as e:
                    logger.error(f"Error destroying correction window directly: {e}")

        logger.info("Destroying main application window.")
        if self.root and self.root.winfo_exists():
            self.root.destroy()

    def open_correction_window(self):
        logger.info("Attempting to open correction window.")
        if self.correction_window_instance and hasattr(self.correction_window_instance, 'window') and self.correction_window_instance.window.winfo_exists():
            self.correction_window_instance.window.lift()
            self.correction_window_instance.window.focus_force()
            logger.info("Correction window already open, lifting to front and focusing.")
        else:
            include_timestamps_main = self.ui.include_timestamps_var.get()
            include_end_times_main = self.ui.include_end_times_var.get() if include_timestamps_main else False

            initial_corr_show_tips = self.config_manager.get_correction_window_show_tips()
            logger.info(f"Initial 'Show Tips' state for Correction Window: {initial_corr_show_tips}")

            self.correction_window_instance = CorrectionWindow(
                self.root,
                config_manager_instance=self.config_manager,
                initial_show_tips_state=initial_corr_show_tips,
                initial_include_timestamps=include_timestamps_main,
                initial_include_end_times=include_end_times_main
            )
            logger.info(f"New correction window created with TS: {include_timestamps_main}, EndTS: {include_end_times_main}, Tips: {initial_corr_show_tips}")

            if self.last_successful_audio_path and self.last_successful_transcription_path:
                logger.info(f"Populating correction window with last successful: Audio='{self.last_successful_audio_path}', Txt='{self.last_successful_transcription_path}'")
                if hasattr(self.correction_window_instance, 'ui'):
                    if hasattr(self.correction_window_instance.ui, 'transcription_file_path_var'):
                        self.correction_window_instance.ui.transcription_file_path_var.set(self.last_successful_transcription_path)
                    if hasattr(self.correction_window_instance.ui, 'audio_file_path_var'):
                        self.correction_window_instance.ui.audio_file_path_var.set(self.last_successful_audio_path)
                    if hasattr(self.correction_window_instance, 'callback_handler') and \
                       hasattr(self.correction_window_instance.callback_handler, 'load_files'):
                        self.root.after(50, self.correction_window_instance.callback_handler.load_files)
            else:
                logger.info("No last successful transcription/audio to auto-load into correction window.")


    def _load_and_display_saved_token(self):
        logger.info("Loading saved Hugging Face token...")
        token = self.config_manager.load_huggingface_token()
        if self.ui:
            self.ui.load_token_ui(token if token else "")
        else:
            logger.warning("_load_and_display_saved_token: UI not ready.")


    def save_huggingface_token(self, token: str):
        token_to_save = token.strip() if token else ""
        logger.info(f"Saving Hugging Face token: {'Present' if token_to_save else 'Empty'}")
        self.config_manager.save_huggingface_token(token_to_save)
        self.config_manager.set_use_auth_token(bool(token_to_save))
        messagebox.showinfo("Token Saved", "Hugging Face token has been saved." if token_to_save else "Hugging Face token has been cleared.", parent=self.root)
        
        if self.audio_processor:
             logger.info("Hugging Face token changed, re-evaluating AudioProcessor state.")
             if self.ui and self.ui.enable_diarization_var.get():
                 try:
                    current_auto_merge = self.ui.auto_merge_var.get() if self.ui else False
                    self._ensure_audio_processor_initialized(
                        force_reinitialize=True,
                        initial_auto_merge_enabled_from_ui=current_auto_merge
                    )
                    if self.audio_processor and self.audio_processor.output_enable_diarization and \
                        self.audio_processor.diarization_handler and \
                        self.audio_processor.diarization_handler.is_model_loaded():
                        self.ui_update_queue.put({
                            "type": constants.MSG_TYPE_STATUS,
                            "text": "Diarization model ready with new token."
                        })
                    elif self.audio_processor and self.audio_processor.enable_diarization:
                         self.ui_update_queue.put({
                            "type": constants.MSG_TYPE_STATUS,
                            "text": "Warning: Diarization model failed with new token. Check token."
                        })
                 except Exception as e:
                     logger.error(f"Error re-initializing AudioProcessor after token save: {e}")
                     self.ui_update_queue.put({
                        "type": constants.MSG_TYPE_STATUS,
                        "text": f"Error applying token: {str(e)[:50]}..."
                    })


    def select_audio_files(self):
        logger.info("Opening file dialog to select audio file(s)...")
        selected_paths = filedialog.askopenfilenames(
            defaultextension=".wav",
            filetypes=[("Audio Files", "*.wav *.mp3 *.aac *.flac *.m4a"), ("All files", "*.*")],
            parent=self.root
        )
        if selected_paths:
            self.audio_file_paths = list(selected_paths)
            if self.ui:
                self.ui.update_audio_file_entry_display(self.audio_file_paths)
            logger.info(f"{len(self.audio_file_paths)} audio file(s) selected.")
            self.last_successful_transcription_path = None
            self.last_successful_audio_path = None
        else:
            logger.info("No audio file selected or selection cancelled.")


    def _make_progress_callback(self):
        def callback(message: str, percentage: int = None):
            try:
                if message:
                    status_payload = {"type": constants.MSG_TYPE_STATUS, "text": message}
                    if hasattr(self, 'ui_update_queue') and self.ui_update_queue is not None:
                        self.ui_update_queue.put(status_payload)
                    else:
                        print(f"Debug: ui_update_queue not available for status: {message}")
                if percentage is not None:
                    progress_payload = {"type": constants.MSG_TYPE_PROGRESS, "value": percentage}
                    if hasattr(self, 'ui_update_queue') and self.ui_update_queue is not None:
                        self.ui_update_queue.put(progress_payload)
                    else:
                        print(f"Debug: ui_update_queue not available for progress: {percentage}")
            except Exception as e:
                print(f"Error in threaded progress_callback: {e}")
                logger.error(f"Error in threaded progress_callback: {e}", exc_info=True)
        return callback

    def _map_ui_model_key_to_whisper_name(self, ui_model_key: str) -> str:
        mapping = {
            "tiny": "tiny", "base": "base", "small": "small", "medium": "medium",
            "large (recommended)": "large", "turbo": "small"
        }
        return mapping.get(ui_model_key, "large")


    def _ensure_audio_processor_initialized(self, force_reinitialize=False, is_initial_setup=False,
                                           initial_model_key=None,
                                           initial_diarization_enabled_from_ui=None,
                                           initial_auto_merge_enabled_from_ui=None):
        
        # --- NEW CACHE LOGIC ---
        # Create a visible cache directory in the user's home folder. This is the recommended location.
        cache_dir_path = os.path.join(os.path.expanduser('~'), 'TranscriptionOli_Cache')
        
        current_enable_diarization = initial_diarization_enabled_from_ui \
            if is_initial_setup and initial_diarization_enabled_from_ui is not None \
            else (self.ui.enable_diarization_var.get() if hasattr(self, 'ui') and self.ui else False)

        current_auto_merge_enabled = initial_auto_merge_enabled_from_ui \
            if is_initial_setup and initial_auto_merge_enabled_from_ui is not None \
            else (self.ui.auto_merge_var.get() if hasattr(self, 'ui') and self.ui else False)
        
        if not current_enable_diarization: 
            current_auto_merge_enabled = False

        ui_model_key_to_use = initial_model_key
        if hasattr(self, 'ui') and self.ui and self.ui.model_var.get():
             if not initial_model_key or not is_initial_setup : 
                ui_model_key_to_use = self.ui.model_var.get()
        
        if not ui_model_key_to_use: 
            logger.warning("Model key not determined, defaulting to 'base'.")
            ui_model_key_to_use = "base"

        actual_whisper_model_name = self._map_ui_model_key_to_whisper_name(ui_model_key_to_use)
        
        current_include_timestamps = self.ui.include_timestamps_var.get() if hasattr(self, 'ui') and self.ui else True
        current_include_end_times = self.ui.include_end_times_var.get() if hasattr(self, 'ui') and self.ui and current_include_timestamps else False

        needs_reinit = force_reinitialize
        if not self.audio_processor:
            needs_reinit = True
        elif not needs_reinit: 
            options_changed = (
                self.audio_processor.transcription_handler.model_name != actual_whisper_model_name or
                self.audio_processor.output_enable_diarization != current_enable_diarization or
                self.audio_processor.output_include_timestamps != current_include_timestamps or
                self.audio_processor.output_include_end_times != current_include_end_times or
                self.audio_processor.output_enable_auto_merge != current_auto_merge_enabled
            )
            if options_changed:
                needs_reinit = True
            elif not self.audio_processor.are_models_loaded(): 
                needs_reinit = True

        if needs_reinit:
            logger.info(f"Initializing/Re-initializing AudioProcessor. Model: '{actual_whisper_model_name}'. "
                        f"Diarization Requested: {current_enable_diarization}. "
                        f"Auto Merge: {current_auto_merge_enabled}. "
                        f"Timestamps: {current_include_timestamps}, EndTimes: {current_include_end_times}. "
                        f"Initial Setup: {is_initial_setup}, ForceReinit: {force_reinitialize}")
            current_progress_callback = self._make_progress_callback()
            try:
                use_auth = self.config_manager.get_use_auth_token()
                hf_token = self.config_manager.load_huggingface_token() if use_auth else None
                processor_config = {
                    'huggingface': {'use_auth_token': 'yes' if use_auth else 'no', 'hf_token': hf_token},
                    'transcription': {'model_name': actual_whisper_model_name}
                }
                # --- PASS THE CACHE DIRECTORY ---
                self.audio_processor = AudioProcessor(
                    config=processor_config, progress_callback=current_progress_callback,
                    enable_diarization=current_enable_diarization,
                    include_timestamps=current_include_timestamps,
                    include_end_times=current_include_end_times,
                    enable_auto_merge=current_auto_merge_enabled,
                    cache_dir=cache_dir_path  # Pass the new cache path here
                )
                if not self.audio_processor.are_models_loaded(): 
                    err_msg = "AudioProcessor critical models (transcription) failed to load. Check logs."
                    logger.error(err_msg)
                    raise RuntimeError(err_msg)

                if self.audio_processor.output_enable_diarization:
                    if not self.audio_processor.diarization_handler or \
                       not self.audio_processor.diarization_handler.is_model_loaded():
                        warning_msg = "Diarization was enabled, but the diarization model could not be loaded. Diarization features will be disabled for this run."
                        logger.warning(f"Non-fatal issue during init: {warning_msg}")
                        if hasattr(self, 'ui_update_queue') and self.ui_update_queue and not is_initial_setup:
                            self.ui_update_queue.put({
                                "type": constants.MSG_TYPE_STATUS,
                                "text": "Warning: Diarization unavailable. Check token & HF conditions."
                            })
                    elif not is_initial_setup: 
                        self.ui_update_queue.put({
                            "type": constants.MSG_TYPE_STATUS,
                            "text": "Diarization model loaded successfully."
                        })
                logger.info("AudioProcessor initialized/re-initialized successfully.")
                return True
            except Exception as e:
                err_msg = f"Failed to initialize/re-initialize audio processing components: {e}"
                logger.exception(err_msg)
                if not is_initial_setup and hasattr(self, 'ui_update_queue') and self.ui_update_queue:
                    self.ui_update_queue.put({"type": constants.MSG_TYPE_STATUS, "text": err_msg})
                raise 
        
        if self.audio_processor:
             logger.debug("Audio processor already initialized, essential models loaded, and options unchanged.")
             if current_enable_diarization and \
                (not self.audio_processor.diarization_handler or \
                 not self.audio_processor.output_enable_diarization or
                 not self.audio_processor.diarization_handler.is_model_loaded()):
                logger.warning("AudioProcessor: Diarization is enabled by user, but model not loaded. Processing will proceed without it.")
                if hasattr(self, 'ui_update_queue') and self.ui_update_queue and not is_initial_setup:
                    self.ui_update_queue.put({
                        "type": constants.MSG_TYPE_STATUS,
                        "text": "Warning: Diarization enabled but model not loaded. Check token."
                    })
             return True
        
        return False


    def start_processing(self):
        logger.info("'Start Processing' button clicked.")
        if not self.audio_file_paths:
            messagebox.showerror("Error", "Please select one or more valid audio files first.", parent=self.root); return
        if self.processing_thread and self.processing_thread.is_alive():
            messagebox.showwarning("Busy", "Processing is already in progress.", parent=self.root); return
        try:
            if not self._ensure_audio_processor_initialized(force_reinitialize=True):
                logger.error("Start processing: Audio processor not ready or failed to re-initialize. Aborting."); return
        except Exception as e:
             logger.error(f"Failed to ensure audio processor initialized for processing: {e}")
             messagebox.showerror("Error", f"Could not initialize audio processor: {e}", parent=self.root)
             return

        self.ui.disable_ui_for_processing()
        
        if len(self.audio_file_paths) == 1:
            self.ui.update_status_and_progress("Processing started...", 0)
            self.ui.update_output_text("Processing started...")
            self.processing_thread = threading.Thread(target=self._processing_thread_worker_single, args=(self.audio_file_paths[0],), daemon=True)
            logger.info(f"Starting single file processing thread for: {self.audio_file_paths[0]} with model {self.audio_processor.transcription_handler.model_name}")
        else:
            self.ui.update_status_and_progress(f"Batch processing started for {len(self.audio_file_paths)} files...", 0)
            self.ui.update_output_text(f"Batch processing started for {len(self.audio_file_paths)} files...")
            self.processing_thread = threading.Thread(target=self._processing_thread_worker_batch, args=(list(self.audio_file_paths),), daemon=True)
            logger.info(f"Starting batch processing thread for {len(self.audio_file_paths)} files with model {self.audio_processor.transcription_handler.model_name}")
        
        self.processing_thread.start()

    def _processing_thread_worker_single(self, audio_file_to_process):
        logger.info(f"Thread worker (single): Starting audio processing for: {audio_file_to_process}")
        status, msg, is_empty, segments_data = constants.STATUS_ERROR, "Unknown error during single file processing.", False, None
        is_plain_text_output_from_processor = False
        try:
            if not self.audio_processor or not self.audio_processor.transcription_handler.is_model_loaded():
                msg = "Critical error: Audio processor or transcription model became unavailable before processing."
                logger.error(msg)
            else:
                result_obj = self.audio_processor.process_audio(audio_file_to_process)
                status = result_obj.status
                msg = result_obj.message
                is_empty = result_obj.status == constants.STATUS_EMPTY
                segments_data = result_obj.data
                is_plain_text_output_from_processor = result_obj.is_plain_text_output

                if result_obj.status == constants.STATUS_SUCCESS and not segments_data and not is_plain_text_output_from_processor:
                    status, is_empty, msg = constants.STATUS_EMPTY, True, result_obj.message or "Successful but no segments generated."
                elif result_obj.status == constants.STATUS_SUCCESS and is_plain_text_output_from_processor and not segments_data:
                     pass


        except Exception as e:
            logger.exception("Thread worker (single): Unhandled error during processing.")
            msg = f"Unexpected error processing {os.path.basename(audio_file_to_process)}: {e}"
        finally:
            logger.info(f"Thread worker (single): Finalizing for {os.path.basename(audio_file_to_process)} with status '{status}'. Plain text output: {is_plain_text_output_from_processor}")
            if self.root and self.root.winfo_exists():
                self.ui_update_queue.put({
                    "type": constants.MSG_TYPE_COMPLETED,
                    constants.KEY_FINAL_STATUS: status,
                    constants.KEY_ERROR_MESSAGE: msg,
                    constants.KEY_IS_EMPTY_RESULT: is_empty,
                    "processed_data": segments_data,
                    "is_plain_text_output": is_plain_text_output_from_processor,
                    "original_audio_path": audio_file_to_process
                })

    def _processing_thread_worker_batch(self, files_to_process_list):
        logger.info(f"Thread worker (batch): Starting processing for {len(files_to_process_list)} files.")
        all_results_for_batch = []
        total_files = len(files_to_process_list)

        for i, file_path in enumerate(files_to_process_list):
            base_filename = os.path.basename(file_path)
            logger.info(f"Batch: Processing file {i+1}/{total_files}: {base_filename}")
            if self.root and self.root.winfo_exists():
                self.ui_update_queue.put({
                    "type": constants.MSG_TYPE_BATCH_FILE_START,
                    constants.KEY_BATCH_FILENAME: base_filename,
                    constants.KEY_BATCH_CURRENT_IDX: i + 1,
                    constants.KEY_BATCH_TOTAL_FILES: total_files
                })

            file_status, file_msg, file_is_empty = constants.STATUS_ERROR, f"Unknown error for {base_filename}", False
            file_data = None
            file_is_plain_text_output = False
            try:
                if not self.audio_processor or not self.audio_processor.transcription_handler.is_model_loaded():
                    file_msg = f"Audio processor or transcription model unavailable for {base_filename}."
                    logger.error(file_msg)
                else:
                    result_obj = self.audio_processor.process_audio(file_path)
                    file_status = result_obj.status
                    file_msg = result_obj.message
                    file_is_empty = result_obj.status == constants.STATUS_EMPTY
                    file_data = result_obj.data
                    file_is_plain_text_output = result_obj.is_plain_text_output
                    
                    if result_obj.status == constants.STATUS_SUCCESS and not file_data and not file_is_plain_text_output:
                         file_status, file_is_empty, file_msg = constants.STATUS_EMPTY, True, result_obj.message or "Successful but no segments."
            
            except Exception as e:
                logger.exception(f"Batch: Unhandled error processing {base_filename}")
                file_msg = f"Critical error during processing of {base_filename}: {e}"
            
            all_results_for_batch.append({
                "original_path": file_path,
                "status": file_status,
                "message": file_msg,
                "is_empty": file_is_empty,
                "data": file_data,
                "is_plain_text_output": file_is_plain_text_output
            })

        logger.info("Batch processing of all files complete.")
        if self.root and self.root.winfo_exists():
            self.ui_update_queue.put({
                "type": constants.MSG_TYPE_BATCH_COMPLETED,
                constants.KEY_BATCH_ALL_RESULTS: all_results_for_batch
            })


    def _prompt_for_save_location_and_save_single(self, data_to_save: any, is_plain_text: bool, original_audio_path: str):
        default_fn = "transcription.txt"
        try:
            name, _ = os.path.splitext(os.path.basename(original_audio_path))
            model_name_suffix = self.audio_processor.transcription_handler.model_name if self.audio_processor else "model"
            default_fn = f"{name}_{model_name_suffix}_transcription.txt"
        except Exception: pass

        chosen_path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text Files", "*.txt")],
            title="Save Transcription As", initialfile=default_fn, parent=self.root
        )
        if chosen_path:
            try:
                self.audio_processor.save_to_txt(chosen_path, data_to_save, is_plain_text=is_plain_text)
                self.last_successful_transcription_path = chosen_path
                self.last_successful_audio_path = original_audio_path
                self.ui.update_status_and_progress("Transcription saved!", 100)
                self.ui.display_processed_output(chosen_path, False)
                messagebox.showinfo("Success", f"Transcription saved to {chosen_path}", parent=self.root)
                if self.root and self.root.winfo_exists(): self.root.focus_force()
            except Exception as e:
                err_msg = f"Could not save file: {e}"
                logger.exception(err_msg)
                self.ui.update_status_and_progress("Save failed.", 100)
                display_content = data_to_save if is_plain_text else "\n".join(data_to_save or [])
                self.ui.update_output_text(f"SAVE FAILED: {err_msg}\n\n{display_content}")
                messagebox.showerror("Save Error", err_msg, parent=self.root)
                if self.root and self.root.winfo_exists(): self.root.focus_force()
        else:
            self.last_successful_transcription_path = None
            self.last_successful_audio_path = None
            self.ui.update_status_and_progress("Save cancelled by user.", 100)
            display_content = data_to_save if is_plain_text else "\n".join(data_to_save or [])
            self.ui.update_output_text(f"File not saved. Transcription content:\n\n{display_content}")
            messagebox.showwarning("Save Cancelled", "File not saved. Content shown in output area.", parent=self.root)
            if self.root and self.root.winfo_exists(): self.root.focus_force()


    def _prompt_for_batch_save_directory_and_save(self, all_processed_results: list):
        if not all_processed_results:
            messagebox.showinfo("Batch Process Complete", "No results to save from the batch.", parent=self.root)
            self.ui.update_status_and_progress("Batch complete. Nothing to save.", 100)
            self.ui.update_output_text("Batch processing finished. No results were generated or all failed.")
            return

        output_dir = filedialog.askdirectory(
            title="Select Directory to Save Batch Transcriptions",
            parent=self.root
        )

        if not output_dir:
            messagebox.showwarning("Batch Save Cancelled", "No directory selected. Batch transcriptions not saved.", parent=self.root) 
            self.ui.update_status_and_progress("Batch complete. Save cancelled.", 100) 
            summary_lines = ["Batch save cancelled. Transcriptions not saved to disk.\n"] 
            for item in all_processed_results[:3]: 
                 summary_lines.append(f"{os.path.basename(item['original_path'])}: {item['status']} - {item['message'][:50]}...") 
            if len(all_processed_results) > 3: summary_lines.append("...") 
            self.ui.display_processed_output(is_batch_summary=True, batch_summary_message="\n".join(summary_lines)) 
            return


        final_output_dir = output_dir
        successful_saves = 0
        failed_saves = 0
        batch_summary_log = [f"Batch Processing Summary (Saved to: {final_output_dir}):"]

        for item in all_processed_results:
            original_file_path = item['original_path']
            base_filename = os.path.basename(original_file_path)
            item_data = item.get("data")
            item_is_plain_text = item.get("is_plain_text_output", False)

            if item['status'] == constants.STATUS_SUCCESS and item_data:
                transcript_filename_base, _ = os.path.splitext(base_filename)
                model_name_suffix = self.audio_processor.transcription_handler.model_name.replace('.', '') if self.audio_processor else "model"
                output_filename = f"{transcript_filename_base}_{model_name_suffix}_transcript.txt"
                
                full_output_path = os.path.join(final_output_dir, output_filename)
                try:
                    self.audio_processor.save_to_txt(full_output_path, item_data, is_plain_text=item_is_plain_text)
                    logger.info(f"Batch save: Successfully saved {full_output_path}")
                    batch_summary_log.append(f"  SUCCESS: {base_filename} -> {output_filename}")
                    successful_saves += 1
                    self.last_successful_audio_path = original_file_path
                    self.last_successful_transcription_path = full_output_path
                except Exception as e:
                    logger.exception(f"Batch save: Failed to save {full_output_path}")
                    batch_summary_log.append(f"  FAIL_SAVE: {base_filename} (Error: {e})")
                    failed_saves += 1
            else:
                logger.warning(f"Batch save: Skipped saving for {base_filename} due to status: {item['status']} - {item['message']}")
                batch_summary_log.append(f"  SKIPPED ({item['status']}): {base_filename} - {item['message']}")
                failed_saves +=1

        summary_message = f"Batch processing complete.\nSuccessfully saved: {successful_saves} file(s).\nFailed/Skipped: {failed_saves} file(s).\n\nLocation: {final_output_dir}"
        messagebox.showinfo("Batch Save Complete", summary_message, parent=self.root)
        self.ui.update_status_and_progress("Batch save complete.", 100)
        self.ui.display_processed_output(is_batch_summary=True, batch_summary_message=summary_message + "\n\n" + "\n".join(batch_summary_log))


    def _check_ui_update_queue(self):
        if not (self.root and self.root.winfo_exists()):
            logger.info("_check_ui_update_queue: Root window no longer exists, stopping polling.")
            return

        try:
            while not self.ui_update_queue.empty():
                payload = self.ui_update_queue.get_nowait()
                
                if not (hasattr(self, 'ui') and self.ui and self.ui.root.winfo_exists()):
                    logger.warning("UI update queue: UI object or its root no longer exists. Skipping update for payload: %s", payload)
                    self.ui_update_queue.task_done()
                    continue

                msg_type = payload.get("type")

                if msg_type == constants.MSG_TYPE_STATUS:
                    self.ui.update_status_and_progress(status_text=payload.get("text"))
                elif msg_type == constants.MSG_TYPE_PROGRESS:
                    self.ui.update_status_and_progress(progress_value=payload.get("value"))
                elif msg_type == constants.MSG_TYPE_COMPLETED:
                    status = payload.get(constants.KEY_FINAL_STATUS)
                    err_msg = payload.get(constants.KEY_ERROR_MESSAGE)
                    is_empty = payload.get(constants.KEY_IS_EMPTY_RESULT)
                    processed_data = payload.get("processed_data")
                    is_plain_text = payload.get("is_plain_text_output", False)
                    original_audio_path = payload.get("original_audio_path")

                    if status == constants.STATUS_SUCCESS and processed_data:
                        self._prompt_for_save_location_and_save_single(processed_data, is_plain_text, original_audio_path)
                    elif status == constants.STATUS_EMPTY:
                        self.ui.update_status_and_progress(err_msg or "No speech detected.", 100)
                        self.ui.display_processed_output(processing_returned_empty=True)
                    elif status == constants.STATUS_ERROR:
                        self.ui.update_status_and_progress(f"Error: {err_msg[:100]}...", 0)
                        self.ui.update_output_text(f"Error processing {os.path.basename(original_audio_path)}:\n{err_msg}")
                        self.error_display_queue.put(f"Error processing {os.path.basename(original_audio_path)}:\n{err_msg}")
                    self.ui.enable_ui_after_processing()

                elif msg_type == constants.MSG_TYPE_BATCH_FILE_START:
                    filename = payload.get(constants.KEY_BATCH_FILENAME)
                    current_idx = payload.get(constants.KEY_BATCH_CURRENT_IDX)
                    total_files = payload.get(constants.KEY_BATCH_TOTAL_FILES)
                    progress_percent = int((current_idx -1) / total_files * 100) if total_files > 0 else 0
                    self.ui.update_status_and_progress(f"Batch: Processing {current_idx}/{total_files}: {filename}", progress_percent)
                    self.ui.update_output_text(f"Batch: Now processing file {current_idx} of {total_files}: {filename}...")

                elif msg_type == constants.MSG_TYPE_BATCH_COMPLETED:
                    all_results = payload.get(constants.KEY_BATCH_ALL_RESULTS)
                    self.ui.update_status_and_progress("Batch processing finished. Awaiting save location...", 100)
                    self._prompt_for_batch_save_directory_and_save(all_results)
                    self.ui.enable_ui_after_processing()

                self.ui_update_queue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            logger.exception("Error in _check_ui_update_queue processing a payload.")
            self.error_display_queue.put(f"Critical UI update error: {e}")
            if hasattr(self, 'ui') and self.ui and hasattr(self.ui, 'root') and self.ui.root.winfo_exists():
                try:
                    self.ui.enable_ui_after_processing()
                except Exception as e_enable:
                    logger.error(f"Error trying to re-enable UI after queue error: {e_enable}")
        finally:
            if self.root and self.root.winfo_exists():
                self.root.after(100, self._check_ui_update_queue)
            else:
                logger.info("_check_ui_update_queue: Root window destroyed, polling stopped.")

    def _poll_error_display_queue(self):
        try:
            while not self.error_display_queue.empty():
                error_message = self.error_display_queue.get_nowait()
                parent_window = self.root if self.root and self.root.winfo_exists() else None
                messagebox.showerror("Application Error/Warning", error_message, parent=parent_window)
                self.error_display_queue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            logger.exception("Error in _poll_error_display_queue.")
        finally:
            if self.root and self.root.winfo_exists():
                self.root.after(200, self._poll_error_display_queue)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main_app_root = tk.Tk()

    main_app_root.geometry("1x1-10000-10000")
    main_app_root.title("Transcription Oli Loader")

    style_for_root = ttk.Style(main_app_root)
    try:
        if 'clam' in style_for_root.theme_names(): style_for_root.theme_use('clam')
        elif 'alt' in style_for_root.theme_names(): style_for_root.theme_use('alt')
        theme_bg = style_for_root.lookup('TFrame', 'background')
        main_app_root.configure(background=theme_bg)
    except tk.TclError as e:
        logger.warning(f"Could not apply early theme/bg for root: {e}")
    
    main_app_root.withdraw()
    main_app_root.update_idletasks()

    launch_screen = LaunchScreen(main_app_root)

    main_app_root.update_idletasks()

    app = MainApp(main_app_root)
    main_app_root.after(150, lambda: app.start_initialization_sequence(launch_screen))

    main_app_root.mainloop()




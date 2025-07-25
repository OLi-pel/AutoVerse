# utils/config_manager.py
import configparser
import os

# The module-level CONFIG_FILE is only used by the older save_token/load_token functions.
# If those functions are no longer used, this can be removed.
# For consistency, they should also use the path derived from constants.DEFAULT_CONFIG_FILE.
# However, the ConfigManager class is the primary focus.

TOKEN_SECTION = 'HuggingFace'
USE_AUTH_TOKEN_OPTION = 'use_auth_token'
TOKEN_OPTION = 'hf_token'

# New section and keys for UI preferences, including tips
UI_PREFERENCES_SECTION = 'UIPreferences'
MAIN_WINDOW_SHOW_TIPS_OPTION = 'main_window_show_tips'
CORRECTION_WINDOW_SHOW_TIPS_OPTION = 'correction_window_show_tips'
# --- [NEW CODE] ---
STARTUP_SHOW_WELCOME_WIZARD_OPTION = 'show_welcome_wizard'
# --- [END NEW CODE] ---


class ConfigManager:
    def __init__(self, config_path): # config_path comes from constants.DEFAULT_CONFIG_FILE
        self.config = configparser.ConfigParser()
        self.path = config_path

        config_dir = os.path.dirname(self.path)
        if config_dir and not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except OSError as e:
                print(f"ConfigManager: CRITICAL - Could not create config directory '{config_dir}'. Config will not load/save. Error: {e}")

        if os.path.exists(self.path):
            try:
                self.config.read(self.path)
            except configparser.Error as e:
                print(f"ConfigManager: Error reading config file {self.path}: {e}. Using default config in memory.")
                self._create_default_config_in_memory()
        else:
            self._create_default_config_and_write()

    def _ensure_section_exists(self, section_name):
        if section_name not in self.config:
            self.config[section_name] = {}

    def _create_default_config_in_memory(self):
        """Creates a default configuration in memory (e.g., if file read fails)."""
        self._ensure_section_exists(TOKEN_SECTION)
        self.config[TOKEN_SECTION][USE_AUTH_TOKEN_OPTION] = 'no'
        self.config[TOKEN_SECTION][TOKEN_OPTION] = ''

        self._ensure_section_exists(UI_PREFERENCES_SECTION)
        self.config[UI_PREFERENCES_SECTION][MAIN_WINDOW_SHOW_TIPS_OPTION] = 'yes' # Tips enabled by default
        self.config[UI_PREFERENCES_SECTION][CORRECTION_WINDOW_SHOW_TIPS_OPTION] = 'yes' # Tips enabled by default
        # --- [NEW CODE] ---
        self.config[UI_PREFERENCES_SECTION][STARTUP_SHOW_WELCOME_WIZARD_OPTION] = 'yes' # Default to showing the wizard
        # --- [END NEW CODE] ---

    def _create_default_config_and_write(self):
        """Creates a default configuration and writes it to the specified path."""
        self._create_default_config_in_memory() # Populate defaults first
        try:
            config_dir = os.path.dirname(self.path)
            if config_dir and not os.path.exists(config_dir):
                 os.makedirs(config_dir, exist_ok=True)

            with open(self.path, 'w') as configfile:
                self.config.write(configfile)
        except IOError as e:
            print(f"ConfigManager: Error creating default config file {self.path}: {e}")

    def get(self, section, key, default=None):
        # Ensure section exists before trying to get a key from it to avoid NoSectionError with fallback
        if section not in self.config:
            # If the section doesn't exist, and a default is provided for the key,
            # it implies we should just return that default.
            # Otherwise, if ConfigParser's default fallback handling is desired for other reasons,
            # this check might need adjustment. But for simple key-value with defaults, this is safer.
            return default
        return self.config.get(section, key, fallback=default)

    def set(self, section, key, value):
        self._ensure_section_exists(section)
        self.config[section][key] = str(value)
        try:
            config_dir = os.path.dirname(self.path)
            if config_dir and not os.path.exists(config_dir):
                 os.makedirs(config_dir, exist_ok=True)

            with open(self.path, 'w') as configfile:
                self.config.write(configfile)
        except IOError as e:
            print(f"ConfigManager: Error writing to config file {self.path}: {e}")

    def save_huggingface_token(self, token):
        self.set(TOKEN_SECTION, TOKEN_OPTION, token if token else "")

    def load_huggingface_token(self):
        return self.get(TOKEN_SECTION, TOKEN_OPTION, '') # Default to empty string

    def set_use_auth_token(self, use_auth: bool):
        self.set(TOKEN_SECTION, USE_AUTH_TOKEN_OPTION, 'yes' if use_auth else 'no')

    def get_use_auth_token(self) -> bool:
        return self.get(TOKEN_SECTION, USE_AUTH_TOKEN_OPTION, 'no').lower() == 'yes'

    # --- Methods for Tips Preference ---
    def set_main_window_show_tips(self, show_tips: bool):
        self.set(UI_PREFERENCES_SECTION, MAIN_WINDOW_SHOW_TIPS_OPTION, 'yes' if show_tips else 'no')

    def get_main_window_show_tips(self) -> bool:
        return self.get(UI_PREFERENCES_SECTION, MAIN_WINDOW_SHOW_TIPS_OPTION, 'yes').lower() == 'yes'

    def set_correction_window_show_tips(self, show_tips: bool):
        self.set(UI_PREFERENCES_SECTION, CORRECTION_WINDOW_SHOW_TIPS_OPTION, 'yes' if show_tips else 'no')

    def get_correction_window_show_tips(self) -> bool:
        return self.get(UI_PREFERENCES_SECTION, CORRECTION_WINDOW_SHOW_TIPS_OPTION, 'yes').lower() == 'yes'

    # --- [NEW CODE] ---
    def set_show_welcome_wizard(self, show_wizard: bool):
        """Saves the user's preference for showing the welcome wizard."""
        self.set(UI_PREFERENCES_SECTION, STARTUP_SHOW_WELCOME_WIZARD_OPTION, 'yes' if show_wizard else 'no')

    def get_show_welcome_wizard(self) -> bool:
        """Checks if the welcome wizard should be shown. Defaults to True."""
        return self.get(UI_PREFERENCES_SECTION, STARTUP_SHOW_WELCOME_WIZARD_OPTION, 'yes').lower() == 'yes'
    # --- [END NEW CODE] ---
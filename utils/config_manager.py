# utils/config_manager.py
import configparser
import os

TOKEN_SECTION = 'HuggingFace'
UI_PREFERENCES_SECTION = 'UIPreferences'
PERFORMANCE_FACTORS_SECTION = 'PerformanceFactors'

# --- (Other constants are unchanged) ---
USE_AUTH_TOKEN_OPTION = 'use_auth_token'; TOKEN_OPTION = 'hf_token'
MAIN_WINDOW_SHOW_TIPS_OPTION = 'main_window_show_tips'; CORRECTION_WINDOW_SHOW_TIPS_OPTION = 'correction_window_show_tips'; STARTUP_SHOW_WELCOME_WIZARD_OPTION = 'show_welcome_wizard'

# --- PHASE 3+: Add new one-time notice flag ---
HAS_SHOWN_PERFORMANCE_NOTICE_OPTION = 'has_shown_performance_notice'

class ConfigManager:
    # --- (__init__ and other methods are unchanged) ---
    def __init__(self, config_path): #...
        self.config = configparser.ConfigParser(); self.path = config_path
        config_dir = os.path.dirname(self.path)
        if config_dir and not os.path.exists(config_dir):
            try: os.makedirs(config_dir, exist_ok=True)
            except OSError: pass
        if os.path.exists(self.path):
            try: self.config.read(self.path)
            except configparser.Error: self._create_default_config_in_memory()
        else: self._create_default_config_and_write()

    def _ensure_section_exists(self, section_name): #...
        if section_name not in self.config: self.config[section_name] = {}

    def _create_default_config_in_memory(self): #...
        self._ensure_section_exists(TOKEN_SECTION); self.config[TOKEN_SECTION].update({USE_AUTH_TOKEN_OPTION: 'no', TOKEN_OPTION: ''})
        self._ensure_section_exists(UI_PREFERENCES_SECTION); self.config[UI_PREFERENCES_SECTION].update({
            MAIN_WINDOW_SHOW_TIPS_OPTION: 'yes', 
            CORRECTION_WINDOW_SHOW_TIPS_OPTION: 'yes', 
            STARTUP_SHOW_WELCOME_WIZARD_OPTION: 'yes',
            HAS_SHOWN_PERFORMANCE_NOTICE_OPTION: 'no' # Defaults to 'no'
        })
        self._ensure_section_exists(PERFORMANCE_FACTORS_SECTION)

    def _create_default_config_and_write(self): #...
        self._create_default_config_in_memory()
        try:
            with open(self.path, 'w') as configfile: self.config.write(configfile)
        except IOError: pass
        
    def get(self, section, key, default=None): #...
        return self.config.get(section, key, fallback=default)

    def set(self, section, key, value): #...
        self._ensure_section_exists(section); self.config[section][key] = str(value)
        try:
            with open(self.path, 'w') as configfile: self.config.write(configfile)
        except IOError: pass

    # --- (Other methods remain unchanged) ---
    def save_huggingface_token(self, token): self.set(TOKEN_SECTION, TOKEN_OPTION, token if token else "")
    def load_huggingface_token(self): return self.get(TOKEN_SECTION, TOKEN_OPTION, '')
    def set_use_auth_token(self, use_auth: bool): self.set(TOKEN_SECTION, USE_AUTH_TOKEN_OPTION, 'yes' if use_auth else 'no')
    def get_main_window_show_tips(self) -> bool: return self.get(UI_PREFERENCES_SECTION, MAIN_WINDOW_SHOW_TIPS_OPTION, 'yes').lower() == 'yes'
    def set_show_welcome_wizard(self, show_wizard: bool): self.set(UI_PREFERENCES_SECTION, STARTUP_SHOW_WELCOME_WIZARD_OPTION, 'yes' if show_wizard else 'no')
    def get_show_welcome_wizard(self) -> bool: return self.get(UI_PREFERENCES_SECTION, STARTUP_SHOW_WELCOME_WIZARD_OPTION, 'yes').lower() == 'yes'

    def get_performance_factor(self, model_key: str) -> float: #...
        try: return self.config.getfloat(PERFORMANCE_FACTORS_SECTION, model_key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError): return 1.25

    def save_performance_factor(self, model_key: str, factor: float): #...
        old_factor = self.get_performance_factor(model_key)
        new_avg_factor = (old_factor * 0.2) + (factor * 0.8)
        clamped_factor = max(0.5, min(new_avg_factor, 5.0))
        self.set(PERFORMANCE_FACTORS_SECTION, model_key, f"{clamped_factor:.4f}")

    # --- NEW METHODS for the one-time performance notice ---
    def get_has_shown_performance_notice(self) -> bool:
        return self.get(UI_PREFERENCES_SECTION, HAS_SHOWN_PERFORMANCE_NOTICE_OPTION, 'no').lower() == 'yes'
        
    def set_has_shown_performance_notice(self, has_shown: bool):
        self.set(UI_PREFERENCES_SECTION, HAS_SHOWN_PERFORMANCE_NOTICE_OPTION, 'yes' if has_shown else 'no')
import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "lastools_path": "",
    "classify_lidar_bat_path": "",
    "downloader_dest_path": "",
    "theme_name": "solar",
    "pdal_path": "",
    "pdal_wrench_path": "",
    "rtklib_path": ""
}

def load_settings():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                user_config = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(user_config)
                return config
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()

def save_settings(config_data):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)
    except IOError as e:
        print(f"Warning: Could not save configuration to {CONFIG_FILE}: {e}")
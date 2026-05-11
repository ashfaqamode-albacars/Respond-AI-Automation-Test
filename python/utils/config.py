import yaml
import os

_config = None

def load_config():
    global _config
    if _config is not None:
        return _config
    config_path = os.path.join(os.path.dirname(__file__), "../config/config.yaml")
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"config.yaml not found at {config_path}. "
            "Copy config.example.yaml to config.yaml and fill in your credentials."
        )
    with open(config_path, "r") as f:
        _config = yaml.safe_load(f)
    return _config

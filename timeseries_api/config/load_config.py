# load_config.py
import os
import yaml
from dotenv import load_dotenv
import re

load_dotenv()

def load_simulation_config():
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "simulation_config.yaml")
    
    with open(path, "r") as f:
        config = yaml.safe_load(f)

    expanded_config = _expand_env_vars(config) 
    return expanded_config

def _expand_env_vars(config):
    if isinstance(config, dict):
        return {k: _expand_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_expand_env_vars(i) for i in config]
    elif isinstance(config, str):
        match = re.match(r"\$\{([^:}]+)(?::([^}]+))?\}", config)
        if match:
            env_key, default = match.groups()
            value = os.getenv(env_key, default)
            if value is None:
                print(f"[WARN] Environment variable '{env_key}' is not set.")
            return value
    return config
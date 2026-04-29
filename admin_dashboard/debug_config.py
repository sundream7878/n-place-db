import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    import config
    print(f"DEBUG: config.__file__ = {config.__file__}")
    print(f"DEBUG: LOCAL_BASE_PATH exists: {hasattr(config, 'LOCAL_BASE_PATH')}")
    if hasattr(config, 'LOCAL_BASE_PATH'):
        print(f"DEBUG: LOCAL_BASE_PATH value: {config.LOCAL_BASE_PATH}")
    else:
        print(f"DEBUG: Available attributes in config: {dir(config)}")
except Exception as e:
    print(f"DEBUG: Error importing config: {e}")

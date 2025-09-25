
import logging, sys, os

def setup_logging(level=None):
    level_name = (os.getenv("LOG_LEVEL") or "").upper()
    if level is None:
        level = getattr(logging, level_name, logging.INFO) if level_name else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s')
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

def get_logger(name: str):
    return logging.getLogger(name)

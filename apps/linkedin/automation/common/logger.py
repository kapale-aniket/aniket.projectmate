import logging
import os

_CONFIGURED = set()


def get_logger(name, log_file=None, level=logging.INFO):
    logger = logging.getLogger(name)
    if name not in _CONFIGURED:
        logger.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(name)s] %(levelname)s %(message)s",
            datefmt="%H:%M:%S",
        )
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
        if log_file:
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        logger.propagate = False
        _CONFIGURED.add(name)
    return logger

import logging


def get_logger(name=None, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if name is None:
        configure_root_logger(logger, level)

    return logger


def configure_root_logger(
    logger: logging.Logger,
    level: int = logging.INFO,
    formatter_string: str | None = None,
):
    logger.setLevel(level)
    handler = logging.StreamHandler()

    if formatter_string is None:
        formatter_string = "%(asctime)s :: %(levelname)s :: %(message)s"

    formatter = logging.Formatter(formatter_string)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    logger.addHandler(handler)
    return logger

import logging

import sentry_sdk
from sentry_sdk.integrations import Integration
from sentry_sdk.integrations.logging import LoggingIntegration

from app.config import settings


def get_logger(name=None) -> logging.Logger:
    logger = logging.getLogger(name)

    if name is None:
        level = settings.log_level.to_int()
        logger.setLevel(level)
        configure_root_logger(logger, level)
    else:
        logger.setLevel(logging.NOTSET)

    return logger


def configure_root_logger(
    logger: logging.Logger,
    level: int = logging.INFO,
    formatter_string: str | None = None,
):
    handler = logging.StreamHandler()

    if formatter_string is None:
        formatter_string = "%(asctime)s :: %(levelname)s :: %(message)s"

    formatter = logging.Formatter(formatter_string)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    logger.addHandler(handler)
    return logger


def init_sentry(sentry_dsn: str | None, integrations: list[Integration] | None = None):
    if sentry_dsn:
        integrations = integrations or []
        integrations.append(
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.WARNING,  # Send warning and errors as events
            )
        )
        sentry_sdk.init(  # type:ignore  # mypy say it's abstract
            sentry_dsn,
            integrations=integrations,
        )

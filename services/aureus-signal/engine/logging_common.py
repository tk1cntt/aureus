from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

DEFAULT_LEVEL = "DEBUG"
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_WHEN = "midnight"
DEFAULT_INTERVAL = 1
DEFAULT_BACKUP_COUNT = 14
SETTINGS_FILENAME = "log_setting.txt"
_AUREUS_CONFIGURED_ATTR = "_aureus_logging_configured"
_AUREUS_SETTINGS_ATTR = "_aureus_logging_settings"


@dataclass
class LoggingSettings:
    log_dir: Path
    level: str
    fmt: str
    when: str
    interval: int
    backup_count: int


def _coerce_positive_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(str(value).strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _default_log_dir() -> Path:
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "logs" / "runtime"


def _settings_file_path(log_dir: Path) -> Path:
    return log_dir / SETTINGS_FILENAME


def _read_settings_file(path: Path) -> dict[str, str]:
    settings: dict[str, str] = {}
    if not path.exists():
        return settings

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip().upper()] = value.strip()

    return settings


def _write_settings_file(path: Path, settings: LoggingSettings) -> None:
    path.write_text(
        "\n".join(
            [
                "# Aureus Signal logging runtime settings",
                f"LOG_LEVEL={settings.level}",
                f"LOG_FORMAT={settings.fmt}",
                f"ROTATE_WHEN={settings.when}",
                f"ROTATE_INTERVAL={settings.interval}",
                f"BACKUP_COUNT={settings.backup_count}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def resolve_logging_settings() -> LoggingSettings:
    # Keep Docker external log directory behavior
    log_dir = Path(os.getenv("LOG_DIR") or _default_log_dir())
    log_dir.mkdir(parents=True, exist_ok=True)

    settings_path = _settings_file_path(log_dir)
    raw_settings = _read_settings_file(settings_path)

    settings = LoggingSettings(
        log_dir=log_dir,
        level=(raw_settings.get("LOG_LEVEL") or DEFAULT_LEVEL).upper(),
        fmt=raw_settings.get("LOG_FORMAT") or DEFAULT_FORMAT,
        when=(raw_settings.get("ROTATE_WHEN") or DEFAULT_WHEN).strip() or DEFAULT_WHEN,
        interval=_coerce_positive_int(raw_settings.get("ROTATE_INTERVAL"), DEFAULT_INTERVAL),
        backup_count=_coerce_positive_int(raw_settings.get("BACKUP_COUNT"), DEFAULT_BACKUP_COUNT),
    )

    # Auto-create settings file if it does not exist
    if not settings_path.exists():
        _write_settings_file(settings_path, settings)

    return settings


def configure_logging(app_name: str) -> LoggingSettings:
    root_logger = logging.getLogger()
    existing_settings = getattr(root_logger, _AUREUS_SETTINGS_ATTR, None)
    if getattr(root_logger, _AUREUS_CONFIGURED_ATTR, False) and isinstance(existing_settings, LoggingSettings):
        return existing_settings

    settings = resolve_logging_settings()
    explicit_log_file = (os.getenv("LOG_FILE") or "").strip()
    if explicit_log_file:
        log_path = Path(explicit_log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        log_path = settings.log_dir / f"{app_name}.log"

    formatter = logging.Formatter(settings.fmt)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = TimedRotatingFileHandler(
        filename=str(log_path),
        when=settings.when,
        interval=settings.interval,
        backupCount=settings.backup_count,
        encoding="utf-8",
        delay=False,
    )
    file_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.setLevel(settings.level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    setattr(root_logger, _AUREUS_CONFIGURED_ATTR, True)
    setattr(root_logger, _AUREUS_SETTINGS_ATTR, settings)

    return settings


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or __name__)

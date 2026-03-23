from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

DEFAULT_LEVEL = "DEBUG"
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_WHEN = "midnight"
DEFAULT_INTERVAL = 1
DEFAULT_BACKUP_COUNT = 14
DEFAULT_RELOAD_INTERVAL_SECONDS = 5
SETTINGS_FILENAME = "log_setting.txt"
_AUREUS_CONFIGURED_ATTR = "_aureus_logging_configured"
_AUREUS_SETTINGS_ATTR = "_aureus_logging_settings"
_AUREUS_LOG_PATH_ATTR = "_aureus_logging_log_path"
_AUREUS_SETTINGS_MTIME_ATTR = "_aureus_logging_settings_mtime"
_AUREUS_LAST_CHECK_ATTR = "_aureus_logging_last_check_ts"


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


def _resolve_log_path(settings: LoggingSettings, app_name: str | None) -> Path:
    explicit_log_file = (os.getenv("LOG_FILE") or "").strip()
    if explicit_log_file:
        log_path = Path(explicit_log_file)
    else:
        app_label = (app_name or "aureus-signal").strip() or "aureus-signal"
        log_path = settings.log_dir / f"{app_label}.log"

    log_path.parent.mkdir(parents=True, exist_ok=True)
    return log_path


def _apply_logging_settings(root_logger: logging.Logger, settings: LoggingSettings, log_path: Path) -> None:
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

    old_handlers = list(root_logger.handlers)
    root_logger.handlers.clear()
    for handler in old_handlers:
        try:
            handler.close()
        except Exception:
            pass

    root_logger.setLevel(getattr(logging, settings.level.upper(), logging.DEBUG))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    setattr(root_logger, _AUREUS_CONFIGURED_ATTR, True)
    setattr(root_logger, _AUREUS_SETTINGS_ATTR, settings)
    setattr(root_logger, _AUREUS_LOG_PATH_ATTR, str(log_path))

    settings_path = _settings_file_path(settings.log_dir)
    try:
        mtime = settings_path.stat().st_mtime if settings_path.exists() else None
    except OSError:
        mtime = None
    setattr(root_logger, _AUREUS_SETTINGS_MTIME_ATTR, mtime)


def configure_logging(app_name: str) -> LoggingSettings:
    root_logger = logging.getLogger()
    existing_settings = getattr(root_logger, _AUREUS_SETTINGS_ATTR, None)
    if getattr(root_logger, _AUREUS_CONFIGURED_ATTR, False) and isinstance(existing_settings, LoggingSettings):
        return existing_settings

    settings = resolve_logging_settings()
    log_path = _resolve_log_path(settings, app_name)
    _apply_logging_settings(root_logger, settings, log_path)
    setattr(root_logger, _AUREUS_LAST_CHECK_ATTR, 0.0)
    return settings


def refresh_logging_settings_if_needed(*, force: bool = False, interval_seconds: float = DEFAULT_RELOAD_INTERVAL_SECONDS) -> bool:
    root_logger = logging.getLogger()
    current_settings = getattr(root_logger, _AUREUS_SETTINGS_ATTR, None)
    if not isinstance(current_settings, LoggingSettings):
        return False

    now = time.time()
    last_check = float(getattr(root_logger, _AUREUS_LAST_CHECK_ATTR, 0.0) or 0.0)
    if not force and (now - last_check) < max(float(interval_seconds), 0.0):
        return False
    setattr(root_logger, _AUREUS_LAST_CHECK_ATTR, now)

    settings_path = _settings_file_path(current_settings.log_dir)
    try:
        current_mtime = settings_path.stat().st_mtime if settings_path.exists() else None
    except OSError:
        return False

    previous_mtime = getattr(root_logger, _AUREUS_SETTINGS_MTIME_ATTR, None)
    if not force and current_mtime == previous_mtime:
        return False

    new_settings = resolve_logging_settings()
    if not force and new_settings == current_settings:
        setattr(root_logger, _AUREUS_SETTINGS_MTIME_ATTR, current_mtime)
        return False

    current_log_path = getattr(root_logger, _AUREUS_LOG_PATH_ATTR, "")
    log_path = Path(current_log_path) if str(current_log_path).strip() else _resolve_log_path(new_settings, app_name=None)
    _apply_logging_settings(root_logger, new_settings, log_path)
    return True


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or __name__)

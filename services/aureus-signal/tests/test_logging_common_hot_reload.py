import io
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import logging_common


class TestLoggingCommonHotReload(unittest.TestCase):
    def setUp(self):
        self._root_logger = logging.getLogger()
        self._original_handlers = list(self._root_logger.handlers)
        self._original_level = self._root_logger.level
        self._original_configured = getattr(self._root_logger, logging_common._AUREUS_CONFIGURED_ATTR, None)
        self._original_settings = getattr(self._root_logger, logging_common._AUREUS_SETTINGS_ATTR, None)

    def tearDown(self):
        current_handlers = list(self._root_logger.handlers)
        self._root_logger.handlers.clear()
        for handler in current_handlers:
            try:
                handler.close()
            except Exception:
                pass
        for handler in self._original_handlers:
            self._root_logger.addHandler(handler)
        self._root_logger.setLevel(self._original_level)

        if self._original_configured is None:
            if hasattr(self._root_logger, logging_common._AUREUS_CONFIGURED_ATTR):
                delattr(self._root_logger, logging_common._AUREUS_CONFIGURED_ATTR)
        else:
            setattr(self._root_logger, logging_common._AUREUS_CONFIGURED_ATTR, self._original_configured)

        if self._original_settings is None:
            if hasattr(self._root_logger, logging_common._AUREUS_SETTINGS_ATTR):
                delattr(self._root_logger, logging_common._AUREUS_SETTINGS_ATTR)
        else:
            setattr(self._root_logger, logging_common._AUREUS_SETTINGS_ATTR, self._original_settings)

    def test_refresh_logging_settings_if_needed_applies_level_change(self):
        with tempfile.TemporaryDirectory() as td:
            log_dir = Path(td)
            with (
                patch.dict(os.environ, {"LOG_DIR": str(log_dir)}, clear=False),
                patch(
                    "engine.logging_common.TimedRotatingFileHandler",
                    side_effect=lambda *args, **kwargs: logging.StreamHandler(io.StringIO()),
                ),
            ):
                settings = logging_common.configure_logging("test_hot_reload")
                self.assertEqual(settings.level, "DEBUG")
                self.assertEqual(logging.getLogger().level, logging.DEBUG)

                settings_path = log_dir / logging_common.SETTINGS_FILENAME
                settings_path.write_text(
                    "\n".join(
                        [
                            "LOG_LEVEL=INFO",
                            f"LOG_FORMAT={logging_common.DEFAULT_FORMAT}",
                            "ROTATE_WHEN=midnight",
                            "ROTATE_INTERVAL=1",
                            "BACKUP_COUNT=14",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

                changed = logging_common.refresh_logging_settings_if_needed(force=True)

                self.assertTrue(changed)
                self.assertEqual(logging.getLogger().level, logging.INFO)


if __name__ == "__main__":
    unittest.main()

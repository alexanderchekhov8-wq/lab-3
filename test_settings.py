"""Проверки загрузки и ввода параметров без дополнительных зависимостей."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from settings import parse_settings, validate_value


class SettingsTests(unittest.TestCase):
    def test_config_cli_priority_and_relative_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"arrival_rate": 30, "output": "out", "cashiers": [4, 2, 2]}))
            settings = parse_settings(["--config", str(path), "--arrival-rate", "35"])
            self.assertEqual(settings.arrival_rate, 35)
            self.assertEqual(settings.cashiers, [2, 4])
            self.assertEqual(settings.runs, 200)
            self.assertEqual(settings.output, Path(directory).resolve() / "out")

    def test_invalid_values(self):
        for key, value in [("runs", 1), ("runs", True), ("seed", -1),
                           ("hours", float("nan")), ("arrival_rate", float("inf")),
                           ("service_mean", 0), ("cashiers", []), ("cashiers", [1.5]),
                           ("cashiers", [0]), ("output", " ")]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_value(key, value)

    def test_interactive_retry_decimal_comma_and_defaults(self):
        answers = ["wrong", "25,5", "", "", "4 2 2", "3", "", "", ""]
        with patch("builtins.input", side_effect=answers), contextlib.redirect_stdout(io.StringIO()):
            settings = parse_settings(["--interactive"])
        self.assertEqual(settings.arrival_rate, 25.5)
        self.assertEqual(settings.cashiers, [2, 4])
        self.assertEqual(settings.runs, 3)
        self.assertEqual(settings.service_mean, 2)

    def test_unknown_config_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"arrival_rates": 20}')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                parse_settings(["--config", str(path)])
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

"""D-05 — f1-simulate CLI integration. Uses Typer's CliRunner."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from f1_core.physics.cli import app

runner = CliRunner(env={"COLUMNS": "200", "LINES": "50"})


def test_cli_help_runs():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_cli_success_on_canonical_fixture(canonical_stint_artifact):
    """Happy path: load_stint returns the canonical fixture -> run_simulation -> table."""
    with patch("f1_core.physics.cli.load_stint", return_value=canonical_stint_artifact):
        result = runner.invoke(app, ["2023", "Bahrain", "VER", "2"])
    assert result.exit_code == 0, f"stdout: {result.stdout}"
    # Table columns present
    assert "Lap" in result.stdout
    assert "Compound" in result.stdout
    assert "Pred(s)" in result.stdout or "Pred_s" in result.stdout


def test_cli_exits_2_on_load_stint_failure():
    """FastF1 / data errors exit code 2 (CONTEXT D-05)."""
    with patch(
        "f1_core.physics.cli.load_stint",
        side_effect=ValueError("no such event"),
    ):
        result = runner.invoke(app, ["1999", "NoSuchRace", "VER", "1"])
    assert result.exit_code == 2
    assert "Error loading stint" in result.stdout


def test_cli_exits_2_on_invalid_driver_code():
    """validate_driver_code regex ^[A-Z]{3}$ failure bubbles up as ValueError -> exit 2."""
    with patch(
        "f1_core.physics.cli.load_stint",
        side_effect=ValueError("driver_code must match ^[A-Z]{3}$"),
    ):
        result = runner.invoke(app, ["2023", "Bahrain", "ver", "2"])
    assert result.exit_code == 2


def test_cli_exits_3_on_physics_failure(canonical_stint_artifact):
    """Runtime physics error exits code 3."""
    with patch("f1_core.physics.cli.load_stint", return_value=canonical_stint_artifact), \
         patch(
             "f1_core.physics.cli.run_simulation",
             side_effect=ZeroDivisionError("pathological parameter combo"),
         ):
        result = runner.invoke(app, ["2023", "Bahrain", "VER", "2"])
    assert result.exit_code == 3
    assert "Simulation failed" in result.stdout


def test_cli_prints_event_count(canonical_stint_artifact):
    """CLI footer reports event count for transparency."""
    with patch("f1_core.physics.cli.load_stint", return_value=canonical_stint_artifact):
        result = runner.invoke(app, ["2023", "Bahrain", "VER", "2"])
    assert result.exit_code == 0
    assert "Events logged" in result.stdout

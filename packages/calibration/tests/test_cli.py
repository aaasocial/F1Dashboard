"""CLI tests via typer.testing.CliRunner."""
from __future__ import annotations
import pytest
from typer.testing import CliRunner

from f1_calibration.cli import app

runner = CliRunner()


def test_cli_help_lists_all_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for name in ("stage1", "stage2", "stage3", "stage4", "stage5", "run-all"):
        assert name in result.stdout, f"missing subcommand {name!r} in help"


def test_stage1_help_mentions_compound_flag():
    result = runner.invoke(app, ["stage1", "--help"])
    assert result.exit_code == 0
    assert "--compound" in result.stdout


def test_stage1_rejects_invalid_compound():
    """T-3-01 flows through CLI: bad --compound exits with code 1."""
    result = runner.invoke(app, ["stage1", "--compound", "X9"])
    assert result.exit_code == 1
    # Message content: 'Invalid input' + regex fragment from validate_compound
    assert "Invalid input" in result.stdout


def test_run_all_rejects_invalid_compound():
    result = runner.invoke(app, ["run-all", "--compound", "BAD"])
    assert result.exit_code == 1
    assert "Invalid input" in result.stdout


def test_stage4_accepts_skip_sbc_flag():
    result = runner.invoke(app, ["stage4", "--help"])
    assert result.exit_code == 0
    assert "--skip-sbc" in result.stdout


def test_run_all_accepts_force_flag():
    result = runner.invoke(app, ["run-all", "--help"])
    assert result.exit_code == 0
    assert "--force" in result.stdout


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    # `no_args_is_help=True` produces a non-zero exit (typer default) but prints help
    assert "stage1" in result.stdout or "stage1" in result.stderr


def test_cli_does_not_print_traceback_on_internal_error(monkeypatch):
    """T-3-04: unexpected exceptions must not leak Python traceback to stdout."""
    # Force stage1 to raise an unexpected Exception via monkeypatch
    import f1_calibration.cli as cli
    def boom(*a, **kw):
        raise KeyError("internal path /etc/secret/bad")
    monkeypatch.setattr(cli, "_open_db", boom)
    result = runner.invoke(app, ["stage1", "--compound", "C3"])
    assert result.exit_code == 3
    assert "Internal error" in result.stdout
    # Traceback signature must not appear
    assert "Traceback" not in result.stdout
    assert "File \"" not in result.stdout

"""f1-simulate CLI entry point (CONTEXT D-05, RESEARCH.md §Typer code example).

Invocation: `f1-simulate <year> <event> <driver> <stint_index>`
Example:    `f1-simulate 2023 Bahrain VER 2`

Exit codes (CONTEXT D-05):
  0  success
  2  FastF1 / load_stint error (data availability, validation)
  3  physics / orchestrator error (numerical issues)

Security (threat register T-02-15, T-02-16):
  - driver_code path traversal: load_stint applies validate_driver_code (^[A-Z]{3}$).
    CLI does not construct any filesystem path from driver_code.
  - Exception tracebacks: CLI catches all exceptions at the boundary and prints
    only the exception message, not the traceback, to avoid leaking internal paths.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from f1_core.ingestion.fastf1_client import load_stint
from f1_core.physics.defaults import make_nominal_params
from f1_core.physics.orchestrator import run_simulation

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


@app.command()
def simulate(
    year: int = typer.Argument(..., help="Season year, e.g. 2023"),
    event: str = typer.Argument(..., help="Event name (substring match), e.g. 'Bahrain'"),
    driver: str = typer.Argument(..., help="3-letter driver code, e.g. 'VER'"),
    stint_index: int = typer.Argument(..., help="1-indexed stint number within the race"),
) -> None:
    """Simulate a real stint with nominal physics parameters and print a per-lap table."""
    try:
        artifact = load_stint(
            year=year,
            event=event,
            driver_code=driver,
            stint_index=stint_index,
        )
    except Exception as exc:   # noqa: BLE001 — CLI boundary; T-02-16 no traceback leak
        console.print(f"[red]Error loading stint:[/red] {exc}")
        raise typer.Exit(code=2)

    try:
        result = run_simulation(artifact, make_nominal_params())
    except Exception as exc:   # noqa: BLE001 — CLI boundary; T-02-16 no traceback leak
        console.print(f"[red]Simulation failed:[/red] {exc}")
        raise typer.Exit(code=3)

    table = Table(title=f"{year} {event} {driver} stint {stint_index}")
    for col in ("Lap", "Compound", "Age", "Pred(s)", "Obs(s)", "Delta(s)",
                "Grip%", "T_tread(C)", "E_tire(MJ)"):
        table.add_column(col, justify="right")
    for row in result.per_lap_rows():
        table.add_row(*[str(x) for x in row])
    console.print(table)
    console.print(f"\n[dim]Events logged: {len(result.events)}[/dim]")


if __name__ == "__main__":
    app()


__all__ = ["app", "simulate"]

"""Bridge to ucmyg/sentra-fleet-engine: the LucidFlex 25K rule engine and deflated Sharpe live
there, so the factory imports them instead of re-implementing the rules.

Set FLEET_ENGINE_DIR to the checkout (default: a sibling folder next to this repo)."""
import os
import sys
from pathlib import Path

FLEET_ENGINE_DIR = Path(os.environ.get(
    "FLEET_ENGINE_DIR", Path(__file__).resolve().parents[3] / "sentra-fleet-engine"))
if not (FLEET_ENGINE_DIR / "fleet_engine" / "rules.py").exists():
    raise ImportError(f"sentra-fleet-engine not found at {FLEET_ENGINE_DIR} (set FLEET_ENGINE_DIR)")
if str(FLEET_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(FLEET_ENGINE_DIR))

from fleet_engine.deflate import deflated_sharpe, expected_max_sharpe  # noqa: E402,F401
from fleet_engine.rules import Rules, run_eval, run_funded  # noqa: E402,F401

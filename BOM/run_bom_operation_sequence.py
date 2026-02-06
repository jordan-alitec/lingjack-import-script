#!/usr/bin/env python3
"""
Run BOM and Operation imports in sequence with a fixed Odoo URL.

Runs in order:
1. import_bom_to_odoo_empty.py (Empty Cabinet BoM)
2. import_bom_to_odoo.py (Actual BoM)
3. import_operation_to_odoo.py (Operations)

All three scripts use ODOO_URL = https://lingjack.odoo.com/
Other settings (DB, username, password, file paths) come from BOM/config.py.
"""

import sys
import traceback
from pathlib import Path
import importlib.util

# BOM root (directory containing config.py)
BASE_DIR = Path(__file__).parent.resolve()

# Force this Odoo URL for all three scripts
ODOO_URL = "https://lingjack.odoo.com/"


def _ensure_config_patched():
    """Add BOM to path, load config, and set ODOO_URL so all scripts use it."""
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    import config  # noqa: F401, E402
    config.ODOO_URL = ODOO_URL
    


def _load_module(module_name: str, file_path: Path):
    """Load a module from a given file path."""
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _run_step(label: str, func):
    """Run a single step with logging and error handling."""
    print("\n" + "=" * 80)
    print(f"START: {label}")
    print("=" * 80)
    try:
        func()
        print("\n" + "-" * 80)
        print(f"DONE: {label}")
        print("-" * 80)
    except SystemExit as e:
        if e.code not in (0, None):
            print("\n" + "!" * 80)
            print(f"ABORTED STEP (SystemExit {e.code}): {label}")
            print("!" * 80)
            raise
    except Exception as e:
        print("\n" + "!" * 80)
        print(f"ERROR in step: {label}")
        print(f"{e}")
        traceback.print_exc()
        print("!" * 80)
        raise


def run_sequence():
    """Run the three imports in order with ODOO_URL = https://lingjack.odoo.com/."""
    _ensure_config_patched()
    print(f"Using ODOO_URL = {ODOO_URL} for all scripts.")

    # 1) Empty Cabinet BoM
    def step_empty():
        mod = _load_module(
            "empty_cabinet_bom_import",
            BASE_DIR / "Empty Cabinet" / "import_bom_to_odoo_empty.py",
        )
        mod.main()

    # 2) Actual BoM
    def step_actual():
        mod = _load_module(
            "actual_bom_import",
            BASE_DIR / "Actual BoM" / "import_bom_to_odoo.py",
        )
        mod.main()

    # 3) Operation
    def step_operation():
        mod = _load_module(
            "operation_import",
            BASE_DIR / "Operation" / "import_operation_to_odoo.py",
        )
        mod.main()

    _run_step("1. Empty Cabinet BoM (import_bom_to_odoo_empty.py)", step_empty)
    _run_step("2. Actual BoM (import_bom_to_odoo.py)", step_actual)
    _run_step("3. Operation (import_operation_to_odoo.py)", step_operation)

    print("\n" + "=" * 80)
    print("ALL THREE IMPORTS COMPLETED")
    print("=" * 80)


def main():
    """
    CLI entry point.

    Usage:
        cd BOM
        python run_bom_operation_sequence.py

    Ensures ODOO_URL = https://lingjack.odoo.com/ for all three scripts.
    DB, username, password, and file paths are read from config.py.
    """
    run_sequence()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Master BOM data import orchestrator.

Runs all individual imports in a single Python call, in this order:
1. Employee
2. Empty Cabinet BoM
3. Actual BoM
4. Operation
5. Manufacturing (MRP)
6. SWO (Sale Work Order)
7. Setsco (combine sheets + import serials)

All scripts use the shared Odoo connection settings defined in the
root-level `config.py` in the BOM directory.
"""

import sys
import traceback
from pathlib import Path
import importlib.util


BASE_DIR = Path(__file__).parent.resolve()


def _load_module(module_name: str, file_path: Path):
    """Dynamically load a module from a given file path."""
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _run_step(label: str, func):
    """Run a single step with simple logging and error capture."""
    print("\n" + "=" * 80)
    print(f"START: {label}")
    print("=" * 80)
    try:
        func()
        print("\n" + "-" * 80)
        print(f"DONE: {label}")
        print("-" * 80)
    except SystemExit as e:
        # Allow scripts that use sys.exit to propagate non-zero status
        if e.code not in (0, None):
            print("\n" + "!" * 80)
            print(f"ABORTED STEP (SystemExit {e.code}): {label}")
            print("!" * 80)
            raise
    except Exception as e:
        print("\n" + "!" * 80)
        print(f"ERROR in step: {label}")
        print(f"{e}")
        print("Full traceback:")
        traceback.print_exc()
        print("!" * 80)
        # Re-raise to stop the pipeline on hard errors
        raise


def run_all():
    """
    Run all imports in sequence using the shared root config.py.

    Expected filesystem layout (relative to this file):
    - Employee/import_employee_to_odoo.py
    - Empty Cabinet/import_bom_to_odoo_empty.py
    - Actual BoM/import_bom_to_odoo.py
    - Operation/import_operation_to_odoo.py
    - Manufacturing/import_mrp_to_odoo.py
    - SWO/import_swo_to_odoo.py
    - Setsco/combine_setsco_sheets.py
    - Setsco/import_setsco_serials_to_odoo.py
    """

    # 1) Employee
    def step_employee():
        mod_path = BASE_DIR / "Employee" / "import_employee_to_odoo.py"
        mod = _load_module("employee_import", mod_path)
        # Use each script's own main(), which already reads from root config.py
        mod.main()

    # 2) Empty Cabinet BoM
    def step_empty_cabinet_bom():
        mod_path = BASE_DIR / "Empty Cabinet" / "import_bom_to_odoo_empty.py"
        mod = _load_module("empty_cabinet_bom_import", mod_path)
        mod.main()

    # 3) Actual BoM
    def step_actual_bom():
        mod_path = BASE_DIR / "Actual BoM" / "import_bom_to_odoo.py"
        mod = _load_module("actual_bom_import", mod_path)
        mod.main()

    # 4) Operation
    def step_operation():
        mod_path = BASE_DIR / "Operation" / "import_operation_to_odoo.py"
        mod = _load_module("operation_import", mod_path)
        mod.main()

    # 5) Manufacturing (MRP)
    def step_manufacturing():
        mod_path = BASE_DIR / "Manufacturing" / "import_mrp_to_odoo.py"
        mod = _load_module("mrp_import", mod_path)
        mod.main()

    # 6) SWO
    def step_swo():
        mod_path = BASE_DIR / "SWO" / "import_swo_to_odoo.py"
        mod = _load_module("swo_import", mod_path)
        mod.main()

    # 7) Setsco (combine sheets, then import serials)
    def step_setsco():
        combine_mod_path = BASE_DIR / "Setsco" / "combine_setsco_sheets.py"
        combine_mod = _load_module("setsco_combine", combine_mod_path)
        combine_mod.main()

        serial_mod_path = BASE_DIR / "Setsco" / "import_setsco_serials_to_odoo.py"
        serial_mod = _load_module("setsco_serial_import", serial_mod_path)
        serial_mod.main()

    # Execute steps in the requested order
    # _run_step("Employee import", step_employee)
    _run_step("Empty Cabinet BoM import", step_empty_cabinet_bom)
    _run_step("Actual BoM import", step_actual_bom)
    _run_step("Operation import", step_operation)
    _run_step("Manufacturing (MRP) import", step_manufacturing)
    _run_step("SWO import", step_swo)
    _run_step("Setsco combine + serial import", step_setsco)

    print("\n" + "=" * 80)
    print("ALL IMPORTS COMPLETED")
    print("=" * 80)


def main():
    """
    CLI entry point.

    Usage:
        python run_all_imports.py

    The individual scripts will respect the flags and file paths defined
    in the shared `config.py` in this directory.
    """
    run_all()


if __name__ == "__main__":
    main()


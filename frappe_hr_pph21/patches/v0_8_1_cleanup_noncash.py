"""Remove unused legacy pairs only after the manual-selection schema is available."""
from frappe_hr_pph21.cleanup import run_cleanup_patch


def execute():
    return run_cleanup_patch()

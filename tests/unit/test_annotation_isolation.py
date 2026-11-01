"""The API never loads the annotation package or the spreadsheet library."""

import subprocess
import sys


def test_importing_the_api_loads_no_annotation_code() -> None:
    # A fresh interpreter, so modules imported by other tests do not hide an import.
    probe = (
        "import sys\n"
        "import govbr_classifier.api.main\n"
        "loaded = sorted(m for m in sys.modules\n"
        "    if m == 'openpyxl' or m.startswith(('openpyxl.', 'govbr_classifier.annotation')))\n"
        "print(','.join(loaded))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""

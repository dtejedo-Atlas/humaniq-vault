"""Idempotent bootstrap of native OCR dependencies in fresh runtime containers."""
import logging
import subprocess
from pathlib import Path


def ensure_ocr_runtime():
    try:
        subprocess.run(['bash', str(Path(__file__).parent / 'scripts' / 'install_ocr.sh')],
                       check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return True
    except (subprocess.SubprocessError, OSError):
        logging.getLogger(__name__).error('OCR dependencies unavailable; image CVs will require manual review until runtime setup succeeds.')
        return False
"""Import smoke without starting a Streamlit server."""

from pathlib import Path
import logging
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.disable(logging.CRITICAL)
import src.agent  # noqa: E402
import app  # noqa: E402
logging.disable(logging.NOTSET)

assert hasattr(src.agent.WorkbenchAgent, "run")
print("IMPORT_SMOKE_OK")

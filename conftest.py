import sys
from pathlib import Path

# Make `connectors` importable and hook scripts loadable by tests.
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "hooks" / "scripts"))

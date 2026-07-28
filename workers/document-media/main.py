from __future__ import annotations

import sys
from pathlib import Path

from sip.worker_runtime import main as worker_main


def main() -> None:
    """Run only the capabilities bound to this immutable worker manifest."""
    manifest = Path(__file__).with_name("worker-manifest.json")
    sys.argv[1:1] = ["--manifest", str(manifest)]
    worker_main()


if __name__ == "__main__":
    main()

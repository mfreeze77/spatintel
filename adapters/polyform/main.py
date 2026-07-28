from __future__ import annotations

import argparse
import json
from pathlib import Path

from sip.models import Classification
from sip.provider_sdk import PolyformFormatAdapter, ProviderExecutionContext


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize a documented Polyform-compatible user export")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--project-id", required=True)
    args = parser.parse_args()
    context = ProviderExecutionContext(
        tenant_id=args.tenant_id,
        project_id=args.project_id,
        purpose="capture_import",
        classification=Classification.CONFIDENTIAL,
    )
    print(json.dumps(PolyformFormatAdapter().normalize(args.source, args.destination, context=context), sort_keys=True, default=str))


if __name__ == "__main__":
    main()

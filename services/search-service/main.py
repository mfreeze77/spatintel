from __future__ import annotations

import os
import uvicorn
from sip.api import create_app

SERVICE_NAME = 'search-service'
app = create_app(service_name=SERVICE_NAME)

def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")), proxy_headers=True)

if __name__ == "__main__":
    main()

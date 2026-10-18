"""Make repo-root packages importable when the API is started from fastapi/.

Local uvicorn is run with fastapi/ as the working directory, so Python only
sees the `app` package. `config`, `database`, and `backend` live beside
fastapi/. In Docker those packages are mounted next to `app` instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve()
for _candidate in (_here.parents[1], _here.parents[2]):
    if (_candidate / "config" / "settings.py").is_file():
        _root = str(_candidate)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        break

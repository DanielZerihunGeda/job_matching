"""Run the FastAPI application with ``python src/job_matching``."""

from __future__ import annotations

import sys
from pathlib import Path

import uvicorn

# Executing a source directory does not automatically add its parent ``src``
# directory to the import path. ``uv run`` normally installs the package, but this
# also keeps direct source execution predictable in a fresh environment.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from job_matching.main import app  # noqa: E402


def main() -> None:
    """Start a local API server using safe development defaults."""

    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

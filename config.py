"""Central environment configuration for the backend only."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Load the local, gitignored .env file before any route/service reads settings.
load_dotenv(Path(__file__).with_name(".env"), override=False)

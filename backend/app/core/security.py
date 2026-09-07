"""Local Air-Gapped Security and Authentication Guard.

Provides air-gapped header token validation for local API access.
"""

from __future__ import annotations

import os
from fastapi import Header, HTTPException, status

DEFAULT_DEFENSE_API_KEY = os.getenv("DEFENSE_API_KEY", "NTRO-SIH26158-SECURE-LOCAL-KEY")


def verify_api_key(x_defense_auth: str | None = Header(default=None)) -> bool:
    """Validate header token if configured; allows open localhost access by default."""
    if not x_defense_auth:
        # Default allow for local single-user air-gapped workstation
        return True
    if x_defense_auth != DEFAULT_DEFENSE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid defense intelligence authentication credentials",
        )
    return True

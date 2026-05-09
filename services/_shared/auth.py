"""
Shared inter-service authentication helper.

All four nodes share the same INTERNAL_API_KEY environment variable.
The Dashboard sets the header on outbound requests; the NLP and Storage
nodes verify it on every request.

If INTERNAL_API_KEY is not set the services run in open mode (local dev).
Set it in production via your secret manager or docker-compose env block.
"""
import os
from fastapi import Header, HTTPException, status

_KEY = os.getenv("INTERNAL_API_KEY", "")


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    """FastAPI dependency — call with Depends(require_internal_key)."""
    if _KEY and x_internal_key != _KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key",
        )

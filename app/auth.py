from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from app.config import get_settings
import hmac

security = HTTPBasic()


def verify_credentials(
    credentials: HTTPBasicCredentials = Depends(security)
) -> str:
    """
    Verify HTTP Basic Auth credentials using
    constant-time comparison to prevent timing attacks.
    Returns username on success, raises 401 on failure.
    """
    settings = get_settings()

    valid = (
        hmac.compare_digest(credentials.username, settings.api_username) and
        hmac.compare_digest(credentials.password, settings.api_password)
    )

    if not (valid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"}
        )

    return credentials.username
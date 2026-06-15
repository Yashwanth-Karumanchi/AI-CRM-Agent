from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
from app.config import get_settings

security = HTTPBasic()

def verify_credentials(
    credentials: HTTPBasicCredentials = Depends(security)
) -> str:
    settings = get_settings()

    correct_username = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.api_username.encode("utf-8")
    )

    correct_password = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.api_password.encode("utf-8")
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"}
        )

    return credentials.username
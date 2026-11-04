from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models.auth import ApiKey, UserAccount
from app.schemas.auth import PermissionName
from app.services.auth import AuthenticationError, AuthService

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="ModelSentryApiKey")

ROLE_PERMISSIONS: dict[str, tuple[PermissionName, ...]] = {
    "admin": ("admin", "operate", "read", "review"),
    "operator": ("operate", "read"),
    "reviewer": ("read", "review"),
    "viewer": ("read",),
}


@dataclass(frozen=True)
class CurrentPrincipal:
    """Authenticated local identity and credential."""

    user: UserAccount
    api_key: ApiKey
    permissions: tuple[PermissionName, ...]


def get_current_principal(
    session: Annotated[Session, Depends(get_db_session)],
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(bearer_scheme),
    ],
) -> CurrentPrincipal:
    """Authenticate a bearer API key without exposing its digest."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid bearer API key is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        api_key = AuthService(session).authenticate(credentials.credentials)
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    return CurrentPrincipal(
        user=api_key.user,
        api_key=api_key,
        permissions=ROLE_PERMISSIONS[api_key.user.role],
    )


def require_admin(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> CurrentPrincipal:
    """Restrict identity and credential administration to administrators."""

    if "admin" not in principal.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permission is required.",
        )
    return principal


def authorize_api_request(
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> CurrentPrincipal:
    """Apply the fixed v0.1 role policy to protected product routes."""

    method = request.method.upper()
    role = principal.user.role
    if role == "admin" or method in {"GET", "HEAD"}:
        return principal
    if role == "operator" and not (
        method == "PATCH" and "/reviews/" in request.url.path
    ):
        return principal
    if role == "reviewer" and method == "PATCH" and "/reviews/" in request.url.path:
        return principal
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The assigned role does not permit this operation.",
    )

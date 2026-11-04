from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.security import CurrentPrincipal, get_current_principal, require_admin
from app.db.session import get_db_session
from app.schemas.auth import (
    ApiKeyCreate,
    ApiKeyRead,
    BootstrapAdminCreate,
    BootstrapAdminRead,
    CurrentPrincipalRead,
    IssuedApiKeyRead,
    UserCreate,
    UserRead,
)
from app.services.auth import (
    AuthConflictError,
    AuthenticationError,
    AuthNotFoundError,
    AuthService,
    IssuedCredential,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
DbSession = Annotated[Session, Depends(get_db_session)]
AdminPrincipal = Annotated[CurrentPrincipal, Depends(require_admin)]
AuthenticatedPrincipal = Annotated[
    CurrentPrincipal,
    Depends(get_current_principal),
]


def _issued_read(credential: IssuedCredential) -> IssuedApiKeyRead:
    metadata = ApiKeyRead.model_validate(credential.api_key)
    return IssuedApiKeyRead(
        **metadata.model_dump(),
        api_key=credential.raw_key,
    )


@router.post(
    "/bootstrap",
    response_model=BootstrapAdminRead,
    status_code=status.HTTP_201_CREATED,
)
def bootstrap_admin(
    payload: BootstrapAdminCreate,
    session: DbSession,
    bootstrap_token: Annotated[
        str | None,
        Header(alias="X-Bootstrap-Token"),
    ] = None,
) -> BootstrapAdminRead:
    """Create the first administrator and return its API key exactly once."""

    try:
        user, credential = AuthService(session).bootstrap_admin(
            payload,
            bootstrap_token,
        )
    except AuthenticationError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error
    except AuthConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return BootstrapAdminRead(
        user=UserRead.model_validate(user),
        credential=_issued_read(credential),
    )


@router.get("/me", response_model=CurrentPrincipalRead)
def get_current_identity(
    principal: AuthenticatedPrincipal,
) -> CurrentPrincipalRead:
    """Return the authenticated identity and effective permission labels."""

    return CurrentPrincipalRead(
        user=UserRead.model_validate(principal.user),
        api_key_id=principal.api_key.id,
        permissions=list(principal.permissions),
    )


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: UserCreate,
    session: DbSession,
    _: AdminPrincipal,
) -> UserRead:
    """Register a local identity with one fixed governance role."""

    try:
        user = AuthService(session).create_user(payload)
    except AuthConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return UserRead.model_validate(user)


@router.get("/users", response_model=list[UserRead])
def list_users(
    session: DbSession,
    _: AdminPrincipal,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[UserRead]:
    """List local identities without exposing credential digests."""

    users = AuthService(session).list_users(offset=offset, limit=limit)
    return [UserRead.model_validate(user) for user in users]


@router.post(
    "/users/{user_id}/api-keys",
    response_model=IssuedApiKeyRead,
    status_code=status.HTTP_201_CREATED,
)
def issue_api_key(
    user_id: UUID,
    payload: ApiKeyCreate,
    session: DbSession,
    _: AdminPrincipal,
) -> IssuedApiKeyRead:
    """Issue a new bearer key and expose the raw secret exactly once."""

    try:
        credential = AuthService(session).issue_api_key(user_id, payload)
    except AuthNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except AuthConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return _issued_read(credential)


@router.get("/users/{user_id}/api-keys", response_model=list[ApiKeyRead])
def list_api_keys(
    user_id: UUID,
    session: DbSession,
    _: AdminPrincipal,
) -> list[ApiKeyRead]:
    """List credential metadata; raw keys and digests are never returned."""

    try:
        api_keys = AuthService(session).list_api_keys(user_id)
    except AuthNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return [ApiKeyRead.model_validate(api_key) for api_key in api_keys]


@router.delete(
    "/api-keys/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_api_key(
    api_key_id: UUID,
    session: DbSession,
    _: AdminPrincipal,
) -> Response:
    """Irreversibly revoke one credential while preserving its audit metadata."""

    try:
        AuthService(session).revoke_api_key(api_key_id)
    except AuthNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except AuthConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)

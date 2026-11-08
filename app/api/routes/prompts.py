from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.prompt import (
    PromptCreate,
    PromptDetailRead,
    PromptRead,
    PromptVersionCreate,
    PromptVersionRead,
)
from app.services.prompt_registry import (
    PromptRegistryConflictError,
    PromptRegistryNotFoundError,
    PromptRegistryService,
)

router = APIRouter(prefix="/prompts", tags=["prompts"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.post("", response_model=PromptDetailRead, status_code=status.HTTP_201_CREATED)
def create_prompt(payload: PromptCreate, session: DbSession) -> PromptDetailRead:
    """Create prompt metadata together with immutable version one."""

    try:
        prompt = PromptRegistryService(session).create_prompt(payload)
    except PromptRegistryConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return PromptDetailRead.model_validate(prompt)


@router.get("", response_model=list[PromptRead])
def list_prompts(
    session: DbSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> list[PromptRead]:
    """List prompt registry metadata in deterministic creation order."""

    prompts = PromptRegistryService(session).list_prompts(
        offset=offset,
        limit=limit,
    )
    return [PromptRead.model_validate(prompt) for prompt in prompts]


@router.get("/{prompt_id}", response_model=PromptDetailRead)
def get_prompt(prompt_id: UUID, session: DbSession) -> PromptDetailRead:
    """Return prompt metadata and its complete version history."""

    try:
        prompt = PromptRegistryService(session).get_prompt(prompt_id)
    except PromptRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return PromptDetailRead.model_validate(prompt)


@router.post(
    "/{prompt_id}/versions",
    response_model=PromptVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_prompt_version(
    prompt_id: UUID,
    payload: PromptVersionCreate,
    session: DbSession,
) -> PromptVersionRead:
    """Append an immutable version using the next sequential number."""

    service = PromptRegistryService(session)
    try:
        version = service.create_version(prompt_id, payload)
    except PromptRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except PromptRegistryConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return PromptVersionRead.model_validate(version)


@router.get("/{prompt_id}/versions", response_model=list[PromptVersionRead])
def list_prompt_versions(
    prompt_id: UUID,
    session: DbSession,
) -> list[PromptVersionRead]:
    """List every immutable version of a prompt."""

    try:
        versions = PromptRegistryService(session).list_versions(prompt_id)
    except PromptRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return [PromptVersionRead.model_validate(version) for version in versions]


@router.get(
    "/{prompt_id}/versions/{version}",
    response_model=PromptVersionRead,
)
def get_prompt_version(
    prompt_id: UUID,
    version: Annotated[int, Path(ge=1)],
    session: DbSession,
) -> PromptVersionRead:
    """Return one exact prompt version for reproducible evaluation."""

    try:
        prompt_version = PromptRegistryService(session).get_version(
            prompt_id,
            version,
        )
    except PromptRegistryNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return PromptVersionRead.model_validate(prompt_version)

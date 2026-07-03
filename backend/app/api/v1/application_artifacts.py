"""Application artifact download endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.application_artifact import ApplicationArtifactMeta
from app.services.application_artifacts import ApplicationArtifactService

router = APIRouter()


@router.get("/{artifact_id}", response_model=ApplicationArtifactMeta)
def get_application_artifact_meta(
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> ApplicationArtifactMeta:
    """Return metadata for one stored application artifact."""
    return ApplicationArtifactService(db).get_meta(user.id, artifact_id)


@router.get("/{artifact_id}/download")
def download_application_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> Response:
    """Download the decrypted artifact bytes (owner only)."""
    data, filename, content_type = ApplicationArtifactService(db).load_pdf_bytes(
        user.id, artifact_id
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

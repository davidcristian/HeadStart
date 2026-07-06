"""Document generation poll endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_verified_user
from app.models.user import User
from app.schemas.document_generation import DocumentGenerationRead
from app.services.document_generations import DocumentGenerationService

router = APIRouter()


@router.get("/{generation_id}", response_model=DocumentGenerationRead)
def get_document_generation(
    generation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_verified_user),
) -> DocumentGenerationRead:
    """Return one resume/cover-letter generation job for polling."""
    return DocumentGenerationService(db).get_for_user(user.id, generation_id)

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.services.persistence import PersistenceService, get_persistence_service


def get_persistence_db_service(
    db: Session = Depends(get_db_session),
) -> PersistenceService:
    return get_persistence_service(db)

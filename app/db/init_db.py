from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import session as db_session
from app.db.models.user import User


def init_default_user(db: Session) -> User:
    settings = get_settings()
    existing_user = db.get(User, settings.default_user_id)
    if existing_user is not None:
        return existing_user

    default_user = User(
        id=settings.default_user_id,
        display_name="Default Candidate",
        role="candidate",
    )
    db.add(default_user)
    db.commit()
    db.refresh(default_user)
    return default_user


def init_db() -> None:
    with db_session.SessionLocal() as db:
        init_default_user(db)

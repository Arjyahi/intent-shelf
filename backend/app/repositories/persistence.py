from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    CartItemRecord,
    FeedRequestLogRecord,
    ImpressionEventRecord,
    LikeEventRecord,
    SaveEventRecord,
    SearchEventRecord,
    SessionEventRecord,
    SessionRecord,
)
from app.schemas.events import Session


class PersistenceRepository:
    """Small ORM repository for runtime persistence tables."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_session(self, session_id: str) -> SessionRecord | None:
        return self.db.get(SessionRecord, session_id)

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def upsert_session(self, session: Session) -> SessionRecord:
        record = self.get_session(session.session_id)
        if record is None:
            record = SessionRecord(
                session_id=session.session_id,
                user_id=session.user_id,
                session_start=session.session_start,
                session_end=session.session_end,
                entry_surface=session.entry_surface,
                source=session.source,
            )
            self.db.add(record)
            self.db.flush()
            return record

        if session.user_id:
            record.user_id = session.user_id
        incoming_session_start = self._normalize_datetime(session.session_start)
        current_session_start = self._normalize_datetime(record.session_start)
        if (
            incoming_session_start is not None
            and current_session_start is not None
            and incoming_session_start < current_session_start
        ):
            record.session_start = session.session_start
        if session.session_end is not None:
            record.session_end = session.session_end
        if session.entry_surface:
            record.entry_surface = session.entry_surface
        record.source = session.source
        self.db.flush()
        return record

    def event_exists(self, model: type, event_id: str) -> bool:
        identity_column = model.id if hasattr(model, "id") else model.event_id
        statement = select(identity_column).where(model.event_id == event_id)
        return self.db.execute(statement).first() is not None

    def add_session_event(self, record: SessionEventRecord) -> None:
        self.db.add(record)
        self.db.flush()

    def list_session_events(self, session_id: str, limit: int) -> list[SessionEventRecord]:
        statement = (
            select(SessionEventRecord)
            .where(SessionEventRecord.session_id == session_id)
            .order_by(
                SessionEventRecord.event_timestamp.desc(),
                SessionEventRecord.id.desc(),
            )
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def add_search_event(self, record: SearchEventRecord) -> None:
        self.db.add(record)
        self.db.flush()

    def add_impression_event(self, record: ImpressionEventRecord) -> None:
        self.db.add(record)
        self.db.flush()

    def add_like_event(self, record: LikeEventRecord) -> None:
        self.db.add(record)
        self.db.flush()

    def list_like_events(self, actor_key: str) -> list[LikeEventRecord]:
        statement = (
            select(LikeEventRecord)
            .where(LikeEventRecord.actor_key == actor_key)
            .order_by(
                LikeEventRecord.event_timestamp.desc(),
                LikeEventRecord.id.desc(),
            )
        )
        return list(self.db.scalars(statement))

    def add_save_event(self, record: SaveEventRecord) -> None:
        self.db.add(record)
        self.db.flush()

    def list_save_events(self, actor_key: str) -> list[SaveEventRecord]:
        statement = (
            select(SaveEventRecord)
            .where(SaveEventRecord.actor_key == actor_key)
            .order_by(
                SaveEventRecord.event_timestamp.desc(),
                SaveEventRecord.id.desc(),
            )
        )
        return list(self.db.scalars(statement))

    def upsert_cart_item(
        self,
        *,
        actor_key: str,
        session_id: str | None,
        user_id: str | None,
        product_id: str,
        quantity: int,
        product_name: str,
        product_type_name: str | None,
        product_group_name: str | None,
        image_path: str | None,
        metadata_json: dict | None,
    ) -> CartItemRecord:
        statement = select(CartItemRecord).where(
            CartItemRecord.actor_key == actor_key,
            CartItemRecord.product_id == product_id,
        )
        record = self.db.scalar(statement)
        if record is None:
            record = CartItemRecord(
                actor_key=actor_key,
                session_id=session_id,
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                product_name=product_name,
                product_type_name=product_type_name,
                product_group_name=product_group_name,
                image_path=image_path,
                metadata_json=metadata_json,
            )
            self.db.add(record)
        else:
            record.session_id = session_id or record.session_id
            record.user_id = user_id or record.user_id
            record.quantity = quantity
            record.product_name = product_name
            record.product_type_name = product_type_name
            record.product_group_name = product_group_name
            record.image_path = image_path
            record.metadata_json = metadata_json

        self.db.flush()
        return record

    def list_cart_items(self, actor_key: str) -> list[CartItemRecord]:
        statement = (
            select(CartItemRecord)
            .where(CartItemRecord.actor_key == actor_key)
            .order_by(CartItemRecord.updated_at.desc(), CartItemRecord.id.desc())
        )
        return list(self.db.scalars(statement))

    def remove_cart_item(self, actor_key: str, product_id: str) -> None:
        statement = delete(CartItemRecord).where(
            CartItemRecord.actor_key == actor_key,
            CartItemRecord.product_id == product_id,
        )
        self.db.execute(statement)

    def clear_cart(self, actor_key: str) -> None:
        statement = delete(CartItemRecord).where(CartItemRecord.actor_key == actor_key)
        self.db.execute(statement)

    def add_feed_request_log(self, record: FeedRequestLogRecord) -> None:
        self.db.add(record)
        self.db.flush()

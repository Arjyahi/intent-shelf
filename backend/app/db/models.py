from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.schemas.common import utc_now


class TimestampMixin:
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class SessionRecord(TimestampMixin, Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    session_start: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    session_end: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    entry_surface: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64), default="intentshelf_app", nullable=False)


class SessionEventRecord(Base):
    __tablename__ = "session_events"
    __table_args__ = (
        Index("ix_session_events_session_timestamp", "session_id", "event_timestamp"),
        Index("ix_session_events_product_timestamp", "product_id", "event_timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    event_timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_surface: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    product_id: Mapped[str | None] = mapped_column(String(32), index=True)
    rank_position: Mapped[int | None] = mapped_column(Integer)
    source_candidate_type: Mapped[str | None] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(64), default="intentshelf_app", nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SearchEventRecord(Base):
    __tablename__ = "search_events"
    __table_args__ = (
        Index("ix_search_events_session_timestamp", "session_id", "event_timestamp"),
        Index("ix_search_events_user_timestamp", "user_id", "event_timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    event_timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    num_results: Mapped[int | None] = mapped_column(Integer)
    strategy_used: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(64), default="intentshelf_app", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ImpressionEventRecord(Base):
    __tablename__ = "impression_events"
    __table_args__ = (
        Index("ix_impression_events_session_timestamp", "session_id", "event_timestamp"),
        Index("ix_impression_events_request_rank", "request_id", "rank_position"),
        Index("ix_impression_events_strategy_timestamp", "ranking_strategy", "event_timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    event_timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    product_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    surface: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    ranking_strategy: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    primary_source: Mapped[str | None] = mapped_column(String(64))
    candidate_sources: Mapped[list | None] = mapped_column(JSON)
    explanation_reason: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    source: Mapped[str] = mapped_column(String(64), default="intentshelf_app", nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class LikeEventRecord(Base):
    __tablename__ = "like_events"
    __table_args__ = (
        Index("ix_like_events_actor_timestamp", "actor_key", "event_timestamp"),
        Index("ix_like_events_product_timestamp", "product_id", "event_timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    actor_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    product_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    event_timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="intentshelf_app", nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SaveEventRecord(Base):
    __tablename__ = "save_events"
    __table_args__ = (
        Index("ix_save_events_actor_timestamp", "actor_key", "event_timestamp"),
        Index("ix_save_events_product_timestamp", "product_id", "event_timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    actor_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    product_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    event_timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="intentshelf_app", nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CartItemRecord(TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("actor_key", "product_id", name="uq_cart_items_actor_product"),
        Index("ix_cart_items_actor_updated", "actor_key", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_key: Mapped[str] = mapped_column(String(160), index=True, nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    product_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_type_name: Mapped[str | None] = mapped_column(String(255))
    product_group_name: Mapped[str | None] = mapped_column(String(255))
    image_path: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class FeedRequestLogRecord(Base):
    __tablename__ = "feed_request_logs"
    __table_args__ = (
        Index("ix_feed_request_logs_strategy_created", "ranking_strategy", "created_at"),
        Index("ix_feed_request_logs_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    request_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    ranking_strategy: Mapped[str | None] = mapped_column(String(64), index=True)
    query: Mapped[str | None] = mapped_column(Text)
    anchor_product_id: Mapped[str | None] = mapped_column(String(32), index=True)
    returned_candidate_count: Mapped[int | None] = mapped_column(Integer)
    blended_candidate_count: Mapped[int | None] = mapped_column(Integer)
    request_metadata: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

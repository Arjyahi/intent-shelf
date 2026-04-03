"""Add runtime persistence tables for sessions, events, cart, and feed logs."""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("session_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_surface", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "session_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source_surface", sa.String(length=64), nullable=False),
        sa.Column("product_id", sa.String(length=32), nullable=True),
        sa.Column("rank_position", sa.Integer(), nullable=True),
        sa.Column("source_candidate_type", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_session_events_event_id", "session_events", ["event_id"])
    op.create_index("ix_session_events_session_id", "session_events", ["session_id"])
    op.create_index("ix_session_events_user_id", "session_events", ["user_id"])
    op.create_index("ix_session_events_event_type", "session_events", ["event_type"])
    op.create_index("ix_session_events_source_surface", "session_events", ["source_surface"])
    op.create_index("ix_session_events_product_id", "session_events", ["product_id"])
    op.create_index(
        "ix_session_events_session_timestamp",
        "session_events",
        ["session_id", "event_timestamp"],
    )
    op.create_index(
        "ix_session_events_product_timestamp",
        "session_events",
        ["product_id", "event_timestamp"],
    )

    op.create_table(
        "search_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("num_results", sa.Integer(), nullable=True),
        sa.Column("strategy_used", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_search_events_event_id", "search_events", ["event_id"])
    op.create_index("ix_search_events_session_id", "search_events", ["session_id"])
    op.create_index("ix_search_events_user_id", "search_events", ["user_id"])
    op.create_index("ix_search_events_request_id", "search_events", ["request_id"])
    op.create_index(
        "ix_search_events_session_timestamp",
        "search_events",
        ["session_id", "event_timestamp"],
    )
    op.create_index(
        "ix_search_events_user_timestamp",
        "search_events",
        ["user_id", "event_timestamp"],
    )

    op.create_table(
        "impression_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("surface", sa.String(length=64), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("ranking_strategy", sa.String(length=64), nullable=False),
        sa.Column("primary_source", sa.String(length=64), nullable=True),
        sa.Column("candidate_sources", sa.JSON(), nullable=True),
        sa.Column("explanation_reason", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_impression_events_event_id", "impression_events", ["event_id"])
    op.create_index("ix_impression_events_session_id", "impression_events", ["session_id"])
    op.create_index("ix_impression_events_user_id", "impression_events", ["user_id"])
    op.create_index("ix_impression_events_product_id", "impression_events", ["product_id"])
    op.create_index("ix_impression_events_surface", "impression_events", ["surface"])
    op.create_index("ix_impression_events_ranking_strategy", "impression_events", ["ranking_strategy"])
    op.create_index("ix_impression_events_request_id", "impression_events", ["request_id"])
    op.create_index(
        "ix_impression_events_session_timestamp",
        "impression_events",
        ["session_id", "event_timestamp"],
    )
    op.create_index(
        "ix_impression_events_request_rank",
        "impression_events",
        ["request_id", "rank_position"],
    )
    op.create_index(
        "ix_impression_events_strategy_timestamp",
        "impression_events",
        ["ranking_strategy", "event_timestamp"],
    )

    op.create_table(
        "like_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("actor_key", sa.String(length=160), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_like_events_event_id", "like_events", ["event_id"])
    op.create_index("ix_like_events_actor_key", "like_events", ["actor_key"])
    op.create_index("ix_like_events_session_id", "like_events", ["session_id"])
    op.create_index("ix_like_events_user_id", "like_events", ["user_id"])
    op.create_index("ix_like_events_product_id", "like_events", ["product_id"])
    op.create_index(
        "ix_like_events_actor_timestamp",
        "like_events",
        ["actor_key", "event_timestamp"],
    )
    op.create_index(
        "ix_like_events_product_timestamp",
        "like_events",
        ["product_id", "event_timestamp"],
    )

    op.create_table(
        "save_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("actor_key", sa.String(length=160), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index("ix_save_events_event_id", "save_events", ["event_id"])
    op.create_index("ix_save_events_actor_key", "save_events", ["actor_key"])
    op.create_index("ix_save_events_session_id", "save_events", ["session_id"])
    op.create_index("ix_save_events_user_id", "save_events", ["user_id"])
    op.create_index("ix_save_events_product_id", "save_events", ["product_id"])
    op.create_index(
        "ix_save_events_actor_timestamp",
        "save_events",
        ["actor_key", "event_timestamp"],
    )
    op.create_index(
        "ix_save_events_product_timestamp",
        "save_events",
        ["product_id", "event_timestamp"],
    )

    op.create_table(
        "cart_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_key", sa.String(length=160), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("product_id", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("product_type_name", sa.String(length=255), nullable=True),
        sa.Column("product_group_name", sa.String(length=255), nullable=True),
        sa.Column("image_path", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("actor_key", "product_id", name="uq_cart_items_actor_product"),
    )
    op.create_index("ix_cart_items_actor_key", "cart_items", ["actor_key"])
    op.create_index("ix_cart_items_session_id", "cart_items", ["session_id"])
    op.create_index("ix_cart_items_user_id", "cart_items", ["user_id"])
    op.create_index("ix_cart_items_product_id", "cart_items", ["product_id"])
    op.create_index("ix_cart_items_actor_updated", "cart_items", ["actor_key", "updated_at"])

    op.create_table(
        "feed_request_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("request_kind", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.String(length=128), nullable=True),
        sa.Column("ranking_strategy", sa.String(length=64), nullable=True),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("anchor_product_id", sa.String(length=32), nullable=True),
        sa.Column("returned_candidate_count", sa.Integer(), nullable=True),
        sa.Column("blended_candidate_count", sa.Integer(), nullable=True),
        sa.Column("request_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("ix_feed_request_logs_request_id", "feed_request_logs", ["request_id"])
    op.create_index("ix_feed_request_logs_session_id", "feed_request_logs", ["session_id"])
    op.create_index("ix_feed_request_logs_user_id", "feed_request_logs", ["user_id"])
    op.create_index("ix_feed_request_logs_ranking_strategy", "feed_request_logs", ["ranking_strategy"])
    op.create_index("ix_feed_request_logs_anchor_product_id", "feed_request_logs", ["anchor_product_id"])
    op.create_index(
        "ix_feed_request_logs_strategy_created",
        "feed_request_logs",
        ["ranking_strategy", "created_at"],
    )
    op.create_index(
        "ix_feed_request_logs_session_created",
        "feed_request_logs",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_feed_request_logs_session_created", table_name="feed_request_logs")
    op.drop_index("ix_feed_request_logs_strategy_created", table_name="feed_request_logs")
    op.drop_index("ix_feed_request_logs_anchor_product_id", table_name="feed_request_logs")
    op.drop_index("ix_feed_request_logs_ranking_strategy", table_name="feed_request_logs")
    op.drop_index("ix_feed_request_logs_user_id", table_name="feed_request_logs")
    op.drop_index("ix_feed_request_logs_session_id", table_name="feed_request_logs")
    op.drop_index("ix_feed_request_logs_request_id", table_name="feed_request_logs")
    op.drop_table("feed_request_logs")

    op.drop_index("ix_cart_items_actor_updated", table_name="cart_items")
    op.drop_index("ix_cart_items_product_id", table_name="cart_items")
    op.drop_index("ix_cart_items_user_id", table_name="cart_items")
    op.drop_index("ix_cart_items_session_id", table_name="cart_items")
    op.drop_index("ix_cart_items_actor_key", table_name="cart_items")
    op.drop_table("cart_items")

    op.drop_index("ix_save_events_product_timestamp", table_name="save_events")
    op.drop_index("ix_save_events_actor_timestamp", table_name="save_events")
    op.drop_index("ix_save_events_product_id", table_name="save_events")
    op.drop_index("ix_save_events_user_id", table_name="save_events")
    op.drop_index("ix_save_events_session_id", table_name="save_events")
    op.drop_index("ix_save_events_actor_key", table_name="save_events")
    op.drop_index("ix_save_events_event_id", table_name="save_events")
    op.drop_table("save_events")

    op.drop_index("ix_like_events_product_timestamp", table_name="like_events")
    op.drop_index("ix_like_events_actor_timestamp", table_name="like_events")
    op.drop_index("ix_like_events_product_id", table_name="like_events")
    op.drop_index("ix_like_events_user_id", table_name="like_events")
    op.drop_index("ix_like_events_session_id", table_name="like_events")
    op.drop_index("ix_like_events_actor_key", table_name="like_events")
    op.drop_index("ix_like_events_event_id", table_name="like_events")
    op.drop_table("like_events")

    op.drop_index("ix_impression_events_strategy_timestamp", table_name="impression_events")
    op.drop_index("ix_impression_events_request_rank", table_name="impression_events")
    op.drop_index("ix_impression_events_request_id", table_name="impression_events")
    op.drop_index("ix_impression_events_ranking_strategy", table_name="impression_events")
    op.drop_index("ix_impression_events_surface", table_name="impression_events")
    op.drop_index("ix_impression_events_product_id", table_name="impression_events")
    op.drop_index("ix_impression_events_user_id", table_name="impression_events")
    op.drop_index("ix_impression_events_session_id", table_name="impression_events")
    op.drop_index("ix_impression_events_event_id", table_name="impression_events")
    op.drop_table("impression_events")

    op.drop_index("ix_search_events_user_timestamp", table_name="search_events")
    op.drop_index("ix_search_events_session_timestamp", table_name="search_events")
    op.drop_index("ix_search_events_request_id", table_name="search_events")
    op.drop_index("ix_search_events_user_id", table_name="search_events")
    op.drop_index("ix_search_events_session_id", table_name="search_events")
    op.drop_index("ix_search_events_event_id", table_name="search_events")
    op.drop_table("search_events")

    op.drop_index("ix_session_events_product_timestamp", table_name="session_events")
    op.drop_index("ix_session_events_session_timestamp", table_name="session_events")
    op.drop_index("ix_session_events_product_id", table_name="session_events")
    op.drop_index("ix_session_events_source_surface", table_name="session_events")
    op.drop_index("ix_session_events_event_type", table_name="session_events")
    op.drop_index("ix_session_events_user_id", table_name="session_events")
    op.drop_index("ix_session_events_session_id", table_name="session_events")
    op.drop_index("ix_session_events_event_id", table_name="session_events")
    op.drop_table("session_events")

    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")

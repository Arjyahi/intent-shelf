from sqlalchemy import inspect, text


def test_db_session_fixture_connects(db_session) -> None:
    result = db_session.execute(text("SELECT 1")).scalar()

    assert result == 1


def test_alembic_upgrade_creates_runtime_tables(db_session) -> None:
    inspector = inspect(db_session.bind)
    table_names = set(inspector.get_table_names())

    assert {
        "sessions",
        "session_events",
        "search_events",
        "impression_events",
        "like_events",
        "save_events",
        "cart_items",
        "feed_request_logs",
    }.issubset(table_names)

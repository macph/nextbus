"""
Test models
"""
from nextbus import db, models


def test_request_log_initial(create_db):
    log = models.RequestLog.query.one()
    assert log.call_count == 0


def test_request_log_negative_limit(create_db):
    assert all(list(models.RequestLog.call(-1) for _ in range(10)))
    log = models.RequestLog.query.one()
    assert log.call_count == 10


def test_request_log_no_limit(create_db):
    assert all(list(models.RequestLog.call(None) for _ in range(10)))
    log = models.RequestLog.query.one()
    assert log.call_count == 10


def test_request_log_with_limit(create_db):
    log = models.RequestLog.query.one()

    assert all(list(models.RequestLog.call(5) for _ in range(5)))
    assert log.call_count == 5

    assert all(list(not models.RequestLog.call(5) for _ in range(5)))
    assert log.call_count == 10


def test_request_next_day(create_db):
    # Move the log to the previous day to test the count resetting
    statement = db.update(models.RequestLog).values(
        last_called=(
            models.RequestLog.last_called - db.cast("1 day", db.Interval)
        ),
        call_count=50,
    )
    db.session.execute(statement)

    log = models.RequestLog.query.one()
    assert log.call_count == 50

    assert models.RequestLog.call(5)
    assert log.call_count == 1

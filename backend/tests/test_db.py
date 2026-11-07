from app.db import DB


def test_concurrent_reads_do_not_fail(tmp_path):
    """Один общий коннект SQLite: без замка параллельные чтения давали InterfaceError и IndexError (500 в проде)."""
    import threading

    db = DB(str(tmp_path / "t.db"))
    uid = db.create_user("u", 8)
    errors: list[str] = []

    def work():
        try:
            for i in range(400):
                db.progress(uid, f"p{i % 20}")
                db.leaderboard()
        except Exception as exc:
            errors.append(repr(exc))

    threads = [threading.Thread(target=work) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors[:3]

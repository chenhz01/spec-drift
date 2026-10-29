"""A project with NO drift — used to prove the checker does not over-report."""


def health(database_up=True) -> dict:
    return {"status": "ok" if database_up else "degraded", "database": database_up}

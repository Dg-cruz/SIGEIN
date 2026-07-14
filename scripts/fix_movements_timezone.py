"""Aplica -3h nas movimentações gravadas em UTC (uma vez)."""
from sqlalchemy import text

from database import engine


def main() -> None:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE movements
                SET data = data - INTERVAL '3 hours'
                WHERE data IS NOT NULL
                """
            )
        )
        print(f"rows_updated={result.rowcount}")
        sample = conn.execute(
            text("SELECT id, data FROM movements ORDER BY id DESC LIMIT 5")
        ).fetchall()
        for row in sample:
            print(row)


if __name__ == "__main__":
    main()

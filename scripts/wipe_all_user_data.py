import asyncio

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


TRUNCATE_SQL = """
TRUNCATE TABLE
  answers,
  participants,
  sessions,
  questions,
  quizzes,
  users
RESTART IDENTITY
CASCADE;
"""


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(text(TRUNCATE_SQL))
        await db.commit()
    print("Deleted all users and related data (quizzes/questions/sessions/participants/answers).")


if __name__ == "__main__":
    asyncio.run(main())


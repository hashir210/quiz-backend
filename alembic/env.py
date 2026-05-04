import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logging.config import fileConfig
from sqlalchemy import create_engine
from alembic import context
from app.core.config import settings
from app.core.database import Base

# import ALL models so alembic can see them
from app.models.user import User
from app.models.quiz import Quiz, Question
from app.models.session import Session
from app.models.participant import Participant, Answer

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online():
    # Use sync driver for migrations (replace asyncpg with psycopg2)
    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    connectable = create_engine(sync_url)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()

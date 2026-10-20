from alembic import context
from sqlalchemy import create_engine, pool

from app.db import Base, database_url
from app import models  # noqa: F401 -- register tables with metadata


if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(database_url(), poolclass=pool.NullPool, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# 1. Import your Base and Models
from app.database import Base 
from app.models import Article

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. Link your models
target_metadata = Base.metadata

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    # Get URL from environment (Docker) or alembic.ini
    db_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        url=db_url,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True  # This helps detect column type changes
        )

        with context.begin_transaction():
            context.run_migrations()

# 3. Actually execute the function
run_migrations_online()

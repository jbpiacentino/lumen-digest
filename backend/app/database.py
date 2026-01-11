import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# If you use docker-compose, the hostname is the service name (e.g., 'db' or 'lumen-db')
# We use an environment variable or a fallback default
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://user:password@lumen-db:5432/lumen_db"
)

# Connect to the database
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Create a session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# This is the "Base" class your migration uses
Base = declarative_base()

# Dependency for FastAPI (to get a DB session in routes)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

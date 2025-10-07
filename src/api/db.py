
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# --------------------------------------------------------------------
# Database Configuration
# --------------------------------------------------------------------

# Default to a local SQLite database if no DATABASE_URL environment variable is set.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./rag.db")


# Create the SQLAlchemy engine — the core interface to the database.
# 'future=True' ensures modern SQLAlchemy 2.0-style behavior.
engine = create_engine(DATABASE_URL, future=True)


# Create a configured "SessionLocal" class.
# Each instance of SessionLocal will serve as a database session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)



# Base class for all ORM models.
# Each table model will subclass this.
Base = declarative_base()

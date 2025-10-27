from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

Base = declarative_base()

class DbInitTest(Base):
    __tablename__ = "db_init_tests"
    id = Column(Integer, primary_key=True, index=True)
    testing_id = Column(String, index=True)

class User(Base):
    __tablename__ = "users"

    id          = Column(Integer, primary_key=True, index=True)
    sub         = Column(String, unique=True, index=True, nullable=False)  # Google permanent id
    email       = Column(String, index=True)
    given_name  = Column(String)
    family_name = Column(String)
    picture     = Column(String)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
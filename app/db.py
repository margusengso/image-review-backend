from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./data.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DbInitTest(Base):
    __tablename__ = "db_init_tests"
    id = Column(Integer, primary_key=True, index=True)
    testing_id = Column(String, index=True)

def init_db():
    Base.metadata.create_all(bind=engine)
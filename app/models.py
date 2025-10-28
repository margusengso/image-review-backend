from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, UniqueConstraint
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

    labels = relationship("LabelSubmission", back_populates="user", cascade="all, delete-orphan")


class TestImage(Base):
    """
    Images from the AWS manifest.json.
    We use the same `id` as provided in the manifest (e.g., "IMG_1150.jpeg").
    """
    __tablename__ = "test_images"

    id = Column(String, primary_key=True, index=True)  # matches manifest.json "id"
    url = Column(String, nullable=False)
    suggested_label = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    submissions = relationship("LabelSubmission", back_populates="image", cascade="all, delete-orphan")


class LabelSubmission(Base):
    """
    Final label provided by a human operator for a given image.
    One submission per (image_id, user_id) — upsert on repeat.
    """
    __tablename__ = "label_submissions"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(String, ForeignKey("test_images.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    label = Column(String, nullable=False)  # the human-provided label
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="labels")
    image = relationship("TestImage", back_populates="submissions")

    __table_args__ = (
        UniqueConstraint("image_id", "user_id", name="uq_submission_image_user"),
    )
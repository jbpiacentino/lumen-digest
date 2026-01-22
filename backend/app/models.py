from sqlalchemy import Column, Integer, String, Text, DateTime, func, Float, JSON, Boolean
from .database import Base

class Article(Base):
    __tablename__ = 'articles'
    
    id = Column(Integer, primary_key=True, autoincrement=True)

    freshrss_id = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    # description = Column(Text)
    summary = Column(Text)
    full_text = Column(Text)
    full_text_source = Column(String)
    full_text_format = Column(String)
    category_id = Column(String, nullable=False, index=True)
    confidence = Column(Float)
    needs_review = Column(Boolean)
    reason=Column(Text)
    runner_up_confidence=Column(Float)
    margin=Column(Float)
    review_status = Column(String)
    override_category_id = Column(String)
    review_flags = Column(JSON)
    review_note = Column(Text)
    language = Column(String)
    source = Column(String)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # raw = Column(JSON)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    

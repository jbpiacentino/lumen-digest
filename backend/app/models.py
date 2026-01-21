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
    

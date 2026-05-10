import uuid
from sqlalchemy import Column, String, DateTime, Boolean, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, index=True)
    description = Column(Text, default="")
    status = Column(String, default="draft", comment="项目状态：draft/planning/writing/auditing/completed/archived")

    template_id = Column(String, nullable=True, comment="使用的模板ID")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    config = relationship("ProjectConfig", back_populates="project", uselist=False, cascade="all, delete-orphan")

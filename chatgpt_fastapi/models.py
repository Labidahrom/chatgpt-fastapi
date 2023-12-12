from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
)
from sqlalchemy import Text as TextType
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass


class TextsParsingSet(Base):
    __tablename__ = 'texts_parsing_set'

    id = Column(Integer, primary_key=True)
    # author = relationship('User', backref='texts_parsing_sets')
    author = Column(UUID(as_uuid=True), ForeignKey('user.id'), nullable=False)
    average_attempts_to_uniqueness = Column(Integer, default=0)
    average_uniqueness = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    failed_texts = Column(TextType, default='')
    is_complete = Column(Boolean, default=False)
    low_uniqueness_texts = Column(TextType, default='')
    parsed_amount = Column(Integer, default=0)
    set_name = Column(String(500))
    task_strings = Column(TextType, default='')
    temperature = Column(Numeric(2, 1), default=0)
    total_amount = Column(Integer)

    def __str__(self):
        return self.set_name


class Text(Base):
    __tablename__ = 'text'

    id = Column(Integer, primary_key=True)
    attempts_to_uniqueness = Column(Integer)
    chat_request = Column(TextType)
    created_at = Column(DateTime, default=func.now())
    header = Column(TextType)
    parsing_set = relationship('TextsParsingSet', backref='texts')
    parsing_set_id = Column(Integer, ForeignKey('texts_parsing_set.id'), nullable=False)
    text = Column(TextType)
    uniqueness = Column(Integer)

    def __str__(self):
        return self.header

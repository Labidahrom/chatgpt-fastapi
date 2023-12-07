from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    Column, String, Integer, Boolean, ForeignKey, Text, DateTime, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func


Base = declarative_base()


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass


class TextsParsingSet(Base):
    __tablename__ = 'texts_parsing_set'

    id = Column(Integer, primary_key=True)
    set_name = Column(String(500))
    total_amount = Column(Integer)
    parsed_amount = Column(Integer, default=0)
    is_complete = Column(Boolean, default=False)
    author_id = Column(UUID(as_uuid=True), ForeignKey('user.id'), nullable=False)
    average_uniqueness = Column(Integer, default=0)
    average_attempts_to_uniqueness = Column(Integer, default=0)
    temperature = Column(Numeric(2,1), default=0)
    created_at = Column(DateTime, default=func.now())
    failed_texts = Column(Text, default='')
    low_uniqueness_texts = Column(Text, default='')
    task_strings = Column(Text, default='')
    author = relationship('User', backref='texts_parsing_sets')

    def __str__(self):
        return self.set_name


class Text(Base):
    __tablename__ = 'text'

    id = Column(Integer, primary_key=True)
    header = Column(Text)
    text = Column(Text)
    chat_request = Column(Text)
    uniqueness = Column(Integer)
    attempts_to_uniqueness = Column(Integer)
    parsing_set_id = Column(Integer, ForeignKey('texts_parsing_set.id'), nullable=False)
    created_at = Column(DateTime, default=func.now())

    parsing_set = relationship('TextsParsingSet', backref='texts')

    def __str__(self):
        return self.header

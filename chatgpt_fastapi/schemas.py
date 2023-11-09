from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel
from fastapi_users import schemas
import uuid
from chatgpt_fastapi.models import User


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass



class TextsParsingSetBase(BaseModel):
    set_name: str
    total_amount: int
    parsed_amount: int = 0
    is_complete: bool = False
    average_uniqueness: int = 0
    average_attempts_to_uniqueness: int = 0
    temperature: Decimal = 0
    failed_texts: str = ''
    low_uniqueness_texts: str = ''
    task_strings: str = ''

class TextsParsingSetCreate(TextsParsingSetBase):
    author_id: int

class TextsParsingSet(TextsParsingSetBase):
    id: int
    created_at: datetime
    author: UserRead

    class Config:
        orm_mode = True


class TextBase(BaseModel):
    header: str
    text: str
    chat_request: str
    uniqueness: int
    attempts_to_uniqueness: int

class TextCreate(TextBase):
    parsing_set_id: int

class Text(TextBase):
    id: int
    created_at: datetime
    parsing_set: TextsParsingSet

    class Config:
        orm_mode = True
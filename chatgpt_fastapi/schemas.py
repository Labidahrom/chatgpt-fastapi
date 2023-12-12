from datetime import datetime
from fastapi_users import schemas
from pydantic import BaseModel
from uuid import UUID


class UserRead(schemas.BaseUser[UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


class TextsParsingSetBase(BaseModel):
    average_uniqueness: int = 0
    average_attempts_to_uniqueness: int = 0
    failed_texts: str = ''
    is_complete: bool = False
    low_uniqueness_texts: str = ''
    parsed_amount: int = 0
    rewriting_task: str = ''
    required_uniqueness: int = 0
    set_name: str
    task_strings: str
    temperature: float = 0
    text_len: int = 0
    total_amount: int = 0


class TextsParsingSetCreate(TextsParsingSetBase):
    author_id: UUID


class TextsParsingSet(TextsParsingSetBase):
    id: int
    author: UserRead
    created_at: datetime

    class Config:
        orm_mode = True


class TextBase(BaseModel):
    attempts_to_uniqueness: int
    chat_request: str
    header: str
    text: str
    uniqueness: int


class TextCreate(TextBase):
    parsing_set_id: int


class Text(TextBase):
    id: int
    created_at: datetime
    parsing_set: TextsParsingSet

    class Config:
        orm_mode = True

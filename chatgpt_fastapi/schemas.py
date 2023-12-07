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
    set_name: str
    total_amount: int = 0
    parsed_amount: int = 0
    is_complete: bool = False
    average_uniqueness: int = 0
    average_attempts_to_uniqueness: int = 0
    temperature: float = 0
    failed_texts: str = ''
    low_uniqueness_texts: str = ''
    task_strings: str
    rewriting_task: str = ''
    required_uniqueness: int = 0
    text_len: int = 0

class TextsParsingSetCreate(TextsParsingSetBase):
    author_id: UUID

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
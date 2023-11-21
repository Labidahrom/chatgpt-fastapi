from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import RedirectResponse
from fastapi.responses import Response
from typing import Type
from chatgpt_fastapi.models import Base, TextsParsingSet, User
from pydantic import BaseModel
from chatgpt_fastapi.database import User, create_db_and_tables, get_async_session
from chatgpt_fastapi.parser import generate_texts
from chatgpt_fastapi.schemas import UserCreate, UserRead, UserUpdate, TextsParsingSetCreate, TextsParsingSetBase
from chatgpt_fastapi.users import auth_backend, current_active_user, fastapi_users

from fastapi import FastAPI, Depends

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import httpx

app = FastAPI()
current_user = fastapi_users.current_user()

templates = Jinja2Templates(directory="chatgpt_fastapi/templates")


def make_parsing_form(cls: Type[BaseModel]):
    async def _parse_form_data(request: Request):
        form = await request.form()
        print('form from request: in make_parsing_form', form)
        return cls(**form)

    return _parse_form_data


app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)


@app.get("/authenticated-route")
async def authenticated_route(user: User = Depends(current_active_user)):
    return {"message": f"Hello {user.email}!"}


@app.on_event("startup")
async def on_startup():
    await create_db_and_tables()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: User = Depends(fastapi_users.current_user(optional=True))):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/texts_list", response_class=HTMLResponse)
async def read_texts_parsing_sets(request: Request, user: User = Depends(fastapi_users.current_user()),
                                  session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(TextsParsingSet))
    parsing_sets = result.scalars().all()
    return templates.TemplateResponse("texts_parsing_sets.html", {"request": request, "user": user,
                                                                  "parsing_sets": parsing_sets})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request, user: User = Depends(fastapi_users.current_user(optional=True))):
    if user:
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        return response
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/auth/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie('fastapiusersauth')  # Deleting the JWT token cookie
    return response


@app.get("/generate_texts", response_class=HTMLResponse)
async def create_texts_task(request: Request, user: User = Depends(fastapi_users.current_user(optional=True))):
    if user:
        return templates.TemplateResponse("generate_texts.html", {"request": request, "user": user})
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/generate_texts")
async def generate_texts_endpoint(
        request: Request,
        user: User = Depends(fastapi_users.current_user(optional=True)),
        set_name: str = Form(...),
        temperature: float = Form(...),
        task_strings: str = Form(...),
        rewriting_task: str = Form(...),
        required_uniqueness: float = Form(...),
        text_len: int = Form(...),
        session: AsyncSession = Depends(get_async_session),
):
    if user:
        print('task_strings: ', task_strings)
        print('temperature: ', temperature)
        await generate_texts(author_id=user.id,
                             set_name=set_name,
                             temperature=temperature,
                             task_strings=task_strings,
                             rewriting_task=rewriting_task,
                             required_uniqueness=required_uniqueness,
                             text_len=text_len,
                             session=session)

        return RedirectResponse(url='/', status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

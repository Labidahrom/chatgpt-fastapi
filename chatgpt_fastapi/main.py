from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import RedirectResponse
from fastapi.responses import Response

from chatgpt_fastapi.models import Base, TextsParsingSet, User

from chatgpt_fastapi.database import User, create_db_and_tables, get_async_session
from chatgpt_fastapi.schemas import UserCreate, UserRead, UserUpdate
from chatgpt_fastapi.users import auth_backend, current_active_user, fastapi_users

from fastapi import FastAPI, Depends

from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import httpx


app = FastAPI()
current_user = fastapi_users.current_user()

templates = Jinja2Templates(directory="chatgpt_fastapi/templates")

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


@app.get("/texts_parsing_sets", response_class=HTMLResponse)
async def read_texts_parsing_sets(session: AsyncSession = Depends(get_async_session)):
    parsing_sets = await session.execute(select(TextsParsingSet))
    return parsing_sets


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request, user: User = Depends(fastapi_users.current_user(optional=True))):
    if user and user.is_authenticated:
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        return response
    return templates.TemplateResponse("login.html", {"request": request})



@app.post("/auth/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie('fastapiusersauth')  # Deleting the JWT token cookie
    return response


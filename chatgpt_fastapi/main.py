from chatgpt_fastapi.database import create_db_and_tables, get_async_session
from chatgpt_fastapi.models import TextsParsingSet, User
from chatgpt_fastapi.parser import generate_texts, get_text_set, generate_text_set_zip
from chatgpt_fastapi.schemas import UserCreate, UserRead, UserUpdate
from chatgpt_fastapi.users import auth_backend, current_active_user, fastapi_users
from fastapi import BackgroundTasks, Depends, FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Type


app = FastAPI()
current_user = fastapi_users.current_user()
templates = Jinja2Templates(directory="chatgpt_fastapi/templates")


def make_parsing_form(cls: Type[BaseModel]):
    async def _parse_form_data(request: Request):
        form = await request.form()
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
    result = await session.execute(select(TextsParsingSet).order_by(TextsParsingSet.id))
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
        background_tasks: BackgroundTasks,
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
        background_tasks.add_task(generate_texts,
                                  author_id=user.id,
                                  set_name=set_name,
                                  temperature=temperature,
                                  task_strings=task_strings,
                                  rewriting_task=rewriting_task,
                                  required_uniqueness=required_uniqueness,
                                  text_len=text_len,
                                  session=session
                                  )

        return RedirectResponse(url='/', status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/delete_text_set/{text_set_id}")
async def get_text_set_for_delete(request: Request, user: User = Depends(fastapi_users.current_user()),
                                  session: AsyncSession = Depends(get_async_session), text_set_id: int = None):
    text_set_to_delete = await get_text_set(text_set_id=text_set_id, session=session)

    if text_set_to_delete:
        return templates.TemplateResponse("delete_parsing_set.html", {"request": request,
                                                                      "set": text_set_to_delete,
                                                                      "user": user})
    else:
        return Response(content="Text set not found", status_code=404)


@app.post("/delete_text_set/{text_set_id}")
async def delete_text_set(request: Request, user: User = Depends(fastapi_users.current_user()),
                          session: AsyncSession = Depends(get_async_session), text_set_id: int = None):
    text_set_to_delete = await get_text_set(text_set_id=text_set_id, session=session)
    if text_set_to_delete:
        await session.delete(text_set_to_delete)
        await session.commit()
    return RedirectResponse(url='/texts_list', status_code=303)


@app.get("/download_text_set/{text_set_id}")
async def download_text_set(request: Request, user: User = Depends(fastapi_users.current_user()),
                            session: AsyncSession = Depends(get_async_session), text_set_id: int = None):
    zip_buffer = await generate_text_set_zip(session=session, text_set_id=text_set_id)

    def iterfile():
        yield from zip_buffer

    zip_buffer.seek(0)
    headers = {
        'Content-Disposition': f'attachment; filename="{text_set_id}.zip"'
    }

    return StreamingResponse(iterfile(), media_type='application/zip', headers=headers)

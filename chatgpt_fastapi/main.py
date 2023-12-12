from chatgpt_fastapi.database import create_db_and_tables, get_async_session
from chatgpt_fastapi.models import TextsParsingSet, User
from chatgpt_fastapi.services import generate_texts, get_text_set, generate_text_set_zip
from chatgpt_fastapi.schemas import UserCreate, UserRead, UserUpdate
from chatgpt_fastapi.users import auth_backend, fastapi_users
from fastapi import BackgroundTasks, Depends, FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI()
current_user = fastapi_users.current_user()
templates = Jinja2Templates(directory="chatgpt_fastapi/templates")

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"]
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


@app.on_event("startup")
async def on_startup():
    await create_db_and_tables()


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user: User = Depends(fastapi_users.current_user(optional=True))):
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/login", response_class=HTMLResponse)
async def login(request: Request, user: User = Depends(fastapi_users.current_user(optional=True))):
    if user:
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        return response
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/auth/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie('fastapiusersauth')
    return response


@app.get("/texts_list", response_class=HTMLResponse)
async def list_texts_parsing_sets(request: Request,
                                  session: AsyncSession = Depends(get_async_session),
                                  user: User = Depends(fastapi_users.current_user())):
    result = await session.execute(select(TextsParsingSet, User.email)
                                   .join(User, TextsParsingSet.author == User.id)
                                   .order_by(TextsParsingSet.id))
    parsing_sets = result.all()
    return templates.TemplateResponse("texts_parsing_sets.html",
                                      {"parsing_sets": parsing_sets,
                                       "request": request,
                                       "user": user})


@app.get("/delete_text_set/{text_set_id}")
async def get_text_set_for_delete(request: Request,
                                  session: AsyncSession = Depends(get_async_session),
                                  text_set_id: int = None,
                                  user: User = Depends(fastapi_users.current_user())):
    text_set_to_delete = await get_text_set(session=session, text_set_id=text_set_id)

    if text_set_to_delete:
        return templates.TemplateResponse("delete_parsing_set.html", {"request": request,
                                                                      "set": text_set_to_delete,
                                                                      "user": user})
    else:
        return Response(content="Text set not found", status_code=404)


@app.post("/delete_text_set/{text_set_id}")
async def delete_text_set(request: Request,
                          session: AsyncSession = Depends(get_async_session),
                          text_set_id: int = None,
                          user: User = Depends(fastapi_users.current_user())):
    text_set_to_delete = await get_text_set(session=session, text_set_id=text_set_id)
    if text_set_to_delete:
        await session.delete(text_set_to_delete)
        await session.commit()
    return RedirectResponse(url='/texts_list', status_code=303)


@app.get("/download_text_set/{text_set_id}")
async def download_text_set(request: Request,
                            session: AsyncSession = Depends(get_async_session),
                            text_set_id: int = None,
                            user: User = Depends(fastapi_users.current_user())):
    zip_buffer = await generate_text_set_zip(session=session, text_set_id=text_set_id)

    def iterfile():
        yield from zip_buffer

    zip_buffer.seek(0)
    headers = {
        'Content-Disposition': f'attachment; filename="{text_set_id}.zip"'
    }

    return StreamingResponse(iterfile(), headers=headers, media_type='application/zip')


@app.get("/generate_texts", response_class=HTMLResponse)
async def create_texts_task(request: Request, user: User = Depends(fastapi_users.current_user(optional=True))):
    if user:
        return templates.TemplateResponse("generate_texts.html", {"request": request, "user": user})
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/generate_texts")
async def send_generate_texts_form(
        request: Request,
        background_tasks: BackgroundTasks,
        required_uniqueness: float = Form(...),
        rewriting_task: str = Form(...),
        session: AsyncSession = Depends(get_async_session),
        set_name: str = Form(...),
        task_strings: str = Form(...),
        temperature: float = Form(...),
        text_len: int = Form(...),
        user: User = Depends(fastapi_users.current_user(optional=True))
):
    if user:
        background_tasks.add_task(generate_texts,
                                  author=user.id,
                                  required_uniqueness=required_uniqueness,
                                  rewriting_task=rewriting_task,
                                  session=session,
                                  set_name=set_name,
                                  temperature=temperature,
                                  task_strings=task_strings,
                                  text_len=text_len
                                  )

        return RedirectResponse(url='/', status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

import asyncio
from chatgpt_fastapi.models import User
from chatgpt_fastapi.database import async_session_maker
from dotenv import load_dotenv
import os
from passlib.context import CryptContext


load_dotenv()
USER_EMAIL = os.getenv("USER_EMAIL")
USER_PASSWORD = os.getenv("USER_PASSWORD")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_user(email: str, password: str):
    hashed_password = pwd_context.hash(password)

    new_user = User(
        email=email,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=True,
        is_verified=True,
    )

    async with async_session_maker() as session:
        session.add(new_user)
        await session.commit()

    print(f"User {email} created successfully.")


if __name__ == "__main__":
    asyncio.run(create_user(USER_EMAIL, USER_PASSWORD))

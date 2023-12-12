import asyncio
from chatgpt_fastapi.database import get_async_session
from chatgpt_fastapi.models import TextsParsingSet, Text, User
from chatgpt_fastapi.randomizer import RANDOMIZER_STRINGS
from dotenv import load_dotenv
from fastapi import Depends
from httpx import AsyncClient
from io import BytesIO
import logging
import openai
import os
import psutil
import random
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID
import zipfile

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API")
TEXTRU_KEY = os.getenv("TEXTRU_KEY")
TEXTRU_URL = os.getenv("TEXTRU_URL")
LOG_LEVEL = os.getenv("LOG_LEVEL")

log_levels = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='parser.log',
    level=log_levels.get(LOG_LEVEL, logging.ERROR)
)


async def log_system_usage():
    cpu_usage = await asyncio.to_thread(psutil.cpu_percent, interval=1, percpu=True)
    memory_usage = await asyncio.to_thread(psutil.virtual_memory)
    swap_memory_usage = await asyncio.to_thread(psutil.swap_memory)

    return (f"CPU Usage:\n{cpu_usage}\n"
            f"Memory usage:\n{memory_usage}\n"
            f"Swap usage:\n{swap_memory_usage}")


async def add_randomize_task(randomize_strings):
    return '\n'.join([random.choice(strings) for strings in randomize_strings])


async def get_text_set(session: AsyncSession = Depends(get_async_session), text_set_id: int = None):
    text_set_query = select(TextsParsingSet).where(TextsParsingSet.id == text_set_id)
    result = await session.execute(text_set_query)
    return result.scalars().first()


async def make_async_textru_call(*args, **kwargs):
    async with AsyncClient() as client:
        result = await client.post(*args, **kwargs)
    return result


async def get_text_from_openai(task, temperature):
    await asyncio.sleep(3)
    randomize_string = await add_randomize_task(RANDOMIZER_STRINGS)
    full_task = task + '\n' + randomize_string
    client = openai.AsyncOpenAI(
        api_key=OPENAI_API_KEY,
    )
    try:
        text_request = await client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": full_task,
                }
            ],
            model="gpt-3.5-turbo",
            temperature=float(temperature)
        )
        text = str(text_request.choices[0].message.content)
        status = 'ok'
        return {
            'text': text,
            'status': status
        }
    except openai.RateLimitError as e:
        error_details = f'Rate limit error: {e}'
    except openai.AuthenticationError as e:
        error_details = f'Authentication token error: {e}'
    except openai.APIConnectionError as e:
        error_details = f'Unable to connect to OpenAI server: {e}'
    except Exception as e:
        error_details = f'General OpenAI error: {e}'
    return {
        'text': None,
        'status': error_details
    }


async def add_text(text, text_len):
    task = (f'Допиши пожалуйста следующий текст,'
            f'что бы его длина составила {text_len}'
            f' символов или больше:\n{text}')
    return await get_text_from_openai(task, temperature=1)


async def raise_uniqueness(text, rewriting_task):
    task = f'{rewriting_task}\n{text}'
    return await get_text_from_openai(task, temperature=1)


async def get_text_uniqueness(text):
    await asyncio.sleep(20)
    headers = {
        "Content-Type": "application/json"
    }
    text_data = {
        "text": text,
        "userkey": TEXTRU_KEY
    }
    response = await make_async_textru_call(TEXTRU_URL, json=text_data, headers=headers)
    uid = response.json().get('text_uid')
    if not uid:
        return 0
    attempts = 0
    uid_data = {
        "uid": uid,
        "userkey": TEXTRU_KEY
    }
    while attempts < 10:
        attempts += 1
        if attempts < 5:
            await asyncio.sleep(20)
        await asyncio.sleep(60)
        response = await make_async_textru_call(TEXTRU_URL, json=uid_data, headers=headers)
        if 'text_unique' in response.json():
            return float(response.json()["text_unique"])
    return 0




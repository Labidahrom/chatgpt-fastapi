import asyncio

from chatgpt_fastapi.api_utils import get_text_from_openai
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


async def generate_text(
        header: str,
        rewriting_task: str,
        required_uniqueness: float,
        task: str,
        temperature: float,
        text_len: int
):
    logging.info(f"{header}: Starting text generation")
    openai_response = await get_text_from_openai(task, temperature)
    text = openai_response.get('text')
    if not text:
        error_details = openai_response.get('status')
        logging.error(f"{header}: Can't get text from OpenAI server: {error_details}. "
                      f"System usage:\n{await log_system_usage()}")
        return error_details

    add_text_counter = 0
    while text_len and (len(text) + 100 < text_len) and add_text_counter < 3:
        add_text_counter += 1
        logging.info(f"{header}: Low text length: {text_len}, trying to rewrite"
                     f"{add_text_counter} time")
        openai_response = await add_text(text, text_len)
        new_text = openai_response.get('text')
        if new_text:
            text = new_text
        else:
            error_details = openai_response.get('status')
            logging.error(f"{header}: During adding text can't get response from OpenAI server: "
                          f"{error_details}\nSystem usage:\n{await log_system_usage()}")
            # protection against duplicate requests has worked, break and leave the current text

            break

    text_uniqueness = await get_text_uniqueness(text)
    if text_uniqueness:
        uniqueness_check_status = 'да'
    else:
        logging.error(f"{header}: Can't get text uniqueness from text.ru server. System usage:"
                      f"\n{await log_system_usage()}")

        uniqueness_check_status = 'нет'

    make_text_unique_counter = 0
    while text_uniqueness < float(required_uniqueness) and make_text_unique_counter <= 2:
        make_text_unique_counter += 1
        logging.info(f"{header}: Low uniqueness: {text_uniqueness}, trying to rewrite"
                     f"{make_text_unique_counter} time")
        openai_response = await raise_uniqueness(text, rewriting_task)
        new_text = openai_response.get('text')
        if new_text:
            text = new_text
        else:
            error_details = openai_response.get('status')
            logging.error(f"{header}: During rewrite text for uniqueness can't get "
                          f"response from OpenAI server: {error_details}\nSystem usage:"
                          f"\n{await log_system_usage()}")
            # protection against duplicate requests has worked, break and leave the current text

            break
        logging.info(f"{header}: rewrite text")
        new_text_uniqueness = await get_text_uniqueness(text)
        if new_text_uniqueness:
            text_uniqueness = new_text_uniqueness
            logging.info(f"{header}: get uniqueness for rewrite text: {text_uniqueness}")
            uniqueness_check_status = 'да'
        else:
            logging.error(f"{header}: Can't get text uniqueness from text.ru server. "
                          f"System usage:\n{await log_system_usage()}")
            uniqueness_check_status = 'нет, дана уникальность предыдущей версии текста'
            # text.ru doesn't respond, leave previous uniqueness
            break

    logging.info(f"{header}: Text generation completed")
    return {
        'attempts_to_uniqueness': make_text_unique_counter,
        'text': text,
        'text_uniqueness': text_uniqueness,
        'uniqueness_check_status': uniqueness_check_status
    }


async def generate_text_set_zip(session: AsyncSession, text_set_id: int):
    buffer = BytesIO()

    text_set_query = select(TextsParsingSet).options(selectinload(TextsParsingSet.texts)).where(
        TextsParsingSet.id == text_set_id)
    result = await session.execute(text_set_query)
    text_set = result.scalars().first()

    with zipfile.ZipFile(buffer, 'a', zipfile.ZIP_DEFLATED, False) as zipf:
        for text in text_set.texts:
            text_content = (f"уникальность: {text.uniqueness}\n\n"
                            f"{text.header}\n"
                            f"{text.text}")
            header = text.header.replace('\r', '')
            zipf.writestr(f"{header}.txt", text_content)

        task_strings = text_set.task_strings
        failed_texts = text_set.failed_texts
        low_uniqueness_texts = text_set.low_uniqueness_texts
        zipf.writestr("запрос на тексты.txt", task_strings)
        if failed_texts:
            zipf.writestr("не получились.txt", failed_texts)
        if low_uniqueness_texts:
            zipf.writestr("тексты с низкой уникальностью.txt", low_uniqueness_texts)

    buffer.seek(0)
    return buffer


async def generate_texts(author_id: UUID,
                         rewriting_task: str,
                         required_uniqueness: float,
                         set_name: str,
                         task_strings: str,
                         temperature: float,
                         text_len: int,
                         session: AsyncSession = Depends(get_async_session)):
    logging.info(f"{set_name}: Starting text set generation\n{await log_system_usage()}")

    task_list = [task for task in task_strings.split('\n') if "||" in task]

    author = await session.get(User, author_id)

    new_set = TextsParsingSet(
        author=author,
        set_name=set_name,
        task_strings=task_strings,
        temperature=temperature,
        total_amount=len(task_list)
    )

    session.add(new_set)
    await session.commit()
    await session.refresh(new_set)

    tasks = [generate_text(
        header,
        rewriting_task,
        required_uniqueness,
        task,
        temperature,
        text_len
    ) for task, header in (task.split('||') for task in task_list)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for task, text_data in zip(task_list, results):
        task, header = task.split('||')

        if isinstance(text_data, dict):
            text = Text(
                attempts_to_uniqueness=text_data['attempts_to_uniqueness'],
                chat_request=task,
                header=header,
                parsing_set=new_set,
                text=text_data['text'],
                uniqueness=text_data['text_uniqueness'],
            )
            session.add(text)
        else:
            new_set.failed_texts += f'{task}&&{text_data}\n'

            if text_data['text_uniqueness'] < required_uniqueness:
                new_set.low_uniqueness_texts += (f"{task}||{text_data['text_uniqueness']}||"
                                                 f"Была ли получена уникальность текста? - "
                                                 f"{text_data['uniqueness_check_status']}\n")

            new_set.parsed_amount += 1
            await session.commit()
            await session.refresh(new_set)

    avg_uniqueness = await session.execute(
        select(func.avg(Text.uniqueness)).where(Text.parsing_set_id == new_set.id)
    )
    avg_attempts = await session.execute(
        select(func.avg(Text.attempts_to_uniqueness)).where(Text.parsing_set_id == new_set.id)
    )

    new_set.average_attempts_to_uniqueness = avg_attempts.scalar_one() or 0
    new_set.average_uniqueness = avg_uniqueness.scalar_one() or 0
    new_set.is_complete = True

    await session.commit()
    logging.info(f"{set_name}: Finish text set generation")
import asyncio
from chatgpt_fastapi.randomizer import add_randomize_task
from chatgpt_fastapi.database import get_async_session
from chatgpt_fastapi.models import TextsParsingSet, Text, User
from dotenv import load_dotenv
from fastapi import Depends
from httpx import AsyncClient
from io import BytesIO
import logging
import openai
import os
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from uuid import UUID
import zipfile


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API")
TEXTRU_KEY = os.getenv("TEXTRU_KEY")
TEXTRU_URL = "http://api.text.ru/post"
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


async def get_text_set(session: AsyncSession = Depends(get_async_session), text_set_id: int = None):
    text_set_query = select(TextsParsingSet).where(TextsParsingSet.id == text_set_id)
    result = await session.execute(text_set_query)
    return result.scalars().first()


async def make_async_textru_call(*args, **kwargs):
    async with AsyncClient() as client:
        result = await client.post(*args, **kwargs)
    return result


async def get_text_from_chat(task, temperature):
    await asyncio.sleep(3)
    randomize_string = await add_randomize_task()
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
    return await get_text_from_chat(task, temperature=1)


async def raise_uniqueness(text, rewriting_task):
    task = f'{rewriting_task}\n{text}'
    return await get_text_from_chat(task, temperature=1)


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


async def generate_text(
        header: str,
        rewriting_task: str,
        required_uniqueness: float,
        task: str,
        temperature: float,
        text_len: int
        ):
    logging.info(f"{header}: Starting text generation")
    openai_response = await get_text_from_chat(task, temperature)
    text = openai_response.get('text')
    if not text:
        error_details = openai_response.get('status')
        logging.error(f"{header}: Can't get text from OpenAI server: {error_details}")
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
                          f"{error_details}")
            # protection against duplicate requests has worked, break and leave the current text
            break

    text_uniqueness = await get_text_uniqueness(text)
    if text_uniqueness:
        uniqueness_check_status = 'да'
    else:
        logging.error(f"{header}: Can't get text uniqueness from text.ru server")
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
            logging.error(f"{header}: During rewrite text for uniqueness can't get response "
                          f"from OpenAI server: {error_details}")
            # protection against duplicate requests has worked, break and leave the current text
            break
        logging.info(f"{header}: rewrite text")
        new_text_uniqueness = await get_text_uniqueness(text)
        if new_text_uniqueness:
            text_uniqueness = new_text_uniqueness
            logging.info(f"{header}: get uniqueness for rewrite text: {text_uniqueness}")
            uniqueness_check_status = 'да'
        else:
            logging.error(f"{header}: Can't get text uniqueness from text.ru server")
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
                         set_name: str,
                         temperature: float,
                         task_strings: str,
                         rewriting_task: str,
                         required_uniqueness: float,
                         text_len: int,
                         session: AsyncSession = Depends(get_async_session)):
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




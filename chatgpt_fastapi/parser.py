from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
import asyncio
import httpx
import zipfile
from io import BytesIO
from fastapi import Depends
from sqlalchemy import select, func
from uuid import UUID
from chatgpt_fastapi.models import TextsParsingSet, Text, User
from chatgpt_fastapi.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API")
TEXTRU_KEY = os.getenv("TEXTRU_KEY")
TEXTRU_URL = "http://api.text.ru/post"


async def make_async_textru_call(*args, **kwargs):
    async with httpx.AsyncClient() as client:
        result = await client.post(*args, **kwargs)
    return result


async def get_text_from_chat(task, temperature):
    await asyncio.sleep(10)
    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
    )
    print('начала работать функция get_text_from_chat')

    result = await client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": task,
            }
        ],
        model="gpt-3.5-turbo",
        temperature=float(temperature)
    )
    print('полученный текст', result.choices[0].message.content)
    return str(result.choices[0].message.content) if result else None


async def add_text(text, text_len):
    task = (f'Допиши пожалуйста следующий текст,'
            f'что бы его длина составила {text_len}'
            f' символов или больше:\n{text}')
    result = await get_text_from_chat(task, temperature=1)

    return result


async def raise_uniqueness(text, rewriting_task):
    task = (f'{rewriting_task}\n{text}')
    result = await get_text_from_chat(task, temperature=1)

    return result['choices'][0]['message']['content']


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
    uid = response.json()['text_uid']
    attempts = 0
    uid_data = {
        "uid": uid,
        "userkey": TEXTRU_KEY
    }
    while attempts < 10:
        if attempts < 5:
            await asyncio.sleep(20)
        await asyncio.sleep(60)
        response = await make_async_textru_call(TEXTRU_URL, json=uid_data, headers=headers)
        if 'text_unique' in response.json():
            return float(response.json()["text_unique"])
        attempts += 1
    print('\nне удалось получить уникальность текста')


async def generate_text(task, temperature, rewriting_task, required_uniqueness, text_len):
    print('запускаем внутреннюю функцию generate_text')
    try:
        text = await get_text_from_chat(task, temperature)
        counter = 0
        print('запускаем проверку на длину')
        while text_len and len(text) + 100 < text_len:
            counter += 1
            print(
                f'\nдописали текст в {counter} раз, длина: {len(text)}. Отправили переписываться по новой\n')
            text = await add_text(text, text_len)
        print('\nполучили текст достаточной длины, щас будем считать уникальность')
        text_uniqueness = await get_text_uniqueness(text)
        print('\nполучили уникальность:', text_uniqueness)
        attempts_to_uniqueness = 0
        while text_uniqueness < float(required_uniqueness) and attempts_to_uniqueness <= 3:
            text = await raise_uniqueness(text, rewriting_task)
            print('\nпереписали текст')
            text_uniqueness = await get_text_uniqueness(text)
            print('\nпересчитали уникальность: ', text_uniqueness)
            attempts_to_uniqueness += 1
        print('\nполучили текст достаточной уникальности')
        return {
            'text': text,
            'attempts_to_uniqueness': 9999,
            'text_uniqueness': 9999
        }
    except Exception as e:
        print('не удалось выполнить задачу')
        print(f'Error: {e}')


def generate_text_set_zip(text_set):
    print('начали архивацию')
    buffer = BytesIO()

    with zipfile.ZipFile(buffer, 'a', zipfile.ZIP_DEFLATED, False) as zipf:
        texts = text_set.texts.all()
        for text in texts:
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
    print('начали работу')
    print('task_strings: ', task_strings)
    task_list = [task for task in task_strings.split('\n') if "||" in task]
    print('получили список задач: ', task_list)

    # Fetch the author object
    author = await session.get(User, author_id)

    # Create new TextsParsingSet
    new_set = TextsParsingSet(
        total_amount=len(task_list),
        author=author,
        set_name=set_name,
        temperature=temperature,
        task_strings=task_strings
    )
    print('создали новый сет')
    session.add(new_set)
    await session.commit()
    await session.refresh(new_set)

    tasks = [generate_text(chat_request, temperature, rewriting_task, required_uniqueness, text_len) for chat_request, _
             in (task.split('||') for task in task_list)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for task, text_data in zip(task_list, results):
        chat_request, header = task.split('||')
        print('обрабатываем результат генерации текста')

        if isinstance(text_data, Exception):
            # Handle exceptions if any
            print(f'Error during text generation for task {chat_request}: {text_data}')
            new_set.failed_texts += task + '\n'
        else:
            # Process the successful result
            if text_data:  # Ensure text_data is not None
                print('текст получился')
                text = Text(
                    header=header,
                    text=text_data['text'],
                    attempts_to_uniqueness=text_data['attempts_to_uniqueness'],
                    uniqueness=text_data['text_uniqueness'],
                    chat_request=chat_request,
                    parsing_set=new_set
                )
                session.add(text)
                print('добавили текст в базу данных')

                if text_data['text_uniqueness'] < required_uniqueness:
                    new_set.low_uniqueness_texts += f"{task}||{text_data['text_uniqueness']}\n"

                new_set.parsed_amount += 1
                await session.commit()
                await session.refresh(new_set)
                print('сохранили текст в базе данных')

    # Calculate average uniqueness and attempts
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
    print('закончили работу')


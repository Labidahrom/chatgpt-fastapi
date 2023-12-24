from chatgpt_fastapi.services import generate_text
import pytest


@pytest.mark.asyncio
async def test_generate_text(mocker):
    # Mock the slow function and return True always
    mocker.patch('chatgpt_fastapi.services.get_text_uniqueness', return_value=1)
    mocker.patch('chatgpt_fastapi.services.get_text_from_openai', return_value={
        'text': 'dkkjkjkj slkjdkljljlkj sljjjj',
        'status': 'ok'
    })
    result = await generate_text(
        header='fkdsjfskfj',
        rewriting_task='fkdsjfskfj',
        required_uniqueness=1,
        task='fkdsjfskfj',
        temperature=1,
        text_len=1
)
    assert result['text'] == 'dkkjkjkj slkjdkljljlkj sljjjj'

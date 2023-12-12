# ChatGPT text generator
## What does this app do?
this application allows you to simultaneously generate a large number of texts at a time based on OpenAI text models. 
By default, it works with ChatGPT 3.5 turbo model is accessed, but can be easily changed to other models, for example 
ChatGPT 4 turbo. Additional features include text checks for:
 - **Uniqueness:** If the uniqueness threshold is below the level you set, the text will be sent for rewriting.
 - **Length:** If the text length is less than what you set, the text will be sent for extension.

## System requirements
- Linux
- Python (3.10 or later)
- Poetry

## Installation
1. If Poetry package manager is not installed, install it according to the guide at 
https://python-poetry.org/docs/#installing-with-the-official-installer
2. Clone repository and install all dependencies:
```
git clone https://github.com/Labidahrom/chatgpt-fastapi.git
cd chatgpt-fastapi
poetry install
```
3. Create a **.env** file at the root directory of the project. In .env, you need to specify variables for 
connecting to the database:
- DATABASE_URL
- DATABASE_USER
- DATABASE_PASSWORD
- DATABASE_NAME  

Security Key for Token Encryption:
- SECRET  

Data for connecting to OpenAI and Text.ru servers:
- OPENAI_API
- TEXTRU_KEY
- TEXTRU_URL  

4. To get the application running in right way, you also need to create the first user. You can use the 
add_new_user_script.py script to achieve this. Run the script:
```
env USER_EMAIL=your_user_email@gmail.com USER_PASSWORD=your_password poetry run python add_new_user_script.py
```
5. Start the application with the command:
```
poetry run uvicorn chatgpt_fastapi.main:app --reload
```
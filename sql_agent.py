import requests, re, io
from typing import List
import pandas as pd
from db import conn
import db
from session import model, key


sys_msg = {'role':'system', 'content':
    """You are a professional developer and Data Engineer.
    You can write correct and high-quality SQL queries based on a user message.

    At the moment, you are interacting with a Database that contains all the necessary information to respond to a user request.
    The key table that you need to query is called {table_name}
    This table consists of the following key columns:
    {fields_description}

    Use all your knowledge of writing SQL queries.
    Competently analyze the user's request and what the user wants to receive.
    Also consider the correct column names and their data types in the table you are accessing.

    Write an SQL query that will be able to get the most relevant data from the table at the user's request.
    Strictly follow the following response format:

    ```sql
    [SQL query]
    If for task completion several queries are required you put them is seperate ```sql blocks.
    If user query does not require any sql e.g. "привет" "как ты работаешь" then send first 5 rows of the table.
    If user asks for general info about the table/column you give general statistics using SQL aggregate functions (like COUNT, MIN, MAX, AVG, etc) or first 50 rows
    You don't need to write any explanations and comments before and after the code, STRICTLY follow this rule:"""
    }

# Извлечение SQL блоков (индивидульные SQL запросы) в список для будущего исполнения
def extract_sql_blocks(text: str) -> List[str]:
        # Извлекаем из ```sql ... ``` блоков
        blocks = re.findall(r"```sql\s*(.*?)\s*```", text, re.DOTALL)

        # Фоллбэк: ищем одиночные SQL-запросы вне блоков
        fallback_matches = re.findall(r"(?i)\b(?:SELECT|PRAGMA)\b\s+.*?;", text, re.DOTALL)
        cleaned = [b.strip().rstrip(";") + ";" for b in blocks + fallback_matches]
        
        print('EXTRACTED')
        
        return cleaned

# Преобразование Excel/CSV таблиц в SQL
def parse_attachment(file_name: str, file_content: str) -> pd.DataFrame:
        ext = file_name.lower().split(".")[-1]
        content_bytes = file_content.encode("latin1")
        
        print('PARSED')

        # Excel файлы
        if ext in ["xlsx", "xls", 'xlsm', 'xlsb', 'odf', 'ods', 'odt']:
            return pd.read_excel(io.BytesIO(content_bytes), engine="openpyxl")
        # Файлы с расширением .csv
        elif ext == "csv":
            return pd.read_csv(io.BytesIO(content_bytes))
        else:
            raise ValueError(f"Неподдерживаемое расширение файла: {ext}")

# Генерация SQL запросов, их обработка и отправка первому агенту
def generate_sql(message: str, file_name: str, file_content: str, table_name: str = 'data') -> str:
    user_message = {
        'role': 'user',
        "content": message,
    }
    
    # Проверка на то, была ли таблица преобразована в SQL
    if not db.is_sql:
        parse_attachment(file_name, file_content).to_sql(table_name, conn, index=False, if_exists='replace')
        db.columns = parse_attachment(file_name, file_content).columns
        db.is_sql = True
    
    # Заполнение систеемного сообщения данными о таблице (название + столбцы)
    sys_msg['content'] = sys_msg["content"].format(table_name=table_name, fields_description=db.columns)
    
    headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    data = {
        "model": model,
        "messages": [sys_msg, user_message],
        "temperature": 0.1
    }

    response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=data)

    # Если при генерации ответа был получен код ответа отличный от 200 (успешно), выводим сообщениес сервера
    if response.status_code != 200:
        raise Exception(f"Mistral API error: {response.status_code} - {response.text}")
    
    # Получаем список SQL блоков (отдельных запросов)
    sql_blocks = extract_sql_blocks(response.json()["choices"][0]["message"]["content"].strip())

    # Берём подключение к БД
    con = conn
    
    sql_results = ''

    # Сохраняем результаты каждого из SQL блоков в переменную sql_results
    for sql in sql_blocks:
        result_df = pd.read_sql_query(sql, con)
        result_text = result_df.to_string(index = False)
        sql_results += result_text+'\n'

    print('SQL to results')
    
    # Передаём SQL запросы и их результаты первому агенту для понимания контекста результатов
    return {"role":"user",
            "content":f"SQL queries: {response.json()["choices"][0]["message"]["content"].strip()}\nSQL query results: {sql_results}"}

if __name__ == "__main__":
    user = input()
    file_path = re.sub(r"'", "", input("Путь к Excel-файлу: "))
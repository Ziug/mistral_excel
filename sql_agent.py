import requests, re, io
from typing import List
import pandas as pd
from db import conn
import db
from session import model, key, sql_sys_msg
import session

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
def generate_sql(message: str, file_name: str, file_content: str, context: str, table_name: str = 'data', need_excel: bool = False) -> dict:
    sys_msg = sql_sys_msg
        
    if context:
        full_message = f"Контекст предыдущего запроса: {context}\nТекущий запрос: {message}"
    else:
        full_message = message

    user_message = {
        'role': 'user',
        "content": full_message,
    }
    
    # Проверка на то, была ли таблица преобразована в SQL
    parse_attachment(file_name, file_content).to_sql(table_name, conn, index=False, if_exists='replace')
    db.columns = parse_attachment(file_name, file_content).columns
    db.df = parse_attachment(file_name, file_content)
    db.is_sql = True
    
    for col in db.columns:
        db.col_uniques[col]=db.df[col].unique()[:10]
    
    if not session.sql_sys_formated:
        # Заполнение систеемного сообщения данными о таблице (название + столбцы)
        sql_sys_msg['content'] = sql_sys_msg["content"].format(table_name=table_name, fields_description=db.columns, fields_uniques=db.col_uniques)
        session.sql_sys_formated = True
    
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
    excel_buffer = io.BytesIO()
    cursor = conn.cursor()

    # Объединённый результат всех SQL-запросов в один DataFrame (если нужно сохранять в файл)
    combined_df = pd.DataFrame()

    # Сохраняем результаты каждого из SQL блоков в переменную sql_results
    # for sql in sql_blocks:
    #     result_df = pd.read_sql_query(sql, con)
    #     result_text = result_df.to_string(index = False)
    #     sql_results += result_text+'\n'
        
    #     combined_df = pd.concat([combined_df, result_df], ignore_index=True)
    
    for sql in sql_blocks:
        sql_lower = sql.strip().lower()

        try:
            if sql_lower.startswith("select"):
                # Сохраняем последний SELECT-запрос, только его экспортируем в Excel
                select_result_df = pd.read_sql_query(sql, conn)
                result_text = select_result_df.to_string(index=False)
                sql_results += result_text + '\n'
                combined_df = pd.concat([combined_df, select_result_df], ignore_index=True)
            elif sql_lower.startswith(("delete", "update", "insert", "create", "drop")):
                cursor.execute(sql)
                conn.commit()
            else:
                sql_results += f"[НЕПОДДЕРЖИВАЕМЫЙ ТИП SQL]: {sql}\n"
        except Exception as e:
            sql_results += f"[ОШИБКА выполнения SQL]: {sql}\n{str(e)}\n"

    print('SQL to results')
    
    # print(need_excel)
    
    
    if need_excel:
        combined_df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)  # возвращаем указатель в начало
        
        
        if need_excel:
            sql_results = 'без результатов так как был запрос на создание экселя'
        
        # Передаём SQL запросы и их результаты первому агенту для понимания контекста результатов + excel_buffer для создания excel документа
        return {
            "role": "user",
            "content": f"SQL queries: {response.json()['choices'][0]['message']['content'].strip()}\nSQL query results: {sql_results}",
            "excel_buffer": excel_buffer
        }
        
    # Передаём SQL запросы и их результаты первому агенту для понимания контекста результатов
    return {
        "role": "user",
        "content": f"SQL queries: {response.json()['choices'][0]['message']['content'].strip()}\nSQL query results: {sql_results}"
    }

if __name__ == "__main__":
    user = input()
    file_path = re.sub(r"'", "", input("Путь к Excel-файлу: "))
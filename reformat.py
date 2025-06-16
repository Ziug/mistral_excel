from typing import List
import requests, sql_agent, re
from session import model, key

sys_msg = {'role':'system', 'content':
    """You are a smart model that competently analyzes a user request and is able to follow system instructions.
    Due to internal knowledge, you need to create one paraphrased copy based on a message from the user.
    You must correctly select synonyms, similar words and the meaning of the phrase for the correct copy.
    Analyze the user's query in depth to form the correct copy.

    For the answer, use strictly the following structure:
    1. The first copy
    2. Нужно создать Excel: да/нет
    
    In the second point you MUST write "2. Нужно создать Excel: " without exceptions.

    Answer strictly in Russian.
    If the user explicitly asks to create a file, upload a table, save the result, edit a table, etc., basically edit the file in any way then specify "да" and at the of the first point add "и сохрани в excel".
    Also if the user asked before to make changes to the table and now asks to edit it without specifying of saving it you still specify "да". 
    If the user simply asks about a table (for example, "how many columns are in the table"), specify "нет".
    For a user request, issue 1 well-written, similar and relevant copy:"""
}

def get_previous_user_message(history: list[dict]) -> str:
    # Идём с конца и ищем последнее сообщение пользователя
    for msg in reversed(history[:-3]):  # пропускаем текущее
        if msg["role"] == "user":
            return msg["content"]
    return ""


# Обращение к ИИ
def reformat(message: str, history: List[dict]) -> str:
    previous = get_previous_user_message(history)
    
    context_block = f"Предыдущее сообщение пользователя (для контекста): {previous}" if previous else ""
    # print(context_block)

    user_message = {
        "role": "user",
        "content": f"{context_block}\nТекущий запрос пользователя: {message['content']}",
    }
    
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
        raise Exception(f"Mistral API error: {response.status_code} - {response.text[:100]}")
    
    match = re.search(r"1. (\s*.*\s)2. (\s*Нужно создать Excel: (да|нет|Да|Нет))", response.json()["choices"][0]["message"]["content"].strip(), re.DOTALL | re.IGNORECASE)
    if not match:
        user_message["content"]=f"Формат ответа нарушен:{response.json()["choices"][0]["message"]["content"].strip()}\n{user_message["content"]}"
        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=data)
        # raise ValueError("Формат ответа нарушен")

    rephrased = match.group(1).strip()
    need_excel = match.group(3).strip().lower() == "да"
    
    user_attachments = message.get("attachments", [])[0]
    
    new_prompt = rephrased
    # print("REFORMATTED:", new_prompt)

    # Обращение к SQL агенту, передаём переформатированный запрос юзера и данные о файле
    sql_res = sql_agent.generate_sql(
        new_prompt, 
        user_attachments["file_name"], 
        user_attachments["file_content"],
        need_excel=need_excel,
        context=previous
    )
    

    # return sql_res
    
    # sql_res = sql_agent.generate_sql(response.json()["choices"][0]["message"]["content"].strip(), 
    #                        user_attachments["file_name"], user_attachments["file_content"])
    
    
    if isinstance(sql_res, dict) and "excel_buffer" in sql_res:
        with open("result.xlsx", "wb") as f:
            f.write(sql_res["excel_buffer"].read())
        print("Excel-файл сохранён как result.xlsx")
        sql_res.pop("excel_buffer", None)
        return sql_res
    
    return sql_res

if __name__ == "__main__":
    ...
    # user = input()
    # print(reformat(user))
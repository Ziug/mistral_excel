import requests, sql_agent
from session import model, key

sys_msg = {'role':'system', 'content':
    """You are a smart model that competently analyzes a user request and is able to follow system instructions.
    Due to internal knowledge, you need to create one paraphrased copy based on a message from the user.
    You must correctly select synonyms, similar words and the meaning of the phrase for the correct copy.
    Analyze the user's query in depth to form the correct copy.

    For the answer, use strictly the following structure:
    1. The first copy

    Answer strictly in Russian.
    If the message provided by the user cannot be changed e.g. "повтори", "не понял", "что, это значит", etc., then just repeat the message without changes
    For a user request, issue 1 well-written, similar and relevant copy:"""
}


# Обращение к ИИ
def reformat(message: str) -> str:
    user_message = {
        'role': 'user',
        "content": message["content"],
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
    
    user_attachments = message.get("attachments", [])[0]
    
    print('REFORMAT')
    
    # Обращение к SQL агенту, передаём переформатированный запрос юзера и данные о файле
    sql_res = sql_agent.generate_sql(response.json()["choices"][0]["message"]["content"].strip(), 
                           user_attachments["file_name"], user_attachments["file_content"])
    
    return sql_res

if __name__ == "__main__":
    ...
    # user = input()
    # print(reformat(user))
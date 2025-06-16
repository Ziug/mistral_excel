"""
requirements: pandas, requests, sqlite3, pydantic, dotenv
"""

import reformat, session
import requests
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel
from session import message_history, key, model

class Pipeline:

    class Valves(BaseModel):
        mistral_api_key: str
        mistral_api_model: str

    def __init__(self):
        self.name = "SQL-over-Excel Mistral Pipeline"

        self.valves = self.Valves(
            mistral_api_key=key,  # <-- сюда вставь свой ключ
            mistral_api_model=model  # или mistral-medium / mistral-large
        ) 
        self.message_history = message_history
        
    # Генерация финального ответа - составление тела запроса и отправка в API
    def generate_answer(self, messages: List[dict]) -> str:        
        headers = {
            "Authorization": f"Bearer {self.valves.mistral_api_key}",
            "Content-Type": "application/json",
        }

        data = {
            "model": self.valves.mistral_api_model,
            "messages": messages,
            "temperature": 0.3
        }        

        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=data)

        # Если при генерации ответа был получен код ответа отличный от 200 (успешно), выводим сообщениес сервера
        if response.status_code != 200:
            raise Exception(f"Mistral API error: {response.status_code} - {response.text[:200]}")

        return response.json()["choices"][0]["message"]["content"].strip()


    # Обращения к другим агентам + составление истории
    def pipe(self, user_message: dict) -> Union[str, Generator, Iterator]:
        session.reset_session_timer()
        question = user_message["content"] # получаем текст сообщения
        attachments = user_message.get("attachments", []) # получаем инфо о файле

        if not attachments:
            return "Пожалуйста, прикрепите Excel-файл."

        # Если история пустая (начало диалога) добавляем в неё системное
        if not self.message_history:
            self.message_history.append({
                "role": "system",
                "content": (
                    """
                    Ты — опытный дата-аналитик. Пользователь задаёт вопросы к Excel-таблицам.
                    Никаких слов об SQL в вашем диалоге нет, пользователь в принципе не знает ничего об этом, поэтому поясняй без IT терминов и т.д. 
                    И от тебя никаких намёков о SQL не должно быть от слова совсем. 
                    Система сразу даст тебе SQL запросы и результаты к ним, которые (из-за ограничений) будут отправленны со стороны пользователя. Не упоминай эти SQL запросы пользователю.
                    Во время составления ответа не используй данные тебе SQL запросы, они служат контекстом для тебя, чтобы ты понимал откуда взялись те или иные результаты.
                    Перед тем как составить ответ проанализируй инфо, данное тебе от SQL агента.
                    """
                )
            })


        # Добавление в историю сообщения от пользователя 
        self.message_history.append({"role": "user", "content": question})
        
        # Кидаем сообщение от пользователя (текст + инфо о файле) агентам по переформатированию запроса и составлению SQL
        tools_response = reformat.reformat(user_message, self.message_history)
        
        # Добавление результата обращений к агентам (SQL запросы и их результаты)
        self.message_history.append(tools_response)
        
        # Удаление старых записей из истории, кроме предыдущей
        if len(self.message_history) == 6:
            self.message_history.pop(2)
        elif len(self.message_history) > 6:
            self.message_history.pop(1)
            self.message_history.pop(1)
            self.message_history.pop(2) # удаление предыдущих SQL запрососв
        
        # Генерация финального ответа и добавление его в историю
        answer = self.generate_answer(self.message_history)
        self.message_history.extend([{"role": "assistant", "content": answer}])
        
        # for i in self.message_history:
        #     print(i)

        return answer

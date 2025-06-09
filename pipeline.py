"""
requirements: pandas, requests, sqlite3, pydantic
"""

import sqlite3, re, reformat, session
import pandas as pd
import requests, io
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
        
    @staticmethod
    def extract_sql_blocks(text: str) -> List[str]:
        # Извлекаем из ```sql ... ``` блоков
        blocks = re.findall(r"```sql\s*(.*?)\s*```", text, re.DOTALL)

        # Фоллбэк: ищем одиночные SQL-запросы вне блоков
        fallback_matches = re.findall(r"(?i)\b(?:SELECT|PRAGMA)\b\s+.*?;", text, re.DOTALL)
        cleaned = [b.strip().rstrip(";") + ";" for b in blocks + fallback_matches]
        cut = len(cleaned)//2
        return cleaned[:cut]
    
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

        if response.status_code != 200:
            raise Exception(f"Mistral API error: {response.status_code} - {response.text[:200]}")

        return response.json()["choices"][0]["message"]["content"].strip()


    def pipe(self, user_message: dict) -> Union[str, Generator, Iterator]:
        session.reset_session_timer()
        question = user_message["content"]
        attachments = user_message.get("attachments", [])

        if not attachments:
            return "Пожалуйста, прикрепите Excel-файл."

        # Добавление системного сообщения и текущего вопроса в историю
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

        tools_response = reformat.reformat(user_message)

        self.message_history.append({"role": "user", "content": question})
        
        self.message_history.append(tools_response)
        
        if len(self.message_history) == 6:
            self.message_history.pop(2)
        elif len(self.message_history) > 6:
            self.message_history.pop(1)
            self.message_history.pop(1)
            self.message_history.pop(2)
        
        answer = self.generate_answer(self.message_history)
        
        self.message_history.extend([{"role": "assistant", "content": answer}])
        for i in self.message_history:
            print(i)
        # conn.close()
        # return answer

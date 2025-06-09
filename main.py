
import re, sys, signal
from pipeline import Pipeline
from db import conn
from session import end_session, reset_session_timer

conn = conn

# Сессионные переменные 
message_history = []
session_timeout = 1800 
session_timer = None


def main():
    pipeline = Pipeline()

    # Завершаем сессию при 30 минут безактивности
    def signal_handler(sig, frame):
        print("\nЗавершение программы.")
        end_session()
        conn.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    
    # Очистка пути до файла от опострава, который появляется при Drag And Drop
    file_path = re.sub(r"'", "", input("Путь к Excel-файлу: "))

    reset_session_timer()  # запустим при старте

    # Чтение файла 
    with open(file_path, "rb") as f:
            file_bytes = f.read()
            file_content = file_bytes.decode("latin1")

    # Запуск бесконечного цикла для диалога с ИИ
    while True:
        question = input("\nВопрос к таблице: ")
        reset_session_timer()

        if question.lower() in ['exit', 'выход']:
            end_session()
            break        

        user_message = {
            "content": question,
            "attachments": [{
                "file_id": "local-test",
                "file_name": file_path.split("/")[-1],
                "file_content": file_content
            }]
        }

        # Запрос в нейронку и получение ответа
        result = pipeline.pipe(user_message=user_message)
        print("\n=== Результат ===\n")
        print(result)
        

if __name__ == "__main__":
    main()
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

        if question.lower() in ["exit", "выход"]:
            end_session()
            break

        user_message = {
            "content": question,
            "attachments": [
                {
                    "file_id": "local-test",
                    "file_name": file_path.split("/")[-1],
                    "file_content": file_content,
                }
            ],
        }

        # Запрос в нейронку и получение ответа
        result = pipeline.pipe(user_message=user_message)
        print("\n=== Результат ===\n")
        print(result)


if __name__ == "__main__":
    main()


### Просится еще какой-нибудь .md файлик с результатами, прогнать его на 5-10 своих вопросах, можно заранее лучшие подготовить которые придумаешь, и вообще отлично будет

### Код чистый красивый, реализация мультиагентки адекватная, единственное что оформление её без классов и модульности (Больше функциональное) мне кажется не подходит, тут скорее история про ООП

### В целом довольно сложно по коду понять сам пайплайн, обычно у тебя весь блок использования ллм выносится в отдельный модуль, агенты с их системниками тоже отдельно, и там уже становится все читаемо и расширяемо

### Я попробую протестировать (Правда пока что мне не на чем) эти данные, но в целом жду результатов работы с датасетом который в репе, снова же 5-10 примеров и результат в .md

import pyperclip
import keyboard
import subprocess
import tkinter as tk
from tkinter import ttk
import threading
import time
import queue
import logging
import os

# Конфигурация
OLLAMA_PATH = r"C:\Users\Дмитрий\AppData\Local\Programs\Ollama\ollama.exe"
MODEL_NAME = "mistral"
HOTKEY = "ctrl+alt+q"
LOG_FILE = "ib_helper.log"
REQUEST_TIMEOUT = 30  # Таймаут запроса в секундах
RETRY_ATTEMPTS = 3  # Количество повторных попыток

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)


class IBHelperApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.tooltip = None
        self.request_queue = queue.Queue()
        self.setup_hotkey()

    def setup_hotkey(self):
        """Регистрация горячей клавиши"""
        try:
            keyboard.add_hotkey(HOTKEY, self.process_request)
            logging.info(f"Горячая клавиша '{HOTKEY}' зарегистрирована")
        except Exception as e:
            logging.error(f"Ошибка регистрации горячей клавиши: {e}")
            self.show_notification("Ошибка", "Не удалось зарегистрировать горячую клавишу")

    def process_request(self):
        """Обработка запроса по горячей клавише"""
        logging.info("Начата обработка запроса")

        selected_text = self.get_selected_text()
        if not selected_text:
            logging.warning("Не удалось получить выделенный текст")
            self.show_notification("Ошибка",
                                   "Не удалось получить выделенный текст. Убедитесь, что текст выделен и доступен для копирования.")
            return

        # Запуск обработки в отдельном потоке
        threading.Thread(
            target=self.worker_thread,
            args=(selected_text,),
            daemon=True
        ).start()

    def worker_thread(self, text):
        """Потоковая обработка запросов к локальной модели"""
        answer = self.ask_local_model(text)
        self.request_queue.put(answer)

    def ask_local_model(self, question):
        """Получение ответа от локальной модели через ollama.exe"""
        prompt = f"Максимально коротко отвечай на вопрос(не более 3 предложений). {question}"
        logging.info(f"Запрос к локальной модели: {prompt}")

        for attempt in range(RETRY_ATTEMPTS):
            try:
                result = subprocess.run(
                    [OLLAMA_PATH, "run", MODEL_NAME],
                    input=prompt.encode('utf-8'),
                    capture_output=True,
                    timeout=REQUEST_TIMEOUT
                )

                if result.returncode == 0:
                    answer = result.stdout.decode('utf-8').strip()
                    logging.info(f"Получен ответ: {answer[:100]}...")
                    return answer
                else:
                    logging.warning(f"Модель вернула ошибку: {result.stderr.decode('utf-8')}")
            except Exception as e:
                logging.warning(f"Попытка {attempt + 1} не удалась: {str(e)}")
                time.sleep(1)

        return "Ошибка: Нет ответа от модели"

    def get_selected_text(self):
        """Улучшенное получение выделенного текста"""
        try:
            # Попытка получить текущий буфер обмена
            clipboard_content = pyperclip.paste().strip()
            if clipboard_content:
                logging.info(f"Текст из буфера обмена: {clipboard_content[:50]}...")
                return clipboard_content

            # Если буфер пуст, пытаемся скопировать выделенный текст
            logging.debug("Буфер пуст, выполняем программное копирование")
            keyboard.send('ctrl+c')
            time.sleep(0.5)  # Увеличенная задержка

            # Повторное чтение буфера
            clipboard_content = pyperclip.paste().strip()
            if clipboard_content:
                logging.info(f"Скопирован текст: {clipboard_content[:50]}...")
                return clipboard_content
            else:
                logging.warning("Не удалось получить текст после копирования")
                return None

        except Exception as e:
            logging.error(f"Ошибка при получении текста: {e}")
            return None

    def show_notification(self, title, message):
        """Показ уведомления"""

        def create_popup():
            popup = tk.Toplevel()
            popup.title(title)
            popup.overrideredirect(True)
            popup.attributes("-topmost", True)
            popup.geometry("+100+100")

            style = ttk.Style()
            style.configure("Popup.TLabel",
                            background="#333",
                            foreground="white",
                            font=("Arial", 10),
                            padding=10)

            label = ttk.Label(popup, text=message, style="Popup.TLabel")
            label.pack()

            popup.after(3000, popup.destroy)

        self.root.after(0, create_popup)

    def check_queue(self):
        """Проверка очереди ответов"""
        try:
            answer = self.request_queue.get_nowait()
            self.show_tooltip(answer)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def show_tooltip(self, text):
        """Отображение ответа"""

        def create_tooltip():
            if self.tooltip:
                self.tooltip.destroy()

            self.tooltip = tk.Toplevel(self.root)
            self.tooltip.overrideredirect(True)
            self.tooltip.attributes("-topmost", True)
            self.tooltip.geometry("+100+100")

            # Анимация появления
            self.tooltip.attributes("-alpha", 0.0)
            for i in range(10):
                self.tooltip.attributes("-alpha", (i + 1) / 10)
                self.tooltip.update()
                time.sleep(0.02)

            style = ttk.Style()
            style.configure("Tooltip.TLabel",
                            background="#2d2d2d",
                            foreground="#e0e0e0",
                            font=("Arial", 10),
                            padding=10)

            label = ttk.Label(self.tooltip, text=text, style="Tooltip.TLabel")
            label.pack()
            label.bind("<Button-1>", lambda e: self.tooltip.destroy())  # Закрытие по клику

            # Автоматическое удаление
            self.tooltip.after(5000, self.tooltip.destroy)

        self.root.after(0, create_tooltip)

    def run(self):
        """Запуск приложения"""
        self.root.after(100, self.check_queue)
        try:
            self.root.mainloop()
        except Exception as e:
            logging.error(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    if not os.path.exists(OLLAMA_PATH):
        logging.error(f"Файл ollama.exe не найден по пути: {OLLAMA_PATH}")
        exit(1)

    app = IBHelperApp()
    app.run()
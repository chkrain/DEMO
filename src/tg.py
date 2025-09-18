# tg.py
from pyplc.core import POU
import requests
import time
import _thread  
from collections import deque

class TelegramMonitor(POU):
    def __init__(self, bot_token, chat_id):
        super().__init__()
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.message_queue = deque()
        self.running = True
        self.lock = _thread.allocate_lock()
        
        _thread.start_new_thread(self._send_messages_worker, ())
        
        self.send_message("Бот в сети")
    
    def send_message(self, message):     
        full_message = f"{message}"
        with self.lock:
            self.message_queue.append(full_message)
    
    def _send_messages_worker(self):
        while self.running:
            message = None
            with self.lock:
                if self.message_queue:
                    message = self.message_queue.popleft()
            
            if message:
                self._send_telegram_message(message)
            time.sleep(1)
    
    def _send_telegram_message(self, message):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"Ошибка отправки в Telegram: {response.text}")
        except Exception as e:
            print(f"Ошибка при отправке сообщения: {e}")
    
    def stop(self):
        self.running = False
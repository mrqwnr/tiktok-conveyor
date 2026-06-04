"""
text_engine.py — Генерация уникальных текстов и хэштегов через DeepSeek API
"""

import requests
import json
import os
import time
from typing import Optional


DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")


def generate_texts(prompt_context: str, count: int = 100, lang: str = "русский", api_key: Optional[str] = None) -> list:
"""Генерирует count уникальных текстов через DeepSeek. prompt_context — описание того, что продвигаем."""
key = api_key or DEEPSEEK_API_KEY
if not key:
    print("[TextEngine] Ошибка: не задан DEEPSEEK_API_KEY")
    return []

system_prompt = (
    f"Ты — креативный копирайтер. Твоя задача — генерировать короткие "
    f"тексты для видео в TikTok на языке: {lang}. "
    f"Каждый текст: 1-2 предложения, цепляющие, естественные. "
    f"В конце каждого текста — 5-10 релевантных хэштегов через пробел. "
    f"Тексты должны быть разными по формулировке, но об одном и том же."
)

user_prompt = (
    f"Сгенерируй ровно {count} уникальных текстов для видео про: {prompt_context}. "
    f"Каждый текст с новой строки. Формат одной строки:
"
    f"Текст с хэштегами
"
    f"Не нумеруй. Не добавляй лишнего."
)

all_texts = []
batch_size = 20

for batch_start in range(0, count, batch_size):
    remaining = count - batch_start
    current_batch = min(batch_size, remaining)

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Сгенерируй ровно {current_batch} текстов. {user_prompt}"}
        ],
        "temperature": 0.9,
        "max_tokens": 4000
    }

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        lines = [l.strip() for l in content.split("
") if l.strip() and not l.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "0"))]
        all_texts.extend(lines[:current_batch])

        print(f"[TextEngine] Батч {batch_start//batch_size + 1}: +{len(lines[:current_batch])} текстов")

    except Exception as e:
        print(f"[TextEngine] Ошибка батча {batch_start//batch_size + 1}: {e}")

    time.sleep(1)

print(f"[TextEngine] Всего сгенерировано: {len(all_texts)}/{count} текстов")
return all_texts


def save_texts(texts: list, output_path: str = "output/texts.txt"):
"""Сохраняет тексты в файл (по одному на строке)."""
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write("
".join(texts))
print(f"[TextEngine] Тексты сохранены: {output_path}")


def load_texts(input_path: str = "output/texts.txt") -> list:
"""Загружает тексты из файла."""
with open(input_path, "r", encoding="utf-8") as f:
    return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
texts = generate_texts("приложение для управления задачами и проектами", count=5)
for t in texts:
    print(t)
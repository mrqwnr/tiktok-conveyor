"""
text_engine.py — Генерация уникальных текстов и хэштегов через Gemini API (бесплатно)
"""

import requests
import json
import os
import time
from typing import Optional


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def generate_texts(prompt_context: str, count: int = 100, lang: str = "русский", api_key: Optional[str] = None) -> list:
"""Генерирует count уникальных текстов через Gemini (бесплатный тир)."""
key = api_key or GEMINI_API_KEY
if not key:
    print("[TextEngine] Ошибка: не задан GEMINI_API_KEY")
    return []

system_prompt = (
    f"Ты — креативный копирайтер для TikTok. Генерируй короткие тексты на языке: {lang}. "
    f"Каждый текст: 1-2 предложения, цепляющие, естественные. "
    f"В конце каждого текста — 5-10 релевантных хэштегов через пробел. "
    f"Тексты должны быть разными по формулировке, но об одном и том же."
)

all_texts = []
batch_size = 20

for batch_start in range(0, count, batch_size):
    remaining = count - batch_start
    current_batch = min(batch_size, remaining)

    prompt = (
        f"{system_prompt}\n\n"
        f"Сгенерируй ровно {current_batch} уникальных текстов для видео про: {prompt_context}.\n"
        f"Каждый текст с новой строки. Формат одной строки:\n"
        f"Текст с хэштегами\n"
        f"Не нумеруй. Не добавляй лишнего."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "maxOutputTokens": 4000
        }
    }

    try:
        resp = requests.post(
            f"{GEMINI_API_URL}?key={key}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        data = resp.json()

        # Gemini возвращает текст в candidates[0].content.parts[0].text
        content = data["candidates"][0]["content"]["parts"][0]["text"]

        lines = [l.strip() for l in content.split("\n") if l.strip() and not l.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.", "0"))]
        all_texts.extend(lines[:current_batch])
        print(f"[TextEngine] Батч {batch_start // batch_size + 1}: +{len(lines[:current_batch])} текстов")

    except Exception as e:
        print(f"[TextEngine] Ошибка батча {batch_start // batch_size + 1}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  Ответ: {e.response.text[:200]}")

    time.sleep(1)

print(f"[TextEngine] Всего сгенерировано: {len(all_texts)}/{count} текстов")
return all_texts


def save_texts(texts: list, output_path: str = "output/texts.txt"):
"""Сохраняет тексты в файл (по одному на строке)."""
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(texts))
print(f"[TextEngine] Тексты сохранены: {output_path}")


def load_texts(input_path: str = "output/texts.txt") -> list:
"""Загружает тексты из файла."""
with open(input_path, "r", encoding="utf-8") as f:
    return [line.strip() for line in f if line.strip()]


if __name__ == "__main__":
texts = generate_texts("приложение для управления задачами и проектами", count=5)
for t in texts:
    print(t)
#!/usr/bin/env python3
"""
tiktok-conveyor — главный оркестратор

Использование:
1. Кладёшь демо-видео в input/
2. Создаёшь accounts.txt (логин/пароль построчно)
3. Задаёшь DEEPSEEK_API_KEY (или ставишь в .env)
4. Запускаешь: python main.py --mode full

Режимы:
--mode clips     — только нарезка видео
--mode texts     — только генерация текстов (нужен API ключ)
--mode finalize  — наложение текста на нарезанные клипы
--mode login     — только авторизация аккаунтов
--mode upload    — загрузка (после логина)
--mode full      — полный конвейер
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Создаём базовые папки
os.makedirs("input", exist_ok=True)
os.makedirs("output/clips", exist_ok=True)
os.makedirs("output/final", exist_ok=True)
os.makedirs("sessions", exist_ok=True)


def main():
  parser = argparse.ArgumentParser(description="TikTok Conveyor — массовая загрузка видео")
  parser.add_argument("--mode", type=str, default="full",
                      choices=["clips", "texts", "finalize", "login", "upload", "full"])
  parser.add_argument("--input", type=str, default="input/demo.mp4",
                      help="Путь к исходному видео")
  parser.add_argument("--clips", type=int, default=100,
                      help="Сколько клипов нарезать")
  parser.add_argument("--prompt", type=str, default="",
                      help="Описание продукта для генерации текстов")
  parser.add_argument("--min-delay", type=int, default=30,
                      help="Мин пауза между загрузками (мин)")
  parser.add_argument("--max-delay", type=int, default=120,
                      help="Макс пауза между загрузками (мин)")
  
  args = parser.parse_args()
  mode = args.mode
  
  print(r"""
╔══════════════════════════════════╗
║      TikTok Conveyor v0.1        ║
║  Массовая загрузка видео в TikTok ║
╚══════════════════════════════════╝
  """)
  
  if mode in ("clips", "full"):
      print("\n📽️  ЭТАП 1: Нарезка видео")
      from video_processor import generate_clips
      
      input_video = args.input
      if not os.path.exists(input_video):
          print(f"[Main] Ошибка: видео не найдено — {input_video}")
          print("[Main] Положи файл в input/ или укажи --input")
          return
      
      clips = generate_clips(input_video, "output/clips", num_clips=args.clips)
      if not clips:
          print("[Main] Нарезка не дала результатов. Выход.")
          return
      print(f"[Main] Нарезано: {len(clips)} клипов")
  
  if mode in ("texts", "full"):
      print("\n✍️  ЭТАП 2: Генерация текстов")
      from text_engine import generate_texts, save_texts
      
      prompt = args.prompt
      if not prompt:
          prompt = input("[Main] Опиши, что на видео (1-2 предложения): ").strip()
          if not prompt:
              print("[Main] Нет описания — тексты не сгенерированы")
              return
      
      texts = generate_texts(prompt, count=args.clips)
      if texts:
          save_texts(texts)
  
  if mode in ("finalize", "full"):
      print("\n🎬  ЭТАП 3: Наложение текста на видео")
      from video_finalizer import batch_add_text
      from text_engine import load_texts
      
      texts = load_texts("output/texts.txt") if os.path.exists("output/texts.txt") else []
      if not texts:
          print("[Main] Нет текстов. Сгенерируй их сначала (--mode texts)")
          return
      
      final_videos = batch_add_text("output/clips", texts)
      print(f"[Main] Готово к загрузке: {len(final_videos)} видео")
  
  if mode in ("login", "full"):
      print("\n🔑  ЭТАП 4: Авторизация аккаунтов")
      from account_manager import load_accounts, login_all_accounts, print_login_report
      import asyncio
      
      if not os.path.exists("accounts.txt"):
          print("[Main] Ошибка: нет файла accounts.txt")
          print("[Main] Создай его в формате:")
          print("логин1\nпароль1\nлогин2\nпароль2")
          return
      
      accounts = load_accounts()
      print(f"[Main] Загружено {len(accounts)} аккаунтов")
      
      results = asyncio.run(login_all_accounts(accounts))
      print_login_report(results)
      
      # Сохраняем отчёт
      with open("sessions/login_report.json", "w", encoding="utf-8") as f:
          json.dump(results, f, ensure_ascii=False, indent=2)
  
  if mode in ("upload", "full"):
      print("\n📤  ЭТАП 5: Загрузка видео")
      from account_manager import load_accounts
      from uploader import batch_upload
      import asyncio
      
      if not os.path.exists("accounts.txt"):
          print("[Main] Нет accounts.txt")
          return
      
      accounts = load_accounts()
      videos = sorted([os.path.join("output/final", f) for f in os.listdir("output/final") if f.endswith(".mp4")])
      
      if not videos:
          print("[Main] Нет готовых видео в output/final/")
          return
      
      texts_file = "output/texts.txt"
      texts = []
      if os.path.exists(texts_file):
          with open(texts_file, "r", encoding="utf-8") as f:
              texts = [line.strip() for line in f if line.strip()]
      
      print(f"[Main] Аккаунтов: {len(accounts)}, Видео: {len(videos)}")
      
      results = asyncio.run(batch_upload(
          accounts, videos, texts,
          min_delay_minutes=args.min_delay,
          max_delay_minutes=args.max_delay
      ))
      
      # Сохраняем отчёт
      with open("sessions/upload_report.json", "w", encoding="utf-8") as f:
          json.dump(results, f, ensure_ascii=False, indent=2)
      
      ok = sum(1 for r in results if r.get("status") == "ok")
      failed = sum(1 for r in results if r.get("status") == "error")
      print(f"\n[Main] 📊 Загрузка завершена: ✅ {ok} | ❌ {failed}")
  
  print("\n✅ Готово!")


if __name__ == "__main__":
  main()
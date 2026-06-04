"""
uploader.py — загрузка видео в TikTok через Playwright (по сохранённым сессиям)
"""

import os
import asyncio
import random
import time
from typing import Optional


async def upload_video(
    account_id: int,
    video_path: str,
    description: str,
    session_path: str,
    headless: bool = False
) -> dict:
    """
    Загружает одно видео в TikTok используя сохранённую сессию.

    Возвращает:
        {"status": "ok" | "error", "url": str | None, "error": str | None}
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        context = await browser.new_context(
            storage_state=session_path,
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        )
        
        page = await context.new_page()
        
        try:
            # 1. Идём на страницу загрузки
            await page.goto("https://www.tiktok.com/upload", timeout=30000)
            await page.wait_for_timeout(3000)
            
            # Проверяем — не выкинуло ли на логин (сессия умерла)
            if "login" in page.url.lower():
                return {"status": "error", "url": None, "error": "SESSION_EXPIRED"}
            
            # 2. Загружаем видео
            file_input = page.locator("input[type='file']").first
            if not await file_input.is_visible():
                # На некоторых версиях TikTok кнопка "Select file" в другом месте
                upload_btn = page.locator("button:has-text('Upload'), button:has-text('Загрузить'), div:has-text('Select file')").first
                await upload_btn.click()
                await page.wait_for_timeout(2000)
                file_input = page.locator("input[type='file']").first
            
            await file_input.set_input_files(video_path)
            
            # 3. Ждём пока видео загрузится
            print(f"[Uploader] ⏳ Загружаю видео на сервер TikTok...")
            await page.wait_for_timeout(15000)  # ждём 15 сек на загрузку
            
            # 4. Вводим описание
            caption_area = page.locator("div[contenteditable='true']").first
            await caption_area.click()
            await page.wait_for_timeout(500)
            
            # Вводим текст посимвольно, как человек
            await caption_area.fill("")
            for char in description:
                await caption_area.type(char, delay=random.randint(30, 80))
            
            await page.wait_for_timeout(1000)
            
            # 5. Отключаем комментарии (опционально — пока оставляем как есть)
            # 6. Публикуем
            post_btn = page.locator("button:has-text('Post'), button:has-text('Опубликовать')").first
            await post_btn.click()
            
            # 7. Ждём результат
            await page.wait_for_timeout(10000)
            
            # Проверяем успех
            page_content = await page.content()
            if "success" in page_content.lower() or "published" in page_content.lower():
                print(f"[Uploader] ✅ Видео загружено: {os.path.basename(video_path)}")
                return {"status": "ok", "url": None, "error": None}
            else:
                return {"status": "error", "url": None, "error": "UPLOAD_FAILED"}
        
        except Exception as e:
            return {"status": "error", "url": None, "error": str(e)}
        
        finally:
            await page.close()
            await browser.close()


async def batch_upload(
    accounts: list,
    video_paths: list,
    descriptions: list,
    sessions_dir: str = "sessions",
    min_delay_minutes: int = 30,
    max_delay_minutes: int = 120
) -> list:
    """
    Массовая загрузка: распределяет видео по аккаунтам.

    Каждому аккаунту выдаётся следующее видео из очереди.
    Между загрузками — случайная пауза.
    """
    results = []
    video_idx = 0

    for acc_id in range(len(accounts)):
        if video_idx >= len(video_paths):
            print("[Uploader] Все видео закончились")
            break
        
        session_path = os.path.join(sessions_dir, f"session_{acc_id}")
        if not os.path.exists(session_path):
            print(f"[Uploader] ⏭ Аккаунт #{acc_id+1}: нет сессии, пропускаем")
            continue
        
        # Ставим видео в очередь этому аккаунту
        videos_for_acc = []
        while video_idx < len(video_paths):
            videos_for_acc.append(video_paths[video_idx])
            video_idx += 1
            # по 1 видео на аккаунт (пока)
            break
        
        for v in videos_for_acc:
            desc_idx = video_paths.index(v) if v in video_paths else 0
            if desc_idx < len(descriptions):
                desc = descriptions[desc_idx]
            else:
                desc = descriptions[desc_idx % len(descriptions)]
            
            print(f"[Uploader] Аккаунт #{acc_id+1}: загружаю {os.path.basename(v)}")
            result = await upload_video(acc_id, v, desc, session_path, headless=False)
            results.append({
                "account_id": acc_id,
                "video": v,
                **result
            })
            
            # Пауза между загрузками
            delay = random.randint(min_delay_minutes, max_delay_minutes)
            print(f"[Uploader] ⏳ Пауза {delay} мин перед следующим...")
            await asyncio.sleep(delay * 60)

    return results


if __name__ == "__main__":
    import json

    async def test():
        result = await upload_video(
            0,
            "output/final/final_0001.mp4",
            "Тестовая загрузка #тест #shorts",
            "sessions/session_0",
            headless=False
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))

    asyncio.run(test())
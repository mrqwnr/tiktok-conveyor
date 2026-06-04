"""
account_manager.py — Авторизация в TikTok, сохранение/загрузка сессий через Playwright
"""

import os
import pickle
import json
import time
from pathlib import Path
from typing import Optional


SESSIONS_DIR = "sessions"
ACCOUNTS_FILE = "accounts.txt"


def load_accounts(filepath: str = ACCOUNTS_FILE) -> list:
    """
    Загружает аккаунты из txt-файла.
    Формат:
    логин
    пароль
    логин
    пароль
    ...
    """
    accounts = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    for i in range(0, len(lines) - 1, 2):
        accounts.append({"username": lines[i], "password": lines[i+1]})

    return accounts


def account_session_path(account_id: int) -> str:
    """Путь к файлу сессии для аккаунта."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return os.path.join(SESSIONS_DIR, f"session_{account_id}")


def is_session_valid(account_id: int) -> bool:
    """Проверяет, существует ли файл сессии."""
    return os.path.exists(account_session_path(account_id))


async def login_all_accounts(accounts: list) -> list:
    """
    Логинит все аккаунты через Playwright.
    Возвращает список результатов: {"username": str, "status": str, "note": str}

    status: "ok" — вошёл, сессия сохранена
            "code_needed" — запрошен код подтверждения
            "banned" — аккаунт заблокирован
            "error" — ошибка

    ВАЖНО: При первом запуске, если вылезет капча или код подтверждения,
    софт остановится на этом аккаунте и попросит тебя ввести код в браузере.
    После ввода — нажми Enter в консоли.
    """
    from playwright.async_api import async_playwright

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        )

        for idx, acc in enumerate(accounts):
            print(f"\n[AccountManager] Аккаунт #{idx + 1}: {acc['username']}")

            page = await context.new_page()

            try:
                await page.goto("https://www.tiktok.com/login/phone-or-email/email", timeout=30000)
                await page.wait_for_timeout(2000)

                username_input = page.locator("input[name='username'], input[name='email'], input[type='text']").first
                await username_input.fill(acc["username"])

                password_input = page.locator("input[type='password']").first
                await password_input.fill(acc["password"])

                login_btn = page.locator("button[type='submit'], button:has-text('Log in'), button:has-text('Войти')").first
                await login_btn.click()

                await page.wait_for_timeout(5000)

                current_url = page.url
                page_content = await page.content()

                if "verify" in current_url.lower() or "code" in current_url.lower() or "captcha" in page_content.lower():
                    print(f"[AccountManager] ❓ {acc['username']}: требуется код/капча. Введи в браузере и нажми Enter...")
                    input()
                    await page.wait_for_timeout(3000)

                if "login" in page.url.lower() or "login" in current_url.lower():
                    results.append({"username": acc["username"], "status": "code_needed", "note": "не удалось войти"})
                else:
                    await context.storage_state(path=account_session_path(idx))
                    results.append({"username": acc["username"], "status": "ok", "note": "сессия сохранена"})
                    print(f"[AccountManager] ✅ {acc['username']}: вошёл")

            except Exception as e:
                results.append({"username": acc["username"], "status": "error", "note": str(e)})
                print(f"[AccountManager] ❌ {acc['username']}: {e}")

            finally:
                await page.close()

        await browser.close()

    return results


def print_login_report(results: list):
    """Печатает отчёт по авторизации."""
    ok = [r for r in results if r["status"] == "ok"]
    code = [r for r in results if r["status"] == "code_needed"]
    banned = [r for r in results if r["status"] == "banned"]
    errors = [r for r in results if r["status"] == "error"]

    print("\n" + "=" * 50)
    print(f"📊 ОТЧЁТ ПО АВТОРИЗАЦИИ")
    print(f"✅ Вошли: {len(ok)}")
    print(f"❓ Требуют код: {len(code)}")
    print(f"🚫 Забанены: {len(banned)}")
    print(f"❌ Ошибок: {len(errors)}")
    print("=" * 50)


if __name__ == "__main__":
    import asyncio
    accounts = load_accounts()
    print(f"[AccountManager] Загружено {len(accounts)} аккаунтов")
    results = asyncio.run(login_all_accounts(accounts))
    print_login_report(results)
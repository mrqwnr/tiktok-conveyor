"""
account_manager.py — Авторизация в TikTok с авто-подтверждением по IMAP
Поддерживает форматы accounts.txt:
Старый: логин
пароль
логин
пароль
...
Новый:  логин:пароль:почта:пароль_почты
"""

import os
import json
import time
import re
import imaplib
import email
from email.header import decode_header


SESSIONS_DIR = "sessions"
ACCOUNTS_FILE = "accounts.txt"

# IMAP настройки для firstmail.ltd (и полоссмейл)
IMAP_HOST = "imap.firstmail.ltd"
IMAP_PORT = 993


def load_accounts(filepath: str = ACCOUNTS_FILE) -> list:
    """
    Загружает аккаунты.
    Авто-определение формата:
    - Если строки идут парами (логин/пароль) — старый формат
    - Если строка содержит 4 части через : — новый формат (лог:пас:почта:пароль_почты)
    """
    accounts = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # Пробуем новый формат (4 секции через :)
    new_format = []
    old_format = []
    for line in lines:
        parts = line.split(":")
        if len(parts) >= 4 and all(p.strip() for p in parts[:4]):
            new_format.append({
                "username": parts[0].strip(),
                "password": parts[1].strip(),
                "email": parts[2].strip(),
                "email_password": parts[3].strip()
            })
        else:
            old_format.append(line)

    # Старый формат — пары логин/пароль
    for i in range(0, len(old_format) - 1, 2):
        accounts.append({
            "username": old_format[i],
            "password": old_format[i+1],
            "email": "",
            "email_password": ""
        })

    # Новый формат — уже готовые объекты
    accounts.extend(new_format)

    return accounts


def account_session_path(account_id: int) -> str:
    """Путь к файлу сессии для аккаунта."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    return os.path.join(SESSIONS_DIR, f"session_{account_id}")


def is_session_valid(account_id: int) -> bool:
    """Проверяет, существует ли файл сессии."""
    return os.path.exists(account_session_path(account_id))


def fetch_tiktok_code_from_email(email_address: str, email_password: str, max_wait: int = 60) -> str | None:
    """
    Подключается к IMAP firstmail, ищет письмо от TikTok,
    выкусывает 6-значный код подтверждения.
    Возвращает код или None, если не нашёл.
    """
    if not email_address or not email_password:
        return None

    print(f"  [IMAP] Подключаюсь к {email_address}...")

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
        mail.login(email_address, email_password)
        mail.select("INBOX")

        # Ждём письма до max_wait секунд, проверяя каждые 5 сек
        deadline = time.time() + max_wait
        while time.time() < deadline:
            status, messages = mail.search(None, "UNSEEN", "FROM", "tiktok")

            if status == "OK":
                # Сортируем — самые новые письма первые
                msg_ids = messages[0].split()
                if msg_ids:
                    # Берём самое новое письмо (последний ID — самое новое)
                    latest_id = msg_ids[-1]
                    status, msg_data = mail.fetch(latest_id, "(RFC822)")

                    if status == "OK":
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        # Декодируем тему
                        subject = ""
                        for part, encoding in decode_header(msg["Subject"] or ""):
                            if isinstance(part, bytes):
                                subject += part.decode(encoding or "utf-8", errors="ignore")
                            else:
                                subject += part

                        print(f"  [IMAP] Письмо от: {msg['From']}, тема: {subject}")

                        # Декодируем тело письма
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() in ("text/plain", "text/html"):
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body += payload.decode("utf-8", errors="ignore")
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode("utf-8", errors="ignore")

                        # Ищем 6-значный код — обычно в письме TikTok он в виде "XXXXXX"
                        # Паттерны: код может быть рядом с "verification code", "код" и тд
                        code_match = re.search(r'\b(\d{6})\b', body)
                        if code_match:
                            code = code_match.group(1)
                            print(f"  [IMAP] ✅ Найден код: {code}")
                            mail.logout()
                            return code

                        # Если код не нашёлся в самом новом — может письмо не от TikTok
                        print(f"  [IMAP] Код не найден в письме, жду дальше...")

            # Ждём 5 сек перед следующей проверкой
            time.sleep(5)

        print(f"  [IMAP] ⏰ Таймаут {max_wait}с — код не получен")
        mail.logout()
        return None

    except Exception as e:
        print(f"  [IMAP] ❌ Ошибка: {e}")
        return None


async def login_all_accounts(accounts: list) -> list:
    """
    Логинит все аккаунты через Playwright.
    Для аккаунтов с email-паролем — авто-подтверждение кода через IMAP.
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

                # Вводим логин
                username_input = page.locator("input[name='username'], input[name='email'], input[type='text']").first
                await username_input.fill(acc["username"])

                # Вводим пароль
                password_input = page.locator("input[type='password']").first
                await password_input.fill(acc["password"])

                # Жмём кнопку логина
                login_btn = page.locator("button[type='submit'], button:has-text('Log in'), button:has-text('Войти')").first
                await login_btn.click()

                await page.wait_for_timeout(5000)

                current_url = page.url
                page_content = await page.content()

                # Проверяем — просит ли код подтверждения
                needs_code = (
                    "verify" in current_url.lower()
                    or "code" in current_url.lower()
                    or "captcha" in page_content.lower()
                    or "отправлено" in page_content.lower()
                )

                if needs_code and acc["email"] and acc["email_password"]:
                    print(f"  [AccountManager] 🔄 Требуется код. Авто-получение через IMAP...")

                    # Ищем поле для ввода кода
                    code_input = page.locator("input[inputmode='numeric'], input[type='text']").first

                    # Пытаемся получить код автоматически
                    code = fetch_tiktok_code_from_email(acc["email"], acc["email_password"], max_wait=60)

                    if code:
                        # Вводим код
                        await code_input.click()
                        await page.wait_for_timeout(500)
                        await code_input.fill(code)
                        await page.wait_for_timeout(2000)

                        # После ввода кода TikTok может попросить нажать подтвердить
                        confirm_btn = page.locator("button[type='submit'], button:has-text('Verify'), button:has-text('Подтвердить')").first
                        if await confirm_btn.is_visible():
                            await confirm_btn.click()
                            await page.wait_for_timeout(3000)
                    else:
                        # Если не получили код — просим ввести вручную
                        print(f"  [AccountManager] ❓ {acc['username']}: введи код из почты в браузере и нажми Enter...")
                        input()
                        await page.wait_for_timeout(3000)

                elif needs_code and not acc["email"]:
                    # Нет данных почты — просим ввести
                    print(f"  [AccountManager] ❓ {acc['username']}: требуется код. Введи в браузере и нажми Enter...")
                    input()
                    await page.wait_for_timeout(3000)

                # Проверка результата
                if "login" in page.url.lower():
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
    errors = [r for r in results if r["status"] == "error"]

    print("\n" + "=" * 50)
    print("📊 ОТЧЁТ ПО АВТОРИЗАЦИИ")
    print(f"✅ Вошли: {len(ok)}")
    print(f"❓ Не удалось войти: {len(code)}")
    print(f"❌ Ошибок: {len(errors)}")
    print("=" * 50)


if __name__ == "__main__":
    import asyncio
    accounts = load_accounts()
    print(f"[AccountManager] Загружено {len(accounts)} аккаунтов")
    for a in accounts:
        has_email = "📧" if a["email"] else "  "
        print(f"  {has_email} {a['username']}")
    results = asyncio.run(login_all_accounts(accounts))
    print_login_report(results)
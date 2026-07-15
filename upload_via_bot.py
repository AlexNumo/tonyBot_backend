import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

# Завантажуємо змінні оточення
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
LESSONS_FILE_PATH = os.getenv("LESSONS_FILE_PATH", "../tony_tg_bot-main/src/data/lessons.json")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "7780694746"))
MATERIAL_DIR = "Material"

if not BOT_TOKEN:
    print("Помилка: BOT_TOKEN не знайдено в .env")
    exit(1)

def get_day_files(day_num):
    day_folder = os.path.join(MATERIAL_DIR, f"day {day_num}")
    if not os.path.exists(day_folder):
        return None
        
    files = os.listdir(day_folder)
    photo_file = None
    video_file = None
    audio_file = None
    pdf_file = None
    
    for f in files:
        f_lower = f.lower()
        full_path = os.path.join(day_folder, f)
        if os.path.isdir(full_path):
            continue
            
        if f_lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
            photo_file = full_path
        elif f_lower.endswith((".mp4", ".mov", ".avi", ".mkv", ".3gp")):
            video_file = full_path
        elif f_lower.endswith((".mp3", ".m4a", ".wav", ".ogg")):
            audio_file = full_path
        elif f_lower.endswith(".pdf"):
            pdf_file = full_path
            
    return {
        "photo": photo_file,
        "video": video_file,
        "audio": audio_file,
        "document": pdf_file
    }

async def upload_file(client, method, file_field, file_path, chat_id, extra_params=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    
    if not os.path.exists(file_path):
        print(f"  Файл не знайдено: {file_path}")
        return None
        
    print(f"  Завантажуємо {os.path.basename(file_path)}...")
    
    # Відкриваємо файл для завантаження
    with open(file_path, 'rb') as f:
        files = {file_field: (os.path.basename(file_path), f)}
        data = {"chat_id": chat_id}
        if extra_params:
            data.update(extra_params)
            
        try:
            res = await client.post(url, data=data, files=files, timeout=60.0)
            result = res.json()
            if result.get("ok"):
                msg = result["result"]
                if file_field == "photo":
                    # Фото повертає список об'єктів PhotoSize, беремо останній (найбільший)
                    return msg["photo"][-1]["file_id"]
                elif file_field in msg:
                    return msg[file_field]["file_id"]
                elif "document" in msg:
                    return msg["document"]["file_id"]
                elif "audio" in msg:
                    return msg["audio"]["file_id"]
                elif "video" in msg:
                    return msg["video"]["file_id"]
            else:
                print(f"  Помилка Telegram API: {result}")
        except Exception as e:
            print(f"  Помилка з'єднання: {e}")
            
    return None

async def main():
    print("==================================================")
    print(" Завантаження матеріалів безпосередньо через Бот API ")
    print("==================================================")
    
    # Зчитуємо lessons.json
    if not os.path.exists(LESSONS_FILE_PATH):
        print(f"Помилка: Файл не знайдено за шляхом {LESSONS_FILE_PATH}")
        return
        
    with open(LESSONS_FILE_PATH, 'r', encoding='utf-8') as f:
        lessons = json.load(f)
        
    async with httpx.AsyncClient() as client:
        # Тестуємо з'єднання
        test_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        try:
            res = await client.get(test_url)
            bot_info = res.json()
            if not bot_info.get("ok"):
                print("Помилка: Невірний токен бота.")
                return
            print(f"Авторизовано як бот: @{bot_info['result']['username']}")
        except Exception as e:
            print(f"Помилка з'єднання: {e}")
            return
            
        print(f"Буде надіслано тестові завантаження адміну з ID: {ADMIN_TELEGRAM_ID}")
        
        updated_count = 0
        
        # Обробляємо дні 5-8
        for lesson in lessons:
            day = lesson["day"]
            if day < 5:
                # Дні 1-4 вже заповнені
                continue
                
            print(f"\n[День {day}] Перевірка матеріалів...")
            day_files = get_day_files(day)
            if not day_files:
                print("  Папка не знайдена.")
                continue
                
            day_key = f"day_{day}"
            
            # Фото
            if day_files["photo"] and not lesson.get("photoFileId"):
                file_id = await upload_file(client, "sendPhoto", "photo", day_files["photo"], ADMIN_TELEGRAM_ID, {"caption": f"Фото {day} дня"})
                if file_id:
                    lesson["photoFileId"] = file_id
                    updated_count += 1
                    print(f"  -> Збережено photoFileId: {file_id}")
                    await asyncio.sleep(2)
                    
            # Відео (якщо немає)
            if day_files["video"] and not lesson.get("videoFileId"):
                file_id = await upload_file(client, "sendVideo", "video", day_files["video"], ADMIN_TELEGRAM_ID, {"caption": f"Відео {day} дня"})
                if file_id:
                    lesson["videoFileId"] = file_id
                    updated_count += 1
                    print(f"  -> Збережено videoFileId: {file_id}")
                    await asyncio.sleep(3)
                    
            # Аудіо
            if day_files["audio"] and not lesson.get("audioFileId"):
                file_id = await upload_file(client, "sendAudio", "audio", day_files["audio"], ADMIN_TELEGRAM_ID, {"caption": f"Аудіо {day} дня"})
                if file_id:
                    lesson["audioFileId"] = file_id
                    updated_count += 1
                    print(f"  -> Збережено audioFileId: {file_id}")
                    await asyncio.sleep(2)
                    
            # Документ (PDF)
            if day_files["document"] and not lesson.get("pdfFileId"):
                file_id = await upload_file(client, "sendDocument", "document", day_files["document"], ADMIN_TELEGRAM_ID, {"caption": f"Робочий зошит {day} дня"})
                if file_id:
                    lesson["pdfFileId"] = file_id
                    lesson["pdfFiles"] = [os.path.basename(day_files["document"])]
                    updated_count += 1
                    print(f"  -> Збережено pdfFileId: {file_id}")
                    await asyncio.sleep(2)
                    
        if updated_count > 0:
            # Зберігаємо зміни у lessons.json
            with open(LESSONS_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(lessons, f, indent=2, ensure_ascii=False)
            print(f"\n✅ Завершено! Оновлено {updated_count} файлів у файлі {LESSONS_FILE_PATH}")
            
            # Якщо є EXPRESS_API_URL, синхронізуємо також через Express
            express_url = os.getenv("EXPRESS_API_URL", "http://localhost:3000").rstrip('/')
            try:
                res = await client.put(f"{express_url}/api/lessons", json={"lessons": lessons})
                if res.status_code == 200:
                    print("✅ Успішно синхронізовано з Express API!")
                else:
                    print(f"⚠️ Попередження: Не вдалося синхронізувати з Express ({res.status_code})")
            except Exception as e:
                print(f"⚠️ Попередження: Не вдалося з'єднатися з Express API: {e}")
        else:
            print("\nУсі файли для днів 5-8 вже мають зареєстровані file_id в lessons.json.")

if __name__ == "__main__":
    asyncio.run(main())

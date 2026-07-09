import os
import sys
import time
import asyncio

try:
    from pyrogram import Client
except ImportError:
    print("Помилка: Бібліотеку pyrogram не знайдено. Встановлюю необхідні пакети...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyrogram", "tgcrypto"])
    from pyrogram import Client

# Шлях до папки з матеріалами
MATERIAL_DIR = "Material"

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

async def main():
    print("==================================================")
    print("   Автоматичне завантаження медіаматеріалів в Telegram   ")
    print("==================================================")
    print("\nДля роботи скрипта вам потрібні API ID та API Hash.")
    print("Отримати їх можна за 2 хвилини тут: https://my.telegram.org/apps")
    
    # Запит параметрів підключення
    try:
        api_id = input("\nВведіть ваш API ID: ").strip()
        api_hash = input("Введіть ваш API Hash: ").strip()
        phone_number = input("Введіть ваш номер телефону (наприклад, +380931234567): ").strip()
        bot_username = input("Введіть username вашого бота (наприклад, tochka_perehodu_bot або tochka_test_bot): ").strip()
    except KeyboardInterrupt:
        print("\nВихід...")
        return
        
    if not bot_username.startswith("@"):
        bot_username = "@" + bot_username
        
    # Ініціалізація клієнта Pyrogram
    # Створюємо сесію в папці проекту
    session_name = "user_uploader_session"
    app = Client(
        session_name,
        api_id=int(api_id),
        api_hash=api_hash,
        phone_number=phone_number
    )
    
    print("\nПідключення до Telegram...")
    await app.start()
    print("Успішно підключено!")
    
    # 1. Завантаження вітального фото
    welcome_photo = os.path.join(MATERIAL_DIR, "Фото до вітального повідомлення.jpg")
    if os.path.exists(welcome_photo):
        print(f"\n[Вітальне] Завантажуємо фото: {os.path.basename(welcome_photo)}...")
        try:
            await app.send_photo(
                chat_id=bot_username,
                photo=welcome_photo,
                caption="#upload [welcome] [photo]"
            )
            print("  Успішно завантажено!")
            await asyncio.sleep(2)  # невелика затримка проти спам-флуду
        except Exception as e:
            print(f"  Помилка завантаження вітального фото: {e}")
    else:
        print(f"\n[Вітальне] Фото не знайдено за шляхом {welcome_photo}. Пропускаємо.")

    # 2. Завантаження матеріалів по днях (1-8)
    for day in range(1, 9):
        day_files = get_day_files(day)
        if not day_files or not any(day_files.values()):
            print(f"\n[День {day}] Папка порожня або відсутня. Пропускаємо.")
            continue
            
        print(f"\n[День {day}] Знайдено файли. Починаємо завантаження...")
        day_key = f"day_{day}"
        
        # Завантажуємо фото
        if day_files["photo"]:
            f_name = os.path.basename(day_files["photo"])
            print(f"  Завантажуємо зображення: {f_name}...")
            try:
                await app.send_photo(
                    chat_id=bot_username,
                    photo=day_files["photo"],
                    caption=f"#upload [{day_key}] [photo]"
                )
                print("    Готово!")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"    Помилка: {e}")
                
        # Завантажуємо відео (навіть великі MOV/MP4)
        if day_files["video"]:
            f_name = os.path.basename(day_files["video"])
            print(f"  Завантажуємо відео-урок (це може зайняти час, файл великий): {f_name}...")
            try:
                await app.send_video(
                    chat_id=bot_username,
                    video=day_files["video"],
                    caption=f"#upload [{day_key}] [video]"
                )
                print("    Готово!")
                await asyncio.sleep(3)
            except Exception as e:
                print(f"    Помилка завантаження відео: {e}")
                
        # Завантажуємо аудіо
        if day_files["audio"]:
            f_name = os.path.basename(day_files["audio"])
            print(f"  Завантажуємо аудіопрактику: {f_name}...")
            try:
                await app.send_audio(
                    chat_id=bot_username,
                    audio=day_files["audio"],
                    caption=f"#upload [{day_key}] [audio]"
                )
                print("    Готово!")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"    Помилка завантаження аудіо: {e}")
                
        # Завантажуємо робочий зошит (PDF)
        if day_files["document"]:
            f_name = os.path.basename(day_files["document"])
            print(f"  Завантажуємо робочий зошит PDF: {f_name}...")
            try:
                await app.send_document(
                    chat_id=bot_username,
                    document=day_files["document"],
                    caption=f"#upload [{day_key}] [document]"
                )
                print("    Готово!")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"    Помилка завантаження документа: {e}")
                
    await app.stop()
    print("\n==================================================")
    print("  Усі наявні матеріали завантажено в Telegram!  ")
    print("  Перевірте консоль вашого бота на наявність логів.")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())

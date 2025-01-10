import sqlite3
import requests
from bs4 import BeautifulSoup
import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox
from tkinter import ttk
from urllib.parse import urljoin
import re
from PIL import Image, ImageTk
import io
import datetime
import time
import threading

# Глобальная переменная для текущего индекса и флаг парсинга
current_index = -1
parsing_active = False

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('mods.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS Mods (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mod_id TEXT,
                        title TEXT,
                        category TEXT,
                        uploader TEXT,
                        description TEXT,
                        full_description TEXT,
                        parsing_date TEXT)''')
                        
    cursor.execute('''CREATE TABLE IF NOT EXISTS Dependencies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mod_id TEXT,
                        dependency_type TEXT,
                        dependency_name TEXT)''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS Images (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        mod_id TEXT,
                        image BLOB,
                        upload_date TEXT)''')
    
    conn.commit()
    conn.close()

def save_to_db(mod_id, title, category, uploader, description, full_description, images, required_mods, dependent_mods):
    parsing_date = str(datetime.datetime.now())
    conn = sqlite3.connect('mods.db')
    cursor = conn.cursor()
    
    cursor.execute('''INSERT INTO Mods (mod_id, title, category, uploader, description, full_description, parsing_date)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                   (mod_id, title, category, uploader, description, full_description, parsing_date))
    
    for image in images:
        cursor.execute('''INSERT INTO Images (mod_id, image, upload_date) VALUES (?, ?, ?)''',
                       (mod_id, sqlite3.Binary(image), parsing_date))
    
    for mod in required_mods:
        cursor.execute('''INSERT INTO Dependencies (mod_id, dependency_type, dependency_name) VALUES (?, ?, ?)''',
                       (mod_id, 'required', mod))
    
    for mod in dependent_mods:
        cursor.execute('''INSERT INTO Dependencies (mod_id, dependency_type, dependency_name) VALUES (?, ?, ?)''',
                       (mod_id, 'dependent', mod))
    
    conn.commit()
    conn.close()

    # Обновление общего количества спарсенных страниц
    update_parsing_count()

def fetch_image(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Ошибка загрузки изображения: {e}")
        return None

def fetch_page_data(mod_id):
    try:
        base_url = "https://www.nexusmods.com/skyrimspecialedition/mods/"
        full_url = urljoin(base_url, mod_id + "?tab=description")
        
        # Получаем HTML-страницу
        response = requests.get(full_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Заголовок
        title = soup.title.string if soup.title else "Нет заголовка"
        title_var.set(f"Заголовок: {title}")
        mod_id_var.set(f"Mod ID: {mod_id}")

        # Категория
        category_block = soup.find("a", href=re.compile(r'/categories/\d+/'))
        category_name = category_block.text.strip() if category_block else "Категория не найдена"
        category_var.set(f"Категория: {category_name}")

        # Загрузивший пользователь
        uploader_block = soup.find("div", {"class": "sideitem"})
        uploader_name = None
        uploader_link = None
        for item in soup.find_all("div", {"class": "sideitem"}):
            if "Uploaded by" in item.text:
                uploader_name = item.find("a").text.strip()
                uploader_link = item.find("a")["href"]
                break
        
        if uploader_name:
            uploader_var.set(f"Загрузивший пользователь: {uploader_name}")
        else:
            uploader_var.set("Загрузивший пользователь: Не найдено")

        # Изображения
        image_blocks = soup.find_all("li", {"class": "thumb"}, limit=5)
        images = []
        for widget in image_frame.winfo_children():
            widget.destroy()  # Удаляем старые изображения
        for idx, li in enumerate(image_blocks, start=1):
            img = li.find("img")
            img_url = img["src"] if img else None
            if img_url:
                img_data = fetch_image(img_url)
                images.append(img_data)
                if img_data:
                    img_photo = ImageTk.PhotoImage(Image.open(io.BytesIO(img_data)))
                    img_label = tk.Label(image_frame, image=img_photo)
                    img_label.image = img_photo  # Сохраняем ссылку на изображение
                    img_label.pack(side=tk.LEFT, padx=5, pady=5)

        # Описание
        description = soup.find("meta", {"name": "description"})
        description_text = description["content"] if description else "Нет описания"
        description_textbox.delete(1.0, tk.END)
        description_textbox.insert(tk.END, description_text)

        # Зависимости
        dependencies_block = soup.find("dl", {"class": "accordion"})
        required_mods = []
        dependent_mods = []
        if dependencies_block:
            dependencies = dependencies_block.find_all("a")
            for dependency in dependencies:
                mod_link = dependency["href"]
                if "auth/sign_in" in mod_link:
                    continue
                mod_name = dependency.text.strip()
                data_tracking = dependency.get("data-tracking")
                if data_tracking and "View Required Mod" in data_tracking:
                    required_mods.append(mod_name)
                elif data_tracking and "View Dependent Mod" in data_tracking:
                    dependent_mods.append(mod_name)

        required_mods_listbox.delete(0, tk.END)
        for mod in required_mods:
            required_mods_listbox.insert(tk.END, mod)

        dependent_mods_listbox.delete(0, tk.END)
        for mod in dependent_mods:
            dependent_mods_listbox.insert(tk.END, mod)

        # Полное описание
        full_description = soup.find("div", {"class": "container mod_description_container condensed"})
        full_description_text = full_description.get_text(separator="\n").strip() if full_description else "Полное описание не найдено."
        full_description_textbox.delete(1.0, tk.END)
        full_description_textbox.insert(tk.END, full_description_text)

        # Сохранение в базу данных
        save_to_db(mod_id, title, category_name, uploader_name, description_text, full_description_text, images, required_mods, dependent_mods)
        
    except Exception as e:
        print(f"Ошибка: {e}")


def fetch_from_db(mod_id):
    conn = sqlite3.connect('mods.db')
    cursor = conn.cursor()

    cursor.execute('''SELECT title, category, uploader, description, full_description FROM Mods WHERE mod_id=?''', (mod_id,))
    row = cursor.fetchone()
    if row:
        title, category, uploader, description, full_description = row
        title_var.set(f"Заголовок: {title}")
        mod_id_var.set(f"Mod ID: {mod_id}")
        category_var.set(f"Категория: {category}")
        uploader_var.set(f"Загрузивший пользователь: {uploader}")
        description_textbox.delete(1.0, tk.END)
        description_textbox.insert(tk.END, description)
        full_description_textbox.delete(1.0, tk.END)
        full_description_textbox.insert(tk.END, full_description)
    
    cursor.execute('''SELECT image FROM Images WHERE mod_id=?''', (mod_id,))
    images = cursor.fetchall()
    for widget in image_frame.winfo_children():
        widget.destroy()  # Удаляем старые изображения
    for idx, (img_data,) in enumerate(images, start=1):
        img_photo = ImageTk.PhotoImage(Image.open(io.BytesIO(img_data)))
        img_label = tk.Label(image_frame, image=img_photo)
        img_label.image = img_photo  # Сохраняем ссылку на изображение
        img_label.pack(side=tk.LEFT, padx=5, pady=5)

    cursor.execute('''SELECT dependency_name FROM Dependencies WHERE mod_id=? AND dependency_type='required' ''', (mod_id,))
    required_mods = cursor.fetchall()
    required_mods_listbox.delete(0, tk.END)
    for mod in required_mods:
        required_mods_listbox.insert(tk.END, mod[0])

    cursor.execute('''SELECT dependency_name FROM Dependencies WHERE mod_id=? AND dependency_type='dependent' ''', (mod_id,))
    dependent_mods = cursor.fetchall()
    dependent_mods_listbox.delete(0, tk.END)
    for mod in dependent_mods:
        dependent_mods_listbox.insert(tk.END, mod[0])

    conn.close()

    # Обновление общего количества спарсенных страниц
    update_parsing_count()

def update_parsing_count():
    conn = sqlite3.connect('mods.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT COUNT(*) FROM Mods''')
    count = cursor.fetchone()[0]
    total_count_var.set(f"Всего спарсено страниц: {count}")
    conn.close()

def on_submit():
    mod_id = mod_id_entry.get()
    fetch_page_data(mod_id)

def on_next():
    global current_index
    conn = sqlite3.connect('mods.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT mod_id FROM Mods ORDER BY id''')
    all_mods = cursor.fetchall()
    if not all_mods:
        return
    current_index = (current_index + 1) % len(all_mods)
    mod_id = all_mods[current_index][0]
    fetch_from_db(mod_id)
    conn.close()

def on_prev():
    global current_index
    conn = sqlite3.connect('mods.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT mod_id FROM Mods ORDER BY id''')
    all_mods = cursor.fetchall()
    if not all_mods:
        return
    current_index = (current_index - 1) % len(all_mods)
    mod_id = all_mods[current_index][0]
    fetch_from_db(mod_id)
    conn.close()

def start_parsing():
    global parsing_active
    parsing_active = True
    try:
        last_mod_id = int(last_mod_id_entry.get())
        threading.Thread(target=parse_all, args=(last_mod_id,)).start()
    except ValueError:
        # Вывод сообщения об ошибке, если введено некорректное значение
        tk.messagebox.showerror("Ошибка", "Пожалуйста, введите корректный ID последнего мода.")
        parsing_active = False

def stop_parsing():
    global parsing_active
    parsing_active = False

def parse_all(last_mod_id):
    global parsing_active
    count = 0
    for mod_id in range(1, last_mod_id + 1):
        if not parsing_active:
            break
        conn = sqlite3.connect('mods.db')
        cursor = conn.cursor()
        cursor.execute('''SELECT mod_id FROM Mods WHERE mod_id=?''', (mod_id,))
        result = cursor.fetchone()
        conn.close()
        if not result:
            fetch_page_data(str(mod_id))  # Преобразуем mod_id в строку
            count += 1
            counter_var.set(f"Спарсено: {count}")
            time.sleep(5)  # Пауза между запросами
    parsing_active = False

# Инициализация базы данных
init_db()

# Создаем главное окно
root = tk.Tk()
root.title("NexusMods Parser")
root.state('zoomed')  # Устанавливаем окно на весь экран

# Переменные
title_var = tk.StringVar()
mod_id_var = tk.StringVar()
category_var = tk.StringVar()
uploader_var = tk.StringVar()
counter_var = tk.StringVar(value="Спарсено: 0")
total_count_var = tk.StringVar(value="Всего спарсено страниц: 0")

# Ввод ModID
mod_id_label = tk.Label(root, text="Mod ID:")
mod_id_label.pack(fill=tk.X, padx=10, pady=5)
mod_id_entry = tk.Entry(root)
mod_id_entry.pack(fill=tk.X, padx=10, pady=5)
mod_id_button = tk.Button(root, text="Парсинг", command=on_submit)
mod_id_button.pack(fill=tk.X, padx=10, pady=5)

# Текущий ModID
current_mod_id_label = tk.Label(root, textvariable=mod_id_var)
current_mod_id_label.pack(fill=tk.X, padx=10, pady=5)

# Заголовок
title_label = tk.Label(root, textvariable=title_var)
title_label.pack(fill=tk.X, padx=10, pady=5)

# Категория
category_label = tk.Label(root, textvariable=category_var)
category_label.pack(fill=tk.X, padx=10, pady=5)

# Загрузивший пользователь
uploader_label = tk.Label(root, textvariable=uploader_var)
uploader_label.pack(fill=tk.X, padx=10, pady=5)

# Изображения
image_frame = tk.Frame(root)
image_frame.pack(fill=tk.X, padx=10, pady=5)

# Описание
description_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=3)
description_textbox.pack(fill=tk.X, padx=10, pady=3)

# Зависимости
dependencies_frame = tk.Frame(root)
dependencies_frame.pack(fill=tk.X, padx=10, pady=3)

required_mods_frame = tk.Frame(dependencies_frame)
required_mods_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
required_mods_label = tk.Label(required_mods_frame, text="- Моды, от которых зависит текущий мод")
required_mods_label.pack(fill=tk.X, padx=5, pady=5)
required_mods_listbox = tk.Listbox(required_mods_frame)
required_mods_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

dependent_mods_frame = tk.Frame(dependencies_frame)
dependent_mods_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
dependent_mods_label = tk.Label(dependent_mods_frame, text="Моды, которые зависят от текущего мода")
dependent_mods_label.pack(fill=tk.X, padx=5, pady=3)
dependent_mods_listbox = tk.Listbox(dependent_mods_frame)
dependent_mods_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

# Полное описание
full_description_textbox = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=3)
full_description_textbox.pack(fill=tk.BOTH, padx=10, pady=3, expand=True)

# Кнопки для навигации по записям
navigation_frame = tk.Frame(root)
navigation_frame.pack(fill=tk.X, padx=10, pady=5)
prev_button = tk.Button(navigation_frame, text="<< Назад", command=on_prev)
prev_button.pack(side=tk.LEFT, padx=5, pady=5)
next_button = tk.Button(navigation_frame, text="Вперед >>", command=on_next)
next_button.pack(side=tk.RIGHT, padx=5, pady=5)

# Ввод ID последнего мода
last_mod_id_label = tk.Label(root, text="ID последнего мода:")
last_mod_id_label.pack(fill=tk.X, padx=10, pady=5)
last_mod_id_entry = tk.Entry(root)
last_mod_id_entry.pack(fill=tk.X, padx=10, pady=5)
parse_all_button = tk.Button(root, text="Парсить всё", command=start_parsing)
parse_all_button.pack(fill=tk.X, padx=10, pady=5)
stop_parsing_button = tk.Button(root, text="Приостановить парсинг", command=stop_parsing)
stop_parsing_button.pack(fill=tk.X, padx=10, pady=5)

# Каунтер для общего количества спарсенных страниц
total_count_label = tk.Label(root, textvariable=total_count_var)
total_count_label.pack(fill=tk.X, padx=10, pady=5)

# Каунтер парсинга
counter_label = tk.Label(root, textvariable=counter_var)
counter_label.pack(fill=tk.X, padx=10, pady=5)

# Запуск главного окна
root.mainloop()

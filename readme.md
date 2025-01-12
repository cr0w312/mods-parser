Зависимости
```
pip install requests bs4 tk pillow dotenv
```

Для корректной работы требуется файл настроек .env
```
move .env.example .env
```

Упаковка в один файл с помощью PyInstaller (pip install -U pyinstaller)

```
pyinstaller --onefile --windowed --distpath=.\build\ main.py
copy .env .\build\.env
```



© by Alhimik
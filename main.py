import json
import os
from flask import Flask, request, jsonify, send_file
import random
import string
import psycopg2
from dotenv import load_dotenv

app = Flask(__name__)

class DataBase():
    def __init__(self):
        load_dotenv('.env')   # загружаем переменные из .env чтобы они остались в секрете
        self.host = os.getenv('DB_HOST', 'localhost')
        self.name = os.getenv('DB_NAME', 'url_shortener')
        self.user = os.getenv('DB_USER', 'postgres')
        self.password = os.getenv('DB_PASSWORD', '')
        self.port = os.getenv('DB_PORT', 5432)
        self.result_con = self.connect()
        if self.result_con:
            self.create_table()

    def connect(self):
        try:

            self.connection = psycopg2.connect(
                host=self.host,
                database=self.name,
                user=self.user,
                password=self.password,
                port=self.port,
                client_encoding='utf-8'  # ← Добавьте эту строку
            )
            print('success connect to DB!')
            return True
        except Exception as er:
            print(f'Fail: {er} Но на этот случай есть json file')
            return False

    def create_table(self):
        cur = self.connection.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS urls (
            short_code VARCHAR(10) PRIMARY KEY,
            original_url TEXT NOT NULL,
            count_cliks INTEGER,
            created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.commit()

    def get_data(self):
        try:
            cur = self.connection.cursor()
            cur.execute("""SELECT short_code, original_url FROM urls""")
            return dict(cur.fetchall())
        except Exception as er:
            print(f"Не удалось добавить запись. {er}")

    def add_data(self, short_code, original_url):
        try:
            cur = self.connection.cursor()
            cur.execute("""INSERT INTO urls (short_code, original_url, count_cliks) VALUES (%s, %s, %s)""", (short_code, original_url, 0))
            self.connection.commit()
        except Exception as er:
            print(f"Не удалось добавить запись. {er}")
        

    def add_click(self, code):
        """для подсчета кликов"""
        cur = self.connection.cursor()
        cur.execute(
            "UPDATE urls SET count_cliks = count_cliks + %s WHERE short_code = %s", (1, code)
        )
        self.connection.commit()



def load_db(file='urls.json'):
    """Загружаем данные из файла"""
    if os.path.exists(file):
        try:
            with open(file, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def clear_json_file(filename='reserve_data.json'):
    """Очищает JSON файл, записывая в него пустой словарь"""
    try:
        with open(filename, 'w') as f:
            json.dump({}, f, indent=2)
        print(f"Файл {filename} успешно очищен")
        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        return False

def save_db(data, file='urls.json'):
    """Сохраняем данные в файл"""
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)


# print(f"DB_data тип: {type(DB_data)}, значение: {DB_data}")
# print(f"DB_obj.result_con: {DB_obj.result_con}")

# Список запрещенных кодов
RESERVED_WORDS = {
    'health', 'stats', 'info', 'shorten',
    'static', 'api', 'admin', 'login', 'register',
    'user', 'users', 'dashboard', 'profile'
}
data_for_update = {}    # данные, которые надо добавить в БД, если сейчас БД недоступна

@app.route('/')
def index():
    try:
        return send_file('static/index.html')
    except Exception as e:
        return jsonify({"error": f"HTML file not found: {str(e)}"}), 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    try:
        return send_file(f'static/{filename}')
    except FileNotFoundError:
        return jsonify({"error": "File not found"}), 404

@app.route('/health')
def health():
    return jsonify({
        "status": "ok",
        "total_links": len(DB_data),
        "storage": "database" if DB_obj.result_con else "file_json"
    })

@app.route('/shorten', methods=['POST'])
def shorten_url():
    try:
        data = request.get_json()
        if not data or 'long_url' not in data:
            return jsonify({"error": "Missing 'long_url' in request"}), 400

        long_url = data['long_url']

        if not long_url.startswith(('http://', 'https://')):
            long_url = 'https://' + long_url

        # Генерируем уникальный код
        while True:
            code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            if code not in DB_data and code not in RESERVED_WORDS:
                break

        # Сохраняем в базу и файл
        DB_data[code] = long_url
        save_db(DB_data)
        if DB_obj.result_con:
            DB_obj.add_data(code, long_url)
        else:
            data_for_update[code] = long_url
            save_db(data_for_update, 'reserve_data.json')

        short_url = f"https://darkshaddow.pythonanywhere.com/{code}"
        return jsonify({
            "short_url": short_url,
            "code": code,
            "original_url": long_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/<code>')
def redirect_code(code):
    if code not in DB_data:
        return jsonify({"error": "Ссылка не найдена"}), 404
    elif DB_obj.result_con:
        DB_obj.add_click(code)

    from flask import redirect
    return redirect(DB_data[code], code=302)

@app.route('/stats')
def stats():
    """Статистика"""
    return jsonify({
        "total_links": len(DB_data),
        "latest_links": dict(list(DB_data.items())[-5:]) if DB_data else {}
    })

@app.route('/info')
def info():
    return jsonify({
        "version": "1.0",
        "author": "DarkShaddow",
        "description": "URL Shortener Service",
        "endpoints": {
            "shorten": "POST /shorten",
            "redirect": "GET /{code}",
            "stats": "GET /stats",
            "health": "GET /health"
        }
    })

DB_obj = DataBase()
# Файл для хранения данных
DB_FILE = 'urls.json'
DB_obj.add_data('123qwe', '123qwe')
# Загружаем данные при старте
if not DB_obj.result_con:   # если нет соединения с бд то пользуемся json файлом
    DB_data = load_db()
else:
    for code, long_url in load_db("reserve_data.json").items():
        DB_obj.add_data(code, long_url)
    clear_json_file()
    DB_data = DB_obj.get_data()


# if __name__ == '__main__':
#     app.run(debug=True)
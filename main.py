import json
import os
from flask import Flask, request, jsonify, send_file
import random
import string
import psycopg2
from dotenv import load_dotenv
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

class DataBase():
    def __init__(self):
        load_dotenv('.env')
        self.host = os.getenv('DB_HOST', 'localhost')
        self.name = os.getenv('DB_NAME', 'url_shortener')
        self.user = os.getenv('DB_USER', 'postgres')
        self.password = os.getenv('DB_PASSWORD', 'password')
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
                client_encoding='utf-8'
            )
            print('✅ Успешное подключение к БД!')
            return True
        except Exception as er:
            print(f'❌ Ошибка подключения к БД: {er}. Используем JSON файл')
            return False

    def create_table(self):
        if self.result_con:
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
            if self.result_con:
                cur = self.connection.cursor()
                cur.execute("""SELECT short_code, original_url FROM urls""")
                result = cur.fetchall()
                return {row[0]: row[1] for row in result} if result else {}
        except Exception as er:
            print(f"❌ Ошибка получения данных из БД: {er}")
        return {}

    def add_data(self, short_code, original_url):
        try:
            if self.result_con:
                cur = self.connection.cursor()
                cur.execute("SELECT 1 FROM urls WHERE short_code = %s", (short_code,))
                exists = cur.fetchone()

                if not exists:
                    cur.execute("INSERT INTO urls (short_code, original_url, count_cliks) VALUES (%s, %s, %s)",
                                (short_code, original_url, 0))
                    self.connection.commit()
                    print(f"✅ Добавлена запись в БД: {short_code}")
        except Exception as er:
            print(f"❌ Ошибка добавления в БД: {er}")

    def add_click(self, code):
        if self.result_con:
            try:
                cur = self.connection.cursor()
                cur.execute("UPDATE urls SET count_cliks = count_cliks + 1 WHERE short_code = %s", (code,))
                self.connection.commit()
            except Exception as er:
                print(f"❌ Ошибка обновления кликов: {er}")

def load_db(file='urls.json'):
    if os.path.exists(file):
        try:
            with open(file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки JSON: {e}")
            return {}
    print("📁 JSON файл не найден, создаем новый")
    return {}

def save_db(data, file='urls.json'):
    try:
        with open(file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"❌ Ошибка сохранения JSON: {e}")

RESERVED_WORDS = {
    'health', 'stats', 'info', 'shorten', 'static', 'api', 'admin'
}

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

        long_url = data['long_url'].strip()
        if not long_url:
            return jsonify({"error": "URL cannot be empty"}), 400

        if not long_url.startswith(('http://', 'https://')):
            long_url = 'https://' + long_url

        # Генерируем уникальный код
        while True:
            code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
            if code not in DB_data and code not in RESERVED_WORDS:
                break

        # Сохраняем данные
        DB_data[code] = long_url
        save_db(DB_data)

        if DB_obj.result_con:
            DB_obj.add_data(code, long_url)

        # ФИКС для Docker: определяем правильный URL
        if 'DOCKER' in os.environ:
            base_url = f"http://{request.host}"
        else:
            base_url = f"http://{request.host}"

        short_url = f"{base_url}/{code}"

        print(f"🔗 Создана ссылка: {code} -> {long_url}")
        print(f"📝 Короткая ссылка: {short_url}")

        return jsonify({
            "short_url": short_url,
            "code": code,
            "original_url": long_url
        })

    except Exception as e:
        print(f"❌ Ошибка в shorten_url: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/<code>')
def redirect_code(code):
    print(f"🔍 Запрос на перенаправление для кода: {code}")
    print(f"📋 Доступные коды: {list(DB_data.keys())}")

    if code in DB_data:
        print(f"↪️ Перенаправление: {code} -> {DB_data[code]}")
        DB_obj.add_click(code)
        from flask import redirect
        return redirect(DB_data[code], code=302)
    else:
        print(f"❌ Код не найден: {code}")
        return jsonify({"error": "Ссылка не найдена"}), 404

@app.route('/stats')
def stats():
    return jsonify({
        "total_links": len(DB_data),
        "latest_links": dict(list(DB_data.items())[-5:]) if DB_data else {}
    })

# Инициализация приложения
DB_obj = DataBase()
DB_data = load_db()

# Синхронизация данных между БД и JSON
if DB_obj.result_con:
    db_data = DB_obj.get_data()
    if db_data:
        # Обновляем JSON данными из БД
        DB_data.update(db_data)
        save_db(DB_data)
        print("✅ Данные синхронизированы из БД в JSON")
else:
    print("📁 Используем хранение данных в JSON файле")

print(f"📊 Загружено ссылок: {len(DB_data)}")
print(f"📋 Коды: {list(DB_data.keys())}")

if __name__ == '__main__':
    # ФИКС для Docker: используем 0.0.0.0 чтобы принимать соединения извне
    app.run(host='0.0.0.0', port=5000, debug=False)

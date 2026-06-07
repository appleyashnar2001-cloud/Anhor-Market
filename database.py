import sqlite3
from datetime import datetime
import pytz

DB_NAME = "work_time.db"
UZB_TZ = pytz.timezone("Asia/Tashkent")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Ishchilar table
    cursor.execute('''CREATE TABLE IF NOT EXISTS workers (
        tg_id INTEGER PRIMARY KEY,
        name TEXT,
        status TEXT DEFAULT 'inactive'
    )''')
    # Davomat table
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        duration TEXT,
        month_key TEXT
    )''')
    # Arxivlangan oylar table
    cursor.execute('''CREATE TABLE IF NOT EXISTS monthly_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month_key TEXT,
        worker_name TEXT,
        total_time TEXT
    )''')
    # Chat table
    cursor.execute('''CREATE TABLE IF NOT EXISTS chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_name TEXT,
        message TEXT,
        timestamp TEXT
    )''')
    conn.commit()
    conn.close()

def add_worker(tg_id, name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO workers (tg_id, name) VALUES (?, ?)", (tg_id, name))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def get_workers():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id, name, status FROM workers")
    rows = cursor.fetchall()
    conn.close()
    return rows

def check_worker(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM workers WHERE tg_id = ?", (tg_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def start_work(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now(UZB_TZ).strftime("%Y-%m-%d %H:%M:%S")
    month_key = datetime.now(UZB_TZ).strftime("%Y-%m")
    cursor.execute("UPDATE workers SET status = 'active' WHERE tg_id = ?", (tg_id,))
    cursor.execute("INSERT INTO attendance (tg_id, start_time, month_key) VALUES (?, ?, ?)", (tg_id, now, month_key))
    conn.commit()
    conn.close()

def end_work(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now_str = datetime.now(UZB_TZ).strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("SELECT id, start_time FROM attendance WHERE tg_id = ? AND end_time IS NULL ORDER BY id DESC LIMIT 1", (tg_id,))
    row = cursor.fetchone()
    
    if row:
        att_id, start_str = row
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(now_str, "%Y-%m-%d %H:%M:%S")
        
        diff = end_dt - start_dt
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        duration_str = f"{hours} soat {minutes} daqiqa"
        
        cursor.execute("UPDATE attendance SET end_time = ?, duration = ? WHERE id = ?", (now_str, duration_str, att_id))
        cursor.execute("UPDATE workers SET status = 'inactive' WHERE tg_id = ?", (tg_id,))
        conn.commit()
        conn.close()
        return duration_str
    conn.close()
    return None

def get_monthly_report(tg_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_month = datetime.now(UZB_TZ).strftime("%Y-%m")
    cursor.execute("SELECT start_time, end_time FROM attendance WHERE tg_id = ? AND month_key = ? AND end_time IS NOT NULL", (tg_id, current_month))
    rows = cursor.fetchall()
    
    total_seconds = 0
    for start_str, end_str in rows:
        start_dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
        total_seconds += (end_dt - start_dt).total_seconds()
        
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    conn.close()
    return f"{hours} soat {minutes} daqiqa"

def save_chat(sender_name, message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now(UZB_TZ).strftime("%H:%M")
    cursor.execute("INSERT INTO chat_logs (sender_name, message, timestamp) VALUES (?, ?, ?)", (sender_name, message, now))
    conn.commit()
    conn.close()

def get_chat_logs():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT sender_name, message, timestamp FROM chat_logs ORDER BY id DESC LIMIT 30")
    rows = cursor.fetchall()
    conn.close()
    return rows

def auto_close_all():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT tg_id FROM workers WHERE status = 'active'")
    active_workers = cursor.fetchall()
    conn.close()
    
    closed_workers = []
    for (tg_id,) in active_workers:
        dur = end_work(tg_id)
        if dur:
            closed_workers.append((tg_id, dur))
    return closed_workers

def archive_month_tizim():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_month = datetime.now(UZB_TZ).strftime("%Y-%m")
    
    cursor.execute("SELECT tg_id, name FROM workers")
    all_workers = cursor.fetchall()
    
    for tg_id, name in all_workers:
        total = get_monthly_report(tg_id)
        cursor.execute("INSERT INTO monthly_archive (month_key, worker_name, total_time) VALUES (?, ?, ?)", (current_month, name, total))
    
    # Yangi oy uchun joriy jadvalni tozalash shart emas, chunki `month_key` o'zgaradi va filtrda 0 bo'lib ko'rinadi.
    conn.commit()
    conn.close()

def get_archive_reports():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT month_key, worker_name, total_time FROM monthly_archive ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

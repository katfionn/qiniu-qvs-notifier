import sqlite3
import os

DB_PATH = "config/devices.db"

def init_db():
    if not os.path.exists("config"):
        os.makedirs("config")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            namespace_id TEXT NOT NULL,
            gb_id TEXT NOT NULL,
            name TEXT NOT NULL,
            last_state TEXT DEFAULT 'unknown',
            UNIQUE(namespace_id, gb_id)
        )
    ''')
    conn.commit()
    conn.close()

def get_all_devices():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices')
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

def add_device(namespace_id: str, gb_id: str, name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO devices (namespace_id, gb_id, name)
            VALUES (?, ?, ?)
        ''', (namespace_id, gb_id, name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_device(device_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM devices WHERE id = ?', (device_id,))
    conn.commit()
    conn.close()

# 兼容老版本 devices.txt 的数据导入
def import_from_txt():
    if not os.path.exists('devices.txt') and not os.path.exists('检查七牛设备是否在线/devices.txt'):
        return

    txt_path = 'devices.txt' if os.path.exists('devices.txt') else '检查七牛设备是否在线/devices.txt'

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            if ':' not in line:
                continue
            parts = line.strip().split(':')
            if len(parts) == 3:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO devices (namespace_id, gb_id, name)
                        VALUES (?, ?, ?)
                    ''', (parts[0], parts[1], parts[2]))
                except Exception as e:
                    print(f"Import error: {e}")

    conn.commit()
    conn.close()

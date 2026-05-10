import os
import sqlite3
import time

# -------------------------------
# CONFIGURATION
# -------------------------------
DB_PATH = "file_index.db"  # absolute path
SCAN_FOLDERS = ["C:\\Users", "D:\\"]  # you can add more drives if needed
EXCLUDE_DIRS = ["AppData\\Local\\Temp", "AppData\\Local\\Packages", "AppData\\Roaming\\Microsoft\\Windows\\Recent", "Recycle Bin"]

# -------------------------------
# DATABASE SETUP
# -------------------------------
def create_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            name TEXT,
            last_modified REAL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_last_scan():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT value FROM metadata WHERE key='last_scan'")
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else 0

def set_last_scan(ts):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("last_scan", str(ts)))
    conn.commit()
    conn.close()

# -------------------------------
# INDEXER
# -------------------------------
def index_files():
    last_scan = get_last_scan()
    print(f"Starting full index. Last scan: {time.ctime(last_scan)}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    new_last_scan = time.time()

    for root in SCAN_FOLDERS:
        for dirpath, dirs, files in os.walk(root, topdown=True):
            # Skip excluded folders
            dirs[:] = [d for d in dirs if not any(excl in os.path.join(dirpath, d) for excl in EXCLUDE_DIRS)]
            print("Scanning:", dirpath) # debug line
            for f in files:
                if f.lower().endswith(".lnk"):  # skip shortcuts
                    continue
                try:
                    full_path = os.path.join(dirpath, f)
                    mtime = os.path.getmtime(full_path)
                    if mtime > last_scan:
                        cur.execute(
                            "INSERT OR REPLACE INTO files (path, name, last_modified) VALUES (?, ?, ?)",
                            (full_path, f, mtime)
                        )
                except Exception:
                    continue

    conn.commit()
    conn.close()
    set_last_scan(new_last_scan)
    print(f"Indexing complete at {time.ctime(new_last_scan)}")

# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    create_db()
    index_files()

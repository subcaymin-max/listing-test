import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional, Tuple

DB_PATH = "data.db"

@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.commit()
        conn.close()

def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ssot_name TEXT,
                ssot_address TEXT,
                ssot_phone TEXT,
                ssot_website_url TEXT,
                ssot_website_anchor TEXT,
                ssot_hours TEXT,
                url_google TEXT,
                url_apple TEXT,
                url_bing TEXT,
                url_yelp TEXT,
                url_yahoo TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS xpaths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site TEXT NOT NULL,            -- google, apple, bing, yelp, yahoo
                layout TEXT,                   -- for yelp: type1/type2; else null
                field TEXT NOT NULL,           -- entity_name, address, phone, website_link_anchor, hours
                xpath TEXT NOT NULL,
                priority INTEGER DEFAULT 1,    -- lower = higher priority
                active INTEGER DEFAULT 1
            )
        """)

def add_client(data: Dict) -> int:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO clients
            (name, ssot_name, ssot_address, ssot_phone, ssot_website_url, ssot_website_anchor, ssot_hours,
             url_google, url_apple, url_bing, url_yelp, url_yahoo)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data.get("name","").strip(),
            data.get("ssot_name","").strip(),
            data.get("ssot_address","").strip(),
            data.get("ssot_phone","").strip(),
            data.get("ssot_website_url","").strip(),
            data.get("ssot_website_anchor","").strip(),
            data.get("ssot_hours","").strip(),
            data.get("url_google","").strip(),
            data.get("url_apple","").strip(),
            data.get("url_bing","").strip(),
            data.get("url_yelp","").strip(),
            data.get("url_yahoo","").strip(),
        ))
        return c.lastrowid

def update_client(client_id: int, data: Dict) -> None:
    with get_conn() as conn:
        c = conn.cursor()
        fields = ["name","ssot_name","ssot_address","ssot_phone","ssot_website_url","ssot_website_anchor","ssot_hours",
                  "url_google","url_apple","url_bing","url_yelp","url_yahoo"]
        sets = ", ".join([f"{f} = ?" for f in fields])
        values = [data.get(f,"") for f in fields]
        values.append(client_id)
        c.execute(f"UPDATE clients SET {sets} WHERE id = ?", values)

def fetch_clients() -> List[sqlite3.Row]:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM clients ORDER BY id DESC")
        return c.fetchall()

def get_client(client_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
        return c.fetchone()

def delete_client(client_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))

def add_xpath(site: str, field: str, xpath: str, layout: Optional[str]=None, priority: int=1, active: bool=True) -> int:
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO xpaths(site, layout, field, xpath, priority, active)
            VALUES (?,?,?,?,?,?)
        """, (site, layout, field, xpath, priority, 1 if active else 0))
        return c.lastrowid

def list_xpaths(site: Optional[str]=None, field: Optional[str]=None, layout: Optional[str]=None, only_active: bool=False) -> List[sqlite3.Row]:
    with get_conn() as conn:
        q = "SELECT * FROM xpaths WHERE 1=1"
        params: List = []
        if site:
            q += " AND site = ?"; params.append(site)
        if field:
            q += " AND field = ?"; params.append(field)
        if layout:
            q += " AND layout = ?"; params.append(layout)
        if only_active:
            q += " AND active = 1"
        q += " ORDER BY site, layout, field, priority ASC"
        return conn.execute(q, params).fetchall()

def toggle_xpath_active(xpath_id: int, active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE xpaths SET active = ? WHERE id = ?", (1 if active else 0, xpath_id))

def delete_xpath(xpath_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM xpaths WHERE id = ?", (xpath_id,))


import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_DB_LOCK = threading.RLock()


def _app_dir():
    from config import APP_DIR

    return APP_DIR


def db_path():
    return _app_dir() / "ynk.db"


def _baglanti():
    conn = sqlite3.connect(str(db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS warnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    moderator_id INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mod_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    event_type TEXT NOT NULL,
                    actor_id INTEGER,
                    target_id INTEGER,
                    channel_id INTEGER,
                    details TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER,
                    channel_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL,
                    closed_at TEXT
                );
                """
            )
            conn.commit()
        finally:
            conn.close()


def migrate_from_json():
    """Eski JSON dosyalarindan veriyi DB'ye tasir (yalnizca DB bos ise)."""
    with _DB_LOCK:
        conn = _baglanti()
        try:
            mevcut = conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()["c"]
            if mevcut and mevcut > 0:
                return
        finally:
            conn.close()

        from config import APP_DIR

        settings_file = APP_DIR / "settings.json"
        if settings_file.exists():
            try:
                import json as _j

                with open(settings_file, "r", encoding="utf-8-sig") as f:
                    data = _j.load(f)
                if isinstance(data, dict):
                    ayar_kaydet(data)
            except Exception:
                pass

        warnings_file = APP_DIR / "warnings.json"
        if warnings_file.exists():
            try:
                import json as _j

                with open(warnings_file, "r", encoding="utf-8") as f:
                    data = _j.load(f)
                for guild_key, users in (data or {}).items():
                    try:
                        guild_id = int(guild_key)
                    except (TypeError, ValueError):
                        continue
                    for user_key, liste in (users or {}).items():
                        try:
                            user_id = int(user_key)
                        except (TypeError, ValueError):
                            continue
                        for w in liste or []:
                            uyari_ekle(
                                guild_id,
                                user_id,
                                w.get("sebep", ""),
                                w.get("yetkili"),
                                w.get("tarih"),
                            )
            except Exception:
                pass


def ayar_yukle():
    init_db()
    migrate_from_json()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        finally:
            conn.close()
    sonuc = {}
    for row in rows:
        try:
            sonuc[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            sonuc[row["key"]] = row["value"]
    return sonuc


def ayar_kaydet(ayarlar):
    if not isinstance(ayarlar, dict):
        return
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            for anahtar, deger in ayarlar.items():
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(anahtar), json.dumps(deger, ensure_ascii=False)),
                )
            conn.commit()
        finally:
            conn.close()


def uyari_ekle(guild_id, user_id, reason, moderator_id=None, created_at=None):
    init_db()
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    moderator_value = None
    if moderator_id is not None:
        try:
            moderator_value = int(moderator_id)
        except (TypeError, ValueError):
            moderator_value = None
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "INSERT INTO warnings (guild_id, user_id, reason, moderator_id, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(guild_id), int(user_id), str(reason), moderator_value, str(created_at)),
            )
            conn.commit()
        finally:
            conn.close()


def uyari_liste(guild_id, user_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            rows = conn.execute(
                "SELECT reason, moderator_id, created_at FROM warnings "
                "WHERE guild_id=? AND user_id=? ORDER BY id ASC",
                (int(guild_id), int(user_id)),
            ).fetchall()
        finally:
            conn.close()
    return [
        {
            "sebep": r["reason"],
            "yetkili": r["moderator_id"],
            "tarih": r["created_at"],
        }
        for r in rows
    ]


def uyari_temizle(guild_id, user_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "DELETE FROM warnings WHERE guild_id=? AND user_id=?",
                (int(guild_id), int(user_id)),
            )
            conn.commit()
        finally:
            conn.close()


def mod_log_ekle(guild_id, event_type, actor_id=None, target_id=None, channel_id=None, details=None):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "INSERT INTO mod_logs (guild_id, event_type, actor_id, target_id, channel_id, details, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    guild_id,
                    str(event_type),
                    actor_id,
                    target_id,
                    channel_id,
                    details,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def ticket_ekle(guild_id, channel_id, user_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "INSERT INTO tickets (guild_id, channel_id, user_id, status, created_at) VALUES (?, ?, ?, 'open', ?)",
                (guild_id, int(channel_id), int(user_id), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


def ticket_kapat(channel_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "UPDATE tickets SET status='closed', closed_at=? WHERE channel_id=?",
                (datetime.now(timezone.utc).isoformat(), int(channel_id)),
            )
            conn.commit()
        finally:
            conn.close()

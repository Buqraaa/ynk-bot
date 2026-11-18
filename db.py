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
                CREATE TABLE IF NOT EXISTS xp (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    xp INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 0,
                    voice_seconds INTEGER NOT NULL DEFAULT 0,
                    last_message TEXT,
                    PRIMARY KEY (guild_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS giveaways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    prize TEXT NOT NULL,
                    winners_count INTEGER NOT NULL DEFAULT 1,
                    host_id INTEGER NOT NULL,
                    end_time TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS giveaway_entries (
                    giveaway_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    PRIMARY KEY (giveaway_id, user_id)
                );
                CREATE TABLE IF NOT EXISTS automod_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
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


# ===================== XP / LEVEL =====================

def xp_ekle(guild_id, user_id, miktar):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            row = conn.execute(
                "SELECT xp, level FROM xp WHERE guild_id=? AND user_id=?",
                (int(guild_id), int(user_id)),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO xp (guild_id, user_id, xp, level) VALUES (?, ?, ?, 0)",
                    (int(guild_id), int(user_id), miktar),
                )
            else:
                conn.execute(
                    "UPDATE xp SET xp = xp + ? WHERE guild_id=? AND user_id=?",
                    (miktar, int(guild_id), int(user_id)),
                )
            conn.commit()
        finally:
            conn.close()


def xp_getir(guild_id, user_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            row = conn.execute(
                "SELECT xp, level, voice_seconds FROM xp WHERE guild_id=? AND user_id=?",
                (int(guild_id), int(user_id)),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return {"xp": 0, "level": 0, "voice_seconds": 0}
    return {"xp": row["xp"], "level": row["level"], "voice_seconds": row["voice_seconds"]}


def xp_level_guncelle(guild_id, user_id, yeni_level):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "UPDATE xp SET level=? WHERE guild_id=? AND user_id=?",
                (yeni_level, int(guild_id), int(user_id)),
            )
            conn.commit()
        finally:
            conn.close()


def voice_xp_ekle(guild_id, user_id, saniye):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            row = conn.execute(
                "SELECT user_id FROM xp WHERE guild_id=? AND user_id=?",
                (int(guild_id), int(user_id)),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO xp (guild_id, user_id, xp, level, voice_seconds) VALUES (?, ?, 0, 0, ?)",
                    (int(guild_id), int(user_id), saniye),
                )
            else:
                conn.execute(
                    "UPDATE xp SET voice_seconds = voice_seconds + ? WHERE guild_id=? AND user_id=?",
                    (saniye, int(guild_id), int(user_id)),
                )
            conn.commit()
        finally:
            conn.close()


def top_xp_listesi(guild_id, limit=10):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            rows = conn.execute(
                "SELECT user_id, xp, level FROM xp WHERE guild_id=? ORDER BY xp DESC LIMIT ?",
                (int(guild_id), limit),
            ).fetchall()
        finally:
            conn.close()
    return [{"user_id": r["user_id"], "xp": r["xp"], "level": r["level"]} for r in rows]


# ===================== GIVEAWAYS =====================

def giveaway_olustur(guild_id, channel_id, message_id, prize, winners_count, host_id, end_time):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "INSERT INTO giveaways (guild_id, channel_id, message_id, prize, winners_count, host_id, end_time, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?)",
                (int(guild_id), int(channel_id), int(message_id), str(prize), int(winners_count), int(host_id), str(end_time), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            conn.close()


def giveaway_katil(giveaway_id, user_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO giveaway_entries (giveaway_id, user_id) VALUES (?, ?)",
                (int(giveaway_id), int(user_id)),
            )
            conn.commit()
        finally:
            conn.close()


def giveaway_katilimcilar(giveaway_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            rows = conn.execute(
                "SELECT user_id FROM giveaway_entries WHERE giveaway_id=?",
                (int(giveaway_id),),
            ).fetchall()
        finally:
            conn.close()
    return [r["user_id"] for r in rows]


def giveaway_bitir(giveaway_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "UPDATE giveaways SET status='ended' WHERE id=?",
                (int(giveaway_id),),
            )
            conn.commit()
        finally:
            conn.close()


def giveaway_getir(giveaway_id):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            row = conn.execute(
                "SELECT * FROM giveaways WHERE id=?",
                (int(giveaway_id),),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    return dict(row)


def aktif_giveawayler():
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            rows = conn.execute(
                "SELECT * FROM giveaways WHERE status='running'",
            ).fetchall()
        finally:
            conn.close()
    return [dict(r) for r in rows]


# ===================== AUTOMOD LOGS =====================

def automod_log_ekle(guild_id, user_id, action, reason):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            conn.execute(
                "INSERT INTO automod_logs (guild_id, user_id, action, reason, created_at) VALUES (?, ?, ?, ?, ?)",
                (int(guild_id), int(user_id), str(action), str(reason), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


def automod_log_liste(guild_id, limit=50):
    init_db()
    with _DB_LOCK:
        conn = _baglanti()
        try:
            rows = conn.execute(
                "SELECT * FROM automod_logs WHERE guild_id=? ORDER BY id DESC LIMIT ?",
                (int(guild_id), limit),
            ).fetchall()
        finally:
            conn.close()
    return [dict(r) for r in rows]

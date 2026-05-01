import os
from datetime import date, timedelta
from typing import Optional

# --- PostgreSQL / Supabase support ---
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    import streamlit as st
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", None)
except Exception:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", None)

USE_POSTGRES = bool(SUPABASE_URL and PSYCOPG2_AVAILABLE)

# SQLite fallback
import sqlite3
DB_PATH = "aanwezigheid.db"

# --- Trainingsconfig ---
TRAININGEN = [
    (0, "Maandag", "19:30"),
    (1, "Dinsdag", "16:30"),
    (2, "Woensdag", "18:00"),
]

UITZONDERINGEN_SEED = {
    date(2026, 5, 5),
    date(2026, 5, 25),
}

STARTDATUM = date(2026, 5, 4)
EINDDATUM = date(2026, 7, 1)


# --- Connectie ---
def get_connection():
    if USE_POSTGRES:
        return psycopg2.connect(SUPABASE_URL)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _rows_to_dicts(cursor):
    """Zet cursor-resultaten altijd om naar lijst van dicts."""
    rows = cursor.fetchall()
    if USE_POSTGRES:
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, r)) for r in rows]
    return [dict(r) for r in rows]


def _q(sql):
    """Vervang ? placeholders door %s voor PostgreSQL."""
    if USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


# --- Init ---
def init_db():
    with get_connection() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""CREATE TABLE IF NOT EXISTS roeiers (
                id SERIAL PRIMARY KEY,
                naam TEXT UNIQUE NOT NULL,
                aangemaakt_op DATE DEFAULT CURRENT_DATE
            )""")
            cur.execute("""CREATE TABLE IF NOT EXISTS aanwezigheid (
                id SERIAL PRIMARY KEY,
                roeier_id INTEGER NOT NULL,
                training_datum TEXT NOT NULL,
                dag_naam TEXT NOT NULL,
                tijd TEXT NOT NULL,
                aanwezig INTEGER NOT NULL DEFAULT 1,
                bijgewerkt_op TIMESTAMP DEFAULT NOW(),
                UNIQUE(roeier_id, training_datum),
                FOREIGN KEY (roeier_id) REFERENCES roeiers(id)
            )""")
            cur.execute("CREATE TABLE IF NOT EXISTS uitzonderingen (datum TEXT PRIMARY KEY)")
            cur.execute("CREATE TABLE IF NOT EXISTS extra_trainingen (datum TEXT PRIMARY KEY, tijd TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS gelockte_trainingen (datum TEXT PRIMARY KEY)")
            for d in UITZONDERINGEN_SEED:
                cur.execute(
                    "INSERT INTO uitzonderingen (datum) VALUES (%s) ON CONFLICT DO NOTHING",
                    (d.isoformat(),)
                )
        else:
            cur.execute("""CREATE TABLE IF NOT EXISTS roeiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                naam TEXT UNIQUE NOT NULL,
                aangemaakt_op TEXT DEFAULT (date('now'))
            )""")
            cur.execute("""CREATE TABLE IF NOT EXISTS aanwezigheid (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roeier_id INTEGER NOT NULL,
                training_datum TEXT NOT NULL,
                dag_naam TEXT NOT NULL,
                tijd TEXT NOT NULL,
                aanwezig INTEGER NOT NULL DEFAULT 1,
                bijgewerkt_op TEXT DEFAULT (datetime('now')),
                UNIQUE(roeier_id, training_datum),
                FOREIGN KEY (roeier_id) REFERENCES roeiers(id)
            )""")
            cur.execute("CREATE TABLE IF NOT EXISTS uitzonderingen (datum TEXT PRIMARY KEY)")
            cur.execute("CREATE TABLE IF NOT EXISTS extra_trainingen (datum TEXT PRIMARY KEY, tijd TEXT NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS gelockte_trainingen (datum TEXT PRIMARY KEY)")
            for d in UITZONDERINGEN_SEED:
                cur.execute("INSERT OR IGNORE INTO uitzonderingen (datum) VALUES (?)", (d.isoformat(),))
        conn.commit()


# --- Trainingen genereren ---
def get_alle_trainingen() -> list[dict]:
    vandaag = date.today()
    uitzonderingen_db = set(get_uitzonderingen())
    extra_db = get_extra_trainingen()

    trainingen = []
    huidige_datum = STARTDATUM
    while huidige_datum < EINDDATUM:
        weekdag = huidige_datum.weekday()
        for dag_nr, dag_naam, tijd in TRAININGEN:
            if weekdag == dag_nr and huidige_datum not in uitzonderingen_db:
                trainingen.append({
                    "datum": huidige_datum,
                    "datum_str": huidige_datum.isoformat(),
                    "dag_naam": dag_naam,
                    "tijd": tijd,
                    "label": f"{dag_naam} {huidige_datum.strftime('%-d %b')} – {tijd}",
                    "verleden": huidige_datum < vandaag,
                })
        huidige_datum += timedelta(days=1)

    bestaande_datums = {t["datum"] for t in trainingen}
    for e in extra_db:
        if e["datum"] not in bestaande_datums:
            d = e["datum"]
            dag_naam = ["Maandag","Dinsdag","Woensdag","Donderdag","Vrijdag","Zaterdag","Zondag"][d.weekday()]
            trainingen.append({
                "datum": d,
                "datum_str": d.isoformat(),
                "dag_naam": dag_naam,
                "tijd": e["tijd"],
                "label": f"{dag_naam} {d.strftime('%-d %b')} – {e['tijd']}",
                "verleden": d < vandaag,
            })

    trainingen.sort(key=lambda t: t["datum"])
    return trainingen


# --- Roeiers ---
def roeier_bestaat(naam: str) -> Optional[int]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT id FROM roeiers WHERE naam = ?"), (naam,))
        rows = _rows_to_dicts(cur)
        return rows[0]["id"] if rows else None


def maak_roeier(naam: str) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("INSERT INTO roeiers (naam) VALUES (%s) RETURNING id", (naam,))
            roeier_id = cur.fetchone()[0]
        else:
            cur.execute("INSERT INTO roeiers (naam) VALUES (?)", (naam,))
            roeier_id = cur.lastrowid
        conn.commit()
        return roeier_id


def get_of_maak_roeier(naam: str) -> int:
    roeier_id = roeier_bestaat(naam)
    return roeier_id if roeier_id else maak_roeier(naam)


def get_alle_roeiers() -> list[str]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT naam FROM roeiers ORDER BY naam")
        return [r["naam"] for r in _rows_to_dicts(cur)]


def verwijder_roeier(naam: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT id FROM roeiers WHERE naam = ?"), (naam,))
        rows = _rows_to_dicts(cur)
        if rows:
            rid = rows[0]["id"]
            cur.execute(_q("DELETE FROM aanwezigheid WHERE roeier_id = ?"), (rid,))
            cur.execute(_q("DELETE FROM roeiers WHERE id = ?"), (rid,))
            conn.commit()


def verwijder_aanwezigheid_roeier(naam: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT id FROM roeiers WHERE naam = ?"), (naam,))
        rows = _rows_to_dicts(cur)
        if rows:
            cur.execute(_q("DELETE FROM aanwezigheid WHERE roeier_id = ?"), (rows[0]["id"],))
            conn.commit()


# --- Aanwezigheid ---
def sla_aanwezigheid_op(roeier_id: int, datum: str, dag_naam: str, tijd: str, aanwezig: bool):
    with get_connection() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("""
                INSERT INTO aanwezigheid (roeier_id, training_datum, dag_naam, tijd, aanwezig)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (roeier_id, training_datum) DO UPDATE SET
                    aanwezig = EXCLUDED.aanwezig,
                    bijgewerkt_op = NOW()
            """, (roeier_id, datum, dag_naam, tijd, int(aanwezig)))
        else:
            cur.execute("""
                INSERT INTO aanwezigheid (roeier_id, training_datum, dag_naam, tijd, aanwezig)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(roeier_id, training_datum) DO UPDATE SET
                    aanwezig = excluded.aanwezig,
                    bijgewerkt_op = datetime('now')
            """, (roeier_id, datum, dag_naam, tijd, int(aanwezig)))
        conn.commit()


def get_aanwezigheid_roeier(roeier_id: int) -> dict[str, bool]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_q("SELECT training_datum, aanwezig FROM aanwezigheid WHERE roeier_id = ?"), (roeier_id,))
        return {r["training_datum"]: bool(r["aanwezig"]) for r in _rows_to_dicts(cur)}


def get_overzicht_per_training() -> dict[str, list[str]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT a.training_datum, r.naam
            FROM aanwezigheid a
            JOIN roeiers r ON r.id = a.roeier_id
            WHERE a.aanwezig = 1
            ORDER BY a.training_datum, r.naam
        """)
        overzicht = {}
        for r in _rows_to_dicts(cur):
            overzicht.setdefault(r["training_datum"], []).append(r["naam"])
        return overzicht


# --- Uitzonderingen ---
def get_uitzonderingen() -> list:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT datum FROM uitzonderingen ORDER BY datum")
        return [date.fromisoformat(r["datum"]) for r in _rows_to_dicts(cur)]


def voeg_uitzondering_toe(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("INSERT INTO uitzonderingen (datum) VALUES (%s) ON CONFLICT DO NOTHING", (datum_str,))
        else:
            cur.execute("INSERT OR IGNORE INTO uitzonderingen (datum) VALUES (?)", (datum_str,))
        conn.commit()


def verwijder_uitzondering(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_q("DELETE FROM uitzonderingen WHERE datum = ?"), (datum_str,))
        conn.commit()


# --- Extra trainingen ---
def get_extra_trainingen() -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT datum, tijd FROM extra_trainingen ORDER BY datum")
        return [{"datum": date.fromisoformat(r["datum"]), "tijd": r["tijd"]} for r in _rows_to_dicts(cur)]


def voeg_extra_training_toe(datum, tijd: str):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("INSERT INTO extra_trainingen (datum, tijd) VALUES (%s, %s) ON CONFLICT DO NOTHING", (datum_str, tijd))
        else:
            cur.execute("INSERT OR IGNORE INTO extra_trainingen (datum, tijd) VALUES (?, ?)", (datum_str, tijd))
        conn.commit()


def verwijder_extra_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_q("DELETE FROM extra_trainingen WHERE datum = ?"), (datum_str,))
        conn.commit()


# --- Gelockte trainingen ---
def get_gelockte_trainingen() -> set:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT datum FROM gelockte_trainingen")
        return {date.fromisoformat(r["datum"]) for r in _rows_to_dicts(cur)}


def lock_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        cur = conn.cursor()
        if USE_POSTGRES:
            cur.execute("INSERT INTO gelockte_trainingen (datum) VALUES (%s) ON CONFLICT DO NOTHING", (datum_str,))
        else:
            cur.execute("INSERT OR IGNORE INTO gelockte_trainingen (datum) VALUES (?)", (datum_str,))
        conn.commit()


def unlock_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(_q("DELETE FROM gelockte_trainingen WHERE datum = ?"), (datum_str,))
        conn.commit()

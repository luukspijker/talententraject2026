import os
import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Optional

# --- PostgreSQL / Supabase support ---
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    import streamlit as st
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", None)
except Exception:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", None)

USE_POSTGRES = bool(SUPABASE_URL and PSYCOPG2_AVAILABLE)
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


# --- Connectie: één persistente connectie per sessie via st.cache_resource ---
@st.cache_resource
def _cached_pg_conn():
    conn = psycopg2.connect(SUPABASE_URL)
    conn.autocommit = False
    return conn


@contextmanager
def db_conn():
    if USE_POSTGRES:
        conn = _cached_pg_conn()
        # Reset eventuele mislukte transacties
        if conn.closed:
            _cached_pg_conn.clear()
            conn = _cached_pg_conn()
        try:
            conn.reset()
        except Exception:
            _cached_pg_conn.clear()
            conn = _cached_pg_conn()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _q(sql):
    """Vervang ? placeholders door %s voor PostgreSQL."""
    if USE_POSTGRES:
        return sql.replace("?", "%s")
    return sql


def _rows(cur):
    rows = cur.fetchall()
    return [dict(r) for r in rows]


# --- Init ---
def init_db():
    with db_conn() as cur:
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
    with db_conn() as cur:
        cur.execute(_q("SELECT id FROM roeiers WHERE naam = ?"), (naam,))
        rows = _rows(cur)
        return rows[0]["id"] if rows else None


def maak_roeier(naam: str) -> int:
    with db_conn() as cur:
        if USE_POSTGRES:
            cur.execute("INSERT INTO roeiers (naam) VALUES (%s) RETURNING id", (naam,))
            return cur.fetchone()["id"]
        else:
            cur.execute("INSERT INTO roeiers (naam) VALUES (?)", (naam,))
            return cur.lastrowid


def get_of_maak_roeier(naam: str) -> int:
    roeier_id = roeier_bestaat(naam)
    return roeier_id if roeier_id else maak_roeier(naam)


def get_alle_roeiers() -> list[str]:
    with db_conn() as cur:
        cur.execute("SELECT naam FROM roeiers ORDER BY naam")
        return [r["naam"] for r in _rows(cur)]


def verwijder_roeier(naam: str):
    with db_conn() as cur:
        cur.execute(_q("SELECT id FROM roeiers WHERE naam = ?"), (naam,))
        rows = _rows(cur)
        if rows:
            rid = rows[0]["id"]
            cur.execute(_q("DELETE FROM aanwezigheid WHERE roeier_id = ?"), (rid,))
            cur.execute(_q("DELETE FROM roeiers WHERE id = ?"), (rid,))


def verwijder_aanwezigheid_roeier(naam: str):
    with db_conn() as cur:
        cur.execute(_q("SELECT id FROM roeiers WHERE naam = ?"), (naam,))
        rows = _rows(cur)
        if rows:
            cur.execute(_q("DELETE FROM aanwezigheid WHERE roeier_id = ?"), (rows[0]["id"],))


# --- Aanwezigheid ---
def sla_aanwezigheid_op(roeier_id: int, datum: str, dag_naam: str, tijd: str, aanwezig: bool):
    with db_conn() as cur:
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


def get_aanwezigheid_roeier(roeier_id: int) -> dict[str, bool]:
    with db_conn() as cur:
        cur.execute(_q("SELECT training_datum, aanwezig FROM aanwezigheid WHERE roeier_id = ?"), (roeier_id,))
        return {r["training_datum"]: bool(r["aanwezig"]) for r in _rows(cur)}


def get_overzicht_per_training() -> dict[str, list[str]]:
    with db_conn() as cur:
        cur.execute("""
            SELECT a.training_datum, r.naam
            FROM aanwezigheid a
            JOIN roeiers r ON r.id = a.roeier_id
            WHERE a.aanwezig != 0
            ORDER BY a.training_datum, r.naam
        """)
        overzicht = {}
        for r in _rows(cur):
            overzicht.setdefault(r["training_datum"], []).append(r["naam"])
        return overzicht


# --- Uitzonderingen ---
def get_uitzonderingen() -> list:
    with db_conn() as cur:
        cur.execute("SELECT datum FROM uitzonderingen ORDER BY datum")
        return [date.fromisoformat(r["datum"]) for r in _rows(cur)]


def voeg_uitzondering_toe(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with db_conn() as cur:
        if USE_POSTGRES:
            cur.execute("INSERT INTO uitzonderingen (datum) VALUES (%s) ON CONFLICT DO NOTHING", (datum_str,))
        else:
            cur.execute("INSERT OR IGNORE INTO uitzonderingen (datum) VALUES (?)", (datum_str,))


def verwijder_uitzondering(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with db_conn() as cur:
        cur.execute(_q("DELETE FROM uitzonderingen WHERE datum = ?"), (datum_str,))


# --- Extra trainingen ---
def get_extra_trainingen() -> list[dict]:
    with db_conn() as cur:
        cur.execute("SELECT datum, tijd FROM extra_trainingen ORDER BY datum")
        return [{"datum": date.fromisoformat(r["datum"]), "tijd": r["tijd"]} for r in _rows(cur)]


def voeg_extra_training_toe(datum, tijd: str):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with db_conn() as cur:
        if USE_POSTGRES:
            cur.execute("INSERT INTO extra_trainingen (datum, tijd) VALUES (%s, %s) ON CONFLICT DO NOTHING", (datum_str, tijd))
        else:
            cur.execute("INSERT OR IGNORE INTO extra_trainingen (datum, tijd) VALUES (?, ?)", (datum_str, tijd))


def verwijder_extra_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with db_conn() as cur:
        cur.execute(_q("DELETE FROM extra_trainingen WHERE datum = ?"), (datum_str,))


# --- Gelockte trainingen ---
def get_gelockte_trainingen() -> set:
    with db_conn() as cur:
        cur.execute("SELECT datum FROM gelockte_trainingen")
        return {date.fromisoformat(r["datum"]) for r in _rows(cur)}


def lock_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with db_conn() as cur:
        if USE_POSTGRES:
            cur.execute("INSERT INTO gelockte_trainingen (datum) VALUES (%s) ON CONFLICT DO NOTHING", (datum_str,))
        else:
            cur.execute("INSERT OR IGNORE INTO gelockte_trainingen (datum) VALUES (?)", (datum_str,))


def unlock_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with db_conn() as cur:
        cur.execute(_q("DELETE FROM gelockte_trainingen WHERE datum = ?"), (datum_str,))

import sqlite3
from datetime import date, timedelta
from typing import Optional

DB_PATH = "aanwezigheid.db"

TRAININGEN = [
    (0, "Maandag", "19:30"),   # Monday
    (1, "Dinsdag", "16:30"),   # Tuesday
    (2, "Woensdag", "18:00"),  # Wednesday
]

UITZONDERINGEN = {
    date(2026, 5, 5),
    date(2026, 5, 25),
}

STARTDATUM = date(2026, 5, 4)  # Eerste maandag van het seizoen
EINDDATUM = date(2026, 7, 1)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS roeiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                naam TEXT UNIQUE NOT NULL,
                aangemaakt_op TEXT DEFAULT (date('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS aanwezigheid (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roeier_id INTEGER NOT NULL,
                training_datum TEXT NOT NULL,
                dag_naam TEXT NOT NULL,
                tijd TEXT NOT NULL,
                aanwezig INTEGER NOT NULL DEFAULT 1,
                bijgewerkt_op TEXT DEFAULT (datetime('now')),
                UNIQUE(roeier_id, training_datum),
                FOREIGN KEY (roeier_id) REFERENCES roeiers(id)
            )
        """)
        conn.commit()


def get_alle_trainingen() -> list[dict]:
    """Genereer alle trainingsdatums van het hele seizoen (verleden + toekomst)."""
    vandaag = date.today()
    trainingen = []
    huidige_datum = STARTDATUM

    while huidige_datum < EINDDATUM:
        weekdag = huidige_datum.weekday()
        for dag_nr, dag_naam, tijd in TRAININGEN:
            if weekdag == dag_nr:
                if huidige_datum not in UITZONDERINGEN:
                    trainingen.append({
                        "datum": huidige_datum,
                        "datum_str": huidige_datum.isoformat(),
                        "dag_naam": dag_naam,
                        "tijd": tijd,
                        "label": f"{dag_naam} {huidige_datum.strftime('%-d %b')} – {tijd}",
                        "verleden": huidige_datum < vandaag,
                    })
        huidige_datum += timedelta(days=1)

    return trainingen


def roeier_bestaat(naam: str) -> Optional[int]:
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM roeiers WHERE naam = ?", (naam,)).fetchone()
        return row["id"] if row else None


def maak_roeier(naam: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute("INSERT INTO roeiers (naam) VALUES (?)", (naam,))
        conn.commit()
        return cursor.lastrowid


def get_of_maak_roeier(naam: str) -> int:
    roeier_id = roeier_bestaat(naam)
    if roeier_id is None:
        roeier_id = maak_roeier(naam)
    return roeier_id


def sla_aanwezigheid_op(roeier_id: int, datum: str, dag_naam: str, tijd: str, aanwezig: bool):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO aanwezigheid (roeier_id, training_datum, dag_naam, tijd, aanwezig)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(roeier_id, training_datum) DO UPDATE SET
                aanwezig = excluded.aanwezig,
                bijgewerkt_op = datetime('now')
        """, (roeier_id, datum, dag_naam, tijd, int(aanwezig)))
        conn.commit()


def get_aanwezigheid_roeier(roeier_id: int) -> dict[str, bool]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT training_datum, aanwezig FROM aanwezigheid WHERE roeier_id = ?",
            (roeier_id,)
        ).fetchall()
        return {row["training_datum"]: bool(row["aanwezig"]) for row in rows}


def get_overzicht_per_training() -> dict[str, list[str]]:
    """Geeft per datum een lijst van namen van aanwezige roeiers."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT a.training_datum, r.naam
            FROM aanwezigheid a
            JOIN roeiers r ON r.id = a.roeier_id
            WHERE a.aanwezig = 1
            ORDER BY a.training_datum, r.naam
        """).fetchall()
        overzicht = {}
        for row in rows:
            overzicht.setdefault(row["training_datum"], []).append(row["naam"])
        return overzicht


def get_alle_roeiers() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT naam FROM roeiers ORDER BY naam").fetchall()
        return [row["naam"] for row in rows]

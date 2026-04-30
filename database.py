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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS uitzonderingen (
                datum TEXT PRIMARY KEY
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extra_trainingen (
                datum TEXT PRIMARY KEY,
                tijd TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gelockte_trainingen (
                datum TEXT PRIMARY KEY
            )
        """)
        # Seed de bekende uitzonderingen als ze er nog niet in staan
        for d in UITZONDERINGEN:
            conn.execute("INSERT OR IGNORE INTO uitzonderingen (datum) VALUES (?)", (d.isoformat(),))
        conn.commit()


def get_alle_trainingen() -> list[dict]:
    """Genereer alle trainingsdatums van het hele seizoen (verleden + toekomst),
    inclusief extra trainingen en met uitzonderingen uit de database."""
    vandaag = date.today()

    # Haal uitzonderingen en extra trainingen op uit de database
    uitzonderingen_db = set(get_uitzonderingen())
    extra_db = get_extra_trainingen()

    trainingen = []
    huidige_datum = STARTDATUM

    while huidige_datum < EINDDATUM:
        weekdag = huidige_datum.weekday()
        for dag_nr, dag_naam, tijd in TRAININGEN:
            if weekdag == dag_nr:
                if huidige_datum not in uitzonderingen_db:
                    trainingen.append({
                        "datum": huidige_datum,
                        "datum_str": huidige_datum.isoformat(),
                        "dag_naam": dag_naam,
                        "tijd": tijd,
                        "label": f"{dag_naam} {huidige_datum.strftime('%-d %b')} – {tijd}",
                        "verleden": huidige_datum < vandaag,
                    })
        huidige_datum += timedelta(days=1)

    # Voeg extra trainingen toe
    extra_datums = {t["datum"] for t in trainingen}
    for e in extra_db:
        if e["datum"] not in extra_datums:
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


def verwijder_roeier(naam: str):
    """Verwijder een roeier en al zijn/haar aanwezigheidsdata."""
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM roeiers WHERE naam = ?", (naam,)).fetchone()
        if row:
            conn.execute("DELETE FROM aanwezigheid WHERE roeier_id = ?", (row["id"],))
            conn.execute("DELETE FROM roeiers WHERE id = ?", (row["id"],))
            conn.commit()


def verwijder_aanwezigheid_roeier(naam: str):
    """Verwijder alleen de aanwezigheidsdata van een roeier, niet de roeier zelf."""
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM roeiers WHERE naam = ?", (naam,)).fetchone()
        if row:
            conn.execute("DELETE FROM aanwezigheid WHERE roeier_id = ?", (row["id"],))
            conn.commit()


# --- Uitzonderingen (datums zonder training) ---

def get_uitzonderingen() -> list:
    with get_connection() as conn:
        rows = conn.execute("SELECT datum FROM uitzonderingen ORDER BY datum").fetchall()
        return [date.fromisoformat(row["datum"]) for row in rows]


def voeg_uitzondering_toe(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO uitzonderingen (datum) VALUES (?)", (datum_str,))
        conn.commit()


def verwijder_uitzondering(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        conn.execute("DELETE FROM uitzonderingen WHERE datum = ?", (datum_str,))
        conn.commit()


# --- Extra trainingen (buiten vast schema) ---

def get_extra_trainingen() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT datum, tijd FROM extra_trainingen ORDER BY datum").fetchall()
        return [{"datum": date.fromisoformat(row["datum"]), "tijd": row["tijd"]} for row in rows]


def voeg_extra_training_toe(datum, tijd: str):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO extra_trainingen (datum, tijd) VALUES (?, ?)", (datum_str, tijd))
        conn.commit()


def verwijder_extra_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        conn.execute("DELETE FROM extra_trainingen WHERE datum = ?", (datum_str,))
        conn.commit()


# --- Gelockte trainingen ---

def get_gelockte_trainingen() -> set:
    with get_connection() as conn:
        rows = conn.execute("SELECT datum FROM gelockte_trainingen").fetchall()
        return {date.fromisoformat(row["datum"]) for row in rows}


def lock_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO gelockte_trainingen (datum) VALUES (?)", (datum_str,))
        conn.commit()


def unlock_training(datum):
    datum_str = datum.isoformat() if not isinstance(datum, str) else datum
    with get_connection() as conn:
        conn.execute("DELETE FROM gelockte_trainingen WHERE datum = ?", (datum_str,))
        conn.commit()

# 🚣 Roeischema – Aanwezigheidsapp

Eenvoudige Streamlit-app voor roeiers om aanwezigheid bij trainingen aan te geven.

## Trainingen
- Maandag 19:30
- Dinsdag 16:30
- Woensdag 18:00

Geen training op: 5 mei en 25 mei 2025. Seizoen loopt t/m 1 juli 2025.

---

## Lokaal draaien

### 1. Installeer dependencies
```bash
pip install -r requirements.txt
```

### 2. Start de app
```bash
streamlit run app.py
```

De app opent automatisch in je browser op `http://localhost:8501`.

---

## Hosten via Streamlit Community Cloud (gratis)

1. Zet de bestanden in een **GitHub repository** (public of private)
2. Ga naar [share.streamlit.io](https://share.streamlit.io)
3. Log in met GitHub en klik op **"New app"**
4. Kies je repository, branch `main`, en bestand `app.py`
5. Klik **Deploy** – binnen een minuut is de app live

Je krijgt een link zoals `https://jouwapp.streamlit.app` die je kunt delen met de roeiers.

> **Let op:** Op Streamlit Cloud wordt de SQLite database gereset bij elke herstart.
> Voor productiegebruik is het aan te raden over te stappen op een externe database,
> bijv. [Supabase](https://supabase.com) (gratis PostgreSQL in de cloud).

---

## Bestandsstructuur

```
roei-app/
├── app.py           # Streamlit UI
├── database.py      # SQLite logica & trainingsgeneratie
├── requirements.txt
└── README.md
```

import streamlit as st
from database import (
    init_db,
    get_of_maak_roeier,
    get_alle_trainingen,
    sla_aanwezigheid_op,
    get_aanwezigheid_roeier,
    get_overzicht_per_training,
    get_alle_roeiers,
)

st.set_page_config(
    page_title="Roeischema",
    page_icon="🚣",
    layout="centered",
)

# Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'DM Serif Display', serif;
    }
    .training-card {
        background: #f8f7f4;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #1a3a5c;
    }
    .aanwezig-badge {
        display: inline-block;
        background: #d4edda;
        color: #155724;
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .afwezig-badge {
        display: inline-block;
        background: #f8d7da;
        color: #721c24;
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .onbekend-badge {
        display: inline-block;
        background: #e2e3e5;
        color: #495057;
        border-radius: 20px;
        padding: 2px 10px;
        font-size: 0.8rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

init_db()

# --- Sessie: naam opslaan ---
if "roeier_naam" not in st.session_state:
    st.session_state.roeier_naam = None
if "roeier_id" not in st.session_state:
    st.session_state.roeier_id = None

# --- Navigatie ---
pagina = st.sidebar.radio("Navigatie", ["📅 Mijn aanwezigheid", "👥 Groepsoverzicht"])

st.title("🚣 Roeischema")

# --- Naam kiezen ---
if st.session_state.roeier_naam is None:
    st.subheader("Welkom! Wie ben jij?")

    bestaande_namen = get_alle_roeiers()
    optie = st.radio("", ["Ik sta al in de lijst", "Ik ben nieuw"], horizontal=True)

    if optie == "Ik sta al in de lijst" and bestaande_namen:
        naam = st.selectbox("Kies je naam", bestaande_namen)
    else:
        naam = st.text_input("Voer je naam in", placeholder="bijv. Jan de Vries")

    if st.button("Doorgaan →", type="primary"):
        naam = naam.strip()
        if naam:
            roeier_id = get_of_maak_roeier(naam)
            st.session_state.roeier_naam = naam
            st.session_state.roeier_id = roeier_id
            st.rerun()
        else:
            st.warning("Vul eerst een naam in.")
    st.stop()

# --- Ingelogd als ---
st.sidebar.markdown(f"**Ingelogd als:** {st.session_state.roeier_naam}")
if st.sidebar.button("Wissel van gebruiker"):
    st.session_state.roeier_naam = None
    st.session_state.roeier_id = None
    st.rerun()

trainingen = get_alle_trainingen()

# ==============================
# PAGINA 1: Eigen aanwezigheid
# ==============================
if pagina == "📅 Mijn aanwezigheid":
    st.subheader(f"Hallo {st.session_state.roeier_naam}! 👋")
    st.caption("Geef hieronder aan bij welke trainingen je aanwezig bent.")

    huidige_status = get_aanwezigheid_roeier(st.session_state.roeier_id)

    if not trainingen:
        st.info("Er zijn geen trainingen meer gepland.")
        st.stop()

    wijzigingen = {}

    for t in trainingen:
        datum_str = t["datum_str"]
        huidige = huidige_status.get(datum_str)  # True/False/None

        col1, col2 = st.columns([3, 2])
        with col1:
            st.markdown(f"**{t['dag_naam']}** {t['datum'].strftime('%-d %B')} &nbsp; `{t['tijd']}`", unsafe_allow_html=True)
        with col2:
            if huidige is True:
                badge = "✅ Aanwezig"
            elif huidige is False:
                badge = "❌ Afwezig"
            else:
                badge = "— Niet opgegeven"

            keuze = st.selectbox(
                label="status",
                options=["Niet opgegeven", "Aanwezig", "Afwezig"],
                index=0 if huidige is None else (1 if huidige else 2),
                key=f"keuze_{datum_str}",
                label_visibility="collapsed",
            )
            wijzigingen[datum_str] = (keuze, t)

    st.divider()
    if st.button("💾 Opslaan", type="primary", use_container_width=True):
        for datum_str, (keuze, t) in wijzigingen.items():
            if keuze != "Niet opgegeven":
                sla_aanwezigheid_op(
                    roeier_id=st.session_state.roeier_id,
                    datum=datum_str,
                    dag_naam=t["dag_naam"],
                    tijd=t["tijd"],
                    aanwezig=(keuze == "Aanwezig"),
                )
        st.success("Opgeslagen! ✅")
        st.rerun()

# ==============================
# PAGINA 2: Groepsoverzicht
# ==============================
elif pagina == "👥 Groepsoverzicht":
    st.subheader("Groepsoverzicht")
    st.caption("Wie is aangemeld voor welke training?")

    overzicht = get_overzicht_per_training()

    if not trainingen:
        st.info("Geen trainingen gepland.")
        st.stop()

    for t in trainingen:
        datum_str = t["datum_str"]
        aanwezigen = overzicht.get(datum_str, [])
        aantal = len(aanwezigen)

        with st.expander(f"**{t['dag_naam']} {t['datum'].strftime('%-d %B')}** – {t['tijd']}  ·  {aantal} aangemeld"):
            if aanwezigen:
                for naam in aanwezigen:
                    st.markdown(f"• {naam}")
            else:
                st.caption("Nog niemand aangemeld.")

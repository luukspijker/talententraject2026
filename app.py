import streamlit as st
from database import (
    init_db,
    get_of_maak_roeier,
    get_alle_trainingen,
    sla_aanwezigheid_op,
    get_aanwezigheid_roeier,
    get_overzicht_per_training,
    get_alle_roeiers,
    verwijder_roeier,
    verwijder_aanwezigheid_roeier,
    get_uitzonderingen,
    voeg_uitzondering_toe,
    verwijder_uitzondering,
    get_extra_trainingen,
    voeg_extra_training_toe,
    verwijder_extra_training,
    get_gelockte_trainingen,
    lock_training,
    unlock_training,
)

st.set_page_config(
    page_title="Talententraject 2026",
    page_icon="🚣",
    layout="centered",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    h1, h2, h3 { font-family: 'DM Serif Display', serif; }
</style>
""", unsafe_allow_html=True)

init_db()

# --- Sessie ---
for key, default in [
    ("roeier_naam", None),
    ("roeier_id", None),
    ("beheerder", False),
    ("pagina", "📅 Mijn aanwezigheid"),
    ("opgeslagen", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# --- Navigatie ---
PAGINAS = ["📅 Mijn aanwezigheid", "👥 Groepsoverzicht", "🔒 Beheer"]
pagina = st.sidebar.radio(
    "Navigatie",
    PAGINAS,
    index=PAGINAS.index(st.session_state.pagina),
    key="nav_radio",
)
st.session_state.pagina = pagina

st.title("🚣 Talententraject 2026")

# ==============================
# BEHEERPAGINA
# ==============================
if pagina == "🔒 Beheer":
    st.subheader("🔒 Beheer")

    if not st.session_state.beheerder:
        wachtwoord = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", type="primary"):
            if wachtwoord == "talentenhoofdcoach26":
                st.session_state.beheerder = True
                st.rerun()
            else:
                st.error("Onjuist wachtwoord.")
        st.stop()

    st.sidebar.success("✅ Beheerder ingelogd")
    if st.sidebar.button("Uitloggen beheer"):
        st.session_state.beheerder = False
        st.rerun()

    tab1, tab2 = st.tabs(["👤 Roeiers", "📅 Trainingen"])

    with tab1:
        st.markdown("### Roeiers verwijderen")
        alle_roeiers = get_alle_roeiers()
        if not alle_roeiers:
            st.info("Er zijn nog geen roeiers.")
        else:
            te_verwijderen = st.selectbox("Kies een roeier", alle_roeiers, key="verwijder_selectbox")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ Verwijder roeier + data", type="primary", use_container_width=True):
                    verwijder_roeier(te_verwijderen)
                    st.session_state.toast = f"✅ {te_verwijderen} volledig verwijderd."
                    st.rerun()
            with col2:
                if st.button("🧹 Wis alleen keuzes", use_container_width=True):
                    verwijder_aanwezigheid_roeier(te_verwijderen)
                    st.session_state.toast = f"✅ Keuzes van {te_verwijderen} gewist."
                    st.rerun()

    with tab2:
        st.divider()
        st.markdown("### Trainingen locken")
        st.caption("Gelockte trainingen kunnen niet meer worden aangepast door roeiers.")

        gelockt = get_gelockte_trainingen()
        alle_trainingen = get_alle_trainingen()
        toekomstige_trainingen = [t for t in alle_trainingen if not t["verleden"]]

        if not toekomstige_trainingen:
            st.caption("Geen aankomende trainingen.")
        else:
            for t in toekomstige_trainingen:
                col1, col2 = st.columns([3, 1])
                with col1:
                    is_gelockt = t["datum"] in gelockt
                    label = f"🔒 {t['label']}" if is_gelockt else t["label"]
                    st.write(label)
                with col2:
                    if is_gelockt:
                        if st.button("Unlock", key=f"unlock_{t['datum_str']}"):
                            unlock_training(t["datum"])
                            st.rerun()
                    else:
                        if st.button("Lock", key=f"lock_{t['datum_str']}"):
                            lock_training(t["datum"])
                            st.rerun()

        st.divider()
        st.markdown("### Uitzonderingen (geen training)")
        uitzonderingen = get_uitzonderingen()

        if uitzonderingen:
            for datum in sorted(uitzonderingen):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(datum.strftime("%-d %B %Y"))
                with col2:
                    if st.button("Verwijder", key=f"del_uit_{datum}"):
                        verwijder_uitzondering(datum)
                        st.rerun()
        else:
            st.caption("Geen uitzonderingen opgeslagen.")

        nieuwe_uitzondering = st.date_input("Voeg uitzondering toe:", key="nieuwe_uitzondering")
        if st.button("➕ Uitzondering toevoegen"):
            voeg_uitzondering_toe(nieuwe_uitzondering)
            st.session_state.toast = f"✅ {nieuwe_uitzondering.strftime('%-d %B')} is een vrije dag."
            st.rerun()

        st.divider()
        st.markdown("### Extra trainingen")
        st.caption("Trainingen buiten het vaste schema (bijv. een zaterdag).")
        extra = get_extra_trainingen()

        if extra:
            for e in sorted(extra, key=lambda x: x["datum"]):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"{e['datum'].strftime('%-d %B %Y')} – {e['tijd']}")
                with col2:
                    if st.button("Verwijder", key=f"del_extra_{e['datum']}"):
                        verwijder_extra_training(e["datum"])
                        st.rerun()
        else:
            st.caption("Geen extra trainingen.")

        col1, col2 = st.columns(2)
        with col1:
            extra_datum = st.date_input("Datum extra training:", key="extra_datum")
        with col2:
            extra_tijd = st.text_input("Tijd (bijv. 10:00)", key="extra_tijd")
        if st.button("➕ Extra training toevoegen"):
            if extra_tijd:
                voeg_extra_training_toe(extra_datum, extra_tijd)
                st.session_state.toast = f"✅ Extra training op {extra_datum.strftime('%-d %B')} toegevoegd."
                st.rerun()
            else:
                st.warning("Vul een tijd in.")

    st.stop()

# ==============================
# NAAM KIEZEN
# ==============================
if st.session_state.roeier_naam is None:
    st.subheader("Welkom! Wie ben jij?")

    bestaande_namen = get_alle_roeiers()
    optie = st.radio("", ["Ik sta al in de lijst", "Ik ben nieuw"], horizontal=True)

    if optie == "Ik sta al in de lijst":
        if bestaande_namen:
            naam = st.selectbox("Kies je naam", bestaande_namen, label_visibility="collapsed")
        else:
            st.info("Er zijn nog geen roeiers in de lijst. Kies 'Ik ben nieuw'.")
            naam = ""
    else:
        naam = st.text_input("Voer je naam in", placeholder="bijv. Jan de Vries", label_visibility="collapsed")

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

    huidige_status = get_aanwezigheid_roeier(st.session_state.roeier_id)
    toekomstig = [t for t in trainingen if not t["verleden"]]
    verleden = [t for t in trainingen if t["verleden"]]

    gelockt = get_gelockte_trainingen()
    wijzigingen = {}

    if not toekomstig:
        st.info("Er zijn geen trainingen meer gepland.")
    else:
        st.caption("Geef hieronder aan bij welke trainingen je aanwezig bent.")

        if st.button("💾 Opslaan", type="primary", use_container_width=True, key="opslaan_boven"):
            for datum_str, (keuze, t) in st.session_state.get("_wijzigingen", {}).items():
                if keuze != "Niet opgegeven":
                    sla_aanwezigheid_op(
                        roeier_id=st.session_state.roeier_id,
                        datum=datum_str,
                        dag_naam=t["dag_naam"],
                        tijd=t["tijd"],
                        aanwezig=(keuze == "Aanwezig"),
                    )
            st.session_state.opgeslagen = True
            st.rerun()

        if st.session_state.opgeslagen:
            st.success("✅ Aanwezigheid opgeslagen!")
            st.session_state.opgeslagen = False

        st.divider()

        nieuwe_wijzigingen = {}
        for t in toekomstig:
            datum_str = t["datum_str"]
            huidige = huidige_status.get(datum_str)
            datum_str = t["datum_str"]
            huidige = huidige_status.get(datum_str)
            is_gelockt = t["datum"] in gelockt

            col1, col2 = st.columns([3, 2])
            with col1:
                if is_gelockt:
                    st.markdown(f"<span style='color:#888'>**{t['dag_naam']}** {t['datum'].strftime('%-d %B')} &nbsp; `{t['tijd']}` 🔒</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"**{t['dag_naam']}** {t['datum'].strftime('%-d %B')} &nbsp; `{t['tijd']}`", unsafe_allow_html=True)
            with col2:
                if is_gelockt:
                    badge = "✅ Aanwezig" if huidige is True else ("❌ Afwezig" if huidige is False else "— Niet opgegeven")
                    st.markdown(f"<span style='color:#888'>{badge}</span>", unsafe_allow_html=True)
                else:
                    keuze = st.selectbox(
                        label="status",
                        options=["Niet opgegeven", "Aanwezig", "Afwezig"],
                        index=0 if huidige is None else (1 if huidige else 2),
                        key=f"keuze_{datum_str}",
                        label_visibility="collapsed",
                    )
                    nieuwe_wijzigingen[datum_str] = (keuze, t)

        # Sla huidige selectbox-waarden op in session_state zodat de knoppen ze kunnen lezen
        st.session_state["_wijzigingen"] = nieuwe_wijzigingen

        st.divider()
        if st.button("💾 Opslaan", type="primary", use_container_width=True, key="opslaan_onder"):
            for datum_str, (keuze, t) in st.session_state.get("_wijzigingen", {}).items():
                if keuze != "Niet opgegeven":
                    sla_aanwezigheid_op(
                        roeier_id=st.session_state.roeier_id,
                        datum=datum_str,
                        dag_naam=t["dag_naam"],
                        tijd=t["tijd"],
                        aanwezig=(keuze == "Aanwezig"),
                    )
            st.session_state.opgeslagen = True
            st.rerun()

    if verleden:
        st.divider()
        with st.expander("📋 Eerdere trainingen bekijken"):
            for t in reversed(verleden):
                datum_str = t["datum_str"]
                huidige = huidige_status.get(datum_str)
                badge = "✅ Aanwezig" if huidige is True else ("❌ Afwezig" if huidige is False else "— Niet opgegeven")
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.markdown(f"<span style='color:#888'>{t['dag_naam']} {t['datum'].strftime('%-d %B')} – {t['tijd']}</span>", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"<span style='color:#888'>{badge}</span>", unsafe_allow_html=True)

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

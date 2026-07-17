import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium

# ── Seitenkonfiguration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Radverkehr in Berlin-Mitte",
    page_icon="🚲",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main { background-color: #F7F9FC; }
    .hero {
        background: linear-gradient(135deg, #0F455D 0%, #156082 100%);
        border-radius: 16px;
        padding: 2.5rem 2rem 2rem 2rem;
        margin-bottom: 1.5rem;
        color: white;
    }
    .hero h1 { font-size: 2.2rem; font-weight: 700; margin: 0; }
    .hero p  { font-size: 1rem; opacity: 0.85; margin: 0.4rem 0 0 0; }
    .kpi-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        border-left: 4px solid #156082;
        box-shadow: 0 1px 6px rgba(0,0,0,0.07);
    }
    .kpi-label { font-size: 0.78rem; color: #6B7280; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
    .kpi-value { font-size: 2rem; font-weight: 700; color: #1B4F3A; line-height: 1.2; }
    .kpi-sub   { font-size: 0.8rem; color: #9CA3AF; margin-top: 0.2rem; }
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1F2937;
        margin: 1.5rem 0 0.8rem 0;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid #E5E7EB;
    }
            
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input {
        color: black !important;
        background-color: white !important;
        border: 1px solid #D1D5DB !important;
    }

    [data-testid="stSidebar"] { background: #A7BCC5; }
    [data-testid="stSidebar"] * { color: black; }
</style>
""", unsafe_allow_html=True)

# ── Konstanten ────────────────────────────────────────────────────────────────
WOCHENTAG_MAP = {
    0: "Montag", 1: "Dienstag", 2: "Mittwoch",
    3: "Donnerstag", 4: "Freitag", 5: "Samstag", 6: "Sonntag"
}
WOCHENTAG_ORDER = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

FARBEN = {
    "gruen":      "#2E7D55",
    "gruen_hell": "#4CAF82",
    "coral":      "#E07B54",
    "grau":       "#9CA3AF",
}

def apply_theme(fig, height=None):
    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=40, b=20),
        font=dict(color="#1F2937"),
    )
    if height:
        fig.update_layout(height=height)
    return fig


@st.cache_data
def lade_daten(uploaded_file):
    df = pd.read_csv(
        uploaded_file,
        skiprows=3,
        usecols=[0, 1],
        names=["Zeitstempel", "Anzahl"]
    )
    df["Zeitstempel"] = pd.to_datetime(df["Zeitstempel"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df = df.dropna(subset=["Zeitstempel"])
    df["Anzahl"] = pd.to_numeric(df["Anzahl"], errors="coerce").fillna(0).astype(int)
    df["Datum"]         = df["Zeitstempel"].dt.date
    df["Stunde"]        = df["Zeitstempel"].dt.hour
    df["Wochentag"]     = df["Zeitstempel"].dt.dayofweek.map(WOCHENTAG_MAP)
    df["Woche"]         = df["Zeitstempel"].dt.isocalendar().week.astype(int)
    df["IstWochenende"] = df["Zeitstempel"].dt.dayofweek >= 5
    # Lesbares Label für Legende
    df["TagTyp"] = df["IstWochenende"].map({False: "Werktag", True: "Wochenende"})
    return df


def kpi_card(label, value, sub=""):
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>"""

# ── Sidebar ───────────────────────────────────────────────────────────────

ZAEHLSTELLEN = {
    "Nordufer": {
        "id": 30003779,
        "url": "https://verkehrsmanagementberlin.eco-counter.com/site/30003779",
        "lat": 52.53179,
        "lon": 13.35147,
    },
    "Invalidenstraße": {
        "id": 100032152,
        "url": "https://verkehrsmanagementberlin.eco-counter.com/site/100032152",
        "lat": 52.52873,
        "lon": 13.38166,
    },
    "Karl-Marx-Allee": {
        "id": 300021646,
        "url": "https://verkehrsmanagementberlin.eco-counter.com/site/300021646",
        "lat": 52.52048,
        "lon": 13.43883,
    },
    "Strausberger Platz": {
        "id": 300041564,
        "url": "https://verkehrsmanagementberlin.eco-counter.com/site/300041564",
        "lat": 52.51931,
        "lon": 13.43282,
    },
    "Jannowitzbrücke": {
        "id": 100024661,
        "url": "https://verkehrsmanagementberlin.eco-counter.com/site/100024661",
        "lat": 52.51433,
        "lon": 13.41817,
    },
}

with st.sidebar:

    st.markdown("## Radverkehr in Berlin-Mitte")
    st.markdown("---")

    auswahl = st.selectbox(
        "Radverkehrszählstelle",
        list(ZAEHLSTELLEN.keys())
    )

    counter = ZAEHLSTELLEN[auswahl]

    counter_id = counter["id"]
    counter_url = counter["url"]
    zaehler_name = auswahl
    lat = counter["lat"]
    lon = counter["lon"]

    st.markdown("---")
    st.markdown("Radverkehr in Berlin-Mitte")
    st.markdown("---")
    st.markdown("<small style='color:#E8E9EC'>Labor-Hausaufgabe<br>im Rahmen der Lehrveranstaltung<br>Digitalisierung intermodaler Radverkehrsangebote<br>im Studiengang<br>Radverkehr in intermodalen Verkehrsnetzen<br>Sommersemester 2026</small>", unsafe_allow_html=True)

# ── Hauptbereich ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
    <h1>🚲 Radverkehr im Bezirk Mitte</h1>
    <p>Zähldaten · Radverkehrsmaßnahmen · Unfalldaten</p>
</div>
""", unsafe_allow_html=True)

# ── URLs ──────────────────────────────────────────────────────────────────────
# ── URLs ──────────────────────────────────────────────────────────────────────

viz_url = (
    'https://viz.berlin.de/site/_masterportal/berlin/index.html'
    '?MAPS={"center":[386892.3647828701,5821737.831466295],'
    '"mode":"2D","zoom":6}'
    '&MENU={"main":{"currentComponent":"root"},'
    '"secondary":{"currentComponent":"root"}}'
    '&LAYERS=['
    '{"id":"basemap_raster_grau","visibility":true},'
    '{"id":"luftbild2025","visibility":true},'
    '{"id":"EcoCounter","visibility":true},'
    '{"id":"bezirke","visibility":true},'
    '{"id":"radplus_2025","visibility":false},'
    '{"id":"radplus_2024","visibility":false},'
    '{"id":"radplus_2023","visibility":false}'
    ']#'
)


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_start, tab_zaehlstelle, tab_massnahmen, tab_unfaelle = st.tabs(
    [
        "🏠 Übersicht",
        "📈 Zählstelle",
        "🚲 Maßnahmen",
        "🚨 Unfälle"
    ]
)


with tab_start:
    st.subheader("Übersicht Berlin-Mitte")

    components.iframe(
        src=viz_url,
        height=750,
        scrolling=True
    )


with tab_zaehlstelle:
    st.subheader(Zählstelle:</b> {zaehler_name}<br>)
    st.caption(f"EcoCounter-ID: {counter_id}")

    components.iframe(
        src=counter_url,
        height=900,
        scrolling=True
    )


with tab_massnahmen:
    st.info("Radverkehrsmaßnahmen werden hier integriert.")


with tab_unfaelle:
    st.info("Unfalldaten werden hier integriert.")




# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small style='color:#9CA3AF'>Datenquelle: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt / Radfahrzählstellen; GB infraVelo GmbH / Radverkehrsmaßnahmen; Statistische Ämter des Bundes und der Länder / Unfallatlas – Unfallorte 2017-2024 </small>",
    unsafe_allow_html=True
)

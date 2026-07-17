import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components
import json
import requests
import xml.etree.ElementTree as ET
from shapely.geometry import Point, shape

def show_ecocounter(url):
    components.iframe(url, height=900, scrolling=True)

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
        "id": 300037797,
        "url": "https://verkehrsmanagementberlin.eco-counter.com/site/300037797",
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

MASSNAHMEN = {}

try:
    response = requests.get(
        "https://gdi.berlin.de/services/wfs/radverkehrsmassnahmen",
        params={
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "radverkehrsmassnahmen",
            "outputFormat": "application/json",
            "srsName": "EPSG:4326"
        },
        timeout=60
    )

    response.raise_for_status()
    wfs_daten = response.json()

    for feature in wfs_daten.get("features", []):

        props = feature.get("properties", {})

        # Nur Bezirk Mitte
        if str(props.get("bezirk", "")).strip().lower() != "mitte":
            continue

        strasse = props.get("strassenname") or "Unbekannte Straße"
        projektnummer = props.get("projektnummer") or ""

        # Eindeutiger Name für die Auswahlbox
        if projektnummer:
            name = f"{strasse} ({projektnummer})"
        else:
            name = strasse

        MASSNAHMEN[name] = feature

except Exception as fehler:
    st.warning(
        f"Die Maßnahmen konnten nicht geladen werden: {fehler}"
    )
    

with st.sidebar:

    st.markdown("## Radverkehr in Berlin-Mitte")
    st.markdown("---")
    st.markdown("📈 Radverkehrszählstelle")

    auswahl = st.selectbox(
        "Standort",
        list(ZAEHLSTELLEN.keys())
    )

    counter = ZAEHLSTELLEN[auswahl]

    counter_id = counter["id"]
    counter_url = counter["url"]
    zaehler_name = auswahl
    lat = counter["lat"]
    lon = counter["lon"]
    st.markdown("---")
    st.markdown("🚧 Radverkehrsmaßnahmen")

    if MASSNAHMEN:

        auswahl = st.selectbox(
            "Straße bzw. Straßenzug",
            list(MASSNAHMEN.keys())
        )

        massnahme = MASSNAHMEN[auswahl]
        massnahme_props = massnahme["properties"]

    else:

        st.info("Keine Maßnahmen verfügbar.")

        auswahl = None
        massnahme = None
        massnahme_props = {}

# ── Hauptbereich ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
    <h1>🚲 Radverkehr im Bezirk Mitte</h1>
    <p>Zähldaten · Radverkehrsmaßnahmen · Unfalldaten</p>
</div>
""", unsafe_allow_html=True)

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

    # Karte auf Berlin-Mitte zentrieren
    karte = folium.Map(
        location=[52.5205, 13.4050],
        zoom_start=13,
        tiles="CartoDB positron"
    )

    # Alle Zählstellen als Marker hinzufügen
    for name, daten in ZAEHLSTELLEN.items():

        ist_ausgewaehlt = name == zaehler_name
        marker_farbe = "green" if ist_ausgewaehlt else "blue"

        popup_html = f"""
        <div style="width:240px; font-family:Arial, sans-serif;">

            <h4 style="margin-bottom:8px; color:#156082;">
                🚲 {name}
            </h4>

           <b>Bezirk:</b> Berlin-Mitte</b><br><br>

           
            <a href="{daten['url']}"
               target="_blank"
               style="
                   background:#156082;
                   color:white;
                   padding:8px 12px;
                   border-radius:6px;
                   text-decoration:none;
                   display:inline-block;
               ">
               Live-Dashboard öffnen
            </a>

        </div>
        """

        folium.Marker(
            location=[daten["lat"], daten["lon"]],
            popup=folium.Popup(
                popup_html,
                max_width=280
            ),
            tooltip=name,
            icon=folium.Icon(
                color=marker_farbe,
                icon="bicycle",
                prefix="fa"
            )
        ).add_to(karte)
        
# Radverkehrsmaßnahmen darstellen
    for feature in MASSNAHMEN.values():

        props = feature["properties"]

        ist_ausgewaehlt = (
            massnahme is not None
            and props.get("projektnummer")
            == massnahme["properties"].get("projektnummer")
        )

        farbe = "#ff9800" if ist_ausgewaehlt else "#1565c0"
        breite = 7 if ist_ausgewaehlt else 4

        folium.GeoJson(
            feature,
            style_function=lambda feature, farbe=farbe, breite=breite: {
                "color": farbe,
                "weight": breite,
                "opacity": 0.9
            },
            highlight_function=lambda feature: {
                "color": "#ff9800",
                "weight": 7,
                "opacity": 1
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[
                    "strassenname",
                    "status",
                    "massnahmen_typ1"
                ],
                aliases=[
                    "Straße:",
                    "Status:",
                    "Maßnahme:"
                ],
                sticky=False
            )
        ).add_to(karte)

    # Karte erst anzeigen, nachdem alle Marker hinzugefügt wurden
    st_folium(
        karte,
        height=550,
        use_container_width=True
    )

with tab_zaehlstelle:
    st.subheader(f"Zählstelle: {zaehler_name}")
   
    components.iframe(
        src=counter_url,
        height=900,
        scrolling=True
    )
    
with tab_massnahmen:
    st.subheader("🚲 Radverkehrsmaßnahmen in Berlin-Mitte")

    wfs_url = "https://gdi.berlin.de/services/wfs/radverkehrsmassnahmen"

    # ------------------------------------------------------------------
    # Grundkarte
    # ------------------------------------------------------------------

    massnahmen_karte = folium.Map(
        location=[52.5205, 13.4050],
        zoom_start=12,
        tiles="CartoDB positron"
    )

    try:
        # --------------------------------------------------------------
        # WFS-Daten laden
        # --------------------------------------------------------------

        response = requests.get(
            wfs_url,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": "radverkehrsmassnahmen",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326"
            },
            timeout=60
        )

        response.raise_for_status()
        wfs_daten = response.json()

        # --------------------------------------------------------------
        # Nur Maßnahmen aus dem Bezirk Mitte übernehmen
        # --------------------------------------------------------------

        features_mitte = []

        for feature in wfs_daten.get("features", []):

            eigenschaften = feature.get("properties", {})
            bezirk = str(eigenschaften.get("bezirk", "")).strip().lower()

            if "mitte" in bezirk and feature.get("geometry"):
                features_mitte.append(feature)

        geojson_mitte = {
            "type": "FeatureCollection",
            "features": features_mitte
        }

        # --------------------------------------------------------------
        # Maßnahmen auf der Karte darstellen
        # --------------------------------------------------------------

 if features_mitte:

    ausgewaehlte_nummer = None

    if massnahme is not None:
        ausgewaehlte_nummer = (
            massnahme["properties"].get("projektnummer")
        )

    for feature in features_mitte:

        props = feature["properties"]

        ist_ausgewaehlt = (
            ausgewaehlte_nummer is not None
            and props.get("projektnummer")
            == ausgewaehlte_nummer
        )

        farbe = "#ff9800" if ist_ausgewaehlt else "#1565c0"
        breite = 8 if ist_ausgewaehlt else 6

        folium.GeoJson(
            feature,
            style_function=lambda feature, farbe=farbe, breite=breite: {
                "color": farbe,
                "weight": breite,
                "opacity": 0.9
            },
            highlight_function=lambda feature: {
                "color": "#ff9800",
                "weight": 9,
                "opacity": 1
            },
            tooltip=folium.GeoJsonTooltip(
                fields=[
                    "strassenname",
                    "status",
                    "massnahmen_typ1"
                ],
                aliases=[
                    "Straße:",
                    "Status:",
                    "Maßnahme:"
                ],
                sticky=False
            )
        ).add_to(massnahmen_karte)

        else:
            st.warning(
                "Es wurden keine Radverkehrsmaßnahmen für Mitte gefunden."
            )

        # --------------------------------------------------------------
        # Legende
        # --------------------------------------------------------------

        legende = """
        <div style="
            position: fixed;
            bottom: 35px;
            left: 35px;
            z-index: 9999;
            background: white;
            padding: 12px 15px;
            border: 2px solid #777;
            border-radius: 6px;
            font-size: 13px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.35);
        ">
            <b>Legende</b><br><br>

            <span style="
                display:inline-block;
                width:28px;
                height:6px;
                background:#1565c0;
                margin-right:8px;
            "></span>

            Radverkehrsmaßnahme<br><br>

            <span style="
                display:inline-block;
                width:28px;
                height:6px;
                background:#ff9800;
                margin-right:8px;
            "></span>

            ausgewählte Maßnahme
        </div>
        """

        massnahmen_karte.get_root().html.add_child(
            folium.Element(legende)
        )

        folium.LayerControl(
            collapsed=False
        ).add_to(massnahmen_karte)

        # --------------------------------------------------------------
        # Karte anzeigen und Klickposition abfragen
        # --------------------------------------------------------------

        kartendaten = st_folium(
            massnahmen_karte,
            height=600,
            use_container_width=True,
            key="massnahmen_karte",
            returned_objects=["last_clicked"]
        )

        st.caption(
            f"Quelle: Geoportal Berlin / infraVelo · "
            f"{len(features_mitte)} Maßnahmen im Bezirk Mitte"
        )

        # --------------------------------------------------------------
        # Maßnahme aus Sidebar oder Kartenklick ermitteln
        # --------------------------------------------------------------

        # Standardmäßig die Auswahl aus der Sidebar verwenden
        ausgewaehltes_feature = massnahme

        klick = kartendaten.get("last_clicked") if kartendaten else None

        if klick:

            klickpunkt = Point(
                klick["lng"],
                klick["lat"]
            )

            geklicktes_feature = None
            kleinster_abstand = float("inf")

            for feature in features_mitte:

                try:
                    geometrie = shape(feature["geometry"])
                    abstand = geometrie.distance(klickpunkt)

                    if abstand < kleinster_abstand:
                        kleinster_abstand = abstand
                        geklicktes_feature = feature

                except (ValueError, TypeError, KeyError):
                    continue

            # Nur bei einem hinreichend genauen Klick
            # die Sidebar-Auswahl überschreiben
            if (
                geklicktes_feature is not None
                and kleinster_abstand < 0.001
            ):
                ausgewaehltes_feature = geklicktes_feature

        # --------------------------------------------------------------
        # Informationen anzeigen
        # --------------------------------------------------------------

        if ausgewaehltes_feature is not None:

            daten = ausgewaehltes_feature.get(
                "properties",
                {}
            )

            st.markdown("---")
            st.subheader("📋 Informationen zur Maßnahme")

            strasse = daten.get("strassenname") or "–"
            strassenseite = daten.get("strassenseite") or "–"
            status = daten.get("status") or "–"
            baustart = daten.get("baustart") or "–"
            bauende = daten.get("bauende") or "–"
            bauherr = daten.get("bauherr") or "–"
            projektnummer = daten.get("projektnummer") or "–"

            projektbeschreibung = (
                daten.get("projektbeschreibung_lang")
                or "Keine Projektbeschreibung vorhanden."
            )

            streckenlaenge = (
                daten.get("streckenlaenge1")
                or daten.get("streckenlaenge")
                or "–"
            )

            if streckenlaenge != "–":
                streckenlaenge = f"{streckenlaenge} m"

            st.markdown(
                f"### 🚲 {strasse}"
            )

            st.caption(
                f"Projektnummer: {projektnummer}"
            )

            spalte1, spalte2 = st.columns(2)

            with spalte1:

                st.markdown(
                    f"""
                    **Straße bzw. Straßenzug:**  
                    {strasse}

                    **Straßenseite:**  
                    {strassenseite}

                    **Status der Maßnahme:**  
                    {status}

                    **Bauherr:**  
                    {bauherr}
                    """
                )

            with spalte2:

                st.markdown(
                    f"""
                    **Quartal des Baustarts:**  
                    {baustart}

                    **Quartal des Bauendes:**  
                    {bauende}

                    **Netz-Art:**  
                    {daten.get("netz_art1") or "–"}

                    **Maßnahmen-Typ:**  
                    {daten.get("massnahmen_typ1") or "–"}

                    **Streckenlänge:**  
                    {streckenlaenge}
                    """
                )

            st.markdown("#### Projektbeschreibung")
            st.write(projektbeschreibung)

        else:

            st.info(
                "Wähle in der Sidebar eine Radverkehrsmaßnahme aus "
                "oder klicke auf eine Maßnahmenlinie."
            )

    except requests.exceptions.RequestException as fehler:

        st.error(
            f"Der WFS-Dienst konnte nicht geladen werden: {fehler}"
        )

        # Grundkarte trotz Fehler darstellen
        st_folium(
            massnahmen_karte,
            height=600,
            use_container_width=True,
            key="massnahmen_karte_fehler"
        )

    except ValueError as fehler:

        st.error(
            f"Die WFS-Daten konnten nicht verarbeitet werden: {fehler}"
        )


st.caption("Quelle: Geoportal Berlin / GB infraVelo GmbH")

with tab_unfaelle:
    st.info("Unfalldaten werden hier integriert.")




# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small style='color:#9CA3AF'>Labor-Hausaufgabe im Rahmen der Lehrveranstaltung „Digitalisierung intermodaler Radverkehrsangebote“ im Studiengang „Radverkehr in intermodalen Verkehrsnetzen“ – Sommersemester 2026</small>",
    unsafe_allow_html=True
)

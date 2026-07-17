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
from shapely.geometry import shape
from shapely.geometry.point import Point

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

            folium.GeoJson(
                geojson_mitte,
                name="Radverkehrsmaßnahmen Mitte",

                style_function=lambda feature: {
                    "color": "#1565c0",
                    "weight": 6,
                    "opacity": 0.85
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
        # Angeklickte Maßnahme ermitteln
        # --------------------------------------------------------------

        klick = kartendaten.get("last_clicked") if kartendaten else None

        if klick:

            klickpunkt = Point(
                klick["lng"],
                klick["lat"]
            )

            ausgewaehltes_feature = None
            kleinster_abstand = float("inf")

            for feature in features_mitte:

                try:
                    geometrie = shape(feature["geometry"])
                    abstand = geometrie.distance(klickpunkt)

                    if abstand < kleinster_abstand:
                        kleinster_abstand = abstand
                        ausgewaehltes_feature = feature

                except (ValueError, TypeError):
                    continue

            # Etwa 80 bis 100 Meter Toleranz
            if (
                ausgewaehltes_feature is not None
                and kleinster_abstand < 0.001
            ):

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

                projektbeschreibung = (
                    daten.get("projektbeschreibung_lang")
                    or "Keine Projektbeschreibung vorhanden."
                )

                projektnummer = daten.get("projektnummer") or "–"

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
                        {daten.get("streckenlaenge1") or daten.get("streckenlaenge") or "–"} m
                        """
                    )

                st.markdown("#### Projektbeschreibung")

                st.write(projektbeschreibung)

                # Weitere Maßnahmentypen darstellen
                weitere_massnahmen = []

                for nummer in range(2, 6):

                    netz_art = daten.get(
                        f"netz_art{nummer}"
                    )

                    massnahmen_typ = daten.get(
                        f"massnahmen_typ{nummer}"
                    )

                    streckenlaenge = daten.get(
                        f"streckenlaenge{nummer}"
                    )

                    if netz_art or massnahmen_typ or streckenlaenge:

                        weitere_massnahmen.append({
                            "Netz-Art": netz_art or "–",
                            "Maßnahmen-Typ": massnahmen_typ or "–",
                            "Streckenlänge": (
                                f"{streckenlaenge} m"
                                if streckenlaenge
                                else "–"
                            )
                        })

                if weitere_massnahmen:

                    st.markdown(
                        "#### Weitere Maßnahmen auf dem Straßenzug"
                    )

                    st.dataframe(
                        weitere_massnahmen,
                        use_container_width=True,
                        hide_index=True
                    )

            else:
                st.info(
                    "Bitte möglichst genau auf eine blaue "
                    "Maßnahmenlinie klicken."
                )

        else:
            st.info(
                "Klicke auf eine Maßnahmenlinie, um die "
                "zugehörigen Informationen unterhalb der Karte anzuzeigen."
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

folium.LayerControl(
        collapsed=False
    ).add_to(massnahmen_karte)

st_folium(
        massnahmen_karte,
        height=600,
        use_container_width=True,
        key="massnahmen_karte"
    )

st.caption("Quelle: Geoportal Berlin / GB infraVelo GmbH")

with tab_unfaelle:
    st.info("Unfalldaten werden hier integriert.")




# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small style='color:#9CA3AF'>Datenquelle: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt / Radfahrzählstellen; GB infraVelo GmbH / Radverkehrsmaßnahmen; Statistische Ämter des Bundes und der Länder / Unfallatlas – Unfallorte 2017-2024 </small>",
    unsafe_allow_html=True
)

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
    # Hilfsfunktionen
    # ------------------------------------------------------------------

    def feld_suchen(eigenschaften, suchbegriffe, standard="–"):
        """
        Sucht ein Feld auch dann, wenn der genaue Feldname
        im WFS leicht anders geschrieben ist.
        """

        def normalisieren(text):
            return (
                str(text)
                .lower()
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss")
                .replace("-", "")
                .replace("_", "")
                .replace(" ", "")
            )

        normalisierte_felder = {
            normalisieren(key): value
            for key, value in eigenschaften.items()
        }

        # Zuerst nach exakten Feldnamen suchen
        for begriff in suchbegriffe:
            begriff_normalisiert = normalisieren(begriff)

            if begriff_normalisiert in normalisierte_felder:
                wert = normalisierte_felder[begriff_normalisiert]

                if wert not in [None, ""]:
                    return wert

        # Danach nach enthaltenen Begriffen suchen
        for feldname, wert in normalisierte_felder.items():
            for begriff in suchbegriffe:
                if normalisieren(begriff) in feldname:
                    if wert not in [None, ""]:
                        return wert

        return standard


    def status_farbe(status):
        status = str(status).lower()

        if any(wort in status for wort in [
            "fertig",
            "umgesetzt",
            "abgeschlossen",
            "realisiert",
            "in betrieb"
        ]):
            return "#2e7d32"

        if any(wort in status for wort in [
            "bau",
            "ausführung",
            "umsetzung"
        ]):
            return "#ef6c00"

        if any(wort in status for wort in [
            "planung",
            "geplant",
            "vorbereitung"
        ]):
            return "#1565c0"

        if any(wort in status for wort in [
            "zurückgestellt",
            "gestoppt",
            "abgebrochen"
        ]):
            return "#c62828"

        return "#757575"


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
        # Layernamen aus den WFS-Capabilities lesen
        # --------------------------------------------------------------

        capabilities = requests.get(
            wfs_url,
            params={
                "service": "WFS",
                "request": "GetCapabilities"
            },
            timeout=30
        )

        capabilities.raise_for_status()

        root = ET.fromstring(capabilities.content)

        layer_namen = []

        for feature_type in root.iter():

            if feature_type.tag.endswith("FeatureType"):

                for element in feature_type:

                    if element.tag.endswith("Name") and element.text:
                        layer_namen.append(element.text.strip())
                        break

        if not layer_namen:
            st.warning("Im WFS-Dienst wurde kein Layer gefunden.")
            st.stop()

        # Ersten gefundenen Fachlayer verwenden
        wfs_layer = layer_namen[0]

        # --------------------------------------------------------------
        # GeoJSON-Daten vom WFS laden
        # --------------------------------------------------------------

        geojson_response = requests.get(
            wfs_url,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": wfs_layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326"
            },
            timeout=60
        )

        # Fallback für ältere WFS-Versionen
        if not geojson_response.ok:

            geojson_response = requests.get(
                wfs_url,
                params={
                    "service": "WFS",
                    "version": "1.1.0",
                    "request": "GetFeature",
                    "typeName": wfs_layer,
                    "outputFormat": "application/json",
                    "srsName": "EPSG:4326"
                },
                timeout=60
            )

        geojson_response.raise_for_status()

        wfs_daten = geojson_response.json()

        neue_features = []

        # --------------------------------------------------------------
        # Felder vereinheitlichen
        # --------------------------------------------------------------

        for feature in wfs_daten.get("features", []):

            eigenschaften = feature.get("properties", {})

            bezirk = feld_suchen(
                eigenschaften,
                ["bezirk", "district", "bezirksname"],
                standard=""
            )

            # Wenn ein Bezirksfeld vorhanden ist, nur Mitte übernehmen
            if bezirk and "mitte" not in str(bezirk).lower():
                continue

            strasse = feld_suchen(
                eigenschaften,
                [
                    "straße",
                    "strasse",
                    "straßenzug",
                    "strassenzug",
                    "projektname",
                    "name"
                ]
            )

            strassenseite = feld_suchen(
                eigenschaften,
                [
                    "straßenseite",
                    "strassenseite",
                    "seite"
                ]
            )

            status = feld_suchen(
                eigenschaften,
                [
                    "status",
                    "projektstatus",
                    "stand"
                ]
            )

            baustart = feld_suchen(
                eigenschaften,
                [
                    "quartal baustart",
                    "baustart",
                    "bauanfang",
                    "startquartal"
                ]
            )

            bauende = feld_suchen(
                eigenschaften,
                [
                    "quartal bauende",
                    "bauende",
                    "fertigstellung",
                    "endequartal"
                ]
            )

            bauherr = feld_suchen(
                eigenschaften,
                [
                    "bauherr",
                    "vorhabentraeger",
                    "vorhabenträger",
                    "projekttraeger",
                    "projektträger"
                ]
            )

            beschreibung = feld_suchen(
                eigenschaften,
                [
                    "projektbeschreibung",
                    "beschreibung",
                    "kurzbeschreibung"
                ]
            )

            netz_art = feld_suchen(
                eigenschaften,
                [
                    "netz-art",
                    "netzart",
                    "netz",
                    "radnetz"
                ]
            )

            massnahmen_typ = feld_suchen(
                eigenschaften,
                [
                    "maßnahmen-typ",
                    "massnahmen-typ",
                    "maßnahmentyp",
                    "massnahmentyp",
                    "typ"
                ]
            )

            streckenlaenge = feld_suchen(
                eigenschaften,
                [
                    "streckenlänge",
                    "streckenlaenge",
                    "länge",
                    "laenge",
                    "length"
                ]
            )

            neue_features.append({
                "type": "Feature",
                "geometry": feature.get("geometry"),
                "properties": {
                    "Straße / Straßenzug": strasse,
                    "Straßenseite": strassenseite,
                    "Status": status,
                    "Quartal Baustart": baustart,
                    "Quartal Bauende": bauende,
                    "Bauherr": bauherr,
                    "Projektbeschreibung": beschreibung,
                    "Netz-Art": netz_art,
                    "Maßnahmen-Typ": massnahmen_typ,
                    "Streckenlänge in m": streckenlaenge,
                    "Farbe": status_farbe(status)
                }
            })

        geojson_mitte = {
            "type": "FeatureCollection",
            "features": neue_features
        }

        # --------------------------------------------------------------
        # Maßnahmen darstellen
        # --------------------------------------------------------------

        if neue_features:

            folium.GeoJson(
                geojson_mitte,
                name="Radverkehrsmaßnahmen",
                style_function=lambda feature: {
                    "color": feature["properties"]["Farbe"],
                    "weight": 5,
                    "opacity": 0.9
                },
                highlight_function=lambda feature: {
                    "weight": 8,
                    "opacity": 1
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=[
                        "Straße / Straßenzug",
                        "Status",
                        "Maßnahmen-Typ"
                    ],
                    aliases=[
                        "Straße:",
                        "Status:",
                        "Maßnahme:"
                    ],
                    sticky=False
                ),
                popup=folium.GeoJsonPopup(
                    fields=[
                        "Straße / Straßenzug",
                        "Straßenseite",
                        "Status",
                        "Quartal Baustart",
                        "Quartal Bauende",
                        "Bauherr",
                        "Projektbeschreibung",
                        "Netz-Art",
                        "Maßnahmen-Typ",
                        "Streckenlänge in m"
                    ],
                    aliases=[
                        "Straße bzw. Straßenzug:",
                        "Straßenseite:",
                        "Status:",
                        "Quartal des Baustarts:",
                        "Quartal des Bauendes:",
                        "Bauherr:",
                        "Projektbeschreibung:",
                        "Netz-Art:",
                        "Maßnahmen-Typ:",
                        "Streckenlänge in m:"
                    ],
                    localize=True,
                    labels=True,
                    max_width=450
                )
            ).add_to(massnahmen_karte)

        else:
            st.warning(
                "Es wurden keine Maßnahmen für den Bezirk Mitte gefunden."
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
            background-color: white;
            padding: 12px 15px;
            border: 2px solid #999;
            border-radius: 6px;
            font-size: 13px;
            box-shadow: 0 1px 5px rgba(0,0,0,0.35);
        ">
            <b>Legende – Status</b><br>

            <div style="margin-top:7px;">
                <span style="
                    display:inline-block;
                    width:20px;
                    height:5px;
                    background:#2e7d32;
                    margin-right:7px;
                "></span>
                Fertig / umgesetzt
            </div>

            <div style="margin-top:5px;">
                <span style="
                    display:inline-block;
                    width:20px;
                    height:5px;
                    background:#ef6c00;
                    margin-right:7px;
                "></span>
                Im Bau
            </div>

            <div style="margin-top:5px;">
                <span style="
                    display:inline-block;
                    width:20px;
                    height:5px;
                    background:#1565c0;
                    margin-right:7px;
                "></span>
                In Planung
            </div>

            <div style="margin-top:5px;">
                <span style="
                    display:inline-block;
                    width:20px;
                    height:5px;
                    background:#c62828;
                    margin-right:7px;
                "></span>
                Zurückgestellt
            </div>

            <div style="margin-top:5px;">
                <span style="
                    display:inline-block;
                    width:20px;
                    height:5px;
                    background:#757575;
                    margin-right:7px;
                "></span>
                Sonstiger Status
            </div>
        </div>
        """

        massnahmen_karte.get_root().html.add_child(
            folium.Element(legende)
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

        st.caption(
            f"Quelle: Geoportal Berlin · "
            f"{len(neue_features)} Maßnahmen in der Karte"
        )

    except requests.exceptions.RequestException as fehler:
        st.error(
            f"Der WFS-Dienst konnte nicht geladen werden: {fehler}"
        )

    except ET.ParseError as fehler:
        st.error(
            f"Die Beschreibung des WFS-Dienstes konnte nicht gelesen werden: "
            f"{fehler}"
        )

    except (ValueError, json.JSONDecodeError) as fehler:
        st.error(
            f"Die WFS-Daten konnten nicht verarbeitet werden: {fehler}"
        )

    except Exception as fehler:
        st.error(
            f"Beim Erstellen der Maßnahmenkarte ist ein Fehler aufgetreten: "
            f"{fehler}"
        )

with tab_unfaelle:
    st.info("Unfalldaten werden hier integriert.")




# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small style='color:#9CA3AF'>Datenquelle: Senatsverwaltung für Mobilität, Verkehr, Klimaschutz und Umwelt / Radfahrzählstellen; GB infraVelo GmbH / Radverkehrsmaßnahmen; Statistische Ämter des Bundes und der Länder / Unfallatlas – Unfallorte 2017-2024 </small>",
    unsafe_allow_html=True
)

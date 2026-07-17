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

# ── Tab Übersicht ────────────────────────────────────────────────────────────────
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
    )

    st.caption(
    "Quelle: Geoportal Berlin / Radverkehrsmaßnahmen (seit 2021); Digitale Plattform Stadtverkehr / Fahrradzählstellen"
    "Lizenz: Datenlizenz Deutschland – Zero – Version 2.0 (dl-zero-de/2.0)"
    )


# ── Tab Zählstellen ────────────────────────────────────────────────────────────────

with tab_zaehlstelle: 
    st.subheader(zaehler_name)
 
    components.iframe(
        src=counter_url,
        height=900,
        scrolling=True
    )
    
# ── Tab Maßnahmen ────────────────────────────────────────────────────────────────

with tab_massnahmen:
    st.subheader("🚲 Radverkehrsmaßnahmen in Berlin-Mitte")
    
    wfs_url = (
        "https://gdi.berlin.de/services/wfs/"
        "radverkehrsmassnahmen"
    )
    
    # --------------------------------------------------------------
    # Ausgangswert aus der Sidebar
    # --------------------------------------------------------------

    sidebar_feature = massnahme

    sidebar_projektnummer = ""

    if sidebar_feature is not None:
        sidebar_projektnummer = str(
            sidebar_feature
            .get("properties", {})
            .get("projektnummer", "")
        )

    # --------------------------------------------------------------
    # Session State initialisieren
    # --------------------------------------------------------------

    if "massnahmen_ausgewaehlt" not in st.session_state:
        st.session_state.massnahmen_ausgewaehlt = sidebar_feature

    if "massnahmen_sidebar_projektnummer" not in st.session_state:
        st.session_state.massnahmen_sidebar_projektnummer = (
            sidebar_projektnummer
        )

    if "massnahmen_letzter_klick" not in st.session_state:
        st.session_state.massnahmen_letzter_klick = None

    # --------------------------------------------------------------
    # Neue Sidebar-Auswahl übernehmen
    # --------------------------------------------------------------

    if (
        sidebar_projektnummer
        != st.session_state.massnahmen_sidebar_projektnummer
    ):
        st.session_state.massnahmen_ausgewaehlt = sidebar_feature

        st.session_state.massnahmen_sidebar_projektnummer = (
            sidebar_projektnummer
        )

        # Alter Kartenklick soll die neue Sidebar-Auswahl
        # nicht erneut überschreiben
        st.session_state.massnahmen_letzter_klick = None

    # --------------------------------------------------------------
    # Aktuell ausgewähltes Feature
    # --------------------------------------------------------------

    ausgewaehltes_feature = st.session_state.get(
        "massnahmen_ausgewaehlt",
        sidebar_feature
    )

    # --------------------------------------------------------------
    # Grundkarte
    # --------------------------------------------------------------

    massnahmen_karte = folium.Map(
        location=[52.5205, 13.4050],
        zoom_start=12,
        tiles="CartoDB positron"
    )

    try:
        # ----------------------------------------------------------
        # WFS-Daten laden
        # ----------------------------------------------------------

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

        # ----------------------------------------------------------
        # Nur Maßnahmen aus dem Bezirk Mitte übernehmen
        # ----------------------------------------------------------

        features_mitte = []

        for feature in wfs_daten.get("features", []):
            eigenschaften = feature.get("properties", {})

            bezirk = str(
                eigenschaften.get("bezirk", "")
            ).strip().lower()

            if bezirk == "mitte" and feature.get("geometry"):
                features_mitte.append(feature)

        # ----------------------------------------------------------
        # Kennung der aktuellen Auswahl
        # ----------------------------------------------------------

        ausgewaehlte_nummer = ""

        if ausgewaehltes_feature is not None:
            ausgewaehlte_nummer = str(
                ausgewaehltes_feature
                .get("properties", {})
                .get("projektnummer", "")
            )

        # ----------------------------------------------------------
        # Maßnahmen einzeln darstellen
        # ----------------------------------------------------------

        if features_mitte:
            for feature in features_mitte:
                props = feature.get("properties", {})

                feature_nummer = str(
                    props.get("projektnummer", "")
                )

                ist_ausgewaehlt = (
                    ausgewaehlte_nummer != ""
                    and feature_nummer == ausgewaehlte_nummer
                )

                farbe = (
                    "#ff9800"
                    if ist_ausgewaehlt
                    else "#1565c0"
                )

                breite = 9 if ist_ausgewaehlt else 5

                folium.GeoJson(
                    feature,
                    style_function=(
                        lambda feature,
                        farbe=farbe,
                        breite=breite: {
                            "color": farbe,
                            "weight": breite,
                            "opacity": 1
                        }
                    ),
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
                "Es wurden keine Radverkehrsmaßnahmen "
                "für Mitte gefunden."
            )

        # ----------------------------------------------------------
        # Legende
        # ----------------------------------------------------------

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
                height:7px;
                background:#ff9800;
                margin-right:8px;
            "></span>
            ausgewählte Maßnahme
        </div>
        """

        massnahmen_karte.get_root().html.add_child(
            folium.Element(legende)
        )

        # ----------------------------------------------------------
        # Karte anzeigen
        # ----------------------------------------------------------

        kartendaten = st_folium(
            massnahmen_karte,
            height=600,
            use_container_width=True,
            key="massnahmen_karte",
            returned_objects=["last_clicked"]
        )

        st.caption(
            "Quelle: Geoportal Berlin / Radverkehrsmaßnahmen (seit 2021)"
            "Lizenz: Datenlizenz Deutschland – Zero – Version 2.0 (dl-zero-de/2.0)"
        )

        # ----------------------------------------------------------
        # Kartenklick auswerten
        # ----------------------------------------------------------

        klick = None

        if kartendaten:
            klick = kartendaten.get("last_clicked")

        if klick:
            klick_id = (
                round(klick["lat"], 7),
                round(klick["lng"], 7)
            )

            if (
                klick_id
                != st.session_state.massnahmen_letzter_klick
            ):
                klickpunkt = Point(
                    klick["lng"],
                    klick["lat"]
                )

                geklicktes_feature = None
                kleinster_abstand = float("inf")

                for feature in features_mitte:
                    try:
                        geometrie = shape(
                            feature["geometry"]
                        )

                        abstand = geometrie.distance(
                            klickpunkt
                        )

                        if abstand < kleinster_abstand:
                            kleinster_abstand = abstand
                            geklicktes_feature = feature

                    except (
                        ValueError,
                        TypeError,
                        KeyError
                    ):
                        continue

                # Circa 80 bis 100 Meter Toleranz
                if (
                    geklicktes_feature is not None
                    and kleinster_abstand < 0.001
                ):
                    st.session_state.massnahmen_ausgewaehlt = (
                        geklicktes_feature
                    )

                    st.session_state.massnahmen_letzter_klick = (
                        klick_id
                    )

                    st.rerun()

                else:
                    st.session_state.massnahmen_letzter_klick = (
                        klick_id
                    )

                    st.info(
                        "Bitte möglichst genau auf eine "
                        "Maßnahmenlinie klicken."
                    )

        # ----------------------------------------------------------
        # Aktuelle Auswahl nach Karteninteraktion erneut abrufen
        # ----------------------------------------------------------

        ausgewaehltes_feature = st.session_state.get(
            "massnahmen_ausgewaehlt",
            sidebar_feature
        )

        # ----------------------------------------------------------
        # Detailinformationen
        # ----------------------------------------------------------

        if ausgewaehltes_feature is not None:
            daten = ausgewaehltes_feature.get(
                "properties",
                {}
            )

            strasse = (
                daten.get("strassenname")
                or "–"
            )

            strassenseite = (
                daten.get("strassenseite")
                or "–"
            )

            status = (
                daten.get("status")
                or "–"
            )

            baustart = (
                daten.get("baustart")
                or "–"
            )

            bauende = (
                daten.get("bauende")
                or "–"
            )

            bauherr = (
                daten.get("bauherr")
                or "–"
            )

            projektnummer = (
                daten.get("projektnummer")
                or "–"
            )

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

            st.markdown("---")
            st.subheader("📋 Informationen zur Maßnahme")

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
                "Wähle in der Sidebar eine Maßnahme aus "
                "oder klicke auf eine Linie in der Karte."
            )

    except requests.exceptions.RequestException as fehler:
        st.error(
            "Der WFS-Dienst konnte nicht geladen werden: "
            f"{fehler}"
        )

        st_folium(
            massnahmen_karte,
            height=600,
            use_container_width=True,
            key="massnahmen_karte_fehler"
        )

    except (ValueError, TypeError, KeyError) as fehler:
        st.error(
            "Die WFS-Daten konnten nicht verarbeitet werden: "
            f"{fehler}"
        )

# ── Tab Unfälle ────────────────────────────────────────────────────────────────
with tab_unfaelle:
    st.subheader(
        "🚨 Fahrradunfälle mit Personenschaden in Berlin-Mitte"
    )

    # -------------------------------------------------------------------------
    # Datenquellen
    # -------------------------------------------------------------------------

    unfall_service_url = (
        "https://services.arcgis.com/"
        "P3ePLMYs2RVChkJx/ArcGIS/rest/services/"
        "Germany_Traffic_Accidents_2025/"
        "FeatureServer/0/query"
    )

    bezirke_wfs_url = (
        "https://gdi.berlin.de/services/wfs/alkis_bezirke"
    )

    # Erst alle Fahrradunfälle in Berlin laden.
    # Die Einschränkung auf Mitte erfolgt räumlich anhand der Bezirksgrenze.
    unfall_filter = (
        "ULAND = '11' "
        "AND IstRadInt = 1"
    )

    # -------------------------------------------------------------------------
    # Karte
    # -------------------------------------------------------------------------

    unfall_karte = folium.Map(
        location=[52.5205, 13.4050],
        zoom_start=13,
        tiles="CartoDB positron",
        control_scale=True
    )

    # -------------------------------------------------------------------------
    # Hilfsfunktionen
    # -------------------------------------------------------------------------

    def finde_bezirke_layername():
        capabilities_response = requests.get(
            bezirke_wfs_url,
            params={
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetCapabilities"
            },
            timeout=60
        )

        capabilities_response.raise_for_status()

        xml_root = ET.fromstring(
            capabilities_response.content
        )

        namespaces = {
            "wfs": "http://www.opengis.net/wfs/2.0"
        }

        layernamen = []

        for name_element in xml_root.findall(
            ".//wfs:FeatureType/wfs:Name",
            namespaces
        ):
            if name_element.text:
                layernamen.append(
                    name_element.text.strip()
                )

        if not layernamen:
            raise ValueError(
                "Im Bezirke-WFS wurde kein Layer gefunden."
            )

        return next(
            (
                layername
                for layername in layernamen
                if "bezirk" in layername.lower()
            ),
            layernamen[0]
        )

    def lade_bezirke_geojson(layername):
        ausgabeformate = [
            "application/json",
            "application/json; subtype=geojson",
            "json"
        ]

        letzter_fehler = ""

        for ausgabeformat in ausgabeformate:
            response = requests.get(
                bezirke_wfs_url,
                params={
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeNames": layername,
                    "outputFormat": ausgabeformat,
                    "srsName": "EPSG:4326"
                },
                timeout=60
            )

            if not response.ok:
                letzter_fehler = response.text
                continue

            try:
                daten = response.json()
            except ValueError:
                letzter_fehler = response.text
                continue

            if daten.get("type") == "FeatureCollection":
                return daten

        raise ValueError(
            "Der Bezirke-WFS konnte nicht als GeoJSON geladen werden. "
            f"{letzter_fehler[:500]}"
        )

    def finde_mitte_feature(bezirke_daten):
        for feature in bezirke_daten.get("features", []):
            eigenschaften = feature.get(
                "properties",
                {}
            )

            attributwerte = [
                str(wert).strip().lower()
                for wert in eigenschaften.values()
                if wert is not None
            ]

            if "mitte" in attributwerte:
                return feature

            attribut_text = " ".join(
                attributwerte
            )

            if " mitte " in f" {attribut_text} ":
                return feature

        return None

    def normalisiere_kategorie(kategorie):
        """
        Gibt eine der drei gewünschten textlichen Kategorien zurück.
        Unterstützt sowohl Textwerte als auch vorsorglich numerische Codes.
        """
        if kategorie is None:
            return "Unfall mit Personenschaden"

        text = str(kategorie).strip()
        text_klein = text.lower()

        if (
            "unfall mit getöteten" in text_klein
            or "getötet" in text_klein
            or "getoetet" in text_klein
            or "tödlich" in text_klein
            or "toedlich" in text_klein
        ):
            return "Unfall mit Getöteten"

        if (
            "unfall mit schwerverletzten" in text_klein
            or "schwerverlet" in text_klein
            or "schwer verletzt" in text_klein
        ):
            return "Unfall mit Schwerverletzten"

        if (
            "unfall mit leichtverletzten" in text_klein
            or "leichtverlet" in text_klein
            or "leicht verletzt" in text_klein
        ):
            return "Unfall mit Leichtverletzten"

        # Fallback, falls der Dienst doch numerische Codes liefert
        try:
            code = int(float(text))

            kategorien_nach_code = {
                1: "Unfall mit Getöteten",
                2: "Unfall mit Schwerverletzten",
                3: "Unfall mit Leichtverletzten"
            }

            return kategorien_nach_code.get(
                code,
                "Unfall mit Personenschaden"
            )

        except (TypeError, ValueError):
            return "Unfall mit Personenschaden"

    def farbe_fuer_kategorie(kategorie_text):
        farben = {
            "Unfall mit Getöteten": "darkred",
            "Unfall mit Schwerverletzten": "orange",
            "Unfall mit Leichtverletzten": "blue"
        }

        return farben.get(
            kategorie_text,
            "gray"
        )

    def unfalltyp_text(utyp):
        """
        Gibt den Unfalltyp als Text zurück.
        Unterstützt sowohl Textwerte als auch vorsorglich numerische Codes.
        """
    
        if utyp is None:
            return "Unbekannt"
    
        text = str(utyp).strip()
    
        if text:
            # Wenn der Dienst bereits einen Text liefert,
            # diesen direkt verwenden.
            if not text.replace(".", "").isdigit():
                return text
    
        try:
            code = int(float(text))
        except (TypeError, ValueError):
            return "Unbekannt"
    
        unfalltypen = {
            1: "Fahrunfall",
            2: "Abbiege-Unfall",
            3: "Einbiegen / Kreuzen-Unfall",
            4: "Überschreiten-Unfall",
            5: "Unfall durch ruhenden Verkehr",
            6: "Unfall im Längsverkehr",
            7: "Sonstiger Unfall"
        }
    
        return unfalltypen.get(
            code,
            "Unbekannt"
        )

    def monat_text(monat):
        monate = {
            1: "Januar",
            2: "Februar",
            3: "März",
            4: "April",
            5: "Mai",
            6: "Juni",
            7: "Juli",
            8: "August",
            9: "September",
            10: "Oktober",
            11: "November",
            12: "Dezember"
        }

        try:
            return monate.get(
                int(float(monat)),
                "–"
            )
        except (TypeError, ValueError):
            return "–"

    def wochentag_text(wochentag):
        wochentage = {
            1: "Sonntag",
            2: "Montag",
            3: "Dienstag",
            4: "Mittwoch",
            5: "Donnerstag",
            6: "Freitag",
            7: "Samstag"
        }

        try:
            return wochentage.get(
                int(float(wochentag)),
                "–"
            )
        except (TypeError, ValueError):
            return "–"

    def uhrzeit_text(stunde):
        try:
            return f"{int(float(stunde)):02d}:00 Uhr"
        except (TypeError, ValueError):
            return "–"

    def jahr_text(jahr):
        try:
            return str(
                int(float(jahr))
            )
        except (TypeError, ValueError):
            return "–"

    # -------------------------------------------------------------------------
    # Daten laden
    # -------------------------------------------------------------------------

    try:
        # ---------------------------------------------------------------------
        # 1. Bezirksgrenze laden
        # ---------------------------------------------------------------------

        bezirke_layername = finde_bezirke_layername()

        bezirke_daten = lade_bezirke_geojson(
            bezirke_layername
        )

        mitte_feature = finde_mitte_feature(
            bezirke_daten
        )

        if mitte_feature is None:
            st.error(
                "Die Bezirksgrenze von Berlin-Mitte "
                "wurde im WFS nicht gefunden."
            )
            st.stop()

        mitte_geometrie = shape(
            mitte_feature["geometry"]
        )

        folium.GeoJson(
            mitte_feature,
            name="Bezirksgrenze Berlin-Mitte",
            style_function=lambda feature: {
                "color": "#263238",
                "weight": 3,
                "fillColor": "#90caf9",
                "fillOpacity": 0.08,
                "dashArray": "7, 5"
            },
            tooltip="Bezirksgrenze Berlin-Mitte"
        ).add_to(unfall_karte)

        # ---------------------------------------------------------------------
        # 2. Berliner Fahrradunfälle laden
        # ---------------------------------------------------------------------

        unfall_response = requests.get(
            unfall_service_url,
            params={
                "where": unfall_filter,
                "outFields": (
                    "UIDENTSTLA,"
                    "UJAHR,"
                    "UMONAT,"
                    "UWOCHENTAG,"
                    "USTUNDE,"
                    "UKATEGORIE,"
                    "UTYP1,"
                    "IstRadInt,"
                    "ULAND"
                ),
                "returnGeometry": "true",
                "outSR": "4326",
                "resultRecordCount": 2000,
                "f": "geojson"
            },
            timeout=60
        )

        unfall_response.raise_for_status()

        unfall_daten = unfall_response.json()

        if "error" in unfall_daten:
            st.error(
                "Der Unfalldatendienst meldet einen Fehler:"
            )
            st.json(
                unfall_daten["error"]
            )
            st.stop()

        berlin_features = unfall_daten.get(
            "features",
            []
        )

        # ---------------------------------------------------------------------
        # 3. Räumlich auf Berlin-Mitte filtern
        # ---------------------------------------------------------------------

        unfall_features = []

        for feature in berlin_features:
            geometrie = feature.get(
                "geometry"
            )

            if not geometrie:
                continue

            koordinaten = geometrie.get(
                "coordinates",
                []
            )

            if len(koordinaten) < 2:
                continue

            try:
                longitude = float(
                    koordinaten[0]
                )

                latitude = float(
                    koordinaten[1]
                )

            except (TypeError, ValueError):
                continue

            unfallpunkt = Point(
                longitude,
                latitude
            )

            if mitte_geometrie.covers(
                unfallpunkt
            ):
                unfall_features.append(
                    feature
                )

        # ---------------------------------------------------------------------
        # 4. Kategorien zählen
        # ---------------------------------------------------------------------

        kategorie_anzahlen = {
            "Unfall mit Getöteten": 0,
            "Unfall mit Schwerverletzten": 0,
            "Unfall mit Leichtverletzten": 0,
            "Unfall mit Personenschaden": 0
        }

        for feature in unfall_features:
            daten = feature.get(
                "properties",
                {}
            )

            kategorie = normalisiere_kategorie(
                daten.get("UKATEGORIE")
            )

            kategorie_anzahlen[kategorie] = (
                kategorie_anzahlen.get(
                    kategorie,
                    0
                )
                + 1
            )

        # ---------------------------------------------------------------------
        # 5. Kennzahlen
        # ---------------------------------------------------------------------

        spalte_1, spalte_2, spalte_3, spalte_4 = st.columns(4)

        with spalte_1:
            st.metric(
                "Fahrradunfälle",
                len(unfall_features)
            )

        with spalte_2:
            st.metric(
                "Mit Getöteten",
                kategorie_anzahlen[
                    "Unfall mit Getöteten"
                ]
            )

        with spalte_3:
            st.metric(
                "Mit Schwerverletzten",
                kategorie_anzahlen[
                    "Unfall mit Schwerverletzten"
                ]
            )

        with spalte_4:
            st.metric(
                "Mit Leichtverletzten",
                kategorie_anzahlen[
                    "Unfall mit Leichtverletzten"
                ]
            )

        # ---------------------------------------------------------------------
        # 6. Unfallpunkte darstellen
        # ---------------------------------------------------------------------

        for feature in unfall_features:
            geometrie = feature.get(
                "geometry",
                {}
            )

            koordinaten = geometrie.get(
                "coordinates",
                []
            )

            if len(koordinaten) < 2:
                continue

            try:
                longitude = float(
                    koordinaten[0]
                )

                latitude = float(
                    koordinaten[1]
                )

            except (TypeError, ValueError):
                continue

            daten = feature.get(
                "properties",
                {}
            )

            kategorie_roh = daten.get(
                "UKATEGORIE"
            )

            kategorie = normalisiere_kategorie(
                kategorie_roh
            )

            farbe = farbe_fuer_kategorie(
                kategorie
            )

            unfalltyp = unfalltyp_text(
            daten.get("UTYP1")
            )

            popup_html = f"""
            <div style="
                width:275px;
                font-family:Arial, sans-serif;
                line-height:1.45;
            ">
                <h4 style="
                    color:#b71c1c;
                    margin-top:0;
                    margin-bottom:10px;
                ">
                    🚨 Fahrradunfall
                </h4>

                <b>Jahr:</b>
                {jahr_text(daten.get("UJAHR"))}<br>
                <b>Unfallkategorie:</b>
                {kategorie}<br>      
                <b>Unfalltyp:</b>
                {unfalltyp}<br>
                <b>Uhrzeit:</b>
                {uhrzeit_text(daten.get("USTUNDE"))}<br><br>
                
            </div>
            """

            folium.CircleMarker(
                location=[
                    latitude,
                    longitude
                ],
                radius=7,
                color=farbe,
                weight=2,
                fill=True,
                fill_color=farbe,
                fill_opacity=0.85,
                popup=folium.Popup(
                    popup_html,
                    max_width=320
                ),
                tooltip=kategorie
            ).add_to(unfall_karte)

        # ---------------------------------------------------------------------
        # 7. Legende
        # ---------------------------------------------------------------------

        legende_html = """
        <div style="
            position:fixed;
            bottom:35px;
            left:35px;
            z-index:9999;
            background:white;
            padding:12px 15px;
            border:2px solid #777;
            border-radius:7px;
            font-size:13px;
            line-height:1.4;
            box-shadow:0 1px 6px rgba(0,0,0,0.35);
        ">
            <b>Unfallkategorie</b><br><br>

            <span style="
                display:inline-block;
                width:13px;
                height:13px;
                border-radius:50%;
                background:darkred;
                margin-right:8px;
                vertical-align:middle;
            "></span>
            Unfall mit Getöteten
            <br><br>

            <span style="
                display:inline-block;
                width:13px;
                height:13px;
                border-radius:50%;
                background:orange;
                margin-right:8px;
                vertical-align:middle;
            "></span>
            Unfall mit Schwerverletzten
            <br><br>

            <span style="
                display:inline-block;
                width:13px;
                height:13px;
                border-radius:50%;
                background:blue;
                margin-right:8px;
                vertical-align:middle;
            "></span>
            Unfall mit Leichtverletzten
            <br><br>

            <span style="
                display:inline-block;
                width:28px;
                border-top:3px dashed #263238;
                margin-right:8px;
                vertical-align:middle;
            "></span>
            Bezirksgrenze Mitte
        </div>
        """

        unfall_karte.get_root().html.add_child(
            folium.Element(
                legende_html
            )
        )

        folium.LayerControl(
            collapsed=True
        ).add_to(unfall_karte)

        # ---------------------------------------------------------------------
        # 8. Karte ausgeben
        # ---------------------------------------------------------------------

        st_folium(
            unfall_karte,
            height=650,
            use_container_width=True,
            key="unfall_karte"
        )

        unbekannte_anzahl = kategorie_anzahlen.get(
            "Unfall mit Personenschaden",
            0
        )

        if unbekannte_anzahl > 0:
            st.warning(
                f"{unbekannte_anzahl} Unfallpunkte konnten keiner "
                "der drei textlichen Unfallkategorien zugeordnet werden."
            )

            vorhandene_rohwerte = sorted({
                str(
                    feature.get(
                        "properties",
                        {}
                    ).get("UKATEGORIE")
                )
                for feature in unfall_features
                if normalisiere_kategorie(
                    feature.get(
                        "properties",
                        {}
                    ).get("UKATEGORIE")
                )
                == "Unfall mit Personenschaden"
            })

            with st.expander(
                "Nicht erkannte Werte aus UKATEGORIE"
            ):
                st.write(
                    vorhandene_rohwerte
                )

        st.caption(
            "Quelle Unfalldaten: Unfallatlas der Statistischen Ämter "
            "des Bundes und der Länder · "
            "Quelle Bezirksgrenze: Geoportal Berlin · "
            f"{len(unfall_features)} Fahrradunfälle "
            "mit Personenschaden in Berlin-Mitte"
        )

    except requests.exceptions.RequestException as fehler:
        st.error(
            "Die Geo- oder Unfalldaten konnten nicht geladen werden: "
            f"{fehler}"
        )

        st_folium(
            unfall_karte,
            height=650,
            use_container_width=True,
            key="unfall_karte_fehler"
        )

    except ET.ParseError as fehler:
        st.error(
            "Die Beschreibung des Bezirke-WFS konnte nicht "
            f"verarbeitet werden: {fehler}"
        )

    except (
        ValueError,
        TypeError,
        KeyError
    ) as fehler:
        st.error(
            "Die Geo- oder Unfalldaten konnten nicht verarbeitet werden: "
            f"{fehler}"
        )


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small style='color:#9CA3AF'>Labor-Hausaufgabe im Rahmen der Lehrveranstaltung „Digitalisierung intermodaler Radverkehrsangebote“ im Studiengang „Radverkehr in intermodalen Verkehrsnetzen“ – Sommersemester 2026</small>",
    unsafe_allow_html=True
)

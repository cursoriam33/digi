import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium

# ── Seitenkonfiguration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Radverkehr Herzberg",
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
        background: linear-gradient(135deg, #1B4F3A 0%, #2E7D55 100%);
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
        border-left: 4px solid #2E7D55;
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

    [data-testid="stSidebar"] { background: #1B4F3A; }
    [data-testid="stSidebar"] * { color: white; }
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


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚲 Radverkehr\n### Herzberg (Elster)")
    st.markdown("---")
    uploaded_file = st.file_uploader(
        "Eco-Visio CSV hochladen",
        type=["csv"],
        help="Export aus Eco-Visio (stündliche Auflösung)"
    )
    st.markdown("---")
    zaehler_name = st.text_input("Zählstellenname", value="Schliebener Straße")
    lat = st.number_input("Breitengrad", value=51.6917, format="%.4f")
    lon = st.number_input("Längengrad",  value=13.2333, format="%.4f")
    st.markdown("---")
    st.markdown("<small>Dashboard | Master Radverkehr<br>Modul Digitalisierung</small>", unsafe_allow_html=True)


# ── Hauptbereich ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
    <h1>🚲 Radverkehrs-Dashboard</h1>
    <p>Stadt Herzberg (Elster) · Zählstelle {zaehler_name if uploaded_file else "–"}</p>
</div>
""", unsafe_allow_html=True)

if not uploaded_file:
    st.info("👈 Bitte eine Eco-Visio CSV-Datei in der Seitenleiste hochladen, um das Dashboard zu starten.")
    st.stop()

# ── Daten laden ───────────────────────────────────────────────────────────────
df = lade_daten(uploaded_file)
pro_tag = df.groupby("Datum")["Anzahl"].sum().reset_index()
pro_tag["Datum"] = pd.to_datetime(pro_tag["Datum"])
pro_tag["IstWochenende"] = pro_tag["Datum"].dt.dayofweek >= 5
pro_tag["TagTyp"] = pro_tag["IstWochenende"].map({False: "Werktag", True: "Wochenende"})

zeitraum = f"{df['Zeitstempel'].min().strftime('%d.%m.%Y')} – {df['Zeitstempel'].max().strftime('%d.%m.%Y')}"

# ── Filter ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Filter")
    jahre = sorted(df["Zeitstempel"].dt.year.unique())
    if len(jahre) > 1:
        jahr_filter = st.selectbox("Jahr", ["Alle"] + [str(j) for j in jahre])
        if jahr_filter != "Alle":
            df = df[df["Zeitstempel"].dt.year == int(jahr_filter)]
            pro_tag = pro_tag[pro_tag["Datum"].dt.year == int(jahr_filter)]

# ── KPI-Kacheln ───────────────────────────────────────────────────────────────
st.markdown(f'<div class="section-title">📋 Kennzahlen · {zeitraum}</div>', unsafe_allow_html=True)

werktag_schnitt   = pro_tag[~pro_tag["IstWochenende"]]["Anzahl"].mean()
wochenend_schnitt = pro_tag[pro_tag["IstWochenende"]]["Anzahl"].mean()
spitzentag = pro_tag.loc[pro_tag["Anzahl"].idxmax()]

k1, k2, k3, k4, k5 = st.columns(5)
k1.markdown(kpi_card("Gesamt", f"{df['Anzahl'].sum():,}", "Radfahrende"), unsafe_allow_html=True)
k2.markdown(kpi_card("Tagesdurchschnitt", f"{pro_tag['Anzahl'].mean():.0f}", "Radfahrende / Tag"), unsafe_allow_html=True)
k3.markdown(kpi_card("Spitzentag", f"{spitzentag['Anzahl']}", spitzentag['Datum'].strftime('%d.%m.%Y')), unsafe_allow_html=True)
k4.markdown(kpi_card("Werktags-Ø", f"{werktag_schnitt:.0f}", "Radfahrende / Tag"), unsafe_allow_html=True)
k5.markdown(kpi_card("Wochenend-Ø", f"{wochenend_schnitt:.0f}", "Radfahrende / Tag"), unsafe_allow_html=True)

# ── Tagestrend ────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">📈 Tagestrend</div>', unsafe_allow_html=True)

fig_trend = px.line(
    pro_tag,
    x="Datum", y="Anzahl",
    color="TagTyp",
    color_discrete_map={"Werktag": FARBEN["gruen"], "Wochenende": FARBEN["coral"]},
    labels={"Anzahl": "Radfahrende", "Datum": "", "TagTyp": ""},
    markers=True,
    template="plotly_white",
)
fig_trend.add_hline(
    y=pro_tag["Anzahl"].mean(),
    line_dash="dash", line_color=FARBEN["grau"],
    annotation_text=f"Ø {pro_tag['Anzahl'].mean():.0f}",
    annotation_font_color=FARBEN["grau"]
)
apply_theme(fig_trend, height=320)
st.plotly_chart(fig_trend, use_container_width=True)

# ── Radverkehr nach Uhrzeit + Wochenmuster ──────────────────────────────────────────────────
col_links, col_rechts = st.columns(2)

with col_links:
    st.markdown('<div class="section-title">🕐 Radverkehr nach Uhrzeit</div>', unsafe_allow_html=True)
    pro_stunde = df.groupby(["Stunde", "IstWochenende"])["Anzahl"].mean().reset_index()
    pro_stunde["TagTyp"] = pro_stunde["IstWochenende"].map({False: "Werktag", True: "Wochenende"})

    fig_tg = px.bar(
        pro_stunde, x="Stunde", y="Anzahl", color="TagTyp", barmode="group",
        color_discrete_map={"Werktag": FARBEN["gruen"], "Wochenende": FARBEN["coral"]},
        labels={"Anzahl": "Ø Radfahrende / Stunde", "Stunde": "Uhrzeit", "TagTyp": ""},
        template="plotly_white",
    )
    apply_theme(fig_tg, height=320)
    fig_tg.update_layout(xaxis=dict(tickmode="linear", dtick=2))
    st.plotly_chart(fig_tg, use_container_width=True)

with col_rechts:
    st.markdown('<div class="section-title">📊 Wochenmuster</div>', unsafe_allow_html=True)
    anzahl_wochen = max(df["Woche"].nunique(), 1)
    pro_wt = df.groupby("Wochentag")["Anzahl"].sum().reset_index()
    pro_wt["Durchschnitt"] = (pro_wt["Anzahl"] / anzahl_wochen).round(0).astype(int)
    pro_wt["Wochentag"] = pd.Categorical(pro_wt["Wochentag"], categories=WOCHENTAG_ORDER, ordered=True)
    pro_wt = pro_wt.sort_values("Wochentag")
    pro_wt["TagTyp"] = pro_wt["Wochentag"].isin(["Samstag", "Sonntag"]).map({False: "Werktag", True: "Wochenende"})

    fig_wt = px.bar(
        pro_wt, x="Wochentag", y="Durchschnitt",
        color="TagTyp",
        color_discrete_map={"Werktag": FARBEN["gruen"], "Wochenende": FARBEN["coral"]},
        labels={"Durchschnitt": "Ø Radfahrende", "Wochentag": "", "TagTyp": ""},
        text="Durchschnitt",
        template="plotly_white",
    )
    fig_wt.update_traces(textposition="outside")
    apply_theme(fig_wt, height=320)
    fig_wt.update_layout(showlegend=False)
    st.plotly_chart(fig_wt, use_container_width=True)

# ── Heatmap ───────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🔥 Heatmap – Wochentag × Uhrzeit</div>', unsafe_allow_html=True)

heatmap_data = df.groupby(["Wochentag", "Stunde"])["Anzahl"].mean().reset_index()
heatmap_pivot = heatmap_data.pivot(index="Wochentag", columns="Stunde", values="Anzahl")
heatmap_pivot = heatmap_pivot.reindex(WOCHENTAG_ORDER)

fig_heat = px.imshow(
    heatmap_pivot,
    color_continuous_scale=[[0, "#F0FDF4"], [0.5, FARBEN["gruen_hell"]], [1, FARBEN["gruen"]]],
    labels={"x": "Uhrzeit", "y": "", "color": "Ø Radfahrende"},
    aspect="auto",
    template="plotly_white",
)
apply_theme(fig_heat, height=280)
st.plotly_chart(fig_heat, use_container_width=True)

# ── Karte ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">🗺️ Standort der Zählstelle</div>', unsafe_allow_html=True)

karte = folium.Map(location=[lat, lon], zoom_start=14, tiles="CartoDB positron")
folium.Marker(
    location=[lat, lon],
    popup=folium.Popup(
        f"<b>{zaehler_name}</b><br>"
        f"Gesamt: {df['Anzahl'].sum():,} Radfahrende<br>"
        f"Tagesdurchschnitt: {pro_tag['Anzahl'].mean():.0f}",
        max_width=220
    ),
    icon=folium.Icon(color="green", icon="info-sign"),
    tooltip=zaehler_name
).add_to(karte)
st_folium(karte, height=350, use_container_width=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<small style='color:#9CA3AF'>Datenquelle: Eco-Visio · "
    "Stadt Herzberg (Elster) · Master Radverkehr, Modul Digitalisierung</small>",
    unsafe_allow_html=True
)

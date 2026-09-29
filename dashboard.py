import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# Load exported dataframes
@st.cache_data
def load_data():
    analysis_df = pd.read_csv("analysis_df_export.csv")
    iran_df = pd.read_csv("iran_df_export.csv")
    return analysis_df, iran_df

# Geocode a city via Wikidata
@st.cache_data
def get_city_coordinates(city):
    url = "https://www.wikidata.org/w/api.php"
    response = requests.get(url, params={"action": "wbsearchentities", "search": city, "language": "en", "format": "json"}, headers={"User-Agent": "MET-Iran-Dashboard/1.0"})

    try:
        results = response.json()["search"]
    except Exception:
        return None

    if not results:
        return None

    entity_id = results[0]["id"]
    response = requests.get(url, params={"action": "wbgetentities", "ids": entity_id, "props": "claims", "format": "json"}, headers={"User-Agent": "MET-Iran-Dashboard/1.0"})
    claims = response.json()["entities"][entity_id]["claims"]

    if "P625" not in claims:
        return None

    coordinates = claims["P625"][0]["mainsnak"]["datavalue"]["value"]
    return (coordinates["latitude"], coordinates["longitude"])

# UNESCO World Heritage Sites in Iran (Wikidata SPARQL)
@st.cache_data
def load_unesco_sites():
    query = """
    SELECT ?siteLabel ?coord WHERE {
      ?site wdt:P1435 wd:Q9259 ;
            wdt:P17 wd:Q794 ;
            wdt:P625 ?coord .

      SERVICE wikibase:label {
        bd:serviceParam wikibase:language "en".
      }
    }
    """
    try:
        response = requests.get("https://query.wikidata.org/sparql", params={"query": query, "format": "json"}, headers={"User-Agent": "StreamlitDashboard"}, timeout=15)
        data = response.json()
    except Exception:
        return pd.DataFrame(columns=["name", "lat", "lon", "site", "wiki_url"])

    rows = []

    for item in data["results"]["bindings"]:
        coord = item["coord"]["value"].replace("Point(", "").replace(")", "")
        lon, lat = coord.split()
        rows.append({"name": item["siteLabel"]["value"], "lat": float(lat), "lon": float(lon), "site": "UNESCO World Heritage", "wiki_url": f"https://en.wikipedia.org/wiki/{item['siteLabel']['value'].replace(' ', '_')}"})

    return pd.DataFrame(rows)

unesco_df = load_unesco_sites()
unesco_load_failed = unesco_df.empty
analysis_df, iran_df = load_data()

# Cultures used to select the Iran dataset
iran_cultures = [
    "Iran", "Iranian", "Iranian (Persian)", "Persian", "Persian, Qajar", "Qajar", "probably Iranian",
    "Indo-Persian", "Graeco-Persian", "Achaemenid", "Achaemenid (?)", "Parthian", "Parthian (?)",
    "Parthian or Sasanian", "Sasanian", "Sasanian (?)", "Sasanian or Islamic"
]

# Chronological order of Iran periods
ordered_periods = [
    "Prehistoric", "Pre-Achaemenid", "Achaemenid", "Hellenistic", "Parthian", "Sasanian", "Early Islamic",
    "Seljuk", "Ilkhanid-Timurid", "Safavid", "Afsharid-Zand", "Qajar", "Pahlavi", "Islamic Republic"
]

# Global begin_year bounds for the Object Explorer range slider (based on full iran_df, stable across filters)
IRAN_MIN_YEAR = int(iran_df["begin_year"].min())
IRAN_MAX_YEAR = int(iran_df["begin_year"].max())

# Reset filters helper
def reset_filters(keys):
    for key in keys:
        st.session_state.pop(key, None)
    st.rerun()

# Map with only UNESCO sites, centered on Isfahan (used when no single object location can be shown)
def show_unesco_only_map():
    if unesco_load_failed:
        st.warning("UNESCO World Heritage Sites could not be loaded from Wikidata right now. Please try reloading the dashboard.")
        return

    fig_map_unesco = px.scatter_map(
        unesco_df, lat="lat", lon="lon", color="site", hover_name="name", zoom=4.3,
        center={"lat": 32.6546, "lon": 51.6680}, height=600,
        color_discrete_map={"UNESCO World Heritage": "goldenrod"}
    )

    fig_map_unesco.update_traces(marker=dict(size=12))
    fig_map_unesco.update_layout(map_style="open-street-map", legend_title_text="Location Site", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))

    st.plotly_chart(fig_map_unesco, use_container_width=True)

    with st.expander("UNESCO World Heritage Sites in Iran (Wikipedia links)"):
        for _, site in unesco_df.drop_duplicates(subset="name").sort_values("name").iterrows():
            st.markdown(f"- [{site['name']}]({site['wiki_url']})")

# Page config
st.set_page_config(page_title="MET Museum Dashboard", page_icon="🏛️", layout="wide", initial_sidebar_state="expanded")

# Light red sidebar
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] {
        background-color: #fdecea;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Navigation
page = st.sidebar.radio("Navigation", ["Overall Collection", "Iranian-Persian Holdings", "Focus Areas of the Iran Collection", "Object Explorer"])

if page == "Overall Collection":

    st.title("🏛️ Iranian Cultural Heritage in the Metropolitan Museum of Art")
    st.caption("Data Analytics Project based on the Metropolitan Museum of Art Open Access Dataset")
    st.header("Overall Collection")

    # Filters
    if st.sidebar.button("Reset Filters", key="oc_reset_btn"):
        reset_filters(["oc_department", "oc_country", "oc_region", "oc_century"])

    department_filter = st.sidebar.multiselect("Department", sorted(analysis_df["department"].dropna().unique()), key="oc_department")
    country_filter = st.sidebar.multiselect("Country", sorted(analysis_df["country_clean"].dropna().unique()), key="oc_country")
    region_filter = st.sidebar.multiselect("World Region", sorted(analysis_df["world_region"].dropna().unique()), key="oc_region")
    century_filter = st.sidebar.multiselect("Dating Start Century", sorted(analysis_df["begin_century"].dropna().unique()), key="oc_century")

    filtered_df = analysis_df.copy()

    if department_filter:
        filtered_df = filtered_df[filtered_df["department"].isin(department_filter)]

    if country_filter:
        filtered_df = filtered_df[filtered_df["country_clean"].isin(country_filter)]

    if region_filter:
        filtered_df = filtered_df[filtered_df["world_region"].isin(region_filter)]

    if century_filter:
        filtered_df = filtered_df[filtered_df["begin_century"].isin(century_filter)]

    if len(filtered_df) == 0:
        st.warning("No objects match the selected filters.")
        st.stop()

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Objects", f"{len(filtered_df):,}")
    col2.metric("Cultures", filtered_df["culture"].nunique())

    missing_culture = round((filtered_df["culture"].isin(["unknown", "unspecified"])).sum() / len(filtered_df) * 100, 2)
    missing_origin = round((filtered_df["country_clean"].isin(["unknown", "unspecified"])).sum() / len(filtered_df) * 100, 2)

    col3.metric("Missing Culture", f"{missing_culture} %")
    col4.metric("Missing Origin", f"{missing_origin} %")

    st.divider()

    # Top cultures
    top_cultures_dashboard = (
        filtered_df[filtered_df["culture"] != "unspecified"]
        .groupby("culture")["object_id"]
        .count()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )

    fig_cultures = px.bar(
        top_cultures_dashboard, x="culture", y="object_id", text_auto=",.0f",
        title="Top 10 Listed Cultures of Origin in the Met Collection Dataset",
        labels={"culture": "Culture", "object_id": "Number of Objects"}
    )

    fig_cultures.update_traces(marker_color="darkred", textposition="outside")
    fig_cultures.update_layout(title_x=0, template="plotly_white")
    fig_cultures.update_xaxes(showgrid=False)
    fig_cultures.update_yaxes(showgrid=False, range=[0, 25000])

    # Top countries
    top_countries_dashboard = (
        filtered_df[(filtered_df["country_clean"] != "unknown") & (filtered_df["country_clean"] != "unspecified")]
        .groupby("country_clean")["object_id"]
        .count()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )

    fig_countries = px.bar(
        top_countries_dashboard, x="country_clean", y="object_id", text_auto=",.0f",
        title="Top 10 Listed Countries of Origin in the Met Collection Dataset",
        labels={"country_clean": "Country", "object_id": "Number of Objects"}
    )

    fig_countries.update_traces(marker_color="darkred", textposition="outside")
    fig_countries.update_layout(title_x=0, template="plotly_white")
    fig_countries.update_xaxes(showgrid=False)
    fig_countries.update_yaxes(showgrid=False, range=[0, 35000])

    # Cultures and countries side by side
    left, right = st.columns(2)

    with left:
        st.plotly_chart(fig_cultures, use_container_width=True)

    with right:
        st.plotly_chart(fig_countries, use_container_width=True)

    # World regions
    region_dashboard = (
        filtered_df
        .groupby("world_region")["object_id"]
        .count()
        .sort_values(ascending=False)
        .reset_index()
    )

    fig_region = px.bar(
        region_dashboard, x="world_region", y="object_id", text_auto=",.0f",
        title="World Region of Origin in the Met Collection Dataset",
        labels={"world_region": "Continent", "object_id": "Numer of Objects"}
    )

    fig_region.update_traces(marker_color="darkred", textposition="outside")
    fig_region.update_layout(title_x=0, template="plotly_white")
    fig_region.update_xaxes(showgrid=False)
    fig_region.update_yaxes(showgrid=False, range=[0, 400000])

    st.plotly_chart(fig_region, use_container_width=True)

    # Historical distribution
    histogram_df = filtered_df[filtered_df["begin_year"] >= -1000]

    fig_hist = px.histogram(
        histogram_df, x="begin_year",
        title="Distribution of Object Dating Start (Year, from 1000 BCE – Earliest Object: 95,000 BC)",
        labels={"begin_year": "Dating Start (Year)"}
    )

    fig_hist.update_traces(marker_color="darkred")
    fig_hist.update_layout(title_x=0, template="plotly_white")
    fig_hist.update_xaxes(showgrid=False)
    fig_hist.update_yaxes(title_text="Number of Objects", showgrid=False)

    st.plotly_chart(fig_hist, use_container_width=True)

elif page == "Iranian-Persian Holdings":

    st.title("🏛️ Iranian Cultural Heritage in the Metropolitan Museum of Art")
    st.header("Iranian-Persian Holdings")

    # Filters
    if st.sidebar.button("Reset Filters", key="iph_reset_btn"):
        reset_filters(["iph_culture", "iph_city", "iph_period"])

    culture_filter = st.sidebar.multiselect("Culture", sorted(iran_df["culture"].dropna().unique()), key="iph_culture")
    city_filter = st.sidebar.multiselect("City", sorted(iran_df["city"].dropna().unique()), key="iph_city")
    period_filter = st.sidebar.multiselect("Iran Period", sorted(iran_df["iran_period"].dropna().unique()), key="iph_period")

    filtered_iran_df = iran_df.copy()

    if culture_filter:
        filtered_iran_df = filtered_iran_df[filtered_iran_df["culture"].isin(culture_filter)]

    if city_filter:
        filtered_iran_df = filtered_iran_df[filtered_iran_df["city"].isin(city_filter)]

    if period_filter:
        filtered_iran_df = filtered_iran_df[filtered_iran_df["iran_period"].isin(period_filter)]

    if len(filtered_iran_df) == 0:
        st.warning("No objects match the selected filters.")
        st.stop()

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Iranian Objects", f"{len(filtered_iran_df):,}")
    col2.metric("Share of Overall Collection", f"{round(len(filtered_iran_df) / len(analysis_df) * 100, 2)} %")

    after_1000 = round(len(filtered_iran_df[filtered_iran_df["begin_year"] >= -1000]) / len(filtered_iran_df) * 100, 2)
    col3.metric("Objects after 1000 BCE", f"{after_1000} %", help="Earliest object in the Iranian-Persian holdings dates to 6000 BCE")

    nishapur_count = len(filtered_iran_df[filtered_iran_df["city"] == "Nishapur"])
    col4.metric("Nishapur Objects", f"{nishapur_count:,}")

    st.divider()

    # Overlay: entire collection vs. Iran
    analysis_df_time = analysis_df[analysis_df["begin_year"] >= -1000].copy()
    iran_pre = filtered_iran_df[filtered_iran_df["begin_year"] >= -1000].copy()
    analysis_df_time["dataset"] = "Entire Collection"
    iran_pre["dataset"] = "Iran Dataset"
    overlay_df = pd.concat([analysis_df_time[["begin_year", "dataset"]], iran_pre[["begin_year", "dataset"]]])

    fig_overlay = px.histogram(
        overlay_df, x="begin_year", color="dataset", barmode="overlay", opacity=0.7,
        title="Distribution of Object Dating Start (Year, from 1000 BCE): Entire Collection vs. Iran Dataset",
        labels={"begin_year": "Object Dating Start (Year)", "dataset": "Dataset"}
    )

    fig_overlay.update_layout(title_x=0, template="plotly_white")
    fig_overlay.update_xaxes(showgrid=False)
    fig_overlay.update_yaxes(showgrid=False, title_text="Number of Objects")

    st.plotly_chart(fig_overlay, use_container_width=True)

    # Selection criteria
    country_count = len(analysis_df[analysis_df["country_clean"] == "Iran"])
    region_count = len(analysis_df[analysis_df["region"] == "Iran"])
    culture_count = len(analysis_df[analysis_df["culture"].isin(iran_cultures)])

    selection_df = pd.DataFrame({"criterion": ["Country", "Culture", "Region"], "count": [country_count, culture_count, region_count]})

    fig_selection = px.bar(
        selection_df, x="criterion", y="count", text_auto=",.0f",
        title="Contribution of Selection Criteria to the Iran Dataset",
        labels={"criterion": "Selection Criterion", "count": "Number of Objects"}
    )

    fig_selection.update_traces(marker_color="darkred", textposition="outside")
    fig_selection.update_layout(title_x=0, template="plotly_white")
    fig_selection.update_xaxes(showgrid=False)
    fig_selection.update_yaxes(showgrid=False, range=[0, 7000])

    st.plotly_chart(fig_selection, use_container_width=True)

    # Top cities
    city_dashboard = filtered_iran_df["city"].value_counts().head(10).reset_index()
    city_dashboard.columns = ["city", "count"]

    fig_city = px.bar(
        city_dashboard, x="city", y="count", text_auto=",.0f",
        title="Top 10 Cities of Origin (Iranian-Persian Objects)",
        labels={"city": "City", "count": "Number of Objects"}
    )

    fig_city.update_traces(marker_color="darkred", textposition="outside")
    fig_city.update_layout(title_x=0, template="plotly_white")
    fig_city.update_xaxes(showgrid=False)
    fig_city.update_yaxes(showgrid=False)

    st.plotly_chart(fig_city, use_container_width=True)

elif page == "Focus Areas of the Iran Collection":

    st.title("🏛️ Iranian Cultural Heritage in the Metropolitan Museum of Art")
    st.header("Focus Areas of the Iran Collection")

    # Filters
    if st.sidebar.button("Reset Filters", key="fa_reset_btn"):
        reset_filters(["fa_period", "fa_department", "fa_classification", "fa_acquisition"])

    period_filter = st.sidebar.multiselect("Iran Period", sorted(iran_df["iran_period"].dropna().unique()), key="fa_period")
    department_filter = st.sidebar.multiselect("Department", sorted(iran_df["department"].dropna().unique()), key="fa_department")
    classification_filter = st.sidebar.multiselect("Classification", sorted(iran_df["classification"].dropna().unique()), key="fa_classification")
    acquisition_filter = st.sidebar.multiselect("Acquisition Type", sorted(iran_df["acquisition_type"].dropna().unique()), key="fa_acquisition")

    filtered_iran_df = iran_df.copy()

    if period_filter:
        filtered_iran_df = filtered_iran_df[filtered_iran_df["iran_period"].isin(period_filter)]

    if department_filter:
        filtered_iran_df = filtered_iran_df[filtered_iran_df["department"].isin(department_filter)]

    if classification_filter:
        filtered_iran_df = filtered_iran_df[filtered_iran_df["classification"].isin(classification_filter)]

    if acquisition_filter:
        filtered_iran_df = filtered_iran_df[filtered_iran_df["acquisition_type"].isin(acquisition_filter)]

    if len(filtered_iran_df) == 0:
        st.warning("No objects match the selected filters.")
        st.stop()

    # KPIs
    col1, col2, col3, col4 = st.columns(4)

    early_islamic_percent = round((filtered_iran_df["iran_period"] == "Early Islamic").sum() / len(filtered_iran_df) * 100, 2)
    col1.metric("Early Islamic Period", f"{early_islamic_percent} %")

    peak_period = len(filtered_iran_df[(filtered_iran_df["begin_year"] >= 800) & (filtered_iran_df["begin_year"] <= 809)])
    col2.metric("Objects 800-809 CE", f"{peak_period:,}")

    nishapur_early = len(filtered_iran_df[(filtered_iran_df["iran_period"] == "Early Islamic") & (filtered_iran_df["city"] == "Nishapur")])
    col3.metric("Nishapur Objects", f"{nishapur_early:,}")

    major_departments_percent = round(len(filtered_iran_df[filtered_iran_df["department"].isin(["Islamic Art", "Ancient Near Eastern Art"])]) / len(filtered_iran_df) * 100, 2)
    col4.metric("Two Major Departments", f"{major_departments_percent} %")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["Historical", "Material", "Acquisition", "Institutional"])

    with tab1:

        # Chronological distribution (Iran periods, ordered)
        period_stats = (
            filtered_iran_df.groupby("iran_period")
            .agg(object_id=("object_id", "count"), min_year=("begin_year", "min"), max_year=("begin_year", "max"))
            .reset_index()
        )

        ordered_periods_present = [p for p in ordered_periods if p in period_stats["iran_period"].values]
        period_stats = period_stats.set_index("iran_period").loc[ordered_periods_present].reset_index()
        period_stats["percentage"] = (period_stats["object_id"] / period_stats["object_id"].sum() * 100).round(2)

        fig_chrono = px.line(
            period_stats, x="iran_period", y="object_id", markers=True, hover_data=["percentage", "min_year", "max_year"],
            title="Chronological Distribution of Iranian-Persian Objects",
            labels={"iran_period": "Historical Period", "object_id": "Number of Objects"}
        )

        fig_chrono.update_traces(line_color="darkred")
        fig_chrono.update_layout(title_x=0, template="plotly_white")
        fig_chrono.update_xaxes(showgrid=False, tickangle=-45)
        fig_chrono.update_yaxes(showgrid=False)

        st.plotly_chart(fig_chrono, use_container_width=True)

        # Objects by historical period (descending)
        iran_period_dashboard = (
            filtered_iran_df.groupby("iran_period")["object_id"]
            .count()
            .sort_values(ascending=False)
            .reset_index()
        )

        fig_period = px.bar(
            iran_period_dashboard, x="iran_period", y="object_id", text_auto=",.0f",
            title="Iranian-Persian Objects by Historical Period",
            labels={"iran_period": "Historical Period", "object_id": "Number of Objects"}
        )

        fig_period.update_traces(marker_color="darkred", textposition="outside")
        fig_period.update_layout(title_x=0, template="plotly_white")
        fig_period.update_xaxes(showgrid=False, tickangle=-45)
        fig_period.update_yaxes(showgrid=False, range=[0, 5000])

        st.plotly_chart(fig_period, use_container_width=True)

        # Early Islamic date distribution
        early_islamic_df = filtered_iran_df[filtered_iran_df["iran_period"] == "Early Islamic"]

        fig_early = px.histogram(
            early_islamic_df, x="begin_year",
            title="Distribution of Object Dating Start (Year) within the Early Islamic Period",
            labels={"begin_year": "Dating Start (Year)"}
        )

        fig_early.update_traces(marker_color="darkred")
        fig_early.update_layout(title_x=0, template="plotly_white")
        fig_early.update_xaxes(showgrid=False)
        fig_early.update_yaxes(showgrid=False, title_text="Number of Objects")

        st.plotly_chart(fig_early, use_container_width=True)

    with tab2:

        # Top object types
        top_objects = (
            filtered_iran_df.groupby("object_name")["object_id"]
            .count()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        fig_objects = px.bar(
            top_objects, x="object_name", y="object_id", text_auto=",.0f",
            title="Top 10 Object Types in the Iranian-Persian Dataset",
            labels={"object_name": "Object Type", "object_id": "Number of Objects"}
        )

        fig_objects.update_traces(marker_color="darkred", textposition="outside")
        fig_objects.update_layout(title_x=0, template="plotly_white")
        fig_objects.update_xaxes(showgrid=False, tickangle=-45)
        fig_objects.update_yaxes(showgrid=False, range=[0, 2500])

        st.plotly_chart(fig_objects, use_container_width=True)

        # Top classifications
        top_classifications = (
            filtered_iran_df.groupby("classification")["object_id"]
            .count()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        fig_classifications = px.bar(
            top_classifications, x="classification", y="object_id", text_auto=",.0f",
            title="Top 10 Classifications in the Iranian-Persian Dataset",
            labels={"classification": "Classification", "object_id": "Number of Objects"}
        )

        fig_classifications.update_traces(marker_color="darkred", textposition="outside")
        fig_classifications.update_layout(title_x=0, template="plotly_white")
        fig_classifications.update_xaxes(showgrid=False, tickangle=-45)
        fig_classifications.update_yaxes(showgrid=False, range=[0, 2000])

        st.plotly_chart(fig_classifications, use_container_width=True)

        # Early Islamic classifications
        early_islamic_classification = (
            filtered_iran_df[filtered_iran_df["iran_period"] == "Early Islamic"]
            .groupby("classification")["object_id"]
            .count()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )

        fig_early_classification = px.bar(
            early_islamic_classification, x="classification", y="object_id", text_auto=",.0f",
            title="Top 10 Classifications in the Early Islamic Period",
            labels={"classification": "Classification", "object_id": "Number of Objects"}
        )

        fig_early_classification.update_traces(marker_color="darkred", textposition="outside")
        fig_early_classification.update_layout(title_x=0, template="plotly_white")
        fig_early_classification.update_xaxes(showgrid=False, tickangle=-45)
        fig_early_classification.update_yaxes(showgrid=False, range=[0, 2000])

        st.plotly_chart(fig_early_classification, use_container_width=True)

    with tab3:

        # Acquisition types
        acquisition_df = (
            filtered_iran_df.groupby("acquisition_type")["object_id"]
            .count()
            .sort_values(ascending=False)
            .reset_index()
        )

        fig_acquisition_type = px.pie(acquisition_df, names="acquisition_type", values="object_id", title="Acquisition Types of Iranian-Persian Objects")
        fig_acquisition_type.update_traces(textinfo="percent+label")
        fig_acquisition_type.update_layout(title_x=0, template="plotly_white")

        st.plotly_chart(fig_acquisition_type, use_container_width=True)

        # Acquisition years
        acquisition_year_dashboard = filtered_iran_df[filtered_iran_df["acquisition_year"] != "unknown"].copy()
        acquisition_year_dashboard["acquisition_year"] = acquisition_year_dashboard["acquisition_year"].astype(int)

        fig_acquisition_hist = px.histogram(
            acquisition_year_dashboard, x="acquisition_year",
            title="Distribution of Acquisition Years",
            labels={"acquisition_year": "Acquisition Year"}
        )

        fig_acquisition_hist.update_traces(marker_color="darkred")
        fig_acquisition_hist.update_layout(title_x=0, template="plotly_white")
        fig_acquisition_hist.update_xaxes(showgrid=False)
        fig_acquisition_hist.update_yaxes(showgrid=False, title_text="Number of Objects")

        st.plotly_chart(fig_acquisition_hist, use_container_width=True)

        # Acquisitions by year
        acquisition_year_count = acquisition_year_dashboard.groupby("acquisition_year")["object_id"].count().reset_index()

        fig_acquisition_scatter = px.scatter(
            acquisition_year_count, x="acquisition_year", y="object_id", hover_data=["acquisition_year"],
            title="Number of Acquisitions by Year",
            labels={"acquisition_year": "Acquisition Year", "object_id": "Number of Objects"}
        )

        fig_acquisition_scatter.update_traces(marker_color="darkred", marker_size=8)
        fig_acquisition_scatter.update_layout(title_x=0, template="plotly_white")
        fig_acquisition_scatter.update_xaxes(showgrid=False)
        fig_acquisition_scatter.update_yaxes(showgrid=False)

        st.plotly_chart(fig_acquisition_scatter, use_container_width=True)

    with tab4:

        # Objects by department
        department_df = (
            filtered_iran_df.groupby("department")["object_id"]
            .count()
            .sort_values(ascending=False)
            .reset_index()
        )

        fig_department = px.bar(
            department_df, x="department", y="object_id", text_auto=",.0f",
            title="Iranian-Persian Objects by Department",
            labels={"department": "Department", "object_id": "Number of Objects"}
        )

        fig_department.update_traces(marker_color="darkred", textposition="outside")
        fig_department.update_layout(title_x=0, template="plotly_white")
        fig_department.update_xaxes(showgrid=False, tickangle=-45)
        fig_department.update_yaxes(showgrid=False, range=[0, 7000])

        st.plotly_chart(fig_department, use_container_width=True)

        # Historical periods by department (rows sorted explicitly, otherwise Plotly connects points out of order)
        department_period_df = (
            filtered_iran_df[filtered_iran_df["department"].isin(["Islamic Art", "Ancient Near Eastern Art"])]
            .groupby(["department", "iran_period"])["object_id"]
            .count()
            .reset_index()
        )

        department_period_df["iran_period"] = pd.Categorical(department_period_df["iran_period"], categories=ordered_periods, ordered=True)
        department_period_df = department_period_df.sort_values(["department", "iran_period"])

        fig_periods = px.line(
            department_period_df, x="iran_period", y="object_id", color="department", markers=True,
            title="Historical Periods by Department",
            labels={"iran_period": "Historical Period", "object_id": "Number of Objects", "department": "Department"}
        )

        fig_periods.update_layout(title_x=0, template="plotly_white")
        fig_periods.update_xaxes(categoryorder="array", categoryarray=ordered_periods, showgrid=False, tickangle=-45)
        fig_periods.update_yaxes(showgrid=False)

        st.plotly_chart(fig_periods, use_container_width=True)

        # Classifications by department
        major_departments_df = filtered_iran_df[filtered_iran_df["department"].isin(["Islamic Art", "Ancient Near Eastern Art"])].copy()
        top_10_classifications = major_departments_df["classification"].value_counts().head(10).index
        major_departments_df.loc[~major_departments_df["classification"].isin(top_10_classifications), "classification"] = "Other"

        department_classification_df = (
            major_departments_df
            .groupby(["department", "classification"])["object_id"]
            .count()
            .reset_index()
        )

        department_classification_df = department_classification_df.sort_values("classification")

        fig_classification_department = px.bar(
            department_classification_df, x="department", y="object_id", color="classification", barmode="stack",
            title="Classifications by Department",
            labels={"department": "Department", "object_id": "Number of Objects", "classification": "Classification"},
            category_orders={
                "department": ["Islamic Art", "Ancient Near Eastern Art", "Arms and Armor"],
                "classification": sorted(department_classification_df["classification"].unique())
            }
        )

        fig_classification_department.update_layout(title_x=0, template="plotly_white", bargap=0.10)
        fig_classification_department.update_xaxes(showgrid=False)
        fig_classification_department.update_yaxes(showgrid=False, range=[0, 6500])

        st.plotly_chart(fig_classification_department, use_container_width=True)

        # Acquisition years by department
        acquisition_department_df = filtered_iran_df[
            (filtered_iran_df["acquisition_year"] != "unknown")
            & (filtered_iran_df["department"].isin(["Islamic Art", "Ancient Near Eastern Art"]))
        ].copy()

        acquisition_department_df["acquisition_year"] = acquisition_department_df["acquisition_year"].astype(int)

        fig_acquisition_department = px.histogram(
            acquisition_department_df, x="acquisition_year", color="department", barmode="overlay", opacity=0.7,
            title="Distribution of Acquisition Years by Department",
            labels={"acquisition_year": "Acquisition Year", "department": "Department"}
        )

        fig_acquisition_department.update_layout(title_x=0, template="plotly_white")
        fig_acquisition_department.update_xaxes(showgrid=False)
        fig_acquisition_department.update_yaxes(showgrid=False, title_text="Number of Objects")

        st.plotly_chart(fig_acquisition_department, use_container_width=True)

elif page == "Object Explorer":

    st.title("🏛️ Iranian Cultural Heritage in the Metropolitan Museum of Art")
    st.header("Object Explorer")

    if st.sidebar.button("Reset Filters", key="oe_reset_btn"):
        st.session_state["oe_period"] = "All"
        st.session_state["oe_department"] = "All"
        st.session_state["oe_classification"] = "All"
        st.session_state["oe_city"] = []
        st.session_state["oe_culture"] = []
        st.session_state["oe_begin_year_range"] = (IRAN_MIN_YEAR, IRAN_MAX_YEAR)
        st.rerun()

    explorer_df = iran_df.copy()

    period_filter = st.sidebar.selectbox("Iran Period", ["All"] + sorted(iran_df["iran_period"].dropna().unique()), key="oe_period")
    department_filter = st.sidebar.selectbox("Department", ["All"] + sorted(iran_df["department"].dropna().unique()), key="oe_department")
    classification_filter = st.sidebar.selectbox("Classification", ["All"] + sorted(iran_df["classification"].dropna().unique()), key="oe_classification")
    city_filter = st.sidebar.multiselect("City", sorted(iran_df["city"].dropna().unique()), key="oe_city")
    culture_filter = st.sidebar.multiselect("Culture", sorted(iran_df["culture"].dropna().unique()), key="oe_culture")
    year_range = st.sidebar.slider("Dating Start (Year) Range", min_value=IRAN_MIN_YEAR, max_value=IRAN_MAX_YEAR, value=(IRAN_MIN_YEAR, IRAN_MAX_YEAR), key="oe_begin_year_range")

    if period_filter != "All":
        explorer_df = explorer_df[explorer_df["iran_period"] == period_filter]

    if department_filter != "All":
        explorer_df = explorer_df[explorer_df["department"] == department_filter]

    if classification_filter != "All":
        explorer_df = explorer_df[explorer_df["classification"] == classification_filter]

    if city_filter:
        explorer_df = explorer_df[explorer_df["city"].isin(city_filter)]

    if culture_filter:
        explorer_df = explorer_df[explorer_df["culture"].isin(culture_filter)]

    explorer_df = explorer_df[(explorer_df["begin_year"] >= year_range[0]) & (explorer_df["begin_year"] <= year_range[1])]

    if len(explorer_df) == 0:
        st.warning("No objects match the selected filters.")
        st.stop()

    object_id = st.selectbox("Object ID", sorted(explorer_df["object_id"].unique()))
    selected_object = explorer_df[explorer_df["object_id"] == object_id]
    selected_row = selected_object.iloc[0]
    selected_city = selected_row["city"]

    # Single API call, reused for Object Number, Met Catalogue Link and the object image
    api_object_id = selected_row["object_id"]
    api_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{api_object_id}"
    api_data = None

    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            api_data = response.json()
        else:
            st.error("Failed to retrieve object information from the MET API.")
    except Exception as error:
        st.error(f"API Error: {error}")

    col1, col2, col3 = st.columns([1, 2, 2])

    with col1:

        st.subheader("Object Details")
        st.write(f"Object ID: {selected_row['object_id']}")
        st.write(f"Title: {selected_row['title']}")
        st.write(f"Object Name: {selected_row['object_name']}")
        st.write(f"Period: {selected_row['iran_period']}")
        st.write(f"Classification: {selected_row['classification']}")
        st.write(f"Object Type: {selected_row['object_name']}")
        st.write(f"Department: {selected_row['department']}")

        if api_data:
            object_number = api_data.get("accessionNumber", "unknown")
            st.write(f"Object Number: {object_number}")

        st.write(f"City: {selected_row['city']}")
        st.write(f"Dating Start (Year): {selected_row['begin_year']}")
        st.write(f"Culture: {selected_row['culture']}")
        st.write(f"Dimension: {selected_row['dimensions']}")

        if api_data:
            object_url = api_data.get("objectURL", "")
            if object_url:
                st.markdown(f"[Met Catalogue Link]({object_url})")

    with col2:

        st.subheader("Object Image")

        if api_data:
            image_url = api_data.get("primaryImageSmall", "")
            if image_url:
                st.image(image_url, caption=selected_row["title"])
            else:
                st.warning("No image available for this object.")

    with col3:

        st.subheader("Geographic Context")

        if selected_city != "unknown" and pd.notna(selected_city) and " or " in selected_city:
            st.info(f"City is ambiguous ({selected_city}), so no single location can be shown.")
            show_unesco_only_map()

        elif selected_city != "unknown" and pd.notna(selected_city):

            city_coordinates = get_city_coordinates(selected_city)

            if city_coordinates:

                city_lat, city_lon = city_coordinates
                city_df = pd.DataFrame({"name": [selected_city], "lat": [city_lat], "lon": [city_lon], "site": ["Object Origin"]})
                map_df = pd.concat([unesco_df, city_df], ignore_index=True)

                fig_map = px.scatter_map(
                    map_df, lat="lat", lon="lon", color="site", hover_name="name", zoom=5,
                    center={"lat": city_lat, "lon": city_lon}, height=600,
                    color_discrete_map={"Object Origin": "darkred", "UNESCO World Heritage": "goldenrod"}
                )

                for trace in fig_map.data:
                    if trace.name == "Object Origin":
                        trace.marker.size = 14
                    elif trace.name == "UNESCO World Heritage":
                        trace.marker.size = 12

                fig_map.update_layout(map_style="open-street-map", legend_title_text="Location Site", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
                fig_map.update_traces(marker=dict(size=14))

                st.plotly_chart(fig_map, use_container_width=True)
                st.markdown(f"[Wikipedia article on {selected_city}](https://en.wikipedia.org/wiki/{selected_city.replace(' ', '_')})")

                with st.expander("UNESCO World Heritage Sites in Iran (Wikipedia links)"):
                    for _, site in unesco_df.drop_duplicates(subset="name").sort_values("name").iterrows():
                        st.markdown(f"- [{site['name']}]({site['wiki_url']})")

            else:
                st.info(f"No Wikidata coordinates found for {selected_city}.")

        else:
            st.info("No city available for this object.")
            show_unesco_only_map()

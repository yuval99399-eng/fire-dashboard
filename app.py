import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import reverse_geocoder as rg
import pycountry_convert as pc

# --- 1. Page Configuration ---
st.set_page_config(page_title="Yuval Fire Analytics", layout="wide", page_icon="🔥")

st.title("🔥 Yuval ft. Nasa Fire Analysis")
# Updated Subtitle: Tailored for security forces
st.markdown("Operational dashboard designed for global security forces: Real-time anomaly detection and strategic analysis.")

# --- 2. API Configuration ---
# ==========================================
# ⚠️ PASTE YOUR API KEY HERE
MAP_KEY = "a987e692baea378c29f7f6967f66b1cb" 
# ==========================================

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCE = "VIIRS_SNPP_NRT"
AREA = "world"
DAYS = "1"

# Continent areas (in million km²) for density calculation
CONTINENT_AREAS = {
    "Asia": 44.58, "Africa": 30.37, "North America": 24.71,
    "South America": 17.84, "Antarctica": 14.0, "Europe": 10.18, "Oceania": 8.52
}

def get_continent_name(country_code):
    """Helper function to convert country code to continent name using pycountry_convert"""
    try:
        continent_code = pc.country_alpha2_to_continent_code(country_code)
        continent_dict = {
            "NA": "North America", "SA": "South America", "AS": "Asia",
            "EU": "Europe", "AF": "Africa", "OC": "Oceania", "AN": "Antarctica"
        }
        return continent_dict.get(continent_code, "Other")
    except:
        return "Other"

@st.cache_data(ttl=600)
def load_data():
    """Fetch CSV data from NASA FIRMS API"""
    url = f"{BASE_URL}/{MAP_KEY}/{SOURCE}/{AREA}/{DAYS}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        return df
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def enrich_data(df):
    """Process raw data: Add risk scores and geolocation info"""
    if df.empty: return df
    
    # Calculate Threat Score
    confidence_map = {'l': 1.0, 'n': 1.2, 'h': 1.5}
    df['risk_factor'] = df['confidence'].map(confidence_map).fillna(1.0)
    df['threat_score'] = df['frp'] * df['risk_factor']
    
    # Reverse Geocoding (Coordinates -> Country Code)
    coordinates = list(zip(df['latitude'], df['longitude']))
    results = rg.search(coordinates)
    
    df['country_code'] = [x['cc'] for x in results]
    df['continent'] = df['country_code'].apply(get_continent_name)
    
    return df

# --- Data Loading & Processing ---
with st.spinner('Acquiring Satellite Data...'):
    raw_df = load_data()
    df = enrich_data(raw_df)

if not df.empty:
    # Time processing
    df['hour'] = df['acq_time'].apply(lambda x: int(f"{x:04d}"[:2]))
    df['hour_str'] = df['hour'].apply(lambda x: f"{x:02d}:00")
    
    # --- Sidebar Filters ---
    st.sidebar.header("🛠️ Mission Control Filters")
    min_hour, max_hour = st.sidebar.slider("Operation Time (UTC)", 0, 23, (0, 23))
    min_frp = st.sidebar.slider("Min Intensity (MW)", 0.0, float(df['frp'].max()), 0.0)
    
    available_continents = sorted(df['continent'].unique())
    selected_continents = st.sidebar.multiselect("Select Continents", available_continents, default=available_continents)
    
    # Apply Filters
    filtered_df = df[
        (df['frp'] >= min_frp) & (df['hour'] >= min_hour) & 
        (df['hour'] <= max_hour) & (df['continent'].isin(selected_continents))
    ]
    
    st.sidebar.markdown("---")
    st.sidebar.write(f"Targets Identified: **{len(filtered_df)}**")
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button("📥 Download Intel Report", data=csv, file_name="fire_intel_report.csv", mime="text/csv")

    # --- 1. Interactive Threat Table ---
    # Updated Header with the Equation
    st.subheader("🚨 Top 5 Critical Threats (Threat Score = FRP × Confidence Factor)")
    
    top_threats = filtered_df.sort_values('threat_score', ascending=False).head(5)
    
    # Interactive Table Configuration
    event = st.dataframe(
        top_threats[['latitude', 'longitude', 'continent', 'frp', 'confidence', 'threat_score']].style.background_gradient(subset=['threat_score'], cmap='Reds'),
        use_container_width=True,
        on_select="rerun",     
        selection_mode="single-row" 
    )

    # --- Map Zoom Logic ---
    # Default view: Global
    map_center = dict(lat=20, lon=0)
    map_zoom = 1

    # Check if a row is selected
    if len(event.selection.rows) > 0:
        selected_index = event.selection.rows[0]
        selected_row = top_threats.iloc[selected_index]
        
        # Update map focus to selected fire
        map_center = dict(lat=selected_row['latitude'], lon=selected_row['longitude'])
        map_zoom = 5 
        
        st.success(f"📍 Focusing on high-threat target in {selected_row['continent']} (Intensity: {selected_row['frp']} MW)")

    # --- 2. Heatmap ---
    st.subheader("🌍 Global Fire Density Heatmap")
    
    if not filtered_df.empty:
        fig_map = px.density_mapbox(
            filtered_df, 
            lat='latitude', 
            lon='longitude', 
            z='frp', 
            radius=10,
            center=map_center, # Dynamic center
            zoom=map_zoom,     # Dynamic zoom
            mapbox_style="carto-darkmatter",
            height=600
        )
        st.plotly_chart(fig_map, use_container_width=True)

    # --- 3. Statistical Analysis ---
    st.subheader("📊 Statistical Risk Analysis")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Total Fire Count by Continent**")
        cont_counts = filtered_df['continent'].value_counts().reset_index()
        cont_counts.columns = ['Continent', 'Count']
        fig_pie = px.pie(cont_counts, values='Count', names='Continent', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown("**🔥 Risk Density: Fires per 1 Million km²**")
        risk_data = []
        for continent in cont_counts['Continent']:
            count = cont_counts[cont_counts['Continent'] == continent]['Count'].values[0]
            area = CONTINENT_AREAS.get(continent, 1)
            density = count / area
            risk_data.append({'Continent': continent, 'Density': density})
        
        risk_df = pd.DataFrame(risk_data).sort_values('Density', ascending=False)
        fig_risk = px.bar(risk_df, x='Density', y='Continent', orientation='h', text_auto='.2f', color='Density', color_continuous_scale='Reds', labels={'Density': 'Fires per Million km²'})
        st.plotly_chart(fig_risk, use_container_width=True)

    # --- 4. Timeline ---
    st.subheader("🕒 Timeline Analysis")
    if not filtered_df.empty:
        hourly_counts = filtered_df['hour_str'].value_counts().reset_index().sort_values('hour_str')
        hourly_counts.columns = ['Hour', 'Count']
        fig_bar = px.bar(hourly_counts, x='Hour', y='Count', color='Count', color_continuous_scale='Oranges')
        st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.error("System Offline: Check API Key or Data Connection.")

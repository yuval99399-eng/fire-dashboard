import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import reverse_geocoder as rg
import pycountry_convert as pc

# --- 1. הגדרות עמוד ---
st.set_page_config(page_title="Yuval Fire Analytics", layout="wide", page_icon="🔥")

st.title("🔥 Yuval ft. Nasa Fire Analysis")
st.markdown("Advanced intelligence dashboard. **Tip:** Select a row in the table below to zoom into that location on the map.")

# --- 2. הגדרות API ---
# ==========================================
# ⚠️ שים כאן את המפתח שלך!
MAP_KEY = "PASTE_YOUR_KEY_HERE" 
# ==========================================

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCE = "VIIRS_SNPP_NRT"
AREA = "world"
DAYS = "1"

# שטחי יבשות (במיליוני קמ"ר)
CONTINENT_AREAS = {
    "Asia": 44.58, "Africa": 30.37, "North America": 24.71,
    "South America": 17.84, "Antarctica": 14.0, "Europe": 10.18, "Oceania": 8.52
}

def get_continent_name(country_code):
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
    if df.empty: return df
    
    confidence_map = {'l': 1.0, 'n': 1.2, 'h': 1.5}
    df['risk_factor'] = df['confidence'].map(confidence_map).fillna(1.0)
    df['threat_score'] = df['frp'] * df['risk_factor']
    
    coordinates = list(zip(df['latitude'], df['longitude']))
    results = rg.search(coordinates)
    
    df['country_code'] = [x['cc'] for x in results]
    df['continent'] = df['country_code'].apply(get_continent_name)
    
    return df

# --- טעינת נתונים ---
with st.spinner('Acquiring Satellite Data...'):
    raw_df = load_data()
    df = enrich_data(raw_df)

if not df.empty:
    df['hour'] = df['acq_time'].apply(lambda x: int(f"{x:04d}"[:2]))
    df['hour_str'] = df['hour'].apply(lambda x: f"{x:02d}:00")
    
    # --- פילטרים ---
    st.sidebar.header("🛠️ Mission Control Filters")
    min_hour, max_hour = st.sidebar.slider("Operation Time (UTC)", 0, 23, (0, 23))
    min_frp = st.sidebar.slider("Min Intensity (MW)", 0.0, float(df['frp'].max()), 0.0)
    
    available_continents = sorted(df['continent'].unique())
    selected_continents = st.sidebar.multiselect("Select Continents", available_continents, default=available_continents)
    
    filtered_df = df[
        (df['frp'] >= min_frp) & (df['hour'] >= min_hour) & 
        (df['hour'] <= max_hour) & (df['continent'].isin(selected_continents))
    ]
    
    st.sidebar.markdown("---")
    st.sidebar.write(f"Targets Identified: **{len(filtered_df)}**")
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button("📥 Download Intel Report", data=csv, file_name="fire_intel_report.csv", mime="text/csv")

    # --- 1. הטבלה האינטראקטיבית (הפיצ'ר החדש!) ---
    st.subheader("🚨 Top 5 Critical Threats (Select a row to Zoom)")
    
    top_threats = filtered_df.sort_values('threat_score', ascending=False).head(5)
    
    # הגדרת הטבלה עם אפשרות בחירה
    event = st.dataframe(
        top_threats[['latitude', 'longitude', 'continent', 'frp', 'confidence', 'threat_score']].style.background_gradient(subset=['threat_score'], cmap='Reds'),
        use_container_width=True,
        on_select="rerun",     # גורם לאפליקציה להתעדכן בלחיצה
        selection_mode="single-row" # מאפשר לבחור רק שורה אחת בכל פעם
    )

    # --- לוגיקה לזום במפה ---
    # ברירת מחדל: מבט גלובלי
    map_center = dict(lat=20, lon=0)
    map_zoom = 1

    # בדיקה אם המשתמש בחר שורה בטבלה
    if len(event.selection.rows) > 0:
        selected_index = event.selection.rows[0]
        # שליפת הנתונים של השורה שנבחרה
        selected_row = top_threats.iloc[selected_index]
        
        # עדכון מרכז המפה והזום
        map_center = dict(lat=selected_row['latitude'], lon=selected_row['longitude'])
        map_zoom = 5 # זום פנימה
        
        # הודעה למשתמש
        st.success(f"📍 Focusing on high-threat target in {selected_row['continent']} (Intensity: {selected_row['frp']} MW)")

    # --- 2. מפת החום (מגיבה לזום) ---
    st.subheader("🌍 Global Fire Density Heatmap")
    
    if not filtered_df.empty:
        fig_map = px.density_mapbox(
            filtered_df, 
            lat='latitude', 
            lon='longitude', 
            z='frp', 
            radius=10,
            center=map_center, # כאן נכנס הקואורדינטה (או הגלובלית או של השריפה שנבחרה)
            zoom=map_zoom,     # כאן נכנס הזום
            mapbox_style="carto-darkmatter",
            height=600
        )
        st.plotly_chart(fig_map, use_container_width=True)

    # --- 3. גרפים סטטיסטיים (חזרנו לגרסה הטובה) ---
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

    # --- 4. ציר זמן ---
    st.subheader("🕒 Timeline Analysis")
    if not filtered_df.empty:
        hourly_counts = filtered_df['hour_str'].value_counts().reset_index().sort_values('hour_str')
        hourly_counts.columns = ['Hour', 'Count']
        fig_bar = px.bar(hourly_counts, x='Hour', y='Count', color='Count', color_continuous_scale='Oranges')
        st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.error("System Offline: Check API Key or Data Connection.")

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import reverse_geocoder as rg # הספרייה החדשה לזיהוי מדינות

# --- 1. הגדרות עמוד ---
st.set_page_config(page_title="Yuval Fire Analytics", layout="wide", page_icon="🔥")

st.title("🔥 Yuval ft. Nasa Fire Analysis")
st.markdown("Advanced intelligence dashboard for monitoring global thermal anomalies.")

# --- 2. הגדרות API ---
# ==========================================
# אל תשכח להדביק את המפתח שלך כאן!
MAP_KEY = "a987e692baea378c29f7f6967f66b1cb" 
# ==========================================

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCE = "VIIRS_SNPP_NRT"
AREA = "world"
DAYS = "1"

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

# פונקציה לחישוב ציון סיכון וזיהוי מדינות
@st.cache_data(ttl=600)
def enrich_data(df):
    if df.empty: return df
    
    # 1. חישוב Threat Score
    # הנוסחה: עוצמה * פקטור ביטחון (Low=1, Nominal=1.2, High=1.5)
    confidence_map = {'l': 1.0, 'n': 1.2, 'h': 1.5}
    df['risk_factor'] = df['confidence'].map(confidence_map).fillna(1.0)
    df['threat_score'] = df['frp'] * df['risk_factor']
    
    # 2. זיהוי מדינות (Reverse Geocoding)
    coordinates = list(zip(df['latitude'], df['longitude']))
    results = rg.search(coordinates) # פעולה כבדה, לכן היא בתוך cache
    df['country_code'] = [x['cc'] for x in results]
    
    return df

# טעינת ועיבוד הנתונים
with st.spinner('Connecting to Satellite & Calculating Risk Scores...'):
    raw_df = load_data()
    df = enrich_data(raw_df)

if not df.empty:
    # הכנת נתוני זמן
    df['hour'] = df['acq_time'].apply(lambda x: int(f"{x:04d}"[:2]))
    df['hour_str'] = df['hour'].apply(lambda x: f"{x:02d}:00") # לגרף
    
    # --- 3. סרגל צד (Filters) ---
    st.sidebar.header("🛠️ Mission Control Filters")
    
    # פילטר שעות
    min_hour, max_hour = st.sidebar.slider("Operation Time (UTC)", 0, 23, (0, 23))
    
    # פילטר עוצמה
    min_frp = st.sidebar.slider("Min Intensity (MW)", 0.0, float(df['frp'].max()), 0.0)
    
    # פילטר מדינות (חדש!)
    all_countries = sorted(df['country_code'].unique())
    selected_countries = st.sidebar.multiselect("Select Countries", all_countries, default=all_countries)
    
    # ביצוע הסינון
    filtered_df = df[
        (df['frp'] >= min_frp) & 
        (df['hour'] >= min_hour) & 
        (df['hour'] <= max_hour) &
        (df['country_code'].isin(selected_countries))
    ]
    
    st.sidebar.markdown("---")
    st.sidebar.write(f"Targets Identified: **{len(filtered_df)}**")
    
    # כפתור הורדת דוח (רעיון מס' 4)
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        "📥 Download Intel Report",
        data=csv,
        file_name="fire_intel_report.csv",
        mime="text/csv"
    )

    # --- 4. טבלת איומים (רעיון מס' 1 - Threat Score) ---
    st.subheader("🚨 Top 5 Critical Threats")
    # מיון לפי הציון החדש שלנו
    top_threats = filtered_df.sort_values('threat_score', ascending=False).head(5)
    
    # יצירת טבלה יפה
    display_cols = ['latitude', 'longitude', 'country_code', 'frp', 'confidence', 'threat_score']
    st.dataframe(
        top_threats[display_cols].style.background_gradient(subset=['threat_score'], cmap='Reds'),
        use_container_width=True
    )

    # --- 5. מפה עם אנימציה (רעיון מס' 3) ---
    st.subheader("🌍 Time-Lapse Operation Map")
    st.markdown("Press the **Play** button below to visualize fire progression over the last 24h.")
    
    # אנחנו צריכים למיין את הדאטה לפי שעות כדי שהאנימציה תרוץ נכון
    anim_df = filtered_df.sort_values('hour')
    
    fig_map = px.scatter_mapbox(
        anim_df,
        lat="latitude", 
        lon="longitude",
        color="frp", 
        size="frp",
        hover_name="country_code",
        animation_frame="hour_str", # זה הקסם שיוצר את הנגן
        color_continuous_scale=px.colors.cyclical.IceFire,
        size_max=30, 
        zoom=1,
        mapbox_style="carto-darkmatter",
        title="Global Fire Progression"
    )
    st.plotly_chart(fig_map, use_container_width=True)

    # --- 6. ניתוח גיאוגרפי (רעיון מס' 2 - Pie Chart) ---
    col_graph1, col_graph2 = st.columns(2)
    
    with col_graph1:
        st.subheader("🏳️ Impact by Country")
        # סופרים כמה שריפות בכל מדינה
        country_counts = filtered_df['country_code'].value_counts().reset_index()
        country_counts.columns = ['Country', 'Count']
        
        # מציגים רק את הטופ 10 כדי שהגרף לא יתפוצץ
        top_countries = country_counts.head(10)
        
        fig_pie = px.pie(
            top_countries, 
            values='Count', 
            names='Country', 
            title='Top 10 Affected Countries',
            hole=0.4 # הופך את זה ל-Donut Chart מודרני
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_graph2:
        st.subheader("🕒 Timeline Analysis")
        # גרף השעות הרגיל והטוב
        hourly_counts = filtered_df['hour_str'].value_counts().reset_index().sort_values('hour_str')
        hourly_counts.columns = ['Hour', 'Count']
        
        fig_bar = px.bar(
            hourly_counts, x='Hour', y='Count',
            color='Count', color_continuous_scale='Oranges'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.error("System Offline: Check API Key or Data Connection.")

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import reverse_geocoder as rg

# --- 1. הגדרות עמוד ---
st.set_page_config(page_title="Yuval Fire Analytics", layout="wide", page_icon="🔥")

st.title("🔥 Yuval ft. Nasa Fire Analysis")
st.markdown("Advanced intelligence dashboard for monitoring global thermal anomalies.")

# --- 2. הגדרות API ---
# ==========================================
# אל תשכח להדביק את המפתח שלך כאן!
MAP_KEY = "PASTE_YOUR_KEY_HERE" 
# ==========================================

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCE = "VIIRS_SNPP_NRT"
AREA = "world"
DAYS = "1"

# מילון עזר להמרת קודי מדינות ליבשות (ללא צורך בספרייה חיצונית נוספת)
def get_continent(country_code):
    # מיפוי בסיסי ליבשות (חלקי אך מכסה את הרוב המוחלט של השריפות)
    continent_map = {
        'NA': 'North America', 'SA': 'South America', 'AS': 'Asia', 'EU': 'Europe', 'AF': 'Africa', 'OC': 'Oceania', 'AN': 'Antarctica'
    }
    # כאן אנו משתמשים בלוגיקה פשוטה יותר: המרת קוד מדינה ליבשת
    # הערה: זהו מיפוי ידני מקוצר לטובת הדגמה כדי למנוע התקנת ספריות נוספות
    # במערכת אמיתית היינו משתמשים ב-pycountry_convert
    
    # מיפוי אזורים נפוצים לשריפות
    if country_code in ['US', 'CA', 'MX']: return 'North America'
    if country_code in ['BR', 'AR', 'BO', 'PY', 'VE', 'CO', 'PE']: return 'South America'
    if country_code in ['AU', 'NZ']: return 'Oceania'
    if country_code in ['CN', 'IN', 'RU', 'ID', 'TH', 'VN', 'KZ']: return 'Asia'
    if country_code in ['CD', 'AO', 'ZM', 'ZA', 'MZ', 'NG', 'SS']: return 'Africa'
    if country_code in ['UA', 'FR', 'ES', 'IT', 'GR', 'PT']: return 'Europe'
    
    return 'Other / Unknown'

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
    
    # 1. חישוב Threat Score
    confidence_map = {'l': 1.0, 'n': 1.2, 'h': 1.5}
    df['risk_factor'] = df['confidence'].map(confidence_map).fillna(1.0)
    df['threat_score'] = df['frp'] * df['risk_factor']
    
    # 2. זיהוי מדינות ויבשות
    coordinates = list(zip(df['latitude'], df['longitude']))
    results = rg.search(coordinates)
    
    df['country_code'] = [x['cc'] for x in results]
    # שימוש בפונקציית העזר שלנו ליבשות
    df['continent'] = df['country_code'].apply(get_continent)
    
    return df

# טעינת ועיבוד הנתונים
with st.spinner('Connecting to Satellite & Calculating Risk Scores...'):
    raw_df = load_data()
    df = enrich_data(raw_df)

if not df.empty:
    # הכנת נתוני זמן
    df['hour'] = df['acq_time'].apply(lambda x: int(f"{x:04d}"[:2]))
    df['hour_str'] = df['hour'].apply(lambda x: f"{x:02d}:00")
    
    # --- 3. סרגל צד (Filters) ---
    st.sidebar.header("🛠️ Mission Control Filters")
    
    # פילטר שעות
    min_hour, max_hour = st.sidebar.slider("Operation Time (UTC)", 0, 23, (0, 23))
    
    # פילטר עוצמה
    min_frp = st.sidebar.slider("Min Intensity (MW)", 0.0, float(df['frp'].max()), 0.0)
    
    # פילטר יבשות (חדש!)
    # אנו אוספים את רשימת היבשות הקיימות בדאטה
    available_continents = sorted(df['continent'].unique())
    selected_continents = st.sidebar.multiselect(
        "Select Continents", 
        available_continents, 
        default=available_continents
    )
    
    # ביצוע הסינון
    filtered_df = df[
        (df['frp'] >= min_frp) & 
        (df['hour'] >= min_hour) & 
        (df['hour'] <= max_hour) &
        (df['continent'].isin(selected_continents))
    ]
    
    st.sidebar.markdown("---")
    st.sidebar.write(f"Targets Identified: **{len(filtered_df)}**")
    
    # כפתור הורדה
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        "📥 Download Intel Report",
        data=csv,
        file_name="fire_intel_report.csv",
        mime="text/csv"
    )

    # --- 4. טבלת איומים עם הנוסחה (רעיון מס' 1 מעודכן) ---
    st.subheader("🚨 Top 5 Critical Threats (Score = FRP × Confidence Factor)")
    
    top_threats = filtered_df.sort_values('threat_score', ascending=False).head(5)
    
    display_cols = ['latitude', 'longitude', 'continent', 'country_code', 'frp', 'confidence', 'threat_score']
    
    # שימוש ב-matplotlib לצביעת הטבלה (דורש את התיקון הקודם שעשינו ב-requirements)
    st.dataframe(
        top_threats[display_cols].style.background_gradient(subset=['threat_score'], cmap='Reds'),
        use_container_width=True
    )

    # --- 5. מפת חום (Heatmap) - חזרה למקור (רעיון מס' 3 מעודכן) ---
    st.subheader("🌍 Global Fire Density Heatmap")
    
    if not filtered_df.empty:
        fig_map = px.density_mapbox(
            filtered_df, 
            lat='latitude', 
            lon='longitude', 
            z='frp', 
            radius=10,
            center=dict(lat=20, lon=0), 
            zoom=1,
            mapbox_style="carto-darkmatter",
            height=600
        )
        st.plotly_chart(fig_map, use_container_width=True)

    # --- 6. ניתוח גיאוגרפי (עכשיו לפי יבשות) ---
    col_graph1, col_graph2 = st.columns(2)
    
    with col_graph1:
        st.subheader("🏳️ Impact by Continent")
        # גרף עוגה לפי יבשות
        cont_counts = filtered_df['continent'].value_counts().reset_index()
        cont_counts.columns = ['Continent', 'Count']
        
        fig_pie = px.pie(
            cont_counts, 
            values='Count', 
            names='Continent', 
            title='Fire Distribution by Region',
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.RdBu
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_graph2:
        st.subheader("🕒 Timeline Analysis")
        hourly_counts = filtered_df['hour_str'].value_counts().reset_index().sort_values('hour_str')
        hourly_counts.columns = ['Hour', 'Count']
        
        fig_bar = px.bar(
            hourly_counts, x='Hour', y='Count',
            color='Count', color_continuous_scale='Oranges'
        )
        st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.error("System Offline: Check API Key or Data Connection.")

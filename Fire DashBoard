import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# --- 1. הגדרות עמוד (Page Config) ---
# מגדיר את כותרת הדפדפן ופריסה רחבה (Wide Layout) כדי שיהיה נוח לדשבורד
st.set_page_config(page_title="Global Wildfire Dashboard", layout="wide")

# כותרת ראשית ותיאור
st.title("🔥 Global Wildfire Monitoring System")
st.markdown("Real-time analysis of fire hotspots detected by NASA VIIRS satellites.")

# --- 2. הגדרות API ---
# כאן עליך להכניס את המפתח שלך
MAP_KEY = "a987e692baea378c29f7f6967f66b1cb" 
BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
SOURCE = "VIIRS_SNPP_NRT"
AREA = "world"
DAYS = "1"

# --- 3. פונקציית טעינת נתונים (עם Cache) ---
# השימוש ב-cache_data קריטי: הוא מונע פנייה לנאס"א בכל פעם שאתה לוחץ על כפתור
# זה משפר ביצועים ומונע חסימה של ה-API
@st.cache_data(ttl=600) # שומר את המידע ל-10 דקות
def load_fire_data():
    url = f"{BASE_URL}/{MAP_KEY}/{SOURCE}/{AREA}/{DAYS}"
    try:
        response = requests.get(url)
        response.raise_for_status() # יזרוק שגיאה אם הבקשה נכשלה
        
        # קריאת ה-CSV מתוך הטקסט שחזר
        df = pd.read_csv(io.StringIO(response.text))
        return df
    except Exception as e:
        st.error(f"Error loading data from NASA: {e}")
        return pd.DataFrame()

# טעינת הנתונים בפועל
with st.spinner('Fetching latest satellite data...'):
    df = load_fire_data()

# --- 4. בניית הדשבורד ---
if not df.empty:
    
    # עיבוד מקדים: חילוץ השעה מתוך acq_time
    # המספר מגיע כ- integer (למשל 130 שזה 01:30, או 1450 שזה 14:50)
    # אנו ממירים למחרוזת, מוסיפים אפסים בהתחלה ולוקחים את השעתיים הראשונות
    df['hour_str'] = df['acq_time'].apply(lambda x: f"{x:04d}"[:2])
    
    # --- שורת מדדים (KPIs) ---
    # זה הופך את זה ל"דשבורד ניהולי" אמיתי
    st.markdown("### 📊 Key Metrics (Last 24h)")
    kpi1, kpi2, kpi3 = st.columns(3)
    
    total_fires = len(df)
    max_intensity = df['frp'].max()
    high_conf_fires = len(df[df['confidence'] == 'h'])

    kpi1.metric("Total Fires Detected", f"{total_fires:,}")
    kpi2.metric("Max Fire Intensity (FRP)", f"{max_intensity:.2f} MW")
    kpi3.metric("High Confidence Alerts", f"{high_conf_fires}")

    st.markdown("---")

    # --- ויזואליזציה 1: מפת העולם (סעיף i) ---
    st.subheader("🌍 Real-Time Fire Map")
    st.markdown("Geographic distribution of detected hotspots.")
    # הפקודה st.map מחפשת אוטומטית עמודות בשם lat/lon או latitude/longitude
    st.map(df, latitude='latitude', longitude='longitude', size=20, color='#ff4b4b')

    # --- ויזואליזציה 2: גרף שעות (סעיף ii) ---
    st.subheader("🕒 Fire Detections by Hour (UTC)")
    
    # קיבוץ הנתונים לפי שעה וספירה
    hourly_counts = df['hour_str'].value_counts().reset_index()
    hourly_counts.columns = ['Hour (UTC)', 'Count']
    hourly_counts = hourly_counts.sort_values('Hour (UTC)')

    # יצירת הגרף עם Plotly
    fig = px.bar(
        hourly_counts, 
        x='Hour (UTC)', 
        y='Count',
        color='Count',
        color_continuous_scale='Reds',
        labels={'Count': 'Number of Fires'}
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- הצגת נתונים גולמיים (אופציונלי) ---
    with st.expander("📂 View Raw Data"):
        st.dataframe(df)

else:
    st.warning("No data available. Please check your API Key.")

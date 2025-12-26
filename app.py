import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# --- 1. הגדרות עמוד ---
st.set_page_config(page_title="Yuval Fire Analytics", layout="wide", page_icon="🔥")

# כותרת ראשית כפי שביקשת
st.title("🔥 Yuval ft. Nasa Fire Analysis")
st.markdown("Real-time monitoring of global thermal anomalies.")

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

# טעינת הנתונים
with st.spinner('Fetching data from NASA satellites...'):
    df = load_data()

if not df.empty:
    # עיבוד זמן: יצירת עמודת 'שעה' כמספר שלם לטובת הסינון
    # acq_time מגיע כ- 130 (עבור 01:30) או 1400 (עבור 14:00)
    # אנו לוקחים את שתי הספרות הראשונות
    df['hour'] = df['acq_time'].apply(lambda x: int(f"{x:04d}"[:2]))
    df['hour_str'] = df['hour'].apply(lambda x: f"{x:02d}") # לגרף
    
    # --- 3. סרגל צד (Sidebar Filters) ---
    st.sidebar.header("🛠️ Filter Settings")
    
    # פילטר 1: טווח שעות (חדש!)
    min_hour, max_hour = st.sidebar.slider(
        "Filter by Hour (UTC)",
        min_value=0,
        max_value=23,
        value=(0, 23) # ברירת מחדל: כל היום
    )

    # פילטר 2: עוצמה
    min_frp = st.sidebar.slider(
        "Minimum Fire Intensity (MW)", 
        min_value=0.0, 
        max_value=float(df['frp'].max()), 
        value=0.0,
        step=0.5
    )
    
    # פילטר 3: יום/לילה
    day_night = st.sidebar.multiselect(
        "Time of Detection",
        options=['D', 'N'],
        default=['D', 'N'],
        format_func=lambda x: "Day" if x == 'D' else "Night"
    )
    
    # ביצוע הסינון בפועל (כולל שעות)
    filtered_df = df[
        (df['frp'] >= min_frp) & 
        (df['daynight'].isin(day_night)) &
        (df['hour'] >= min_hour) & 
        (df['hour'] <= max_hour)
    ]
    
    # הצגת סטטוס בצד
    st.sidebar.markdown("---")
    st.sidebar.write(f"Showing **{len(filtered_df)}** fires out of {len(df)}")

    # --- 4. מדדים (KPIs) ---
    # הורדנו את הממוצע, נשארנו עם 3 עמודות נקיות
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Active Fires", f"{len(filtered_df):,}")
    
    max_frp = filtered_df['frp'].max() if not filtered_df.empty else 0
    col2.metric("Max Intensity", f"{max_frp:.2f} MW")
    
    high_conf = len(filtered_df[filtered_df['confidence'] == 'h'])
    col3.metric("High Confidence Alerts", f"{high_conf}")

    st.markdown("---")

    # --- 5. המפה (Density Heatmap) ---
    st.subheader("🌍 Global Fire Density")
    
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
            height=600 # הגדלתי קצת את הגובה שיהיה מרשים
        )
        st.plotly_chart(fig_map, use_container_width=True)

    # --- 6. גרף השעות (עכשיו ברוחב מלא) ---
    st.subheader("🕒 Peak Fire Hours (UTC)")
    
    if not filtered_df.empty:
        hourly_counts = filtered_df['hour_str'].value_counts().reset_index().sort_values('hour_str')
        hourly_counts.columns = ['Hour', 'Count']
        
        fig_bar = px.bar(
            hourly_counts, 
            x='Hour', 
            y='Count',
            color='Count',
            color_continuous_scale='Oranges', # שיניתי לכתום שיתאים לאש
            text_auto=True # מציג את המספרים על העמודות
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # --- 7. טבלת נתונים ---
    with st.expander("📂 View Raw Data Table"):
        st.dataframe(filtered_df)

else:
    st.error("No data available. Check your API Key.")

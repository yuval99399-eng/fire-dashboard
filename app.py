import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# --- 1. הגדרות עמוד ועיצוב ---
st.set_page_config(page_title="Global Fire Dashboard", layout="wide", page_icon="🔥")

# כותרת ראשית
st.title("🔥 NASA VIIRS: Global Fire Analysis")
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
    # עיבוד זמן
    df['hour_str'] = df['acq_time'].apply(lambda x: f"{x:04d}"[:2])
    
    # --- 3. סרגל צד (Sidebar Filters) ---
    st.sidebar.header("🛠️ Filter Settings")
    
    # פילטר עוצמה
    min_frp = st.sidebar.slider(
        "Minimum Fire Intensity (MW)", 
        min_value=0.0, 
        max_value=float(df['frp'].max()), 
        value=0.0,
        step=0.5
    )
    
    # פילטר יום/לילה
    day_night = st.sidebar.multiselect(
        "Time of Detection",
        options=['D', 'N'],
        default=['D', 'N'],
        format_func=lambda x: "Day" if x == 'D' else "Night"
    )
    
    # ביצוע הסינון בפועל
    filtered_df = df[(df['frp'] >= min_frp) & (df['daynight'].isin(day_night))]
    
    # הצגת סטטוס בצד
    st.sidebar.markdown("---")
    st.sidebar.write(f"Showing **{len(filtered_df)}** fires out of {len(df)}")
    if len(filtered_df) == 0:
        st.warning("No fires match your filters!")

    # --- 4. מדדים (KPIs) ---
    # נותן תמונת מצב מהירה למנהל
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Fires", f"{len(filtered_df):,}")
    
    avg_frp = filtered_df['frp'].mean() if not filtered_df.empty else 0
    col2.metric("Avg. Intensity", f"{avg_frp:.2f} MW")
    
    max_frp = filtered_df['frp'].max() if not filtered_df.empty else 0
    col3.metric("Max Intensity", f"{max_frp:.2f} MW")
    
    high_conf = len(filtered_df[filtered_df['confidence'] == 'h'])
    col4.metric("High Confidence Alerts", f"{high_conf}")

    # --- 5. המפה החדשה: Density Heatmap ---
    st.subheader("🌍 Fire Density Heatmap")
    st.markdown("Darker areas indicate higher concentration of intense fires.")
    
    if not filtered_df.empty:
        fig_map = px.density_mapbox(
            filtered_df, 
            lat='latitude', 
            lon='longitude', 
            z='frp', # הצבע נקבע לפי עוצמת האש!
            radius=10,
            center=dict(lat=20, lon=0), 
            zoom=1,
            mapbox_style="carto-darkmatter", # עיצוב כהה ומקצועי
            title="Global Fire Intensity Heatmap"
        )
        st.plotly_chart(fig_map, use_container_width=True)

    # --- 6. הגרפים הנוספים ---
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.subheader("🔥 Intensity vs. Latitude")
        # גרף ה-Scatter שאהבת
        if not filtered_df.empty:
            fig_scatter = px.scatter(
                filtered_df, 
                x="latitude", 
                y="frp", 
                color="confidence",
                size="frp",
                hover_data=['longitude'],
                color_discrete_map={'l': 'yellow', 'n': 'orange', 'h': 'red'},
                labels={"frp": "Intensity (MW)", "latitude": "Latitude"}
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

    with row2_col2:
        st.subheader("🕒 Peak Fire Hours (UTC)")
        # גרף השעות (חובה לפי ההוראות)
        if not filtered_df.empty:
            hourly_counts = filtered_df['hour_str'].value_counts().reset_index().sort_values('hour_str')
            hourly_counts.columns = ['Hour', 'Count']
            
            fig_bar = px.bar(
                hourly_counts, 
                x='Hour', 
                y='Count',
                color='Count',
                color_continuous_scale='Reds'
            )
            st.plotly_chart(fig_bar, use_container_width=True)

    # --- 7. טבלת נתונים (מוסתרת) ---
    with st.expander("📂 View Raw Data Table"):
        st.dataframe(filtered_df)

else:
    st.error("No data available. Check your API Key or try again later.")

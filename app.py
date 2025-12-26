import streamlit as st
import pandas as pd
import plotly.express as px
import pydeck as pdk
import requests
import io

# --- 1. הגדרות עמוד ועיצוב ---
st.set_page_config(page_title="Advanced Wildfire Dashboard", layout="wide", page_icon="🔥")

# הוספת CSS מותאם אישית להעלמת שוליים מיותרים
st.markdown("""
<style>
    .reportview-container {
        margin-top: -2em;
    }
    .stDeployButton {display:none;}
    footer {visibility: hidden;}
    #stDecoration {display:none;}
</style>
""", unsafe_allow_html=True)

st.title("🔥 NASA VIIRS: Advanced Fire Analytics")
st.markdown("Interactive dashboard analyzing global thermal anomalies in real-time.")

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

# טעינת נתונים
with st.spinner('Connecting to NASA satellites...'):
    df = load_data()

if not df.empty:
    # עיבוד נתונים
    df['hour_str'] = df['acq_time'].apply(lambda x: f"{x:04d}"[:2])
    
    # --- 3. סרגל צד (Sidebar) לפילוח נתונים ---
    st.sidebar.header("🛠️ Filter Controls")
    
    # פילטר 1: עוצמת אש מינימלית
    min_frp = st.sidebar.slider("Minimum Fire Intensity (MW)", 
                                min_value=0.0, 
                                max_value=float(df['frp'].max()), 
                                value=0.0,
                                step=0.5)
    
    # פילטר 2: יום/לילה
    day_night_filter = st.sidebar.multiselect("Time of Detection", 
                                              options=['D', 'N'], 
                                              default=['D', 'N'],
                                              format_func=lambda x: "Day" if x == 'D' else "Night")
    
    # סינון הדאטה לפי הבחירה
    filtered_df = df[(df['frp'] >= min_frp) & (df['daynight'].isin(day_night_filter))]
    
    # הצגת כמות תוצאות אחרי סינון
    st.sidebar.markdown("---")
    st.sidebar.write(f"Showing **{len(filtered_df)}** fires out of {len(df)}")

    # --- 4. מדדים ראשיים (Top Level Metrics) ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Fires", f"{len(filtered_df):,}", delta_color="inverse")
    
    # חישוב ממוצע עוצמה
    avg_frp = filtered_df['frp'].mean() if not filtered_df.empty else 0
    col2.metric("Avg. Intensity", f"{avg_frp:.1f} MW")
    
    # השריפה הכי חזקה
    max_frp = filtered_df['frp'].max() if not filtered_df.empty else 0
    col3.metric("Max Intensity", f"{max_frp:.1f} MW")
    
    # אחוז ביטחון גבוה
    high_conf = len(filtered_df[filtered_df['confidence'] == 'h'])
    col4.metric("High Confidence", f"{high_conf}")

    # --- 5. מפה תלת-ממדית (The "Cool" Part) ---
    st.subheader("🌍 3D Density Map")
    st.markdown("Hexagon layer showing fire density. Taller columns = More fires in that area.")

    # הגדרת שכבת המפה
    layer = pdk.Layer(
        "HexagonLayer",
        filtered_df,
        get_position=["longitude", "latitude"],
        auto_highlight=True,
        elevation_scale=50,
        pickable=True,
        elevation_range=[0, 3000],
        extruded=True,
        coverage=1,
    )

    # הגדרת זווית המצלמה (View)
    view_state = pdk.ViewState(
        longitude=0,
        latitude=20,
        zoom=1.5,
        min_zoom=1,
        max_zoom=15,
        pitch=40.5, # זווית הטיה כדי שיראו תלת מימד
        bearing=0,
    )

    # הצגת המפה
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "Density: {elevationValue}"}
    ))

    # --- 6. גרפים מתקדמים ---
    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        st.subheader("🔥 Intensity vs. Latitude")
        # גרף שמראה איפה השריפות הכי חזקות (קו רוחב)
        fig_scatter = px.scatter(
            filtered_df, 
            x="latitude", 
            y="frp", 
            color="confidence",
            size="frp",
            hover_data=['longitude'],
            title="Fire Intensity Distribution by Latitude",
            labels={"frp": "Fire Radiative Power (MW)", "latitude": "Latitude"}
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with row2_col2:
        st.subheader("🕒 Peak Fire Hours")
        # גרף שעות משופר
        hourly_counts = filtered_df['hour_str'].value_counts().reset_index().sort_values('hour_str')
        hourly_counts.columns = ['Hour', 'Count']
        
        fig_bar = px.bar(
            hourly_counts, 
            x='Hour', 
            y='Count',
            color='Count',
            color_continuous_scale='Magma', # צבעי אש יפים יותר
            title="When do fires happen? (UTC Time)"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.error("No data available. Please check your API Key.")

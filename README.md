# This is the code for my Fire-dashboard

# I Hope (!!) you gonna like it and give me the job :) 

Key Assumptions & Design Philosophy

**1.** This dashboard was designed with First Responders and Security Forces in mind, serving as a tool for immediate situational awareness and rapid response. Consequently, the system prioritizes real-time data visualization over historical trends.

Alternative approach that as been considered was, A research-oriented tool aimed at long-term fire prevention would have focused differently emphasizing historical data analysis, seasonal trends, and predictive modeling for future forecasting.

**2.** It is important to clarify that the data points represent satellite detected thermal anomalies and not necessarily confirmed wildfires.

Users should be aware that "Active Fire" counts may include false positives such as industrial gas flaring, sun glint on water surfaces, or volcanic activity. The high volume of daily points reflects all heat sources detected by NASA sensors, rather than a confirmed count of catastrophic fire events.

**3.** Data Latency & Refresh Rate To support the critical need for up-to-date intelligence, the system is configured to fetch and update satellite data at **10-minute intervals**. This ensures that the operational view remains as current as possible within the limitations of satellite overpass times.

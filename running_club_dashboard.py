import streamlit as st
import pandas as pd
import altair as alt
import folium
from folium.plugins import HeatMap
from collections import defaultdict
import streamlit.components.v1 as components
import numpy as np
import os

# ------------------------
# CONFIG
# ------------------------

SHEET_NAME = "Arrowe Park ED Run Club"
CREDENTIALS_FILE = "runclubmapper-3e2cb58c2b12.json"

# ------------------------
# Mobile Mode Toggle
# ------------------------

st.sidebar.markdown("📱 **View Settings**")
mobile_mode = st.sidebar.checkbox("Enable Mobile Mode", value=False)

# ------------------------
# AUTH + LOAD DATA
# ------------------------

@st.cache_data
def load_sheets():
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
    client = gspread.authorize(creds)
    workbook = client.open(SHEET_NAME)

    meets_sheet = workbook.worksheet("Run Club Meets")
    values = meets_sheet.get_all_values()
    headers = values[0]
    data = values[1:]

    df_meets = pd.DataFrame(data, columns=headers)
    df_meets.rename(columns={
        headers[0]: "Week",
        headers[1]: "Date",
        headers[2]: "Runners",
        headers[3]: "Location",
        headers[4]: "Distance"
    }, inplace=True)

    df_meets = df_meets[df_meets['Date'].str.strip() != ""]
    df_meets['Date'] = df_meets['Date'].apply(lambda x: str(x).strip())
    df_meets['Date'] = pd.to_datetime(df_meets['Date'], errors='coerce', dayfirst=True)
    df_meets = df_meets.dropna(subset=['Date'])
    df_meets['RunnerList'] = df_meets['Runners'].apply(lambda x: [r.strip() for r in x.split(',') if r.strip()])
    df_meets['Distance'] = pd.to_numeric(df_meets['Distance'], errors='coerce')

    runners_sheet = workbook.worksheet("Runners")
    df_runners = pd.DataFrame(runners_sheet.get_all_records())
    df_runners['name'] = df_runners['name'].str.strip()

    return df_meets, df_runners

df, runners_df = load_sheets()

# ------------------------
# Postcode Cache
# ------------------------

@st.cache_data(show_spinner=False)
def load_or_update_postcode_cache(location_counts):
    import os
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter

    cache_path = "G:/My Drive/RunningClub/postcode_cache.csv"
    if os.path.exists(cache_path):
        postcode_cache = pd.read_csv(cache_path)
    else:
        postcode_cache = pd.DataFrame(columns=["Location", "lat", "lon"])

    known = set(postcode_cache['Location'])
    current = set(location_counts['Location'])
    missing = list(current - known)

    if missing:
        geolocator = Nominatim(user_agent="runclub-geocoder")
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
        new_rows = []
        for loc in missing:
            try:
                g = geocode(loc)
                if g:
                    new_rows.append({"Location": loc, "lat": g.latitude, "lon": g.longitude})
            except Exception:
                continue
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            postcode_cache = pd.concat([postcode_cache, new_df], ignore_index=True)
            postcode_cache.to_csv(cache_path, index=False)

    return postcode_cache

# ------------------------
# Runner Registry
# ------------------------

st.sidebar.header("🔍 Runner Registry")
runners_display = runners_df[['name', 'capnumber']].copy()

exploded = df.explode('RunnerList')
exploded['Runner'] = exploded['RunnerList'].str.strip()
run_counts = exploded['Runner'].value_counts()

# Assign milestone badges: numeric for 5/10, medals for 25/50/100
badges = []
for name in runners_display['name']:
    count = run_counts.get(name, 0)
    if count >= 100:
        badges.append("🏅")
    elif count >= 50:
        badges.append("🥈")
    elif count >= 25:
        badges.append("🥉")
    elif count >= 10:
        badges.append("🔟")
    elif count >= 5:
        badges.append("5️⃣")
    else:
        badges.append("")

runners_display['🎖️'] = badges

st.sidebar.dataframe(runners_display, hide_index=True, use_container_width=True)

st.sidebar.markdown("""
**🎖️ Badge Key**  
5️⃣ – 5+ runs  
🔟 – 10+ runs  
🥉 – 25+ runs  
🥈 – 50+ runs  
🏅 – 100+ runs
""")

# ------------------------
# Run Club Wrapped
# ------------------------

st.header("🎁 Run Club Wrapped")

# Celebrate newest runner once per session
if 'new_runner_welcomed' not in st.session_state:
    newest = runners_df.loc[runners_df['capnumber'].idxmax()]
    st.balloons()
    st.success(f"🎉 Welcome to our newest runner, {newest['name']}!")
    st.session_state['new_runner_welcomed'] = True

cap_input = st.text_input("Enter your capnumber:")
runner_name = None
if cap_input:
    try:
        cap_input = int(cap_input)
        match = runners_df[runners_df['capnumber'] == cap_input]
        if not match.empty:
            runner_name = match.iloc[0]['name'].strip()
            st.success(f"Found runner: {runner_name}")
        else:
            st.warning("Capnumber not found. Please try again.")
    except ValueError:
        st.warning("Capnumber must be a number.")

if runner_name:
    exploded = df.explode('RunnerList')
    exploded['Date'] = pd.to_datetime(exploded['Date'])
    exploded['Runner'] = exploded['RunnerList'].str.strip()
    runner_df = exploded[exploded['Runner'] == runner_name]
    if not runner_df.empty:
        total_runs = len(runner_df)
        unique_locations = runner_df['Location'].nunique()
        first_run = runner_df['Date'].min().strftime('%d/%m/%Y')
        last_run = runner_df['Date'].max().strftime('%d/%m/%Y')
        most_common_location = runner_df['Location'].value_counts().idxmax()
        total_km = round(runner_df['Distance'].sum(), 1)

        def longest_streak(dates):
            weeks = sorted(set(pd.to_datetime(dates).dt.isocalendar().week))
            streak = max_streak = 0
            prev_week = None
            for week in weeks:
                if prev_week is not None and week == prev_week + 1:
                    streak += 1
                else:
                    streak = 1
                max_streak = max(max_streak, streak)
                prev_week = week
            return max_streak

        streak = longest_streak(runner_df['Date'])

        st.markdown(f"## {'###' if mobile_mode else '##'} 👋 Well done, **{runner_name}**!")
        col1, col2 = st.columns(2) if not mobile_mode else (st.container(), st.container())

        with col1:
            st.markdown(f"""
            - 🏃‍♂️ **{total_runs}** runs completed  
            - 📍 **{unique_locations}** different locations  
            - 🔥 Longest streak: **{streak} runs**  
            """)

        with col2:
            st.markdown(f"""
            - 🛣️ Total **{total_km} km**  
            - 🏞️ Most runs at **{most_common_location}**  
            - 📅 First run: **{first_run}**  
            - 📅 Last run: **{last_run}**
            """)

        runs_over_time = runner_df.groupby(runner_df['Date'].dt.to_period("M")).size().to_frame('Runs')
        runs_over_time.index = runs_over_time.index.to_timestamp()
        st.markdown("### 📈 Monthly Activity")
        chart_data = runs_over_time.copy()
        chart_data.index = pd.to_datetime(chart_data.index)
        st.line_chart(chart_data, use_container_width=mobile_mode)

        st.markdown("### 📅 Detected Run Dates")
        formatted_dates = runner_df[['Date', 'Location']].copy()
        formatted_dates = formatted_dates.sort_values('Date').reset_index(drop=True)
        formatted_dates.index += 1
        formatted_dates['Date'] = formatted_dates['Date'].dt.strftime('%d/%m/%Y')
        st.write(formatted_dates)

        monthly_counts = runs_over_time['Runs'].to_string()
        summary_text = f"""
Runner Unwrapped for {runner_name}

🏃‍♂️ Total runs: {total_runs}
📍 Unique locations: {unique_locations}
🔥 Longest streak: {streak} consecutive runs
🛣️ Total distance: {total_km} km
🏞️ Most common location: {most_common_location}
📅 First run: {first_run}
📅 Last run: {last_run}

📈 Runs per month:
{monthly_counts}
"""
        st.download_button(
            label="📥 Download My Stats",
            data=summary_text,
            file_name=f"{runner_name}_wrapped.txt",
            mime="text/plain"
        )

# ------------------------
# Club Totals + Heatmap + Leaderboard
# ------------------------

total_club_km = df.apply(lambda row: len(row['RunnerList']) * row['Distance'], axis=1).sum()
st.subheader("📊 Total Distance Run by the Club")
st.metric(label="", value=f"{round(total_club_km, 1)} km")

st.subheader("📍 Run Location Heatmap")
location_counts = df.groupby('Location').size().reset_index(name='count')
location_map = folium.Map(location=[53.38, -3.07], zoom_start=10)

postcode_cache = load_or_update_postcode_cache(location_counts)
location_counts = location_counts.merge(postcode_cache, on="Location", how="left")
location_counts = location_counts.dropna(subset=['lat', 'lon'])
location_counts['weight'] = location_counts['count'].apply(lambda x: np.log1p(x))
heat_data = location_counts[['lat', 'lon', 'weight']].values.tolist()
HeatMap(heat_data).add_to(location_map)

components.html(location_map._repr_html_(), height=500)

st.subheader("🏅 Most Frequent Attenders")
filtered = exploded['Runner'].value_counts().reset_index()
filtered.columns = ['Runner', 'Count']
filtered = filtered[filtered['Count'] >= 3]
chart = alt.Chart(filtered).mark_bar().encode(
    x=alt.X('Runner', sort='-y'),
    y='Count',
    tooltip=['Runner', 'Count']
).properties(height=400)

st.altair_chart(chart, use_container_width=True)


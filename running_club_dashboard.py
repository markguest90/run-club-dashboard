
import streamlit as st
import pandas as pd
import altair as alt
import folium
from folium.plugins import HeatMap
from collections import defaultdict
import streamlit.components.v1 as components
components.html(
    """<meta name="robots" contents="noindex">""",
    height=0
)
import numpy as np
import os
#st.write("Files in app directory:", os.listdir())
import json
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from datetime import datetime

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
secrets = st.secrets["google_sheets"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(secrets), scope)

# ------------------------
# CONFIG
# ------------------------

SHEET_NAME = "Arrowe Park ED Run Club"

# ------------------------
# Mobile Mode Toggle
# ------------------------

#st.sidebar.markdown("📱 **View Settings**")
#mobile_mode = st.sidebar.checkbox("Enable Mobile Mode", value=False)

# ------------------------
# STREAK FUNCTIONS (moved up to support Wrapped)
# ------------------------

def longest_streak_by_week(weeks):
    # Floor all week values and remove nulls
    normalized = sorted(set(int(np.floor(w)) for w in weeks if pd.notnull(w)))
    if not normalized:
        return 0

    streak = max_streak = 1
    for i in range(1, len(normalized)):
        if normalized[i] == normalized[i - 1] + 1:
            streak += 1
        else:
            streak = 1
        max_streak = max(max_streak, streak)
    return max_streak

def current_streak_by_week(weeks, all_weeks):
    runner_weeks = set(int(np.floor(w)) for w in weeks if pd.notnull(w))
    all_weeks = sorted(set(int(np.floor(w)) for w in all_weeks if pd.notnull(w)))

    if not runner_weeks or not all_weeks:
        return 0

    streak = 0
    for week in reversed(all_weeks):
        if week in runner_weeks:
            streak += 1
        else:
            break  # first missed week ends the streak

    return streak

# ------------------------
# AUTH + LOAD DATA
# ------------------------

@st.cache_data
def load_sheets():
    import gspread
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
    df_meets['Week'] = pd.to_numeric(df_meets['Week'], errors='coerce')

    runners_sheet = workbook.worksheet("Runners")
    df_runners = pd.DataFrame(runners_sheet.get_all_records())
    df_runners['name'] = df_runners['name'].str.strip()

    return df_meets, df_runners

df, runners_df = load_sheets()
exploded = df.explode('RunnerList')
exploded['Runner'] = exploded['RunnerList'].str.strip()

# ------------------------
# Dashboard Title - 4 variants
# ------------------------
#st.markdown("""
#<div style='text-align: center;'>
#    <h1 style='font-size: 2.8em;'>Run Club 🏃‍♂️Dashboard🏃‍♀️</h1>
#    <p style='font-size: 1.2em; color: gray;'>Celebrate your achievements, track your streaks, and explore your run club stats!</p>
#</div>
#""", unsafe_allow_html=True)

# ---------------------
# Refresh option
# ---------------------


# Create a 3-column layout and place the button in the rightmost column
col1, col2, col3 = st.columns([8, 1, 1])
with col3:
    if st.button("🔄", help="Click to reload Google Sheet"):
        st.cache_data.clear()
        st.rerun()

st.markdown(
    """
    <div style='text-align: center; padding: 1rem; background-color: #f0f8ff; border-radius: 10px;'>
        <h1 style='margin-bottom: 0.5rem;'>Run Club 🏃‍♂️Dashboard🏃‍♀️</h1>
    </div>
    """,
    unsafe_allow_html=True)

#st.markdown("""
# <div style='text-align: center; background-color: #f0f8ff; padding: 1em; border-radius: 12px;'>
#    <h1 style='font-size: 2.5em; letter-spacing: 0.03em; margin-bottom: 0.2em;'>Arrowe Park ED Run Club</h1>
#    <h1 style='font-size: 2.5em; letter-spacing: 0.03em; margin-top: 0;'> 
#        <span style='font-size: 0.9em;'>🏃‍♀️</span> Dashboard <span style='font-size: 0.9em;'>🏃‍♂️</span>
#    </h1>
#</div>
#""", unsafe_allow_html=True)

#st.markdown(
#    """
#    <h1 style='
#        text-align: center;
#        background: linear-gradient(90deg, #4CAF50, #2196F3);
#        -webkit-background-clip: text;
#        -webkit-text-fill-color: transparent;
#        font-weight: bold;
#    '>
#        Arrowe Park ED Run Club 🏃‍♂️Dashboard🏃‍♀️
#    </h1>
#    """,
#    unsafe_allow_html=True)

#st.markdown(
#    """
#    <h1 style='
#        text-align: center;
#        color: #333;
#        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
#    '>
#    Run Club 🏃‍♂️Dashboard🏃‍♀️
#    </h1>
#    """,
#    unsafe_allow_html=True
#)


# ------------------------
# Mobile Sidebar Tip for Runner Registry
# ------------------------
st.markdown("""
<style>
@keyframes pulseFade {
  0% { opacity: 0; transform: scale(0.95); }
  10% { opacity: 1; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.02); }
  90% { opacity: 1; transform: scale(1); }
  100% { opacity: 0; transform: scale(0.95); }
}

.mobile-tip {
  animation: pulseFade 5s ease-in-out forwards;
}
</style>

<div class="mobile-tip">
  <div style="padding:10px; background:#EFEAFF; border-radius:5px; text-align:center; font-size: 1.05em;">
    Tap ❯❯ top left to open the Runner Registry and find your capnumber!
  </div>
</div>
""", unsafe_allow_html=True)


# ------------------------
# Runner Registry with Badges
# ------------------------

st.sidebar.header("🔍 Runner Registry")
runners_display = runners_df[['name', 'capnumber']].copy()

run_counts = exploded['Runner'].value_counts()
badges = []
for name in runners_display['name']:
    count = run_counts.get(name, 0)
    if count >= 100:
        badges.append("🏅")
    elif count >= 50:
        badges.append("🥈")
    elif count >= 25:
        badges.append("🥉")
    elif count >= 20:
        badges.append("🚀")
    elif count >= 15:
        badges.append("⚡")
    elif count >= 10:
        badges.append("🔟")
    elif count >= 5:
        badges.append("5️⃣")
    else:
        badges.append("")

runners_display['🎖️'] = badges
st.sidebar.dataframe(runners_display, hide_index=True, use_container_width=True)

st.sidebar.markdown("""
5️⃣ – 5+ runs  
🔟 – 10+ runs  
⚡ – 15+ runs  
🚀 – 20+ runs  
🥉 – 25+ runs  
🥈 – 50+ runs  
🏅 – 100+ runs
""")


# ------------------------
# 🎁 Run Club Wrapped
# ------------------------

if 'new_runner_welcomed' not in st.session_state:
    newest = runners_df.loc[runners_df['capnumber'].idxmax()]
    st.balloons()
    st.success(f"🎉 Welcome to our newest runner, {newest['name']}!")
    st.session_state['new_runner_welcomed'] = True

runner_df = pd.DataFrame()
runner_name = None

st.header("🎁 Run Club Wrapped")
# ------------------------

cap_input = st.text_input("Enter your capnumber:")
runner_df = pd.DataFrame()
runner_name = None

if cap_input:
    try:
        cap_input = int(cap_input)
        match = runners_df[runners_df['capnumber'] == cap_input]
        if not match.empty:
            runner_name = match.iloc[0]['name'].strip()
            runner_df = exploded[exploded['Runner'] == runner_name]
            st.success(f"Found runner: {runner_name}")

            # 🎁 Run Club Wrapped now renders reliably
            total_runs = len(runner_df)
            unique_locations = runner_df['Location'].nunique()
            first_run = runner_df['Date'].min()
            last_run = runner_df['Date'].max()
            most_common_location = runner_df['Location'].value_counts().idxmax()
            total_km = round(runner_df['Distance'].sum(), 1)

            runner_weeks = runner_df['Week']
            longest_runner_streak = longest_streak_by_week(runner_weeks)

            first_run_fmt = first_run.strftime('%d/%m/%Y')
            last_run_fmt = last_run.strftime('%d/%m/%Y')

            st.markdown(f"## 👋 Well done, **{runner_name}**!")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"""
                - 🏃‍♂️ **{total_runs}** runs completed  
                - 📍 **{unique_locations}** different locations  
                - 🔥 Longest streak: **{longest_runner_streak} weeks**  
                """)

            with col2:
                st.markdown(f"""
                - 🛣️ Total **{total_km} km**  
                - 🏞️ Most runs at **{most_common_location}**  
                - 📅 First run: **{first_run_fmt}**  
                - 📅 Last run: **{last_run_fmt}**
                """)

            # Monthly Activity chart
            runs_over_time = runner_df.groupby(runner_df['Date'].dt.to_period("M")).size().to_frame('Runs')
            runs_over_time.index = runs_over_time.index.to_timestamp()

            st.markdown("### 📈 Monthly Activity")


            # Recalculate and format chart data
            chart_data = runs_over_time.copy()
            chart_data = chart_data.sort_index()  # ensure datetime order
            chart_data['Month'] = chart_data.index.strftime('%b %Y')

            # Create an ordered categorical type to ensure proper ordering
            chart_data['Month'] = pd.Categorical(
                chart_data['Month'],
                categories=chart_data['Month'].tolist(),
                ordered=True
            )

            # Plot with Altair to control the x-axis
            chart = alt.Chart(chart_data.reset_index()).mark_line(point=True).encode(
                x=alt.X('Month:N', sort=list(chart_data['Month'].unique())),
                y='Runs:Q',
                tooltip=['Month', 'Runs']
            )

            st.altair_chart(chart, use_container_width=True)



            # Detected Run Dates
            #st.markdown("### 📅 Detected Run Dates")
            #formatted_dates = runner_df[['Date', 'Location']].copy()
            #formatted_dates = formatted_dates.sort_values('Date').reset_index(drop=True)
            #formatted_dates.index += 1
            #formatted_dates['Date'] = formatted_dates['Date'].dt.strftime('%d/%m/%Y')
            #st.write(formatted_dates)

            # Downloadable Summary
            monthly_counts = runs_over_time.copy()
            monthly_counts.index = monthly_counts.index.strftime('%m-%Y')
            monthly_counts_text = monthly_counts.to_string()

            summary_text = f"""
Runner Unwrapped for {runner_name}

🏃‍♂️ Total runs: {total_runs}
📍 Unique locations: {unique_locations}
🔥 Longest streak: {longest_runner_streak} consecutive weeks
🛣️ Total distance: {total_km} km
🏞️ Most common location: {most_common_location}
📅 First run: {first_run_fmt}
📅 Last run: {last_run_fmt}

📈 Runs per month:
{monthly_counts_text}
"""

            st.download_button(
                label="📥 Download My Stats",
                data=summary_text,
                file_name=f"{runner_name}_wrapped.txt",
                mime="text/plain"
            )

        else:
                 st.warning("capnumber not found")
    except ValueError:
        st.warning("capnumber must be a number")

# --- 👶 Run Club Baby Count ---
expected_cols = ["Week #", "Run Club Baby Count"]
missing = [c for c in expected_cols if c not in df.columns]

if missing:
    st.error(f"Missing expected columns: {missing}. Found: {list(df.columns)}")

else:
    st.subheader("👶 Run Club Baby Count!")

    # Get only week + baby columns, drop blanks
    baby_df = df[expected_cols].dropna()

    if baby_df.empty:
        st.info("No baby announcements yet — watch this space! 🍼✨")
    else:
        # Sort newest week first
        baby_df = baby_df.sort_values("Week #", ascending=False)

        # Headline tally
        total_babies = len(baby_df)
        baby_word = "Baby" if total_babies == 1 else "Babies"
        st.markdown(f"**Total Run Club {baby_word} so far: {total_babies} 👶**")

        # Load runners sheet
        runners_df = pd.DataFrame(sh.worksheet("Runners").get_all_records())

        # Pastel card styling (inject once)
        st.markdown(
            """
            <style>
                .baby-box {
                    background-color: #fdf6f0; /* pastel peach */
                    padding: 12px;
                    border-radius: 10px;
                    margin-bottom: 8px;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        import re
        for _, row in baby_df.iterrows():
            entry = str(row["Run Club Baby Count"])
            week = int(row["Week #"])

            # Extract parent capnumbers inside (capX+capY)
            caps = re.findall(r"cap\\d+", entry)
            parents = []
            for cap in caps:
                match = runners_df[runners_df["capnumber"].astype(str) == cap.replace("cap", "")]
                if not match.empty:
                    parents.append(f"**{match.iloc[0]['name']}**")

            # Baby name = text before '('
            baby_name = entry.split("(")[0].strip()

            if len(parents) == 2:
                st.markdown(
                    f"<div class='baby-box'>🎉 👶 <b>{baby_name}</b> joined the Run Club family in "
                    f"<b>Week {week}</b>, congratulations to {parents[0]} & {parents[1]}! 🎉</div>",
                    unsafe_allow_html=True
                )
            elif len(parents) == 1:
                st.markdown(
                    f"<div class='baby-box'>🎉 👶 <b>{baby_name}</b> joined the Run Club family in "
                    f"<b>Week {week}</b>, congratulations to {parents[0]}! 🎉</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div class='baby-box'>🎉 👶 <b>{baby_name}</b> joined the Run Club family in "
                    f"<b>Week {week}</b>! 🎉</div>",
                    unsafe_allow_html=True
                )



# ------------------------
# Club Totals + Heatmap + Leaderboard
# ------------------------

total_club_km = df.apply(lambda row: len(row['RunnerList']) * row['Distance'], axis=1).sum()
st.subheader("📊 Total Distance Run by the Club")
st.metric(label="Total Distance", value=f"{round(total_club_km, 1)} km", label_visibility="collapsed")

# ------------------------
# 🏆 Latest Awards
# ------------------------

st.subheader("🏆 Latest Milestones")

# Define milestones and corresponding badge emojis
milestones = {5: "5️⃣", 10: "🔟", 15: "⚡", 20: "🚀", 25: "🥉", 50: "🥈", 100: "🏅"}

# Gather all run dates per runner, sorted
runner_run_dates = exploded[['Runner', 'Date']].dropna().sort_values(['Runner', 'Date'])

# Record when each runner hit each milestone
milestone_events = []

for runner in runner_run_dates['Runner'].unique():
    dates = runner_run_dates[runner_run_dates['Runner'] == runner].sort_values('Date')['Date'].reset_index(drop=True)
    for milestone in milestones:
        if len(dates) >= milestone:
            milestone_events.append({
                "Runner": runner,
                "Runs": milestone,
                "Date": dates.iloc[milestone - 1],
                "Badge": milestones[milestone]
            })

# Convert and display the last 3 awards
awards_df = pd.DataFrame(milestone_events)
awards_df = awards_df.sort_values("Date", ascending=False).head(3)

if not awards_df.empty:
    for _, row in awards_df.iterrows():
        st.success(f"{row['Badge']} **{row['Runner']}** reached **{row['Runs']} runs** on **{row['Date'].strftime('%d/%m/%Y!')}**")
else:
    st.info("No awards to show yet.")

# ------------------------
# Load or update locations cache via Google Sheet
# ------------------------

@st.cache_data(show_spinner=False)
def load_or_update_locations_cache(location_counts):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["google_sheets"]), scope)
    client = gspread.authorize(creds)

    # Open the cache sheet
    sheet = client.open("locations_cache").sheet1
    existing_data = sheet.get_all_records()
    locations_cache = pd.DataFrame(existing_data)

    known = set(locations_cache['Location'])
    current = set(location_counts['Location'])
    missing = list(current - known)

    if datetime.today().weekday() in [4,5,6]:  # Updates on Fridays/Sat/Sun onlys or change to in [3, 4]:
        if missing:
            geolocator = Nominatim(user_agent="runclub-geocoder")
            geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
            new_rows = []
            for loc in missing:
                try:
                    g = geocode(loc)
                    if g:
                        new_rows.append({"Location": loc, "lat": g.latitude, "lon": g.longitude})
                        sheet.append_row([loc, g.latitude, g.longitude])
                except Exception:
                    continue
            if new_rows:
                new_df = pd.DataFrame(new_rows)
                locations_cache = pd.concat([locations_cache, new_df], ignore_index=True)

    return locations_cache

# ------------------------
# Run Location Heatmap Display
# ------------------------

st.subheader("🗺️ Run Location Heatmap")

location_counts = df.groupby('Location').size().reset_index(name='count')
locations_cache = load_or_update_locations_cache(location_counts)
location_counts = location_counts.merge(locations_cache, on="Location", how="left")
location_counts = location_counts.dropna(subset=['lat', 'lon'])

location_counts['weight'] = location_counts['count'].apply(lambda x: np.log1p(x))
heat_data = location_counts[['lat', 'lon', 'weight']].values.tolist()

location_map = folium.Map(location=[53.37, -3.04], zoom_start=9.5)
HeatMap(heat_data).add_to(location_map)
components.html(location_map._repr_html_(), height=350)

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

# ------------------------
# Streaks (All-Time and Current based on Week)
# ------------------------

# ------------------------
# Display Current/All-time Streak Table
# ------------------------

st.subheader("🔥 Streaks")
streak_mode = st.radio("Select", ["Current", "All-time"], horizontal=True, label_visibility="collapsed")

streak_data = []
all_weeks = df['Week'].unique()

for runner in exploded['Runner'].unique():
    weeks = exploded[exploded['Runner'] == runner]['Week']
    if streak_mode == "Current":
        streak = current_streak_by_week(weeks, all_weeks)
        label = "Current Streak"
        if streak >= 2:
            streak_data.append((runner, streak))
    else:
        streak = longest_streak_by_week(weeks)
        label = "Longest Streak"
        if streak >= 3:
            streak_data.append((runner, streak))

streak_df = pd.DataFrame(streak_data, columns=['Runner', label]).sort_values(by=label, ascending=False).reset_index(drop=True)
# Show 4+ week streak popup for top runner in current mode
if streak_mode == "Current" and not streak_df.empty:
    top_runner = streak_df.iloc[0]
    if top_runner[label] >= 4:
        st.success(f"🔥 {top_runner['Runner']} is on a {top_runner[label]}-week streak!")

if not streak_df.empty:
    st.dataframe(streak_df, hide_index=True, use_container_width=True)
else:
    st.info("No streaks to display.")

# def make_sparkline(weeks, weeks_range):   ### TICKS AND CROSSES STREAK IDEA
  #  attended = set(int(np.floor(w)) for w in weeks if pd.notnull(w))
  #  return ''.join(['✅' if w in attended else '❌' for w in weeks_range])

# Get full range of integer weeks and slice last 6
# all_weeks_full = sorted(set(int(np.floor(w)) for w in all_weeks if pd.notnull(w)))
# all_weeks_range = all_weeks_full[-6:] if len(all_weeks_full) >= 6 else all_weeks_full

# streak_data = []
# for runner in exploded['Runner'].unique():
   # weeks = exploded[exploded['Runner'] == runner]['Week']
   # spark = make_sparkline(weeks, all_weeks_range)

   # if streak_mode == "Current":
   #     streak = current_streak_by_week(weeks, all_weeks)
   #     label = "Current Streak"
   #     if streak >= 2:
#        streak_data.append((runner, streak, spark))
 #   else:
  #      streak = longest_streak_by_week(weeks)
   #     label = "Longest Streak"
    #    if streak >= 3:
     #       streak_data.append((runner, streak, spark))
#
## Display streaks + sparkline
#columns = ['Runner', label, 'Last 6 Weeks']
#streak_df = pd.DataFrame(streak_data, columns=columns).sort_values(by=label, ascending=False).reset_index(drop=True)
#if not streak_df.empty:
 #   st.dataframe(streak_df, hide_index=True, use_container_width=True)
#else:
 #   st.info("No streaks to display.")


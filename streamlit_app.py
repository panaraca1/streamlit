# app.py
import streamlit as st
import json
from datetime import datetime, timedelta, date
import random
import os
import calendar

# --- CONFIGURATION & INITIALIZATION ---
st.set_page_config(
    page_title="Momentum - Habit Tracker",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="auto",
)

# Use a local JSON file for session state persistence
STATE_FILE = "state.json"

# --- STATE MANAGEMENT ---

def save_state(state):
    """Saves the entire state dictionary to a JSON file."""
    # Convert date objects to ISO strings for JSON serialization
    serializable_state = state.copy()
    serializable_state['habits'] = []
    for habit in state['habits']:
        h_copy = habit.copy()
        h_copy['creationDate'] = h_copy['creationDate'].isoformat() if isinstance(h_copy['creationDate'], date) else h_copy['creationDate']
        h_copy['completions'] = [c.isoformat() if isinstance(c, date) else c for c in h_copy['completions']]
        serializable_state['habits'].append(h_copy)
    
    with open(STATE_FILE, "w") as f:
        json.dump(serializable_state, f, indent=4)

def load_state():
    """Loads the state from a JSON file, or returns a default state."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                state = json.load(f)
                # Convert ISO strings back to date objects
                for habit in state['habits']:
                    habit['creationDate'] = datetime.fromisoformat(habit['creationDate']).date()
                    habit['completions'] = [datetime.fromisoformat(c).date() for c in habit['completions']]
                return state
            except (json.JSONDecodeError, TypeError, KeyError):
                # If file is corrupted or schema is old, start fresh
                return get_default_state()
    else:
        return get_default_state()

def generate_initial_data():
    """Generates sample habits with a realistic 2-week history."""
    habits = [
        {'name': 'Drink 8 glasses of water', 'emoji': '💧', 'frequency': 'daily'},
        {'name': 'Exercise for 30 minutes', 'emoji': '🏃', 'frequency': 'daily'},
        {'name': 'Read for 20 minutes', 'emoji': '📚', 'frequency': 'daily'}
    ]
    
    new_habits = []
    today = date.today()
    for i, habit_def in enumerate(habits):
        new_habit = {
            'id': int(datetime.now().timestamp() * 1000) + i,
            'name': habit_def['name'],
            'emoji': habit_def['emoji'],
            'frequency': habit_def['frequency'],
            'completions': [],
            'creationDate': today,
            'order': i,
            'unlockedTrophies': []
        }
        # Generate fake history
        for day_ago in range(1, 15):
            d = today - timedelta(days=day_ago)
            if random.random() > 0.3: # ~70% chance of completion
                new_habit['completions'].append(d)
        new_habits.append(new_habit)
    return new_habits

def get_default_state():
    """Returns the default state for a new user."""
    return {"habits": generate_initial_data()}

# Initialize session state
if "state" not in st.session_state:
    st.session_state.state = load_state()

# --- UTILITY & DATE FUNCTIONS ---

def get_today():
    """Returns today's date."""
    return date.today()

# --- CORE LOGIC & CALCULATIONS (Ported from JavaScript) ---

def calculate_streaks(habit):
    """Calculates the current and longest streaks for a habit."""
    if not habit['completions']:
        return {'currentStreak': 0, 'longestStreak': 0}

    completions = sorted(list(set(habit['completions'])), reverse=True)
    today = get_today()
    
    # Calculate current streak
    current_streak = 0
    if today in completions:
        current_streak = 1
        last_date = today
        for d in completions[1:]:
            if last_date - d == timedelta(days=1):
                current_streak += 1
                last_date = d
            else:
                break
    
    # Calculate longest streak
    if not completions:
        return {'currentStreak': current_streak, 'longestStreak': 0}
        
    longest_streak = 0
    temp_streak = 1
    # Need at least one element to have a streak of 1
    if completions:
        longest_streak = 1
        for i in range(len(completions) - 1):
            if completions[i] - completions[i+1] == timedelta(days=1):
                temp_streak += 1
            else:
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 1
        longest_streak = max(longest_streak, temp_streak)
    
    return {'currentStreak': current_streak, 'longestStreak': longest_streak}

# --- CALLBACK FUNCTIONS ---

def toggle_completion(habit_id):
    """Callback function to toggle a habit's completion for today."""
    state = st.session_state.state
    today = get_today()
    habit = next((h for h in state['habits'] if h['id'] == habit_id), None)
    
    if habit:
        if today in habit['completions']:
            habit['completions'].remove(today)
        else:
            habit['completions'].append(today)
            st.toast(f"Great job on completing '{habit['name']}'! 🎉")
            # Check for all habits completed to show balloons
            habits_to_show = [h for h in state['habits'] if h['frequency'] == 'daily']
            completed_count = sum(1 for h in habits_to_show if today in h['completions'])
            if completed_count == len(habits_to_show):
                st.balloons()
        
        save_state(state)

# --- UI COMPONENTS ---

def display_main_dashboard():
    """Renders the main dashboard UI for today's habits."""
    state = st.session_state.state
    today = get_today()
    habits_to_show = [h for h in state['habits'] if h['frequency'] == 'daily']
    habits_to_show.sort(key=lambda x: x.get('order', 0))

    if not habits_to_show:
        st.info("No daily habits yet. Add one from the 'My Habits' section below to get started!")
        return

    completed_count = sum(1 for h in habits_to_show if today in h['completions'])
    total_count = len(habits_to_show)
    progress = (completed_count / total_count) if total_count > 0 else 0

    col1, col2 = st.columns([3, 1])
    with col1:
        st.progress(progress, text=f"{int(progress*100)}%")
    with col2:
        st.markdown(f"**{completed_count} / {total_count} Done**")
    
    st.markdown("---")
    
    for habit in habits_to_show:
        is_completed = today in habit['completions']
        streaks = calculate_streaks(habit)
        current_streak = streaks['currentStreak']
        
        cols = st.columns([1, 4, 2, 1])
        with cols[0]:
            st.markdown(f"<p style='font-size: 2rem; text-align: center;'>{habit['emoji']}</p>", unsafe_allow_html=True)
        with cols[1]:
            habit_name_display = f"~~{habit['name']}~~" if is_completed else habit['name']
            st.markdown(f"**{habit_name_display}**")
            streak_color = "#fbbf24" if current_streak > 0 else "grey"
            st.markdown(f"<span style='color: {streak_color};'>🔥 {current_streak} Day Streak</span>", unsafe_allow_html=True)

        with cols[2]:
            if st.button("View Details", key=f"detail_{habit['id']}"):
                st.session_state.detail_habit_id = habit['id']
                st.rerun()

        with cols[3]:
            # ** THE FIX IS HERE **
            # Use the on_change callback to handle state changes safely.
            # Streamlit automatically reruns the script when a callback is used.
            st.checkbox(
                "done", 
                value=is_completed, 
                key=f"check_{habit['id']}", 
                label_visibility="collapsed",
                on_change=toggle_completion,
                args=(habit['id'],)
            )
        st.markdown("---")


def display_habit_management():
    """Renders the UI for adding, editing, and viewing all habits."""
    state = st.session_state.state
    st.header("🎯 My Habits")

    with st.popover("➕ Add New Habit"):
        with st.form("new_habit_form", clear_on_submit=True):
            new_name = st.text_input("Habit Name", placeholder="e.g., Read for 20 minutes")
            new_emoji = st.text_input("Emoji Icon", placeholder="e.g., 📚")
            new_freq = st.selectbox("Frequency", ["daily", "weekly"])
            
            submitted = st.form_submit_button("Save Habit")
            if submitted:
                if new_name and new_emoji:
                    new_habit = {
                        'id': int(datetime.now().timestamp() * 1000),
                        'name': new_name, 'emoji': new_emoji, 'frequency': new_freq,
                        'completions': [], 'creationDate': get_today(),
                        'order': len(state['habits']), 'unlockedTrophies': []
                    }
                    state['habits'].append(new_habit)
                    save_state(state)
                    st.success(f"Habit '{new_name}' added!")
                else:
                    st.error("Please provide both a name and an emoji.")

    if not state['habits']:
        return
        
    for i, habit in enumerate(sorted(state['habits'], key=lambda h: h.get('order', 0))):
        cols = st.columns([1, 4, 1, 1, 1])
        with cols[0]:
            st.markdown(f"<p style='font-size: 1.5rem;'>{habit['emoji']}</p>", unsafe_allow_html=True)
        with cols[1]:
            st.write(habit['name'])
        with cols[2]:
            if i > 0:
                if st.button("⬆️", key=f"up_{habit['id']}", help="Move up"):
                    current_order = habit.get('order', i)
                    prev_habit = state['habits'][i-1]
                    prev_order = prev_habit.get('order', i-1)
                    habit['order'], prev_habit['order'] = prev_order, current_order
                    save_state(state)
                    st.rerun()
        with cols[3]:
            if i < len(state['habits']) - 1:
                if st.button("⬇️", key=f"down_{habit['id']}", help="Move down"):
                    current_order = habit.get('order', i)
                    next_habit = state['habits'][i+1]
                    next_order = next_habit.get('order', i+1)
                    habit['order'], next_habit['order'] = next_order, current_order
                    save_state(state)
                    st.rerun()
        with cols[4]:
             with st.popover("✏️", help="Edit or Delete"):
                st.markdown(f"**Edit: {habit['name']}**")
                edited_name = st.text_input("Name", value=habit['name'], key=f"name_{habit['id']}")
                edited_emoji = st.text_input("Emoji", value=habit['emoji'], key=f"emoji_{habit['id']}")
                
                if st.button("Save Changes", key=f"save_{habit['id']}", type="primary"):
                    habit['name'], habit['emoji'] = edited_name, edited_emoji
                    save_state(state)
                    st.rerun()

                if st.button("Delete Habit", key=f"del_{habit['id']}", type="secondary"):
                    state['habits'] = [h for h in state['habits'] if h['id'] != habit['id']]
                    save_state(state)
                    st.rerun()


def display_statistics():
    """Renders the statistics dashboard."""
    # ... (This function remains unchanged) ...
    state = st.session_state.state
    st.header("📊 Statistics")
    
    today = get_today()
    total_completions = 0
    seven_day_completions, seven_day_opportunities = 0, 0
    thirty_day_completions, thirty_day_opportunities = 0, 0
    habit_stats = []

    if not state['habits']:
        st.info("No data to show. Complete some habits first!")
        return

    for habit in state['habits']:
        total_completions += len(habit['completions'])
        creation_date = habit['creationDate']
        
        for i in range(30):
            d = today - timedelta(days=i)
            if d >= creation_date:
                if i < 7:
                    seven_day_opportunities += 1
                    if d in habit['completions']: seven_day_completions += 1
                thirty_day_opportunities += 1
                if d in habit['completions']: thirty_day_completions += 1
        
        days_since_creation = (today - creation_date).days + 1
        rate_days = min(30, days_since_creation)
        recent_completions = len([c for c in habit['completions'] if c >= (today - timedelta(days=30))])
        completion_rate = (recent_completions / rate_days * 100) if rate_days > 0 else 0
        habit_stats.append({**habit, 'completionRate': completion_rate})
    
    seven_day_rate = (seven_day_completions / seven_day_opportunities * 100) if seven_day_opportunities > 0 else 0
    thirty_day_rate = (thirty_day_completions / thirty_day_opportunities * 100) if thirty_day_opportunities > 0 else 0

    cols = st.columns(3)
    cols[0].metric("7-Day Rate", f"{seven_day_rate:.0f}%")
    cols[1].metric("30-Day Rate", f"{thirty_day_rate:.0f}%")
    cols[2].metric("Total Completions", total_completions)

    if habit_stats:
        habit_stats.sort(key=lambda x: x['completionRate'], reverse=True)
        best_habit, worst_habit = habit_stats[0], habit_stats[-1]
        
        st.markdown("---")
        cols = st.columns(2)
        with cols[0]:
            st.subheader("✅ Best Habit")
            st.markdown(f"**{best_habit['emoji']} {best_habit['name']}** ({best_habit['completionRate']:.0f}%)")
        with cols[1]:
            st.subheader("💪 Needs Work")
            st.markdown(f"**{worst_habit['emoji']} {worst_habit['name']}** ({worst_habit['completionRate']:.0f}%)")


def display_trophies():
    """Renders the trophy shelf."""
    # ... (This function remains unchanged) ...
    state = st.session_state.state
    st.header("🏆 Trophy Shelf")

    trophy_defs = [
        {'id': 'streak-3', 'name': '3-Day Streak', 'icon': '🥉', 'check': lambda h, _: calculate_streaks(h)['longestStreak'] >= 3},
        {'id': 'streak-7', 'name': '7-Day Streak', 'icon': '🥈', 'check': lambda h, _: calculate_streaks(h)['longestStreak'] >= 7},
        {'id': 'streak-30', 'name': '30-Day Streak', 'icon': '🥇', 'check': lambda h, _: calculate_streaks(h)['longestStreak'] >= 30},
        {'id': 'complete-100', 'name': '100 Completions', 'icon': '💯', 'check': lambda _, s: s['total_completions'] >= 100}
    ]

    total_completions = sum(len(h['completions']) for h in state['habits'])
    global_stats = {'total_completions': total_completions}
    earned_trophies = {t['id'] for t in trophy_defs for h in state['habits'] if t['check'](h, global_stats)}

    cols = st.columns(4)
    for i, t in enumerate(trophy_defs):
        is_earned = t['id'] in earned_trophies
        style = "opacity: 1;" if is_earned else "opacity: 0.3; filter: grayscale(100%);"
        cols[i % 4].markdown(f"""
        <div style="text-align: center; {style}">
            <p style="font-size: 3rem; margin-bottom: 0;">{t['icon']}</p>
            <p><strong>{t['name']}</strong></p>
        </div>
        """, unsafe_allow_html=True)


@st.dialog("Habit Details")
def display_detail_dialog(habit_id):
    """Renders the habit detail view with calendar in a dialog."""
    # ... (This function remains unchanged) ...
    state = st.session_state.state
    habit = next((h for h in state['habits'] if h['id'] == habit_id), None)
    if not habit:
        st.error("Habit not found.")
        return

    streaks = calculate_streaks(habit)
    st.markdown(f"<h1 style='text-align: center;'>{habit['emoji']} {habit['name']}</h1>", unsafe_allow_html=True)
    cols = st.columns(2)
    cols[0].metric("🔥 Current Streak", f"{streaks['currentStreak']} Days")
    cols[1].metric("⭐ Longest Streak", f"{streaks['longestStreak']} Days")
    
    st.markdown("---")
    st.subheader("Progress Calendar")

    view_date_key = f"view_date_{habit_id}"
    if view_date_key not in st.session_state:
        st.session_state[view_date_key] = get_today()
        
    cols = st.columns([1, 2, 1])
    if cols[0].button("◀️ Prev"):
        st.session_state[view_date_key] = st.session_state[view_date_key].replace(day=1) - timedelta(days=1)
    cols[1].markdown(f"<h4 style='text-align: center;'>{st.session_state[view_date_key].strftime('%B %Y')}</h4>", unsafe_allow_html=True)
    if cols[2].button("Next ▶️"):
        st.session_state[view_date_key] = (st.session_state[view_date_key].replace(day=28) + timedelta(days=4)).replace(day=1)
        
    calendar_html = generate_calendar_html(habit, st.session_state[view_date_key].year, st.session_state[view_date_key].month)
    st.markdown(calendar_html, unsafe_allow_html=True)
    st.info("Note: Interacting with the calendar to change past dates is not supported in this version.")


def generate_calendar_html(habit, year, month):
    """Generates an HTML table representing a calendar for a given habit."""
    # ... (This function remains unchanged) ...
    cal = calendar.Calendar()
    month_days = cal.itermonthdates(year, month)
    html = """<style>.cal-table{width:100%;border-collapse:collapse;}.cal-th,.cal-td{text-align:center;padding:10px;border:1px solid #4a4a4a;}.cal-day-completed{background-color:#28a745;color:white;}.cal-day-missed{background-color:#fbebee;color:#dc3545;}.cal-day-future{color:#6c757d;}.cal-day-other-month{opacity:0.3;}.cal-today{border:2px solid #28a745 !important;font-weight:bold;}</style><table class="cal-table"><tr><th class=cal-th>S</th><th class=cal-th>M</th><th class=cal-th>T</th><th class=cal-th>W</th><th class=cal-th>T</th><th class=cal-th>F</th><th class=cal-th>S</th></tr><tr>"""
    today, creation_date = get_today(), habit['creationDate']
    for i, day in enumerate(month_days):
        classes = ["cal-td"]
        if day.month != month: classes.append("cal-day-other-month")
        else:
            if day in habit['completions']: classes.append("cal-day-completed")
            elif day < today and day >= creation_date: classes.append("cal-day-missed")
            elif day > today: classes.append("cal-day-future")
            if day == today: classes.append("cal-today")
        html += f'<td class="{" ".join(classes)}">{day.day}</td>'
        if (i + 1) % 7 == 0: html += "</tr><tr>"
    html += "</tr></table>"
    return html

# --- MAIN APP LAYOUT ---

st.title("Momentum 🎯")
st.markdown("Your personal dashboard for building consistent, life-changing habits.")

if "detail_habit_id" in st.session_state and st.session_state.detail_habit_id is not None:
    display_detail_dialog(st.session_state.detail_habit_id)
    if st.button("Back to Dashboard"):
        del st.session_state.detail_habit_id
        st.rerun()
else:
    with st.expander("✨ Today's Habits", expanded=True):
        display_main_dashboard()
    with st.expander("🎯 My Habits"):
        display_habit_management()
    with st.expander("📊 Statistics"):
        display_statistics()
    with st.expander("🏆 Trophy Shelf"):
        display_trophies()

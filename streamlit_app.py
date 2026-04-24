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
    serializable_state = state.copy()
    
    # Serialize habits with date objects
    serializable_state['habits'] = []
    for habit in state.get('habits', []):
        h_copy = habit.copy()
        h_copy['creationDate'] = h_copy['creationDate'].isoformat() if isinstance(h_copy['creationDate'], date) else h_copy['creationDate']
        h_copy['completions'] = [c.isoformat() if isinstance(c, date) else c for c in h_copy['completions']]
        serializable_state['habits'].append(h_copy)
    
    # Tasks are already serializable since dates are stored as ISO strings
    serializable_state['tasks'] = state.get('tasks', [])
    
    with open(STATE_FILE, "w") as f:
        json.dump(serializable_state, f, indent=4)

def load_state():
    """Loads the state from a JSON file, or returns a default state."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                state = json.load(f)
                # Convert habit date strings back to date objects
                for habit in state.get('habits', []):
                    habit['creationDate'] = datetime.fromisoformat(habit['creationDate']).date()
                    habit['completions'] = [datetime.fromisoformat(c).date() for c in habit['completions']]
                return state
            except (json.JSONDecodeError, TypeError, KeyError):
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
            'id': int(datetime.now().timestamp() * 1000) + i, 'name': habit_def['name'],
            'emoji': habit_def['emoji'], 'frequency': habit_def['frequency'],
            'completions': [], 'creationDate': today, 'order': i, 'unlockedTrophies': []
        }
        for day_ago in range(1, 15):
            d = today - timedelta(days=day_ago)
            if random.random() > 0.3:
                new_habit['completions'].append(d)
        new_habits.append(new_habit)
    return new_habits

def get_default_state():
    """Returns the default state for a new user, including an empty tasks list."""
    return {"habits": generate_initial_data(), "tasks": []}

# Initialize session state
if "state" not in st.session_state:
    st.session_state.state = load_state()

# --- UTILITY & DATE FUNCTIONS ---

def get_today():
    """Returns today's date."""
    return date.today()

# --- CORE LOGIC & CALCULATIONS ---

def calculate_streaks(habit):
    """Calculates the current and longest streaks for a habit."""
    if not habit.get('completions'):
        return {'currentStreak': 0, 'longestStreak': 0}

    completions = sorted(list(set(habit['completions'])), reverse=True)
    today = get_today()
    
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
    
    longest_streak = 0
    if completions:
        longest_streak = 1
        temp_streak = 1
        for i in range(len(completions) - 1):
            if completions[i] - completions[i+1] == timedelta(days=1):
                temp_streak += 1
            else:
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 1
        longest_streak = max(longest_streak, temp_streak)
    
    return {'currentStreak': current_streak, 'longestStreak': longest_streak}

# --- CALLBACK FUNCTIONS ---

def toggle_habit_completion(habit_id):
    """Callback to toggle a habit's completion for today."""
    state = st.session_state.state
    today = get_today()
    habit = next((h for h in state['habits'] if h['id'] == habit_id), None)
    
    if habit:
        if today in habit['completions']:
            habit['completions'].remove(today)
        else:
            habit['completions'].append(today)
            st.toast(f"Great job on completing '{habit['name']}'! 🎉")
            habits_to_show = [h for h in state['habits'] if h['frequency'] == 'daily']
            completed_count = sum(1 for h in habits_to_show if today in h['completions'])
            if completed_count == len(habits_to_show):
                st.balloons()
        save_state(state)

def toggle_task_completion(task_id):
    """Callback to toggle a task's 'done' status."""
    state = st.session_state.state
    task = next((t for t in state.get('tasks', []) if t['id'] == task_id), None)
    if task:
        task['done'] = not task['done']
        save_state(state)

# --- UI COMPONENTS ---

def display_main_dashboard():
    """Renders the main dashboard UI for today's habits."""
    state = st.session_state.state
    today = get_today()
    habits_to_show = [h for h in state['habits'] if h['frequency'] == 'daily']
    habits_to_show.sort(key=lambda x: x.get('order', 0))

    if not habits_to_show:
        st.info("No daily habits yet. Add one from 'My Habits' to get started!")
        return

    completed_count = sum(1 for h in habits_to_show if today in h['completions'])
    total_count = len(habits_to_show)
    progress = (completed_count / total_count) if total_count > 0 else 0

    col1, col2 = st.columns([3, 1])
    col1.progress(progress, text=f"{int(progress*100)}%")
    col2.markdown(f"**{completed_count} / {total_count} Done**")
    
    st.markdown("---")
    
    for habit in habits_to_show:
        is_completed = today in habit['completions']
        streaks = calculate_streaks(habit)
        current_streak = streaks['currentStreak']
        
        cols = st.columns([1, 4, 2, 1])
        cols[0].markdown(f"<p style='font-size: 2rem; text-align: center;'>{habit['emoji']}</p>", unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"**{'~~'+habit['name']+'~~' if is_completed else habit['name']}**")
            streak_color = "#fbbf24" if current_streak > 0 else "grey"
            st.markdown(f"<span style='color: {streak_color};'>🔥 {current_streak} Day Streak</span>", unsafe_allow_html=True)
        if cols[2].button("View Details", key=f"detail_{habit['id']}"):
            st.session_state.detail_habit_id = habit['id']
            st.rerun()
        cols[3].checkbox("done", value=is_completed, key=f"check_{habit['id']}", label_visibility="collapsed", on_change=toggle_habit_completion, args=(habit['id'],))
        st.markdown("---")

def display_tasks_section():
    """Renders the UI for task management."""
    state = st.session_state.state
    
    col1, col2 = st.columns([4, 1])
    col1.header("✅ Tasks To-Do")
    with col2:
        with st.popover("➕"):
            st.markdown("**Add a new task**")
            # This is the form from your prompt, adapted for this app
            today = get_today()
            tomorrow = today + timedelta(days=1)
            with st.form("add_task_form", clear_on_submit=True):
                new_task_text = st.text_input("New task", placeholder="e.g. Prepare meeting notes")
                c1, c2 = st.columns(2)
                new_prio = c1.selectbox("Priority", ["high", "medium", "low"])
                new_task_date = c2.date_input("Date", value=today) # Defaults to today
                
                if st.form_submit_button("Add Task", type="primary"):
                    if new_task_text.strip():
                        new_task = {
                            "id":       int(datetime.now().timestamp() * 1000), "text":     new_task_text.strip(),
                            "done":     False, "date":     new_task_date.isoformat(),
                            "priority": new_prio,
                        }
                        state.setdefault("tasks", []).append(new_task)
                        save_state(state) # Use the app's save function
                        st.rerun()
                    else:
                        st.warning("Task cannot be empty.")
    
    tasks = state.get("tasks", [])
    if not tasks:
        st.info("No tasks yet. Add one using the ➕ button above!")
        return
        
    prio_map = {"high": "🔥", "medium": "🔸", "low": "🔹"}
    parse_date = lambda d_str: datetime.fromisoformat(d_str).date()

    # Sort tasks by date, then by priority index
    tasks.sort(key=lambda t: (parse_date(t['date']), ["high", "medium", "low"].index(t['priority'])))
    
    for task in tasks:
        task_date, is_done = parse_date(task['date']), task['done']
        
        cols = st.columns([1, 6, 1])
        with cols[0]:
            st.checkbox("done", value=is_done, key=f"task_check_{task['id']}", label_visibility="collapsed", on_change=toggle_task_completion, args=(task['id'],))
        with cols[1]:
            task_text_display = f"~~{task['text']}~~" if is_done else task['text']
            st.markdown(f"{prio_map.get(task['priority'], '')} {task_text_display}")
            
            date_color = "default"
            date_display_text = f"🗓️ {task_date.strftime('%b %d')}"
            if task_date < get_today() and not is_done:
                date_color = "red"
                date_display_text = f"⚠️ **OVERDUE** ({task_date.strftime('%b %d')})"
            st.markdown(f":{date_color}[{date_display_text}]")

        with cols[2]:
            if st.button("🗑️", key=f"del_task_{task['id']}", help="Delete task"):
                state['tasks'] = [t for t in state['tasks'] if t['id'] != task['id']]
                save_state(state)
                st.rerun()
        st.markdown("---")

def display_habit_management():
    """Renders the UI for adding, editing, and viewing all habits."""
    state = st.session_state.state
    
    col1, col2 = st.columns([4, 1])
    col1.header("🎯 My Habits")
    with col2:
         with st.popover("➕"):
            st.markdown("**Add a new habit**")
            with st.form("new_habit_form", clear_on_submit=True):
                new_name = st.text_input("Habit Name", placeholder="e.g., Read for 20 minutes")
                new_emoji = st.text_input("Emoji Icon", placeholder="e.g., 📚")
                new_freq = st.selectbox("Frequency", ["daily", "weekly"])
                
                if st.form_submit_button("Save Habit"):
                    if new_name and new_emoji:
                        new_habit = {
                            'id': int(datetime.now().timestamp() * 1000), 'name': new_name, 'emoji': new_emoji, 
                            'frequency': new_freq, 'completions': [], 'creationDate': get_today(),
                            'order': len(state['habits']), 'unlockedTrophies': []
                        }
                        state['habits'].append(new_habit)
                        save_state(state)
                    else:
                        st.error("Please provide both a name and an emoji.")

    if not state['habits']:
        return
        
    for i, habit in enumerate(sorted(state['habits'], key=lambda h: h.get('order', 0))):
        cols = st.columns([1, 4, 1, 1, 1])
        cols[0].markdown(f"<p style='font-size: 1.5rem;'>{habit['emoji']}</p>", unsafe_allow_html=True)
        cols[1].write(habit['name'])
        if i > 0 and cols[2].button("⬆️", key=f"up_{habit['id']}", help="Move up"):
            state['habits'][i], state['habits'][i-1] = state['habits'][i-1], state['habits'][i]
            for idx, h in enumerate(state['habits']): h['order'] = idx
            save_state(state); st.rerun()
        if i < len(state['habits']) - 1 and cols[3].button("⬇️", key=f"down_{habit['id']}", help="Move down"):
            state['habits'][i], state['habits'][i+1] = state['habits'][i+1], state['habits'][i]
            for idx, h in enumerate(state['habits']): h['order'] = idx
            save_state(state); st.rerun()
        with cols[4]:
             with st.popover("✏️", help="Edit or Delete"):
                st.markdown(f"**Edit: {habit['name']}**")
                edited_name = st.text_input("Name", value=habit['name'], key=f"name_{habit['id']}")
                edited_emoji = st.text_input("Emoji", value=habit['emoji'], key=f"emoji_{habit['id']}")
                if st.button("Save Changes", key=f"save_{habit['id']}", type="primary"):
                    habit['name'], habit['emoji'] = edited_name, edited_emoji
                    save_state(state); st.rerun()
                if st.button("Delete Habit", key=f"del_{habit['id']}", type="secondary"):
                    state['habits'] = [h for h in state['habits'] if h['id'] != habit['id']]
                    save_state(state); st.rerun()

def display_statistics():
    """Renders the statistics dashboard."""
    state = st.session_state.state
    st.header("📊 Statistics")
    
    if not state.get('habits'):
        st.info("No data to show. Complete some habits first!")
        return

    today = get_today()
    total_completions, s_day_comp, s_day_opp, t_day_comp, t_day_opp = 0, 0, 0, 0, 0
    habit_stats = []
    for habit in state['habits']:
        total_completions += len(habit['completions'])
        creation_date = habit['creationDate']
        for i in range(30):
            d = today - timedelta(days=i)
            if d >= creation_date:
                if i < 7:
                    s_day_opp += 1
                    if d in habit['completions']: s_day_comp += 1
                t_day_opp += 1
                if d in habit['completions']: t_day_comp += 1
        days_since_creation = (today - creation_date).days + 1
        rate_days = min(30, days_since_creation)
        recent_completions = len([c for c in habit['completions'] if c >= (today - timedelta(days=30))])
        completion_rate = (recent_completions / rate_days * 100) if rate_days > 0 else 0
        habit_stats.append({**habit, 'completionRate': completion_rate})
    
    s_day_rate = (s_day_comp / s_day_opp * 100) if s_day_opp > 0 else 0
    t_day_rate = (t_day_comp / t_day_opp * 100) if t_day_opp > 0 else 0

    cols = st.columns(3)
    cols[0].metric("7-Day Rate", f"{s_day_rate:.0f}%")
    cols[1].metric("30-Day Rate", f"{t_day_rate:.0f}%")
    cols[2].metric("Total Completions", total_completions)

    if habit_stats:
        habit_stats.sort(key=lambda x: x['completionRate'], reverse=True)
        best, worst = habit_stats[0], habit_stats[-1]
        st.markdown("---")
        cols = st.columns(2)
        cols[0].subheader("✅ Best Habit"); cols[0].markdown(f"**{best['emoji']} {best['name']}** ({best['completionRate']:.0f}%)")
        cols[1].subheader("💪 Needs Work"); cols[1].markdown(f"**{worst['emoji']} {worst['name']}** ({worst['completionRate']:.0f}%)")

def display_trophies():
    """Renders the trophy shelf."""
    state = st.session_state.state
    st.header("🏆 Trophy Shelf")

    trophy_defs = [
        {'id': 'streak-3', 'name': '3-Day Streak', 'icon': '🥉', 'check': lambda h, _: calculate_streaks(h)['longestStreak'] >= 3},
        {'id': 'streak-7', 'name': '7-Day Streak', 'icon': '🥈', 'check': lambda h, _: calculate_streaks(h)['longestStreak'] >= 7},
        {'id': 'streak-30', 'name': '30-Day Streak', 'icon': '🥇', 'check': lambda h, _: calculate_streaks(h)['longestStreak'] >= 30},
        {'id': 'complete-100', 'name': '100 Completions', 'icon': '💯', 'check': lambda _, s: s['total_completions'] >= 100}
    ]

    total_completions = sum(len(h.get('completions', [])) for h in state.get('habits', []))
    global_stats = {'total_completions': total_completions}
    earned_trophies = {t['id'] for t in trophy_defs for h in state.get('habits', []) if t['check'](h, global_stats)}

    cols = st.columns(4)
    for i, t in enumerate(trophy_defs):
        is_earned = t['id'] in earned_trophies
        style = "opacity: 1;" if is_earned else "opacity: 0.3; filter: grayscale(100%);"
        cols[i % 4].markdown(f"""
        <div style="text-align: center; {style}">
            <p style="font-size: 3rem; margin-bottom: 0;">{t['icon']}</p><p><strong>{t['name']}</strong></p>
        </div>""", unsafe_allow_html=True)

@st.dialog("Habit Details")
def display_detail_dialog(habit_id):
    """Renders the habit detail view with calendar in a dialog."""
    habit = next((h for h in st.session_state.state['habits'] if h['id'] == habit_id), None)
    if not habit: st.error("Habit not found."); return

    streaks = calculate_streaks(habit)
    st.markdown(f"<h1 style='text-align: center;'>{habit['emoji']} {habit['name']}</h1>", unsafe_allow_html=True)
    cols = st.columns(2)
    cols[0].metric("🔥 Current Streak", f"{streaks['currentStreak']} Days")
    cols[1].metric("⭐ Longest Streak", f"{streaks['longestStreak']} Days")
    st.subheader("Progress Calendar")

    view_date_key = f"view_date_{habit_id}"
    if view_date_key not in st.session_state: st.session_state[view_date_key] = get_today()
    
    cols = st.columns([1, 2, 1])
    if cols[0].button("◀️"): st.session_state[view_date_key] = st.session_state[view_date_key].replace(day=1) - timedelta(days=1)
    cols[1].markdown(f"<h4 style='text-align: center;'>{st.session_state[view_date_key].strftime('%B %Y')}</h4>", unsafe_allow_html=True)
    if cols[2].button("▶️"): st.session_state[view_date_key] = (st.session_state[view_date_key].replace(day=28) + timedelta(days=4)).replace(day=1)
    
    st.markdown(generate_calendar_html(habit, st.session_state[view_date_key].year, st.session_state[view_date_key].month), unsafe_allow_html=True)
    st.info("Retroactively marking dates is not supported in this version.")

def generate_calendar_html(habit, year, month):
    """Generates an HTML table representing a calendar for a given habit."""
    cal = calendar.Calendar()
    html = """<style>.cal-table{width:100%;border-collapse:collapse;}.cal-th,.cal-td{text-align:center;padding:10px;border:1px solid #4a4a4a;}.cal-day-completed{background-color:#28a745;color:white;}.cal-day-missed{background-color:#fbebee;color:#dc3545;}.cal-day-future{color:#6c757d;}.cal-day-other-month{opacity:0.3;}.cal-today{border:2px solid #28a745 !important;font-weight:bold;}</style><table class="cal-table"><tr><th>S</th><th>M</th><th>T</th><th>W</th><th>T</th><th>F</th><th>S</th></tr><tr>"""
    today, creation_date = get_today(), habit['creationDate']
    for i, day in enumerate(cal.itermonthdates(year, month)):
        classes = ["cal-td"]
        if day.month != month: classes.append("cal-day-other-month")
        else:
            if day in habit['completions']: classes.append("cal-day-completed")
            elif day < today and day >= creation_date: classes.append("cal-day-missed")
            elif day > today: classes.append("cal-day-future")
            if day == today: classes.append("cal-today")
        html += f'<td class="{" ".join(classes)}">{day.day}</td>'
        if (i + 1) % 7 == 0: html += "</tr><tr>"
    return html + "</tr></table>"

# --- MAIN APP LAYOUT ---

st.title("Momentum 🎯")
st.markdown("Your personal dashboard for building consistent habits and managing tasks.")

if "detail_habit_id" in st.session_state and st.session_state.detail_habit_id is not None:
    display_detail_dialog(st.session_state.detail_habit_id)
    if st.button("Back to Dashboard"):
        del st.session_state.detail_habit_id
        st.rerun()
else:
    with st.expander("✨ Today's Habits", expanded=True):
        display_main_dashboard()
    with st.expander("✅ Tasks To-Do", expanded=True):
        display_tasks_section()
    with st.expander("🎯 My Habits"):
        display_habit_management()
    with st.expander("📊 Statistics"):
        display_statistics()
    with st.expander("🏆 Trophy Shelf"):
        display_trophies()

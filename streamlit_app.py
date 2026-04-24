# app.py
import streamlit as st
import json
from datetime import datetime, timedelta, date
import random
import os
import calendar
import io
import hashlib

# --- PDF Reporting Dependencies ---
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib import colors
except ImportError:
    st.error("ReportLab library not found. Please run 'pip install reportlab' to enable PDF reporting.")
    st.stop()

# --- CONFIGURATION & INITIALIZATION ---
st.set_page_config(
    page_title="Momentum - Habit Tracker",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="auto",
)

USER_DB_FILE = "users.json"

# --- AUTHENTICATION UTILITIES ---

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_users():
    if os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f)

def get_user_state_file(username):
    return f"state_{username}.json"

# --- STATE MANAGEMENT ---

def save_state(state, username):
    """Saves the user-specific state to a JSON file."""
    serializable_state = state.copy()
    serializable_state['habits'] = []
    for habit in state.get('habits', []):
        h_copy = habit.copy()
        h_copy['creationDate'] = h_copy['creationDate'].isoformat() if isinstance(h_copy['creationDate'], date) else h_copy['creationDate']
        h_copy['completions'] = [c.isoformat() if isinstance(c, date) else c for c in h_copy['completions']]
        serializable_state['habits'].append(h_copy)
    
    serializable_state['tasks'] = state.get('tasks', [])
    with open(get_user_state_file(username), "w") as f:
        json.dump(serializable_state, f, indent=4)

def load_state(username):
    """Loads the user-specific state."""
    state_file = get_user_state_file(username)
    if os.path.exists(state_file):
        with open(state_file, "r") as f:
            try:
                state = json.load(f)
                for habit in state.get('habits', []):
                    habit['creationDate'] = datetime.fromisoformat(habit['creationDate']).date()
                    habit['completions'] = [datetime.fromisoformat(c).date() for c in habit['completions']]
                return state
            except (json.JSONDecodeError, TypeError, KeyError):
                return get_default_state()
    else:
        return get_default_state()

def generate_initial_data():
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
        new_habits.append(new_habit)
    return new_habits

def get_default_state():
    return {"habits": generate_initial_data(), "tasks": []}

# --- CORE LOGIC & CALCULATIONS ---

def calculate_streaks(habit):
    if not habit.get('completions'): return {'currentStreak': 0, 'longestStreak': 0}
    completions = sorted(list(set(habit['completions'])), reverse=True)
    today = date.today()
    current_streak = 0
    if today in completions:
        current_streak = 1
        last_date = today
        for d in completions[1:]:
            if last_date - d == timedelta(days=1):
                current_streak += 1
                last_date = d
            else: break
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

def generate_pdf_report(completed_habits, completed_tasks, planned_tasks):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(8.5 * inch, 11 * inch), topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    today = date.today()
    tomorrow = today + timedelta(days=1)
    story.append(Paragraph(f"Daily Report - {today.strftime('%B %d, %Y')}", styles['h1']))
    story.append(Spacer(1, 0.25 * inch))

    # Habits
    story.append(Paragraph("✅ Habits Completed", styles['h2']))
    if completed_habits:
        items = [ListItem(Paragraph(f"{h['emoji']} {h['name']}", styles['Normal']), bulletColor=colors.green) for h in completed_habits]
        story.append(ListFlowable(items, bulletType='bullet', leftIndent=20))
    else: story.append(Paragraph("None", styles['Normal']))
    
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph(f"🗓️ Plan for Tomorrow", styles['h2']))
    if planned_tasks:
        items = [ListItem(Paragraph(f"{t['text']} ({t['priority']})", styles['Normal'])) for t in planned_tasks]
        story.append(ListFlowable(items, bulletType='bullet', leftIndent=20))
    else: story.append(Paragraph("No tasks planned", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- UI COMPONENTS ---

def display_main_dashboard():
    state = st.session_state.state
    today = date.today()
    habits_to_show = [h for h in state['habits'] if h['frequency'] == 'daily']
    habits_to_show.sort(key=lambda x: x.get('order', 0))

    if not habits_to_show:
        st.info("No daily habits yet.")
        return

    completed_count = sum(1 for h in habits_to_show if today in h['completions'])
    total_count = len(habits_to_show)
    progress = (completed_count / total_count) if total_count > 0 else 0

    col1, col2 = st.columns([3, 1])
    col1.progress(progress, text=f"{int(progress*100)}%")
    col2.markdown(f"**{completed_count} / {total_count} Done**")
    
    for habit in habits_to_show:
        is_completed = today in habit['completions']
        streaks = calculate_streaks(habit)
        cols = st.columns([1, 4, 2, 1])
        cols[0].markdown(f"### {habit['emoji']}")
        with cols[1]:
            st.markdown(f"**{'~~'+habit['name']+'~~' if is_completed else habit['name']}**")
            st.markdown(f"🔥 {streaks['currentStreak']} Day Streak")
        if cols[2].button("Details", key=f"dt_{habit['id']}"):
            st.session_state.detail_habit_id = habit['id']
            st.rerun()
        cols[3].checkbox("done", value=is_completed, key=f"chk_{habit['id']}", label_visibility="collapsed", 
                         on_change=toggle_habit_completion, args=(habit['id'],))

def toggle_habit_completion(habit_id):
    state = st.session_state.state
    today = date.today()
    habit = next((h for h in state['habits'] if h['id'] == habit_id), None)
    if habit:
        if today in habit['completions']: habit['completions'].remove(today)
        else: habit['completions'].append(today)
        save_state(state, st.session_state.username)

def display_tasks_section():
    state = st.session_state.state
    col1, col2 = st.columns([4, 1])
    col1.header("✅ Tasks To-Do")
    with col2:
        with st.popover("➕"):
            with st.form("add_task_form", clear_on_submit=True):
                new_task_text = st.text_input("New task")
                new_prio = st.selectbox("Priority", ["high", "medium", "low"])
                new_task_date = st.date_input("Date", value=date.today())
                if st.form_submit_button("Add Task"):
                    if new_task_text.strip():
                        new_task = {"id": int(datetime.now().timestamp() * 1000), "text": new_task_text, "done": False, "date": new_task_date.isoformat(), "priority": new_prio}
                        state.setdefault("tasks", []).append(new_task)
                        save_state(state, st.session_state.username); st.rerun()

    tasks = state.get("tasks", [])
    for task in tasks:
        cols = st.columns([1, 6, 1])
        done = cols[0].checkbox("done", value=task['done'], key=f"tchk_{task['id']}", label_visibility="collapsed")
        if done != task['done']:
            task['done'] = done
            save_state(state, st.session_state.username); st.rerun()
        cols[1].markdown(f"{'~~' + task['text'] + '~~' if task['done'] else task['text']} ({task['priority']})")
        if cols[2].button("🗑️", key=f"tdel_{task['id']}"):
            state['tasks'] = [t for t in state['tasks'] if t['id'] != task['id']]
            save_state(state, st.session_state.username); st.rerun()

def display_account_section():
    st.header("👤 Account Settings")
    with st.expander("Change Password"):
        with st.form("change_password_form"):
            old_p = st.text_input("Current Password", type="password")
            new_p = st.text_input("New Password", type="password")
            if st.form_submit_button("Update Password"):
                users = load_users()
                if users.get(st.session_state.username) == hash_password(old_p):
                    users[st.session_state.username] = hash_password(new_p)
                    save_users(users)
                    st.success("Password updated!")
                else:
                    st.error("Incorrect current password")
    
    if st.button("Logout", type="primary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- AUTHENTICATION SCREEN ---

def auth_screen():
    st.title("Momentum 🎯")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                users = load_users()
                if u in users and users[u] == hash_password(p):
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.session_state.state = load_state(u)
                    st.rerun()
                else:
                    st.error("Invalid username or password")
    
    with tab2:
        with st.form("signup_form"):
            u = st.text_input("Choose Username")
            p = st.text_input("Choose Password", type="password")
            if st.form_submit_button("Create Account", use_container_width=True):
                users = load_users()
                if u in users:
                    st.error("Username already exists")
                elif len(u) < 3 or len(p) < 4:
                    st.error("Username/Password too short")
                else:
                    users[u] = hash_password(p)
                    save_users(users)
                    st.success("Account created! Please login.")

# --- MAIN APP LOGIC ---

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    auth_screen()
else:
    st.title(f"Momentum: {st.session_state.username} 🎯")
    
    # Detail View check
    if "detail_habit_id" in st.session_state and st.session_state.detail_habit_id is not None:
        habit = next((h for h in st.session_state.state['habits'] if h['id'] == st.session_state.detail_habit_id), None)
        st.write(f"### {habit['emoji']} {habit['name']}")
        st.info("Calendar view coming soon.")
        if st.button("Back"):
            del st.session_state.detail_habit_id
            st.rerun()
    else:
        with st.expander("✨ Today's Habits", expanded=True):
            display_main_dashboard()
        with st.expander("✅ Tasks To-Do", expanded=True):
            display_tasks_section()
        with st.expander("🎯 My Habits"):
            display_habit_management() # (Keep existing logic from previous block)
            # Simplified management for brevity in this response
            state = st.session_state.state
            for habit in state['habits']:
                c1, c2 = st.columns([4, 1])
                c1.write(f"{habit['emoji']} {habit['name']}")
                if c2.button("🗑️", key=f"manage_del_{habit['id']}"):
                    state['habits'] = [h for h in state['habits'] if h['id'] != habit['id']]
                    save_state(state, st.session_state.username); st.rerun()

        with st.expander("📈 Daily Reporting"):
            st.header("Daily Reporting")
            if st.button("Generate Report PDF"):
                # Data gathering logic
                today = date.today()
                comp_h = [h for h in st.session_state.state['habits'] if today in h['completions']]
                plan_t = [t for t in st.session_state.state.get('tasks', []) if not t['done']]
                pdf = generate_pdf_report(comp_h, [], plan_t)
                st.download_button("Download PDF", pdf, file_name="report.pdf")

        with st.expander("👤 Account & Security"):
            display_account_section()

def display_habit_management():
    # Helper to allow adding habits in the management tab
    state = st.session_state.state
    with st.popover("Add New Habit"):
        with st.form("new_habit_auth_form"):
            n = st.text_input("Name")
            e = st.text_input("Emoji")
            if st.form_submit_button("Save"):
                new_h = {'id': int(datetime.now().timestamp()*1000), 'name': n, 'emoji': e, 'frequency': 'daily', 'completions': [], 'creationDate': date.today(), 'order': len(state['habits'])}
                state['habits'].append(new_h)
                save_state(state, st.session_state.username); st.rerun()

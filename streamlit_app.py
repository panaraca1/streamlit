# app.py
import streamlit as st
import json
from datetime import datetime, timedelta, date
import random
import os
import calendar
import io

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

STATE_FILE = "state.json"

# --- STATE MANAGEMENT ---

def save_state(state):
    """Saves the entire state dictionary to a JSON file."""
    serializable_state = state.copy()
    serializable_state['habits'] = []
    for habit in state.get('habits', []):
        h_copy = habit.copy()
        h_copy['creationDate'] = h_copy['creationDate'].isoformat() if isinstance(h_copy['creationDate'], date) else h_copy['creationDate']
        h_copy['completions'] = [c.isoformat() if isinstance(c, date) else c for c in h_copy['completions']]
        serializable_state['habits'].append(h_copy)
    
    serializable_state['tasks'] = state.get('tasks', [])
    with open(STATE_FILE, "w") as f:
        json.dump(serializable_state, f, indent=4)

def load_state():
    """Loads the state from a JSON file, or returns a default state."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
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
    return {"habits": generate_initial_data(), "tasks": []}

if "state" not in st.session_state:
    st.session_state.state = load_state()

# --- UTILITY & DATE FUNCTIONS ---

def get_today():
    return date.today()

def parse_task_date(date_str):
    try:
        return datetime.fromisoformat(date_str).date()
    except (TypeError, ValueError):
        return None

# --- CORE LOGIC & CALCULATIONS ---

def calculate_streaks(habit):
    """Calculates current and longest streaks."""
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

def generate_pdf_report(completed_habits, completed_tasks, planned_tasks):
    """Uses reportlab to generate a PDF report in memory using ListFlowable."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(8.5 * inch, 11 * inch), 
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    today = get_today()
    tomorrow = today + timedelta(days=1)
    title = f"Daily Report - {today.strftime('%A, %B %d, %Y')}"
    story.append(Paragraph(title, styles['h1']))
    story.append(Spacer(1, 0.25 * inch))

    # --- Habits Completed ---
    story.append(Paragraph("✅ Habits Completed Today", styles['h2']))
    if completed_habits:
        habit_items = []
        for habit in completed_habits:
            # Note: Emojis require custom fonts in ReportLab; standard fonts may show boxes
            p = Paragraph(f"{habit['emoji']} {habit['name']}", styles['Normal'])
            habit_items.append(ListItem(p, bulletColor=colors.green))
        story.append(ListFlowable(habit_items, bulletType='bullet', leftIndent=20))
    else:
        story.append(Paragraph("<i>No habits completed today.</i>", styles['Italic']))
    story.append(Spacer(1, 0.25 * inch))

    # --- Tasks Completed ---
    story.append(Paragraph("✅ Tasks Completed Today", styles['h2']))
    if completed_tasks:
        task_items = []
        for task in completed_tasks:
            p = Paragraph(task['text'], styles['Normal'])
            task_items.append(ListItem(p, bulletColor=colors.green))
        story.append(ListFlowable(task_items, bulletType='bullet', leftIndent=20))
    else:
        story.append(Paragraph("<i>No tasks completed today.</i>", styles['Italic']))
    story.append(Spacer(1, 0.25 * inch))

    # --- Plan for Tomorrow ---
    story.append(Paragraph(f"🗓️ Plan for Tomorrow ({tomorrow.strftime('%Y-%m-%d')})", styles['h2']))
    if planned_tasks:
        planned_items = []
        for task in planned_tasks:
            p = Paragraph(f"{task['text']} (Priority: {task['priority']})", styles['Normal'])
            planned_items.append(ListItem(p, bulletColor=colors.black))
        story.append(ListFlowable(planned_items, bulletType='bullet', leftIndent=20))
    else:
        story.append(Paragraph("<i>No tasks planned for tomorrow.</i>", styles['Italic']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- CALLBACK FUNCTIONS ---

def toggle_habit_completion(habit_id):
    state = st.session_state.state
    today = get_today()
    habit = next((h for h in state['habits'] if h['id'] == habit_id), None)
    if habit:
        if today in habit['completions']:
            habit['completions'].remove(today)
        else:
            habit['completions'].append(today)
            st.toast(f"Great job on '{habit['name']}'! 🎉")
        save_state(state)

def toggle_task_completion(task_id):
    state = st.session_state.state
    task = next((t for t in state.get('tasks', []) if t['id'] == task_id), None)
    if task:
        task['done'] = not task['done']
        save_state(state)

# --- UI COMPONENTS ---

def display_main_dashboard():
    state = st.session_state.state
    today = get_today()
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
        cols[3].checkbox("done", value=is_completed, key=f"chk_{habit['id']}", label_visibility="collapsed", on_change=toggle_habit_completion, args=(habit['id'],))

def display_tasks_section():
    state = st.session_state.state
    col1, col2 = st.columns([4, 1])
    col1.header("✅ Tasks To-Do")
    with col2:
        with st.popover("➕"):
            with st.form("add_task_form", clear_on_submit=True):
                new_task_text = st.text_input("New task")
                new_prio = st.selectbox("Priority", ["high", "medium", "low"])
                new_task_date = st.date_input("Date", value=get_today())
                if st.form_submit_button("Add Task"):
                    if new_task_text.strip():
                        new_task = {"id": int(datetime.now().timestamp() * 1000), "text": new_task_text, "done": False, "date": new_task_date.isoformat(), "priority": new_prio}
                        state.setdefault("tasks", []).append(new_task)
                        save_state(state); st.rerun()

    tasks = state.get("tasks", [])
    for task in tasks:
        cols = st.columns([1, 6, 1])
        cols[0].checkbox("done", value=task['done'], key=f"tchk_{task['id']}", on_change=toggle_task_completion, args=(task['id'],), label_visibility="collapsed")
        cols[1].markdown(f"{'~~' + task['text'] + '~~' if task['done'] else task['text']} ({task['priority']})")
        if cols[2].button("🗑️", key=f"tdel_{task['id']}"):
            state['tasks'] = [t for t in state['tasks'] if t['id'] != task['id']]
            save_state(state); st.rerun()

def display_reporting_section():
    st.header("📈 Daily Reporting")
    state = st.session_state.state
    today = get_today()
    tomorrow = today + timedelta(days=1)
    
    completed_habits = [h for h in state.get('habits', []) if today in h.get('completions', [])]
    completed_tasks = [t for t in state.get('tasks', []) if t.get('done') and parse_task_date(t['date']) == today]
    planned_tasks = [t for t in state.get('tasks', []) if parse_task_date(t['date']) == tomorrow and not t.get('done')]

    if st.button("Generate Report PDF"):
        pdf_buffer = generate_pdf_report(completed_habits, completed_tasks, planned_tasks)
        st.download_button(label="📥 Download PDF", data=pdf_buffer, file_name=f"report_{today}.pdf", mime="application/pdf")

def display_habit_management():
    state = st.session_state.state
    st.header("🎯 My Habits")
    with st.popover("Add New Habit"):
        with st.form("new_habit_form"):
            n = st.text_input("Habit Name")
            e = st.text_input("Emoji")
            f = st.selectbox("Frequency", ["daily", "weekly"])
            if st.form_submit_button("Save"):
                new_h = {'id': int(datetime.now().timestamp()*1000), 'name': n, 'emoji': e, 'frequency': f, 'completions': [], 'creationDate': get_today(), 'order': len(state['habits'])}
                state['habits'].append(new_h); save_state(state); st.rerun()

    for habit in state['habits']:
        cols = st.columns([4, 1])
        cols[0].write(f"{habit['emoji']} {habit['name']}")
        if cols[1].button("Delete", key=f"hdel_{habit['id']}"):
            state['habits'] = [h for h in state['habits'] if h['id'] != habit['id']]; save_state(state); st.rerun()

def display_statistics():
    st.header("📊 Statistics")
    state = st.session_state.state
    if not state['habits']: return
    total = sum(len(h['completions']) for h in state['habits'])
    st.metric("Total Completions", total)

def display_trophies():
    st.header("🏆 Trophy Shelf")
    st.write("Earn trophies by maintaining streaks!")

@st.dialog("Habit Details")
def display_detail_dialog(habit_id):
    habit = next((h for h in st.session_state.state['habits'] if h['id'] == habit_id), None)
    if habit:
        st.write(f"### {habit['emoji']} {habit['name']}")
        st.write("History view (Calendar) would go here.")

# --- MAIN APP LAYOUT ---
st.title("Momentum 🎯")

if "detail_habit_id" in st.session_state and st.session_state.detail_habit_id is not None:
    display_detail_dialog(st.session_state.detail_habit_id)
    if st.button("Back"):
        del st.session_state.detail_habit_id; st.rerun()
else:
    with st.expander("✨ Today's Habits", expanded=True):
        display_main_dashboard()
    with st.expander("✅ Tasks To-Do", expanded=True):
        display_tasks_section()
    with st.expander("🎯 My Habits"):
        display_habit_management()
    with st.expander("📈 Daily Reporting"):
        display_reporting_section()
    with st.expander("📊 Statistics"):
        display_statistics()
    with st.expander("🏆 Trophy Shelf"):
        display_trophies()

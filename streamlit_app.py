import streamlit as st
import json
import hashlib
import os
import calendar
import random
import io
from datetime import datetime, timedelta, date

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Fellow Ups",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

USERS_FILE = "users.json"

def get_salt():
    try:
        return st.secrets["admin_key"]
    except Exception:
        return "fellow-ups-default-salt"


# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    salted = get_salt() + password
    return hashlib.sha256(salted.encode()).hexdigest()

def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def register_user(username: str, password: str, display_name: str) -> tuple[bool, str]:
    users = load_users()
    username = username.strip().lower()
    if not username or not password:
        return False, "Username and password cannot be empty."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    if username in users:
        return False, "Username already taken. Please choose another."
    users[username] = {
        "display_name": display_name.strip() or username,
        "password_hash": hash_password(password),
        "created_at": date.today().isoformat(),
    }
    save_users(users)
    return True, "Account created successfully!"

def login_user(username: str, password: str) -> tuple[bool, str]:
    users = load_users()
    username = username.strip().lower()
    if username not in users:
        return False, "No account found with that username."
    if users[username]["password_hash"] != hash_password(password):
        return False, "Incorrect password."
    return True, users[username]["display_name"]


# ─────────────────────────────────────────────
# PER-USER DATA FILE
# ─────────────────────────────────────────────

def user_data_file(username: str) -> str:
    return f"data_{username}.json"

def load_user_state(username: str) -> dict:
    fpath = user_data_file(username)
    if os.path.exists(fpath):
        with open(fpath, "r") as f:
            try:
                state = json.load(f)
                for habit in state.get("habits", []):
                    habit["creationDate"] = datetime.fromisoformat(habit["creationDate"]).date()
                    habit["completions"] = [datetime.fromisoformat(c).date() for c in habit["completions"]]
                for task in state.get("tasks", []):
                    task["date"] = datetime.fromisoformat(task["date"]).date() if task.get("date") else date.today().isoformat()
                return state
            except Exception:
                pass
    return get_default_state()

def save_user_state(username: str, state: dict):
    fpath = user_data_file(username)
    serializable = state.copy()
    serializable["habits"] = []
    for habit in state["habits"]:
        h = habit.copy()
        h["creationDate"] = h["creationDate"].isoformat() if isinstance(h["creationDate"], date) else h["creationDate"]
        h["completions"] = [c.isoformat() if isinstance(c, date) else c for c in h["completions"]]
        serializable["habits"].append(h)
    serializable["tasks"] = []
    for task in state.get("tasks", []):
        t = task.copy()
        if isinstance(t.get("date"), date):
            t["date"] = t["date"].isoformat()
        serializable["tasks"].append(t)
    with open(fpath, "w") as f:
        json.dump(serializable, f, indent=4)

def generate_initial_habits():
    habits_def = [
        {"name": "Drink 8 glasses of water", "emoji": "💧", "frequency": "daily"},
        {"name": "Exercise for 30 minutes",  "emoji": "🏃", "frequency": "daily"},
        {"name": "Read for 20 minutes",      "emoji": "📚", "frequency": "daily"},
    ]
    today = date.today()
    habits = []
    for i, hd in enumerate(habits_def):
        habit = {
            "id": int(datetime.now().timestamp() * 1000) + i,
            "name": hd["name"], "emoji": hd["emoji"], "frequency": hd["frequency"],
            "completions": [], "creationDate": today, "order": i, "unlockedTrophies": [],
        }
        for day_ago in range(1, 15):
            d = today - timedelta(days=day_ago)
            if random.random() > 0.3:
                habit["completions"].append(d)
        habits.append(habit)
    return habits

def get_default_state() -> dict:
    tomorrow = date.today() + timedelta(days=1)
    return {
        "habits": generate_initial_habits(),
        "tasks": [
            {"id": 1, "text": "Plan my morning routine",  "done": False, "date": tomorrow.isoformat(), "priority": "high"},
            {"id": 2, "text": "Review today's learnings", "done": False, "date": tomorrow.isoformat(), "priority": "medium"},
        ],
    }


# ─────────────────────────────────────────────
# HABIT LOGIC
# ─────────────────────────────────────────────

def calculate_streaks(habit: dict) -> dict:
    if not habit["completions"]:
        return {"currentStreak": 0, "longestStreak": 0}
    completions = sorted(set(habit["completions"]), reverse=True)
    today = date.today()
    current_streak = 0
    if today in completions:
        current_streak = 1
        last = today
        for d in completions[1:]:
            if last - d == timedelta(days=1):
                current_streak += 1
                last = d
            else:
                break
    longest = 1
    temp = 1
    for i in range(len(completions) - 1):
        if completions[i] - completions[i + 1] == timedelta(days=1):
            temp += 1
        else:
            longest = max(longest, temp)
            temp = 1
    longest = max(longest, temp)
    return {"currentStreak": current_streak, "longestStreak": longest}

def toggle_habit(habit_id: int):
    state = st.session_state.user_state
    today = date.today()
    habit = next((h for h in state["habits"] if h["id"] == habit_id), None)
    if habit:
        if today in habit["completions"]:
            habit["completions"].remove(today)
        else:
            habit["completions"].append(today)
            st.toast(f"✅ '{habit['name']}' completed!")
            daily = [h for h in state["habits"] if h["frequency"] == "daily"]
            if all(today in h["completions"] for h in daily):
                st.balloons()
        save_user_state(st.session_state.username, state)

def generate_calendar_html(habit: dict, year: int, month: int) -> str:
    cal = calendar.Calendar()
    today = date.today()
    creation = habit["creationDate"]
    html = """<style>
    .cal-table{width:100%;border-collapse:collapse;font-size:13px;}
    .cal-th{text-align:center;padding:8px 4px;color:#888;font-weight:600;}
    .cal-td{text-align:center;padding:8px 4px;border-radius:6px;}
    .cal-day-completed{background:#22c55e;color:white;font-weight:600;}
    .cal-day-missed{background:#fee2e2;color:#dc2626;}
    .cal-day-future{color:#ccc;}
    .cal-day-other-month{opacity:0.2;}
    .cal-today{outline:2px solid #22c55e;}
    </style>
    <table class="cal-table"><tr>
    <th class=cal-th>Su</th><th class=cal-th>Mo</th><th class=cal-th>Tu</th>
    <th class=cal-th>We</th><th class=cal-th>Th</th><th class=cal-th>Fr</th>
    <th class=cal-th>Sa</th></tr><tr>"""
    for i, day in enumerate(cal.itermonthdates(year, month)):
        classes = ["cal-td"]
        if day.month != month:
            classes.append("cal-day-other-month")
        else:
            if day in habit["completions"]:
                classes.append("cal-day-completed")
            elif day < today and day >= creation:
                classes.append("cal-day-missed")
            elif day > today:
                classes.append("cal-day-future")
            if day == today:
                classes.append("cal-today")
        html += f'<td class="{" ".join(classes)}">{day.day}</td>'
        if (i + 1) % 7 == 0:
            html += "</tr><tr>"
    html += "</tr></table>"
    return html


# ─────────────────────────────────────────────
# PDF REPORT GENERATOR
# ─────────────────────────────────────────────

def generate_pdf_report(display_name: str, state: dict) -> bytes:
    """Generates a shareable A4 PDF daily report using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

    today    = date.today()
    tomorrow = today + timedelta(days=1)
    buffer   = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm,   bottomMargin=2*cm,
    )

    # Colour palette
    GREEN        = colors.HexColor("#16a34a")
    GREEN_LIGHT  = colors.HexColor("#dcfce7")
    RED_LIGHT    = colors.HexColor("#fee2e2")
    AMBER_LIGHT  = colors.HexColor("#fef3c7")
    GRAY_BG      = colors.HexColor("#f8fafc")
    GRAY_BORDER  = colors.HexColor("#e2e8f0")
    GRAY_TEXT    = colors.HexColor("#64748b")
    DARK         = colors.HexColor("#0f172a")
    WHITE        = colors.white

    # Style helpers
    def ps(name, **kw):
        p = ParagraphStyle(name)
        defaults = dict(fontName="Helvetica", fontSize=10, leading=15, textColor=DARK)
        defaults.update(kw)
        for k, v in defaults.items():
            setattr(p, k, v)
        return p

    s_title   = ps("title",   fontSize=22, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=28)
    s_sub     = ps("sub",     fontSize=11, textColor=GRAY_TEXT, alignment=TA_CENTER, leading=16)
    s_muted   = ps("muted",   fontSize=9,  textColor=GRAY_TEXT, leading=13)
    s_muted_c = ps("mutedc",  fontSize=9,  textColor=GRAY_TEXT, leading=13, alignment=TA_CENTER)
    s_section = ps("section", fontSize=13, fontName="Helvetica-Bold", leading=18)
    s_normal  = ps("normal")
    s_bold    = ps("bold",    fontName="Helvetica-Bold")
    s_center  = ps("center",  alignment=TA_CENTER)
    s_footer  = ps("footer",  fontSize=8,  textColor=GRAY_TEXT, alignment=TA_CENTER)

    story = []

    # ── Header ──────────────────────────────────────
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Fellow Ups", s_title))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph(f"Daily Report — {display_name}", s_sub))
    story.append(Paragraph(f"Generated on {today.strftime('%A, %B %d, %Y')}", s_muted_c))
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=GRAY_BORDER))
    story.append(Spacer(1, 0.5*cm))

    # ── Section 1: Today's Habits ────────────────────
    daily_habits    = sorted([h for h in state["habits"] if h["frequency"] == "daily"], key=lambda x: x.get("order", 0))
    completed_today = [h for h in daily_habits if today in h["completions"]]
    total_h         = len(daily_habits)
    done_h          = len(completed_today)
    pct_h           = int(done_h / total_h * 100) if total_h else 0

    story.append(Paragraph("Today's Habit Check-In", s_section))
    story.append(Spacer(1, 0.2*cm))

    # Summary banner
    banner_bg = GREEN_LIGHT if pct_h == 100 else AMBER_LIGHT
    banner = Table([[
        Paragraph(f"<b>{done_h}/{total_h}</b><br/>Completed",      s_muted_c),
        Paragraph(f"<b>{pct_h}%</b><br/>Completion Rate",          s_muted_c),
        Paragraph(f"<b>{total_h - done_h}</b><br/>Not yet done",   s_muted_c),
    ]], colWidths=["33%", "34%", "33%"])
    banner.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), banner_bg),
        ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
        ("INNERGRID",     (0,0), (-1,-1), 0.5, GRAY_BORDER),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
    ]))
    story.append(banner)
    story.append(Spacer(1, 0.3*cm))

    if daily_habits:
        h_rows = [[
            Paragraph("<b>Habit</b>",   s_muted),
            Paragraph("<b>Streak</b>",  s_muted),
            Paragraph("<b>Status</b>",  s_muted),
        ]]
        h_styles = [
            ("BACKGROUND",    (0,0), (-1,0), GRAY_BG),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, GRAY_BG]),
            ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.5, GRAY_BORDER),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]
        for idx, habit in enumerate(daily_habits):
            streaks = calculate_streaks(habit)
            is_done = today in habit["completions"]
            row_n   = idx + 1
            status  = "<font color='#16a34a'><b>Done</b></font>" if is_done else "<font color='#d97706'><b>Pending</b></font>"
            h_rows.append([
                Paragraph(f"{habit['emoji']} {habit['name']}", s_normal),
                Paragraph(f"Fire {streaks['currentStreak']} days", s_normal),
                Paragraph(status, s_normal),
            ])
            h_styles.append(("BACKGROUND", (2, row_n), (2, row_n), GREEN_LIGHT if is_done else AMBER_LIGHT))

        habit_table = Table(h_rows, colWidths=["55%", "25%", "20%"])
        habit_table.setStyle(TableStyle(h_styles))
        story.append(habit_table)

    story.append(Spacer(1, 0.6*cm))

    # ── Section 2: Today's Task Completion ──────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_BORDER))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Today's Task Completion", s_section))
    story.append(Spacer(1, 0.2*cm))

    def parse_date(v):
        return datetime.fromisoformat(v).date() if isinstance(v, str) else v

    today_tasks   = [t for t in state.get("tasks", []) if parse_date(t["date"]) == today]
    done_tasks    = [t for t in today_tasks if t["done"]]
    undone_tasks  = [t for t in today_tasks if not t["done"]]
    pct_t         = int(len(done_tasks) / len(today_tasks) * 100) if today_tasks else 0

    if not today_tasks:
        story.append(Paragraph("No tasks were scheduled for today.", s_muted))
    else:
        story.append(Paragraph(
            f"Completed <b>{len(done_tasks)}</b> of <b>{len(today_tasks)}</b> tasks ({pct_t}%)",
            s_normal
        ))
        story.append(Spacer(1, 0.2*cm))
        pmap = {"high": "High", "medium": "Medium", "low": "Low"}
        t_rows = [[
            Paragraph("<b>Task</b>",     s_muted),
            Paragraph("<b>Priority</b>", s_muted),
            Paragraph("<b>Status</b>",   s_muted),
        ]]
        t_styles = [
            ("BACKGROUND",    (0,0), (-1,0), GRAY_BG),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, GRAY_BG]),
            ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.5, GRAY_BORDER),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ]
        for idx, task in enumerate(today_tasks):
            is_done = task["done"]
            row_n   = idx + 1
            label   = "<font color='#16a34a'><b>Done</b></font>" if is_done else "<font color='#dc2626'><b>Missed</b></font>"
            txt     = f"<strike>{task['text']}</strike>" if is_done else task["text"]
            t_rows.append([
                Paragraph(txt, s_normal),
                Paragraph(pmap.get(task.get("priority","medium"), "Medium"), s_normal),
                Paragraph(label, s_normal),
            ])
            t_styles.append(("BACKGROUND", (2,row_n), (2,row_n), GREEN_LIGHT if is_done else RED_LIGHT))
        task_table = Table(t_rows, colWidths=["55%", "25%", "20%"])
        task_table.setStyle(TableStyle(t_styles))
        story.append(task_table)

    story.append(Spacer(1, 0.6*cm))

    # ── Section 3: Tomorrow's Task Sheet ────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_BORDER))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(f"Tomorrow's Plan — {tomorrow.strftime('%A, %B %d')}", s_section))
    story.append(Spacer(1, 0.2*cm))

    tmr_tasks = [t for t in state.get("tasks", []) if parse_date(t["date"]) == tomorrow]

    if not tmr_tasks:
        story.append(Paragraph("No tasks planned for tomorrow yet.", s_muted))
    else:
        porder = {"high": 0, "medium": 1, "low": 2}
        tmr_tasks_sorted = sorted(tmr_tasks, key=lambda t: porder.get(t.get("priority","medium"), 1))
        pbg   = {"high": RED_LIGHT, "medium": AMBER_LIGHT, "low": GREEN_LIGHT}
        plabel= {"high": "High",    "medium": "Medium",    "low": "Low"}

        tmr_rows = [[
            Paragraph("<b>#</b>",         s_muted_c),
            Paragraph("<b>Task</b>",      s_muted),
            Paragraph("<b>Priority</b>",  s_muted),
            Paragraph("<b>Done?</b>",     s_muted_c),
        ]]
        tmr_styles = [
            ("BACKGROUND",    (0,0), (-1,0), GRAY_BG),
            ("FONTSIZE",      (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, GRAY_BG]),
            ("BOX",           (0,0), (-1,-1), 0.5, GRAY_BORDER),
            ("INNERGRID",     (0,0), (-1,-1), 0.5, GRAY_BORDER),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING",   (0,0), (-1,-1), 8),
            ("ALIGN",         (0,0), (0,-1), "CENTER"),
            ("ALIGN",         (3,0), (3,-1), "CENTER"),
        ]
        for idx, task in enumerate(tmr_tasks_sorted):
            prio  = task.get("priority", "medium")
            row_n = idx + 1
            tmr_rows.append([
                Paragraph(str(row_n), s_center),
                Paragraph(task["text"], s_normal),
                Paragraph(plabel.get(prio, "Medium"), s_normal),
                Paragraph("[ ]", s_center),
            ])
            tmr_styles.append(("BACKGROUND", (2,row_n), (2,row_n), pbg.get(prio, AMBER_LIGHT)))

        tmr_table = Table(tmr_rows, colWidths=["8%", "57%", "23%", "12%"])
        tmr_table.setStyle(TableStyle(tmr_styles))
        story.append(tmr_table)

    # ── Footer ──────────────────────────────────────
    story.append(Spacer(1, 0.6*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_BORDER))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        f"Fellow Ups — shared by {display_name} on {today.strftime('%d %b %Y')}  |  habit.streamlit.app",
        s_footer
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ─────────────────────────────────────────────
# AUTH UI
# ─────────────────────────────────────────────

def show_auth_page():
    st.markdown("""
    <style>
    .auth-header { text-align: center; padding: 2rem 0 1rem; }
    .auth-header h1 { font-size: 3rem; margin-bottom: 0.2rem; }
    .auth-header p  { color: #888; font-size: 1.1rem; }
    </style>
    <div class="auth-header">
        <h1>🤝 Fellow Ups</h1>
        <p>Build habits. Plan tomorrow. Show up for yourself.</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_signup = st.tabs(["🔐 Sign In", "✨ Create Account"])

    with tab_login:
        st.markdown("#### Welcome back!")
        username = st.text_input("Username", key="login_user", placeholder="your username")
        password = st.text_input("Password", type="password", key="login_pass", placeholder="••••••••")
        if st.button("Sign In", type="primary", use_container_width=True, key="login_btn"):
            if username and password:
                ok, result = login_user(username, password)
                if ok:
                    st.session_state.logged_in    = True
                    st.session_state.username     = username.strip().lower()
                    st.session_state.display_name = result
                    st.session_state.user_state   = load_user_state(st.session_state.username)
                    st.rerun()
                else:
                    st.error(result)
            else:
                st.warning("Please enter your username and password.")

    with tab_signup:
        st.markdown("#### Create your free account")
        new_display = st.text_input("Your Name",          key="reg_display", placeholder="e.g. Rahul")
        new_user    = st.text_input("Choose a Username",  key="reg_user",    placeholder="e.g. rahul123")
        new_pass    = st.text_input("Choose a Password",  type="password", key="reg_pass",  placeholder="min. 6 characters")
        new_pass2   = st.text_input("Confirm Password",   type="password", key="reg_pass2", placeholder="repeat password")
        if st.button("Create Account", type="primary", use_container_width=True, key="reg_btn"):
            if not new_user or not new_pass:
                st.warning("Please fill in all fields.")
            elif new_pass != new_pass2:
                st.error("Passwords do not match.")
            else:
                ok, msg = register_user(new_user, new_pass, new_display)
                if ok:
                    st.success(msg + " Please sign in.")
                else:
                    st.error(msg)


# ─────────────────────────────────────────────
# HABIT SECTION UI
# ─────────────────────────────────────────────

def show_habits_section():
    state    = st.session_state.user_state
    username = st.session_state.username
    today    = date.today()

    daily_habits = sorted(
        [h for h in state["habits"] if h["frequency"] == "daily"],
        key=lambda x: x.get("order", 0),
    )

    if not daily_habits:
        st.info("No daily habits yet. Add one below!")
    else:
        completed = sum(1 for h in daily_habits if today in h["completions"])
        total     = len(daily_habits)
        pct       = completed / total if total else 0
        st.progress(pct, text=f"{completed}/{total} habits done today — {int(pct*100)}%")
        st.markdown("")

        for habit in daily_habits:
            is_done = today in habit["completions"]
            streaks = calculate_streaks(habit)
            cur     = streaks["currentStreak"]
            c1, c2, c3 = st.columns([1, 5, 1])
            with c1:
                st.markdown(f"<p style='font-size:1.8rem;text-align:center;margin:0'>{habit['emoji']}</p>", unsafe_allow_html=True)
            with c2:
                name_display = f"~~{habit['name']}~~" if is_done else f"**{habit['name']}**"
                st.markdown(name_display)
                flame_color = "#f59e0b" if cur > 0 else "#ccc"
                st.markdown(f"<span style='color:{flame_color};font-size:0.85rem'>🔥 {cur}-day streak</span>", unsafe_allow_html=True)
            with c3:
                st.checkbox(
                    "done", value=is_done,
                    key=f"chk_{habit['id']}",
                    label_visibility="collapsed",
                    on_change=toggle_habit,
                    args=(habit["id"],),
                )
            st.divider()

    with st.expander("➕ Add New Habit"):
        with st.form("add_habit_form", clear_on_submit=True):
            col1, col2 = st.columns([3, 1])
            new_name  = col1.text_input("Habit Name", placeholder="e.g. Meditate 10 mins")
            new_emoji = col2.text_input("Emoji",      placeholder="🧘")
            new_freq  = st.selectbox("Frequency", ["daily", "weekly"])
            if st.form_submit_button("Add Habit", type="primary"):
                if new_name and new_emoji:
                    new_habit = {
                        "id": int(datetime.now().timestamp() * 1000),
                        "name": new_name, "emoji": new_emoji, "frequency": new_freq,
                        "completions": [], "creationDate": date.today(),
                        "order": len(state["habits"]), "unlockedTrophies": [],
                    }
                    state["habits"].append(new_habit)
                    save_user_state(username, state)
                    st.rerun()
                else:
                    st.error("Please enter both a name and an emoji.")

    with st.expander("⚙️ Manage Habits"):
        for i, habit in enumerate(sorted(state["habits"], key=lambda h: h.get("order", 0))):
            c1, c2, c3, c4 = st.columns([1, 4, 2, 1])
            c1.markdown(f"<p style='font-size:1.2rem'>{habit['emoji']}</p>", unsafe_allow_html=True)
            c2.write(habit["name"])
            with c3:
                btn_c1, btn_c2 = st.columns(2)
                if i > 0 and btn_c1.button("⬆️", key=f"up_{habit['id']}"):
                    prev = state["habits"][i - 1]
                    habit["order"], prev["order"] = prev.get("order", i-1), habit.get("order", i)
                    save_user_state(username, state)
                    st.rerun()
                if i < len(state["habits"]) - 1 and btn_c2.button("⬇️", key=f"dn_{habit['id']}"):
                    nxt = state["habits"][i + 1]
                    habit["order"], nxt["order"] = nxt.get("order", i+1), habit.get("order", i)
                    save_user_state(username, state)
                    st.rerun()
            with c4:
                with st.popover("✏️"):
                    edited_name  = st.text_input("Name",  value=habit["name"],  key=f"en_{habit['id']}")
                    edited_emoji = st.text_input("Emoji", value=habit["emoji"], key=f"ee_{habit['id']}")
                    if st.button("Save", key=f"sv_{habit['id']}", type="primary"):
                        habit["name"] = edited_name
                        habit["emoji"] = edited_emoji
                        save_user_state(username, state)
                        st.rerun()
                    if st.button("🗑️ Delete", key=f"dl_{habit['id']}"):
                        state["habits"] = [h for h in state["habits"] if h["id"] != habit["id"]]
                        save_user_state(username, state)
                        st.rerun()


# ─────────────────────────────────────────────
# TOMORROW'S TASKS SECTION UI
# ─────────────────────────────────────────────

def show_tasks_section():
    state    = st.session_state.user_state
    username = st.session_state.username
    tomorrow = date.today() + timedelta(days=1)

    def parse_date(v):
        return datetime.fromisoformat(v).date() if isinstance(v, str) else v

    tomorrow_tasks = [t for t in state.get("tasks", []) if parse_date(t["date"]) == tomorrow]

    st.markdown(f"**{tomorrow.strftime('%A, %b %d')}**")
    priority_colors = {"high": "#ef4444", "medium": "#f59e0b", "low": "#22c55e"}

    if not tomorrow_tasks:
        st.info("No tasks planned yet. Add one below!")
    else:
        done_count = sum(1 for t in tomorrow_tasks if t["done"])
        total      = len(tomorrow_tasks)
        st.progress(done_count / total if total else 0, text=f"{done_count}/{total} tasks planned")
        st.markdown("")

        for task in tomorrow_tasks:
            c1, c2, c3 = st.columns([1, 7, 1])
            with c1:
                p_color = priority_colors.get(task.get("priority", "medium"), "#888")
                st.markdown(f"<div style='width:10px;height:10px;border-radius:50%;background:{p_color};margin-top:14px'></div>", unsafe_allow_html=True)
            with c2:
                text_style = "text-decoration:line-through;color:#aaa;" if task["done"] else ""
                st.markdown(f"<p style='{text_style}margin:8px 0'>{task['text']}</p>", unsafe_allow_html=True)
            with c3:
                def toggle_task(tid=task["id"]):
                    for t in state["tasks"]:
                        if t["id"] == tid:
                            t["done"] = not t["done"]
                    save_user_state(username, state)
                st.checkbox(
                    "done", value=task["done"],
                    key=f"task_{task['id']}",
                    label_visibility="collapsed",
                    on_change=toggle_task,
                )
            with st.popover("⋯", help="Edit/Delete"):
                new_text = st.text_input("Task", value=task["text"], key=f"tt_{task['id']}")
                new_prio = st.selectbox("Priority", ["high", "medium", "low"],
                                        index=["high","medium","low"].index(task.get("priority","medium")),
                                        key=f"tp_{task['id']}")
                if st.button("Save", key=f"ts_{task['id']}", type="primary"):
                    task["text"]     = new_text
                    task["priority"] = new_prio
                    save_user_state(username, state)
                    st.rerun()
                if st.button("🗑️ Delete", key=f"td_{task['id']}"):
                    state["tasks"] = [t for t in state["tasks"] if t["id"] != task["id"]]
                    save_user_state(username, state)
                    st.rerun()

    st.markdown("---")
    with st.form("add_task_form", clear_on_submit=True):
        new_task_text = st.text_input("New task for tomorrow", placeholder="e.g. Prepare meeting notes")
        new_prio      = st.selectbox("Priority", ["high", "medium", "low"])
        if st.form_submit_button("Add Task ➕", type="primary"):
            if new_task_text.strip():
                new_task = {
                    "id":       int(datetime.now().timestamp() * 1000),
                    "text":     new_task_text.strip(),
                    "done":     False,
                    "date":     tomorrow.isoformat(),
                    "priority": new_prio,
                }
                state.setdefault("tasks", []).append(new_task)
                save_user_state(username, state)
                st.rerun()
            else:
                st.warning("Task cannot be empty.")


# ─────────────────────────────────────────────
# STATISTICS SECTION
# ─────────────────────────────────────────────

def show_statistics():
    state  = st.session_state.user_state
    today  = date.today()
    habits = state["habits"]

    if not habits:
        st.info("Complete some habits to see statistics!")
        return

    total_completions = sum(len(h["completions"]) for h in habits)
    s7_done = s7_total = s30_done = s30_total = 0
    habit_rates = []

    for habit in habits:
        creation = habit["creationDate"]
        for i in range(30):
            d = today - timedelta(days=i)
            if d >= creation:
                if i < 7:
                    s7_total += 1
                    if d in habit["completions"]: s7_done += 1
                s30_total += 1
                if d in habit["completions"]: s30_done += 1
        days   = min(30, (today - creation).days + 1)
        recent = len([c for c in habit["completions"] if c >= today - timedelta(days=30)])
        habit_rates.append({**habit, "rate": (recent / days * 100) if days else 0})

    c1, c2, c3 = st.columns(3)
    c1.metric("7-Day Rate",        f"{s7_done/s7_total*100:.0f}%"   if s7_total  else "N/A")
    c2.metric("30-Day Rate",       f"{s30_done/s30_total*100:.0f}%" if s30_total else "N/A")
    c3.metric("Total Completions", total_completions)

    if habit_rates:
        habit_rates.sort(key=lambda x: x["rate"], reverse=True)
        best, worst = habit_rates[0], habit_rates[-1]
        st.markdown("---")
        bc, wc = st.columns(2)
        with bc:
            st.markdown("**✅ Best Habit**")
            st.markdown(f"{best['emoji']} {best['name']} — {best['rate']:.0f}%")
        with wc:
            st.markdown("**💪 Needs Work**")
            st.markdown(f"{worst['emoji']} {worst['name']} — {worst['rate']:.0f}%")


# ─────────────────────────────────────────────
# TROPHIES SECTION
# ─────────────────────────────────────────────

def show_trophies():
    state = st.session_state.user_state
    trophy_defs = [
        {"id": "s3",   "name": "3-Day Streak",    "icon": "🥉", "check": lambda h, g: calculate_streaks(h)["longestStreak"] >= 3},
        {"id": "s7",   "name": "7-Day Streak",    "icon": "🥈", "check": lambda h, g: calculate_streaks(h)["longestStreak"] >= 7},
        {"id": "s30",  "name": "30-Day Streak",   "icon": "🥇", "check": lambda h, g: calculate_streaks(h)["longestStreak"] >= 30},
        {"id": "c100", "name": "100 Completions", "icon": "💯", "check": lambda h, g: g["total"] >= 100},
    ]
    total  = sum(len(h["completions"]) for h in state["habits"])
    earned = {t["id"] for t in trophy_defs for h in state["habits"] if t["check"](h, {"total": total})}

    cols = st.columns(4)
    for i, t in enumerate(trophy_defs):
        style = "" if t["id"] in earned else "opacity:0.25;filter:grayscale(100%)"
        cols[i].markdown(f"""
        <div style="text-align:center;{style}">
            <p style="font-size:2.5rem;margin:0">{t['icon']}</p>
            <p style="font-size:0.85rem"><strong>{t['name']}</strong></p>
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# DETAIL DIALOG
# ─────────────────────────────────────────────

@st.dialog("Habit Details")
def show_detail_dialog(habit_id: int):
    state = st.session_state.user_state
    habit = next((h for h in state["habits"] if h["id"] == habit_id), None)
    if not habit:
        st.error("Habit not found.")
        return

    streaks = calculate_streaks(habit)
    st.markdown(f"<h2 style='text-align:center'>{habit['emoji']} {habit['name']}</h2>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.metric("🔥 Current Streak", f"{streaks['currentStreak']} days")
    c2.metric("⭐ Longest Streak",  f"{streaks['longestStreak']} days")
    st.markdown("---")
    st.subheader("Progress Calendar")

    key = f"view_date_{habit_id}"
    if key not in st.session_state:
        st.session_state[key] = date.today()

    nav1, nav2, nav3 = st.columns([1, 2, 1])
    if nav1.button("◀️ Prev"):
        st.session_state[key] = (st.session_state[key].replace(day=1) - timedelta(days=1))
    nav2.markdown(f"<h4 style='text-align:center'>{st.session_state[key].strftime('%B %Y')}</h4>", unsafe_allow_html=True)
    if nav3.button("Next ▶️"):
        st.session_state[key] = (st.session_state[key].replace(day=28) + timedelta(days=4)).replace(day=1)

    st.markdown(generate_calendar_html(habit, st.session_state[key].year, st.session_state[key].month), unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    show_auth_page()
    st.stop()

state        = st.session_state.user_state
username     = st.session_state.username
display_name = st.session_state.display_name

# ── Header bar ──────────────────────────────
header_col, report_col, logout_col = st.columns([5, 2, 1])

with header_col:
    st.markdown(
        f"## 🤝 Fellow Ups &nbsp; <span style='font-size:1rem;color:#888'>Hi, {display_name}!</span>",
        unsafe_allow_html=True,
    )

with report_col:
    if st.button("📄 Download Daily Report", use_container_width=True, help="Generate a PDF summary to share with your fellows"):
        with st.spinner("Building your report..."):
            try:
                pdf_bytes = generate_pdf_report(display_name, state)
                filename  = f"fellowups_{username}_{date.today().isoformat()}.pdf"
                st.download_button(
                    label="⬇️ Save PDF now",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True,
                )
                st.success("Report ready! Click above to save.")
            except Exception as e:
                st.error(f"Could not generate PDF: {e}")

with logout_col:
    if st.button("Sign Out", type="secondary"):
        for key in ["logged_in", "username", "display_name", "user_state"]:
            st.session_state.pop(key, None)
        st.rerun()

st.markdown("---")

# ── Main layout ─────────────────────────────
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🎯 Today's Habits")
    show_habits_section()

with right_col:
    st.subheader("📋 Tomorrow's Tasks")
    show_tasks_section()

st.markdown("---")

# ── Bottom tabs ──────────────────────────────
tab_stats, tab_trophies = st.tabs(["📊 Statistics", "🏆 Trophy Shelf"])
with tab_stats:
    show_statistics()
with tab_trophies:
    show_trophies()

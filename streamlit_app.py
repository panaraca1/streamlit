def generate_pdf_report(completed_habits, completed_tasks, planned_tasks):
    """Uses reportlab to generate a PDF report in memory."""
    buffer = io.BytesIO()
    # Reduced margins slightly to ensure content fits
    doc = SimpleDocTemplate(buffer, pagesize=(8.5 * inch, 11 * inch), topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    story = []
    
    # Title
    today = get_today()
    tomorrow = today + timedelta(days=1)
    title = f"Daily Report - {today.strftime('%A, %B %d, %Y')}"
    story.append(Paragraph(title, styles['h1']))
    story.append(Spacer(1, 0.25 * inch))

    # --- Habits Completed Section ---
    story.append(Paragraph("✅ Habits Completed Today", styles['h2']))
    if completed_habits:
        habit_list_items = []
        for habit in completed_habits:
            # Note: Standard ReportLab fonts do not support Emojis. 
            # They may appear as boxes unless you register a custom TTF font.
            p = Paragraph(f"{habit['emoji']} {habit['name']}", styles['Normal'])
            habit_list_items.append(ListItem(p, bulletColor=colors.green))
        
        # Wrap the items in a ListFlowable
        habit_list = ListFlowable(habit_list_items, bulletType='bullet', leftIndent=20)
        story.append(habit_list)
    else:
        story.append(Paragraph("<i>No habits completed today.</i>", styles['Italic']))
    story.append(Spacer(1, 0.25 * inch))

    # --- Tasks Completed Section ---
    story.append(Paragraph("✅ Tasks Completed Today", styles['h2']))
    if completed_tasks:
        task_list_items = []
        for task in completed_tasks:
            p = Paragraph(task['text'], styles['Normal'])
            task_list_items.append(ListItem(p, bulletColor=colors.green))
        
        completed_task_list = ListFlowable(task_list_items, bulletType='bullet', leftIndent=20)
        story.append(completed_task_list)
    else:
        story.append(Paragraph("<i>No tasks completed today.</i>", styles['Italic']))
    story.append(Spacer(1, 0.25 * inch))

    # --- Plan for Tomorrow Section ---
    story.append(Paragraph(f"🗓️ Plan for Tomorrow ({tomorrow.strftime('%Y-%m-%d')})", styles['h2']))
    if planned_tasks:
        planned_list_items = []
        for task in planned_tasks:
            p = Paragraph(f"{task['text']} (Priority: {task['priority']})", styles['Normal'])
            # Using a circle/bullet since PDF checkboxes are complex to draw manually here
            planned_list_items.append(ListItem(p, bulletColor=colors.black))
        
        planned_task_list = ListFlowable(planned_list_items, bulletType='bullet', leftIndent=20)
        story.append(planned_task_list)
    else:
        story.append(Paragraph("<i>No tasks planned for tomorrow.</i>", styles['Italic']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer

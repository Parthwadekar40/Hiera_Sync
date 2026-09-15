"""Build HieraSync AI — Review Seminar-I presentation (.pptx)."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn
import os

BASE = os.path.dirname(__file__)
CHARTS = os.path.join(BASE, "charts")

# ---------------- palette ----------------
NAVY   = RGBColor(0x0B, 0x1E, 0x3B)
NAVY2  = RGBColor(0x14, 0x33, 0x63)
INDIGO = RGBColor(0x4F, 0x46, 0xE5)
CYAN   = RGBColor(0x06, 0xB6, 0xD4)
GOLD   = RGBColor(0xF5, 0x9E, 0x0B)
LIGHT  = RGBColor(0xF3, 0xF6, 0xFC)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
DARK   = RGBColor(0x1E, 0x29, 0x3B)
MUTED  = RGBColor(0x64, 0x74, 0x8B)
GREEN  = RGBColor(0x10, 0xB9, 0x81)
RED    = RGBColor(0xEF, 0x44, 0x44)
SOFT   = RGBColor(0xEE, 0xF2, 0xFF)
BORDER = RGBColor(0xCB, 0xD5, 0xE1)
GOLD_D = RGBColor(0xB4, 0x53, 0x09)

TOTAL_SLIDES = 30
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]

# ---------------- helpers ----------------
def set_bg(slide, color):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color

def new_slide(bg=LIGHT):
    s = prs.slides.add_slide(BLANK)
    set_bg(s, bg)
    return s

def add_shape(slide, shape_type, l, t, w, h, fill=None, line=None,
              line_w=1.0, radius=None):
    shp = slide.shapes.add_shape(shape_type, Inches(l), Inches(t),
                                 Inches(w), Inches(h))
    shp.shadow.inherit = False
    if fill is not None:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    else:
        shp.fill.background()
    if line is not None:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    else:
        shp.line.fill.background()
    if radius is not None:
        try:
            shp.adjustments[0].value = radius
        except Exception:
            pass
    return shp

def tf_of(shp, anchor=MSO_ANCHOR.TOP, wrap=True, m=0.08):
    tf = shp.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    tf.margin_left = Inches(m)
    tf.margin_right = Inches(m)
    tf.margin_top = Inches(0.04)
    tf.margin_bottom = Inches(0.04)
    return tf

def para(tf, text="", size=12, bold=False, color=DARK, align=PP_ALIGN.LEFT,
         first=False, space_after=4, space_before=0, italic=False):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(space_after)
    p.space_before = Pt(space_before)
    p.alignment = align
    if text:
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = "Calibri"
        r.font.italic = italic
    return p

def mixed_para(tf, parts, align=PP_ALIGN.LEFT, first=False,
               space_after=4, size=12):
    """parts = list of (text, bold, color, size?)"""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.space_after = Pt(space_after)
    p.alignment = align
    for part in parts:
        text, bold, color = part[0], part[1], part[2]
        sz = part[3] if len(part) > 3 else size
        r = p.add_run()
        r.text = text
        r.font.size = Pt(sz)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = "Calibri"
    return p

def bullets(tf, items, size=12.5, color=DARK, bullet="▪  ", gap=5, first_text=None):
    started = False
    for it in items:
        if isinstance(it, tuple):
            head, rest = it
            p = tf.paragraphs[0] if not started else tf.add_paragraph()
            p.space_after = Pt(gap)
            p.alignment = PP_ALIGN.LEFT
            for txt, b, c in [(bullet, True, INDIGO), (head, True, DARK), (rest, False, color)]:
                r = p.add_run()
                r.text = txt
                r.font.size = Pt(size)
                r.font.bold = b
                r.font.color.rgb = c
                r.font.name = "Calibri"
        else:
            p = tf.paragraphs[0] if not started else tf.add_paragraph()
            p.space_after = Pt(gap)
            p.alignment = PP_ALIGN.LEFT
            for txt, b, c in [(bullet, True, INDIGO), (it, False, color)]:
                r = p.add_run()
                r.text = txt
                r.font.size = Pt(size)
                r.font.bold = b
                r.font.color.rgb = c
                r.font.name = "Calibri"
        started = True

def connector(slide, x1, y1, x2, y2, color=INDIGO, w=2.0, arrow=True,
              ctype=MSO_CONNECTOR.STRAIGHT):
    conn = slide.shapes.add_connector(ctype, Inches(x1), Inches(y1),
                                      Inches(x2), Inches(y2))
    conn.shadow.inherit = False
    conn.line.color.rgb = color
    conn.line.width = Pt(w)
    if arrow:
        try:
            ln = conn.line._get_or_add_ln()
            for tag in ("a:tailEnd",):
                for child in ln.findall(qn(tag)):
                    ln.remove(child)
            tail = ln.makeelement(qn("a:tailEnd"),
                                  {"type": "triangle", "w": "med", "len": "med"})
            ln.append(tail)
        except Exception:
            pass
    return conn

def label(slide, l, t, w, h, text, size=9, color=MUTED,
          align=PP_ALIGN.CENTER, bold=False, bg=None):
    shp = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h,
                    fill=bg, radius=0.3)
    tf = tf_of(shp, anchor=MSO_ANCHOR.MIDDLE, m=0.03)
    para(tf, text, size=size, bold=bold, color=color, align=align, first=True,
         space_after=0)
    return shp

def box_text(slide, l, t, w, h, title, body=None, fill=WHITE, accent=None,
             title_size=12, body_size=10.5, tcolor=DARK, center=False,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, title_color=None):
    shp = add_shape(slide, shape, l, t, w, h, fill=fill, line=BORDER,
                    line_w=1.0, radius=0.08)
    if accent is not None:
        bar = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, l, t, 0.09, h,
                        fill=accent, radius=0.5)
    tf = tf_of(shp, anchor=MSO_ANCHOR.MIDDLE if center else MSO_ANCHOR.TOP, m=0.12)
    al = PP_ALIGN.CENTER if center else PP_ALIGN.LEFT
    para(tf, title, size=title_size, bold=True,
         color=title_color or NAVY, align=al, first=True, space_after=3)
    if body:
        para(tf, body, size=body_size, color=tcolor, align=al, space_after=0)
    return shp

def header(slide, kicker, title, num):
    add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 0, 13.333, 1.22, fill=NAVY)
    add_shape(slide, MSO_SHAPE.RECTANGLE, 0, 1.22, 13.333, 0.045, fill=GOLD)
    tb = add_shape(slide, MSO_SHAPE.RECTANGLE, 0.45, 0.12, 11.0, 1.0, fill=None)
    tf = tf_of(tb, m=0.0)
    para(tf, kicker.upper(), size=10.5, bold=True, color=CYAN, first=True,
         space_after=1)
    para(tf, title, size=25, bold=True, color=WHITE, space_after=0)
    pill = add_shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 12.05, 0.32, 0.85, 0.55,
                     fill=NAVY2, line=CYAN, line_w=1.25, radius=0.45)
    tfp = tf_of(pill, anchor=MSO_ANCHOR.MIDDLE, m=0.02)
    para(tfp, f"{num:02d}", size=15, bold=True, color=WHITE,
         align=PP_ALIGN.CENTER, first=True, space_after=0)

def footer(slide, left="HieraSync AI  •  Review Seminar – I",
           right="CSE (AI & ML), SBJIT Nagpur"):
    tb = add_shape(slide, MSO_SHAPE.RECTANGLE, 0.45, 7.06, 12.43, 0.35, fill=None)
    tf = tf_of(tb, m=0.0)
    p = tf.paragraphs[0]
    p.space_after = Pt(0)
    for txt, b in [(left + "      ", False), (right, False)]:
        r = p.add_run()
        r.text = txt
        r.font.size = Pt(8.5)
        r.font.bold = b
        r.font.color.rgb = MUTED
        r.font.name = "Calibri"

def content_slide(kicker, title, num):
    s = new_slide(LIGHT)
    header(s, kicker, title, num)
    footer(s)
    return s

def notes(slide, text):
    try:
        slide.notes_slide.placeholders[1].text = text
    except Exception:
        pass

def style_table(table, col_widths, header_fill=NAVY, font_size=10.5,
                header_size=11):
    table.horz_banding = False
    table.first_row = False
    for i, w in enumerate(col_widths):
        table.columns[i].width = Inches(w)
    for r in range(len(table.rows)):
        for c in range(len(table.columns)):
            cell = table.cell(r, c)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            if r == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = header_fill
            else:
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if r % 2 == 1 else SOFT
            for p in cell.text_frame.paragraphs:
                p.space_after = Pt(1)
                p.space_before = Pt(1)
                for run in p.runs:
                    run.font.size = Pt(header_size if r == 0 else font_size)
                    run.font.bold = (r == 0)
                    run.font.color.rgb = WHITE if r == 0 else DARK
                    run.font.name = "Calibri"
            # borders
            try:
                tcPr = cell._tc.get_or_add_tcPr()
                for edge in ("L", "R", "T", "B"):
                    tag = qn(f"a:ln{edge}")
                    for child in tcPr.findall(tag):
                        tcPr.remove(child)
                    ln = tcPr.makeelement(tag, {"w": "12700"})
                    solid = tcPr.makeelement(qn("a:solidFill"), {})
                    srgb = tcPr.makeelement(qn("a:srgbClr"), {"val": "CBD5E1"})
                    solid.append(srgb)
                    ln.append(solid)
                    tcPr.append(ln)
            except Exception:
                pass

def make_table(slide, l, t, w, h, data, col_widths, **kw):
    gframe = slide.shapes.add_table(len(data), len(data[0]),
                                    Inches(l), Inches(t), Inches(w), Inches(h))
    table = gframe.table
    for r, row in enumerate(data):
        for c, val in enumerate(row):
            table.cell(r, c).text = val
    style_table(table, col_widths, **kw)
    return gframe

# ================================================================
# SLIDE 1 — TITLE
# ================================================================
s = new_slide(NAVY)
add_shape(s, MSO_SHAPE.OVAL, 10.6, -2.2, 5.0, 5.0, fill=NAVY2)
add_shape(s, MSO_SHAPE.OVAL, -2.0, 4.6, 4.6, 4.6, fill=NAVY2)
add_shape(s, MSO_SHAPE.RECTANGLE, 0.55, 0.45, 1.4, 0.06, fill=GOLD)
pill = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.55, 0.75, 6.6, 0.5,
                 fill=None, line=CYAN, line_w=1.5, radius=0.5)
tf = tf_of(pill, anchor=MSO_ANCHOR.MIDDLE, m=0.15)
para(tf, "REVIEW SEMINAR – I  •  VII SEMESTER  •  MAJOR PROJECT", size=11.5,
     bold=True, color=CYAN, align=PP_ALIGN.LEFT, first=True, space_after=0)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.45, 8.2, 2.6, fill=None)
tf = tf_of(tb, m=0.05)
para(tf, "HieraSync AI", size=54, bold=True, color=WHITE, first=True,
     space_after=2)
para(tf, "Smart Academic Workflow & Event Management System", size=19,
     bold=False, color=GOLD, space_after=6)
para(tf, "One role-aware workspace for tasks, approvals, events, notifications, analytics and AI assistance.",
     size=12.5, color=RGBColor(0xC7, 0xD2, 0xFE), space_after=0)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.55, 4.35, 8.0, 1.0, fill=None)
tf = tf_of(tb, m=0.0)
para(tf, "Department of Computer Science & Engineering (Artificial Intelligence & Machine Learning)",
     size=12.5, bold=True, color=WHITE, first=True, space_after=2)
para(tf, "S. B. Jain Institute of Technology, Management & Research, Nagpur  •  Academic Year 2026–27",
     size=11.5, color=RGBColor(0x94, 0xA3, 0xB8), space_after=0)
for i, (role, val) in enumerate([
        ("PRESENTED BY", "[Your Name]  •  Roll No: [__]  •  VII Sem, CSE (AI & ML)"),
        ("GUIDED BY", "[Guide Name], [Designation], Dept. of CSE (AI & ML)"),
        ("PROJECT REPOSITORY", "github.com / Parthwadekar40 / Hiera_Sync")]):
    y = 5.5 + i * 0.62
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.55, y, 7.9, 0.52,
              fill=NAVY2, line=BORDER, line_w=0.75, radius=0.25)
    tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.75, y + 0.04, 7.5, 0.44, fill=None)
    tf = tf_of(tb, anchor=MSO_ANCHOR.MIDDLE, m=0.0)
    mixed_para(tf, [(role + "   ", True, CYAN, 10.5), (val, False, WHITE, 11.5)],
               first=True, space_after=0)
card = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 9.35, 1.5, 3.45, 4.4,
                 fill=WHITE, radius=0.06)
tf = tf_of(card, anchor=MSO_ANCHOR.TOP, m=0.22)
para(tf, "AT A GLANCE", size=11, bold=True, color=INDIGO, first=True,
     space_after=6, align=PP_ALIGN.LEFT)
for big, small in [("17+", "REST API modules (FastAPI)"),
                   ("13+", "Web pages (React + TS)"),
                   ("10", "Role-based user roles"),
                   ("2-stage", "HOD → Principal approvals"),
                   ("AI", "Risk engine + chat + reports")]:
    mixed_para(tf, [(big + "  ", True, NAVY, 15), (small, False, MUTED, 11)],
               space_after=7)
notes(s, "Good morning respected reviewers. I present HieraSync AI, our major project: a smart academic workflow and event management system built for our department. This Review Seminar-I covers our progress so far — the problem, design, technology and the modules already implemented and running.")

# ================================================================
# SLIDE 2 — ROADMAP
# ================================================================
s = content_slide("Flow of presentation", "Presentation Roadmap", 2)
items = [("01", "Title"), ("02", "Introduction"), ("03", "Problem & Objectives"),
         ("04", "Literature Survey"), ("05", "System Design"),
         ("06", "Technology Used"), ("07", "Developed Modules"),
         ("08", "Advantages & Uses"), ("09", "References"), ("10", "Conclusion")]
for i, (no, cap) in enumerate(items):
    r, c = divmod(i, 5)
    x = 0.45 + c * 2.57
    y = 1.62 + r * 2.35
    card = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, 2.32, 2.0,
                     fill=WHITE, line=BORDER, line_w=1.0, radius=0.08)
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, 2.32, 0.62,
              fill=INDIGO if i % 2 == 0 else NAVY, radius=0.08)
    tf = tf_of(card, anchor=MSO_ANCHOR.MIDDLE, m=0.12)
    para(tf, no, size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER,
         first=True, space_after=10)
    para(tf, cap, size=13.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER,
         space_after=0)
label(s, 0.45, 6.42, 12.43, 0.5,
      "Review Seminar – I reflects ACTUAL implementation progress — every module shown today is designed, coded and running in our repository.",
      size=10.5, color=NAVY, bold=True, bg=RGBColor(0xFE, 0xF3, 0xC7))
notes(s, "I will walk through ten sections, from the problem to design, technology, working modules, advantages, references and conclusion.")

# ================================================================
# SLIDE 3 — INTRODUCTION
# ================================================================
s = content_slide("1 · Introduction", "Introduction — What is HieraSync?", 3)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.55, 7.6, 5.2, fill=None)
tf = tf_of(tb, m=0.0)
bullets(tf, [
    ("A full-stack web platform ", "that centralizes departmental work — tasks, events, approvals, notifications, goals and reports — in one place."),
    ("Role-aware by design: ", "Principal → HOD → Faculty → Staff/Students, with 10 distinct roles and access rules."),
    ("Built for CSE (AI & ML), SBJIT Nagpur, ", "and generalizable to any department or institute."),
    ("Real engineering scale: ", "17 REST API modules, 13+ UI pages, JWT security, scheduled reminders and an AI assistant."),
    ("One-line value: ", "it replaces registers, scattered WhatsApp threads and Excel sheets with a single accountable workspace."),
], size=13)
box_text(s, 8.5, 1.55, 3.9, 1.5, "Domain", "Web-based Academic Workflow Automation + Applied AI (heuristic risk scoring, summarization, report generation).", accent=INDIGO)
box_text(s, 8.5, 3.25, 3.9, 1.5, "Users", "Principal, HOD, Faculty, TAs, Lab Assistants, Staff, Students & Student Representatives.", accent=CYAN)
box_text(s, 8.5, 4.95, 3.9, 1.5, "Deployment", "Cloud-ready: React SPA + FastAPI services + Firebase (Firestore, Auth, Storage).", accent=GOLD)
notes(s, "HieraSync is a role-aware web platform for our department. It brings tasks, approvals, events and analytics together, with AI assistance for prioritization and risk alerts.")

# ================================================================
# SLIDE 4 — BACKGROUND & MOTIVATION
# ================================================================
s = content_slide("1 · Introduction", "Background & Motivation", 4)
probs = [("Approvals get lost", "Paper forms and chat messages have no trail — requests stall for days with no visibility."),
         ("No workload view", "HODs cannot see who is overloaded; work distribution is guesswork."),
         ("Manual reporting", "Monthly/NAAC reports are assembled by hand from Excel sheets — slow and error-prone."),
         ("Missed deadlines", "No reminders, no risk signals — tasks slip until it is too late.")]
for i, (t, b) in enumerate(probs):
    box_text(s, 0.45 + i * 3.19, 1.6, 2.94, 2.2, t, b, accent=[RED, GOLD, INDIGO, CYAN][i])
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 4.15, 12.35, 2.6, fill=None)
tf = tf_of(tb, m=0.0)
bullets(tf, [
    ("Motivation: ", "digitize the hierarchy itself — every request flows through the correct authority with timestamps, comments and status."),
    ("Opportunity: ", "cloud + AI can automate prioritization, reminders and delay-risk alerts at near-zero operational cost."),
    ("Outcome: ", "faster decisions, fair workload distribution and accreditation-ready digital records (NAAC/NBA documentation)."),
], size=12)
label(s, 0.45, 6.05, 12.43, 0.6,
      "2025–26 evidence: a UNSW pilot cut admin workload 60% with AI agents  •  2026 surveys: Asana AI leads risk detection but paywalls AI at $10.99+/user/mo — academic teams need a low-cost alternative.",
      size=10, color=NAVY, bold=True, bg=RGBColor(0xFE, 0xF3, 0xC7))
notes(s, "Departments still run on paper and chat apps. That causes lost approvals, invisible workloads and painful manual reporting. HieraSync digitizes the hierarchy itself. Recent 2025-26 studies back this: AI agents cut admin workload by up to sixty percent in pilots.")

# ================================================================
# SLIDE 5 — PROBLEM STATEMENT
# ================================================================
s = content_slide("2 · Problem Statement & Objectives", "Problem Statement", 5)
ps = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.45, 1.55, 12.43, 1.5,
               fill=NAVY, radius=0.06)
tf = tf_of(ps, anchor=MSO_ANCHOR.MIDDLE, m=0.3)
para(tf, "\u201C Academic departments lack a unified, role-aware digital system to assign, track, approve and analyse teaching and administrative work — causing delays, opacity and overload. \u201D",
     size=15.5, bold=False, color=WHITE, align=PP_ALIGN.CENTER, first=True,
     space_after=0, italic=True)
cards = [("Fragmented\ncommunication", "Tasks live across WhatsApp, mail and memory — nothing is searchable or tracked.", INDIGO),
         ("No accountability trail", "Who approved what, and when? Paper leaves no audit log.", CYAN),
         ("Approval bottleneck", "Single-channel, manual HOD → Principal routing takes days.", GOLD),
         ("Zero data insight", "No analytics on load, delays or performance for decisions.", GREEN)]
for i, (t, b, acc) in enumerate(cards):
    box_text(s, 0.45 + i * 3.19, 3.4, 2.94, 2.9, t, b, accent=acc,
             title_size=13, center=False)
notes(s, "Our formal problem statement: departments lack a unified role-aware system for academic work. Four concrete pains follow from this — fragmentation, no audit trail, slow approvals and zero analytics.")

# ================================================================
# SLIDE 6 — OBJECTIVES
# ================================================================
s = content_slide("2 · Problem Statement & Objectives", "Objectives & Scope", 6)
objs = [("O1 — Centralized role-based workspace",
         "Tasks, events, approvals, documents, goals and notifications in one secure portal."),
        ("O2 — Two-stage digital approvals",
         "Structured HOD → Principal workflow with comments, history and status tracking."),
        ("O3 — Automation of follow-ups",
         "Notification center, scheduled daily reminders and deadline alerts — no manual chasing."),
        ("O4 — AI assistance",
         "Deadline-risk prediction, priority scoring, conversational assistant and auto-generated reports."),
        ("O5 — Analytics & one-click reports",
         "Dashboards, faculty performance views and exportable department summaries.")]
for i, (t, b) in enumerate(objs):
    y = 1.55 + i * 0.98
    add_shape(s, MSO_SHAPE.OVAL, 0.55, y + 0.12, 0.52, 0.52, fill=INDIGO)
    tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.55, y + 0.12, 0.52, 0.52, fill=None)
    tf = tf_of(tb, anchor=MSO_ANCHOR.MIDDLE, m=0.0)
    para(tf, str(i + 1), size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER,
         first=True, space_after=0)
    tb = add_shape(s, MSO_SHAPE.RECTANGLE, 1.3, y, 7.6, 0.9, fill=None)
    tf = tf_of(tb, m=0.0)
    mixed_para(tf, [(t + "  ", True, NAVY, 12.5), (b, False, DARK, 12)],
               first=True, space_after=0)
box_text(s, 9.3, 1.55, 3.55, 2.5, "Scope (Review-I)", "Department-level web deployment: CSE (AI & ML). Web-first responsive UI; Firebase cloud backend; heuristic AI (no GPU servers).", accent=GREEN)
box_text(s, 9.3, 4.25, 3.55, 2.2, "Success criteria", "All 5 objectives demonstrable live: login as each role → assign → approve → notify → analyse.", accent=GOLD)
notes(s, "Five measurable objectives guide the build — workspace, approvals, automation, AI and analytics. Scope is department-level for Review-I, with institute scale-up planned.")

# ================================================================
# SLIDE 7 — LITERATURE SURVEY (existing systems)
# ================================================================
s = content_slide("3 · Literature Survey", "Existing Systems — Comparative Study", 7)
data = [
    ["System / Category", "Strengths", "Limitations found"],
    ["Manual registers,\nExcel, WhatsApp", "Zero cost; familiar", "No tracking or audit trail; data loss; zero analytics"],
    ["Traditional college ERPs", "Cover fees / attendance / records", "Costly, rigid, weak faculty task-workflows; poor UX"],
    ["AI PM suites 2026\n(Asana, Monday,\nClickUp, Notion AI)", "Risk detection, summaries,\nworkflow automation", "AI paywalled $7–20/user/mo;\ncorporate-generic: no academic\nhierarchy or dept. analytics"],
    ["Google Workspace\n(Mail, Calendar, Drive)", "Good collaboration", "Scattered tools; no RBAC workflows or approval audit"],
    ["Moodle / LMS platforms", "Strong learning content", "Student-centric; no faculty admin / approval workflows"],
]
make_table(s, 0.45, 1.55, 12.43, 4.6, data, [3.0, 4.4, 5.03], font_size=10.5)
label(s, 0.45, 6.3, 12.43, 0.55,
      "Inference (incl. 2026 app surveys): nothing combines academic hierarchy + workflows + approvals + analytics + AI in one low-cost stack — the gap HieraSync targets.",
      size=11, color=NAVY, bold=True, bg=RGBColor(0xFE, 0xF3, 0xC7))
notes(s, "We surveyed five categories. Each solves part of the problem, but none combines academic hierarchy, approvals, analytics and AI in one low-cost system. That is our gap.")

# ================================================================
# SLIDE 8 — LITERATURE SURVEY (papers + gaps)
# ================================================================
s = content_slide("3 · Literature Survey", "Research Papers & Identified Gaps", 8)
papers = [
    ("[1]  IEEE Xplore — “A Detailed Analysis of College ERP Software Systems.”",
     "ERPs raise efficiency, but cost/complexity block adoption. → Our low-cost modular cloud stack."),
    ("[2]  IJERT (2026) — Swain et al., modular web-based college ERP.",
     "Cuts admin labor; flexible expansion. → Our router-per-module design."),
    ("[3]  Frontiers Educ. (2025) — Khairullah et al., AI in HEI academic + admin processes.",
     "AI scheduling, resource mgmt, decision support (Univ. of Murcia case). → Our risk engine + analytics."),
    ("[4]  Frontiers Educ. (2025) — Buele et al., faculty perceptions of AI.",
     "AI without support strategies overloads staff. → Human-in-the-loop approvals: AI suggests, humans decide."),
]
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.5, 7.8, 4.0, fill=None)
tf = tf_of(tb, m=0.0)
for head, rest in papers:
    mixed_para(tf, [(head + " ", True, NAVY, 10.5), (rest, False, DARK, 10.5)],
               first=(head == papers[0][0]), space_after=6)
para(tf, "Also reviewed: AI-agents-in-HE study (60% admin cut, UNSW pilot) · IJARSCT Django ERP (RBAC design) · 2026 AI-PM app surveys (Asana / Monday / ClickUp / Notion).",
     size=10, color=MUTED, space_after=0, italic=True)
gaps = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 8.65, 1.5, 3.75, 4.0,
                 fill=WHITE, line=BORDER, line_w=1.0, radius=0.06)
tf = tf_of(gaps, m=0.15)
para(tf, "GAPS  →  OUR ANSWER", size=11.5, bold=True, color=INDIGO, first=True,
     space_after=5)
for g in ["Prior work = student records & fees → we target faculty workflows",
          "AI paywalled $7–20/user/mo → our zero-cost heuristic engine",
          "Full automation risks overload → human-in-the-loop approvals",
          "Heavy on-premise ERPs → serverless Firebase, web-only"]:
    p = tf.add_paragraph()
    p.space_after = Pt(5)
    for txt, b, c in [("✔ ", True, GREEN), (g, False, DARK)]:
        r = p.add_run()
        r.text = txt
        r.font.size = Pt(11)
        r.font.bold = b
        r.font.color.rgb = c
        r.font.name = "Calibri"
label(s, 0.45, 5.7, 12.43, 0.55,
      "Full citations with links are listed in the References section (slide 23).",
      size=10.5, color=MUTED, bg=SOFT)
notes(s, "Recent 2025-26 research supports our direction: ERPs help but are costly; AI pilots cut admin workload up to sixty percent; but full automation without support can overload staff — so our novelty is faculty workflows plus human-in-the-loop approvals plus zero-cost AI risk scoring.")

# ================================================================
# SLIDE 9 — DESIGN APPROACH
# ================================================================
s = content_slide("4 · System Design", "Design Approach & Methodology", 9)
left = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.55, 6.2, 5.2, fill=None)
tf = tf_of(left, m=0.0)
para(tf, "HOW WE BUILT IT", size=11, bold=True, color=INDIGO, first=True,
     space_after=4)
bullets(tf, [
    ("Agile, module-wise slices: ", "each module = API router + UI page + Firestore model, demoed incrementally."),
    ("3-tier architecture: ", "React SPA → FastAPI REST → Firebase backend-as-a-service."),
    ("Security-first: ", "Firebase Auth + JWT; role check dependency on every protected endpoint."),
    ("Automation layer: ", "APScheduler cron (daily 8 AM reminders) + notification engine."),
], size=12)
right = add_shape(s, MSO_SHAPE.RECTANGLE, 6.95, 1.55, 5.9, 5.2, fill=None)
tf = tf_of(right, m=0.0)
para(tf, "KEY DESIGN DECISIONS", size=11, bold=True, color=INDIGO, first=True,
     space_after=4)
bullets(tf, [
    ("Firestore NoSQL ", "— flexible workflow documents, serverless scaling, no DB ops."),
    ("Router-per-module API ", "— 17 independent routers; easy to extend without breakage."),
    ("Heuristic AI first ", "— deadline-risk scoring without GPU/LLM cost; LLM-ready chat hook."),
    ("Audit-friendly ", "— timestamps, comments and stage history on every approval."),
], size=12)
notes(s, "We followed agile vertical slices. The design is a secure three-tier system with a router-per-module API and heuristic AI that needs no expensive infrastructure.")

# ================================================================
# SLIDE 10 — ARCHITECTURE
# ================================================================
s = content_slide("4 · System Design", "System Architecture (3-Tier + Cloud)", 10)
# Client tier
box_text(s, 0.45, 1.55, 3.3, 4.5, "TIER 1 — CLIENT  (React 19 + TS + Vite)",
         "• Dashboard, Tasks (Kanban), Calendar\n• Approvals, Goals, Reports\n• AI Chat + Notification Center\n• AuthContext • Protected routes\n• Tailwind + Framer Motion UI",
         accent=CYAN, title_size=11, body_size=10)
# App tier
box_text(s, 4.05, 1.55, 5.35, 4.5, "TIER 2 — APPLICATION  (FastAPI REST · /api/v1)",
         "Routers: auth · users · departments · tasks\ntask-requests · approvals · events · goals\ncomments · attachments · notifications\nanalytics · reports · ai · files · search\nsettings · join\n— JWT + RBAC middleware · CORS —\n— APScheduler: daily 8 AM reminders —",
         accent=INDIGO, title_size=11, body_size=10)
# Data tier
box_text(s, 9.7, 1.55, 3.2, 4.5, "TIER 3 — CLOUD DATA  (Firebase)",
         "• Cloud Firestore\n  (users, tasks, approvals…)\n• Firebase Authentication\n• Firebase Storage\n  (attachments)\n• Email hooks",
         accent=GOLD, title_size=11, body_size=10)
connector(s, 3.75, 3.4, 4.05, 3.4, color=INDIGO, w=2.5)
label(s, 3.28, 2.95, 1.25, 0.4, "HTTPS · JSON", size=8.5, bold=True, color=INDIGO)
connector(s, 9.4, 3.4, 9.7, 3.4, color=INDIGO, w=2.5)
label(s, 9.0, 2.95, 1.5, 0.4, "Admin SDK", size=8.5, bold=True, color=INDIGO)
connector(s, 9.7, 4.6, 9.4, 4.6, color=MUTED, w=1.5)
label(s, 0.45, 6.2, 12.43, 0.5,
      "Stateless REST  •  JWT in Authorization header  •  Role check on every request  •  Auto OpenAPI docs at /docs",
      size=10, color=NAVY, bold=True, bg=SOFT)
notes(s, "Three tiers: a React single-page app, a FastAPI REST layer with seventeen routers and JWT role checks, and Firebase for data, auth and storage. A scheduler fires daily reminders.")

# ================================================================
# SLIDE 11 — DFD LEVEL 0
# ================================================================
s = content_slide("4 · System Design", "Data Flow Diagram — Level 0 (Context)", 11)
cx, cy, cw, ch = 5.5, 3.1, 2.35, 2.35
add_shape(s, MSO_SHAPE.OVAL, cx, cy, cw, ch, fill=INDIGO)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, cx, cy + 0.55, cw, 1.2, fill=None)
tf = tf_of(tb, anchor=MSO_ANCHOR.MIDDLE, m=0.05)
para(tf, "HieraSync AI", size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER,
     first=True, space_after=1)
para(tf, "System (0)", size=11, color=RGBColor(0xC7, 0xD2, 0xFE),
     align=PP_ALIGN.CENTER, space_after=0)
box_text(s, 0.6, 1.7, 2.7, 1.15, "☐  FACULTY", "Task updates, requests", center=True, title_size=12, body_size=10)
box_text(s, 10.05, 1.7, 2.7, 1.15, "☐  HOD", "Assigns, reviews, reports", center=True, title_size=12, body_size=10)
box_text(s, 0.6, 5.1, 2.7, 1.15, "☐  PRINCIPAL / ADMIN", "Final approval, users", center=True, title_size=12, body_size=10)
box_text(s, 10.05, 5.1, 2.7, 1.15, "☐  CLOUD SERVICES", "Store · Auth · Notify", center=True, title_size=12, body_size=10)
connector(s, 3.3, 2.1, 5.5, 3.3, color=INDIGO, w=2)
label(s, 3.55, 2.2, 1.7, 0.4, "updates / requests", size=8.5, color=INDIGO)
connector(s, 5.5, 3.9, 3.3, 2.6, color=MUTED, w=1.5)
connector(s, 7.85, 3.3, 10.05, 2.1, color=INDIGO, w=2)
label(s, 8.0, 2.2, 1.7, 0.4, "tasks / approvals", size=8.5, color=INDIGO)
connector(s, 10.05, 2.6, 7.85, 3.9, color=MUTED, w=1.5)
connector(s, 3.3, 5.7, 5.5, 4.9, color=INDIGO, w=2)
label(s, 3.55, 5.75, 1.7, 0.4, "decisions / config", size=8.5, color=INDIGO)
connector(s, 7.85, 4.9, 10.05, 5.7, color=INDIGO, w=2)
label(s, 8.0, 5.75, 1.7, 0.4, "persist / alerts", size=8.5, color=INDIGO)
notes(s, "The context diagram shows HieraSync as one process with four external entities: faculty, HOD, principal-admin, and cloud services exchanging tasks, approvals and alerts.")

# ================================================================
# SLIDE 12 — DFD LEVEL 1
# ================================================================
s = content_slide("4 · System Design", "Data Flow Diagram — Level 1 (Detail)", 12)
procs = [("P1\nUsers & Roles", "login, RBAC"), ("P2\nTasks & Events", "assign, track"),
         ("P3\nApprovals", "HOD→Principal"), ("P4\nNotify & Remind", "alerts, cron"),
         ("P5\nAI & Reports", "risk, analytics")]
for i, (t, sub) in enumerate(procs):
    x = 0.45 + i * 2.55
    box_text(s, x, 1.6, 2.3, 1.5, t, sub, center=True, title_size=11.5,
             body_size=9.5, accent=[INDIGO, CYAN, GOLD, GREEN, NAVY][i])
    if i < 4:
        connector(s, x + 2.3, 2.35, x + 2.55, 2.35, color=INDIGO, w=2)
stores = ["D1 · Users", "D2 · Tasks/Events", "D3 · Approvals", "D4 · Notify Log"]
for i, t in enumerate(stores):
    x = 1.2 + i * 2.9
    shp = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, x, 4.1, 2.2, 0.9,
                    fill=SOFT, line=INDIGO, line_w=1.25, radius=0.15)
    tf = tf_of(shp, anchor=MSO_ANCHOR.MIDDLE, m=0.05)
    para(tf, t, size=11, bold=True, color=NAVY, align=PP_ALIGN.CENTER,
         first=True, space_after=0)
for i in range(4):
    connector(s, 1.6 + i * 2.55, 3.1, 2.3 + i * 2.9, 4.1, color=MUTED, w=1.5)
connector(s, 11.55, 4.55, 12.5, 2.35, color=GREEN, w=1.5)
label(s, 10.9, 5.15, 2.0, 0.55, "P5 reads D1–D4\n→ dashboards", size=9.5, color=GREEN, bold=True)
label(s, 0.45, 5.6, 9.9, 0.55,
      "Flow: Users authenticate (P1) → work is assigned & tracked (P2) → approvals move hierarchically (P3) → stakeholders are alerted (P4) → AI + analytics summarize (P5).",
      size=10, color=NAVY, bg=SOFT)
notes(s, "Level one decomposes the system into five processes and four data stores. Authentication feeds task tracking, which feeds approvals, notifications, and finally AI analytics.")

# ================================================================
# SLIDE 13 — USE CASE
# ================================================================
s = content_slide("4 · System Design", "Use Case Diagram", 13)
actors = ["ADMIN", "PRINCIPAL", "HOD", "FACULTY"]
for i, a in enumerate(actors):
    y = 1.6 + i * 1.22
    add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.45, y, 1.9, 0.85, fill=NAVY,
              radius=0.4)
    tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.45, y, 1.9, 0.85, fill=None)
    tf = tf_of(tb, anchor=MSO_ANCHOR.MIDDLE, m=0.02)
    para(tf, "◉  " + a, size=10.5, bold=True, color=WHITE, align=PP_ALIGN.CENTER,
         first=True, space_after=0)
add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 2.7, 1.55, 10.18, 5.05, fill=WHITE,
          line=BORDER, line_w=1.0, radius=0.04)
label(s, 2.85, 1.62, 2.6, 0.4, "—  HieraSync System Boundary  —", size=9.5,
      color=INDIGO, bold=True)
ucs = ["Login &\nRBAC", "Manage\nEmployees", "Create / Assign\nTasks", "Update\nProgress",
       "Request\nTask", "Approve\n(HOD)", "Approve\n(Principal)", "Manage\nEvents",
       "View\nAnalytics", "AI Chat &\nReports", "Receive\nAlerts", "Goals &\nMilestones"]
for i, t in enumerate(ucs):
    r, c = divmod(i, 4)
    x = 3.0 + c * 2.45
    y = 2.15 + r * 1.45
    shp = add_shape(s, MSO_SHAPE.OVAL, x, y, 2.1, 1.1, fill=SOFT, line=INDIGO,
                    line_w=1.25)
    tf = tf_of(shp, anchor=MSO_ANCHOR.MIDDLE, m=0.05)
    para(tf, t, size=9.5, bold=True, color=NAVY, align=PP_ALIGN.CENTER,
         first=True, space_after=0)
links = {0: [0, 1, 11], 1: [6, 8, 9], 2: [2, 5, 8, 9], 3: [0, 3, 4, 7, 10]}
for ai, ucl in links.items():
    ay = 1.6 + ai * 1.22 + 0.42
    for u in ucl:
        r, c = divmod(u, 4)
        uy = 2.15 + r * 1.45 + 0.55
        connector(s, 2.35, ay, 3.0, uy, color=BORDER, w=1.0, arrow=False)
notes(s, "Four actors interact with twelve use cases. Admin manages users, faculty executes tasks, HOD assigns and reviews, and the principal gives final approvals and views analytics.")

# ================================================================
# SLIDE 14 — DATABASE / ER
# ================================================================
s = content_slide("4 · System Design", "Database Design — Firestore Collections", 14)
cols = [
    ("users", "id · name · email\nrole (10 roles)\ndepartment_id\ndesignation, status"),
    ("departments", "id · name · code\nhod_id"),
    ("tasks", "id · title · assignee\npriority · status\nprogress · deadline\nrisk_score · goal_id"),
    ("approvals", "id · title · requester\nstage, hod_comment\nprincipal_comment\nstatus"),
    ("events", "id · title · date\ntype · person\nlocation"),
    ("notifications", "id · user_id · title\ntype · is_read"),
    ("goals", "id · title · category\ntarget_date\n+ milestones[]"),
    ("comments /\nattachments", "subcollections\nof tasks:\nmentions, files"),
]
for i, (t, b) in enumerate(cols):
    r, c = divmod(i, 4)
    x = 0.45 + c * 3.19
    y = 1.6 + r * 2.35
    box_text(s, x, y, 2.94, 2.1, "▦  " + t, b, accent=[INDIGO, CYAN, GOLD, GREEN][c],
             title_size=11.5, body_size=9.5)
label(s, 0.45, 6.32, 12.43, 0.55,
      "Relations: departments 1—N users  •  users 1—N tasks  •  tasks 1—N comments / attachments  •  goals 1—N milestones  •  approvals link requester → HOD → Principal",
      size=10, color=NAVY, bold=True, bg=SOFT)
notes(s, "Firestore holds eight collections. Departments own users, users own tasks, tasks carry comments and attachments, and approvals chain requester to HOD to principal.")

# ================================================================
# SLIDE 15 — APPROVAL FLOWCHART
# ================================================================
s = content_slide("4 · System Design", "Core Workflow — Approval Flowchart", 15)
fx = 5.35
def flow_oval(y, text):
    shp = add_shape(s, MSO_SHAPE.OVAL, fx, y, 2.6, 0.6, fill=NAVY)
    tf = tf_of(shp, anchor=MSO_ANCHOR.MIDDLE, m=0.05)
    para(tf, text, size=11, bold=True, color=WHITE, align=PP_ALIGN.CENTER,
         first=True, space_after=0)
def flow_box(y, text, fill=WHITE, tc=NAVY, h=0.62):
    shp = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, fx, y, 2.6, h, fill=fill,
                    line=INDIGO if fill == WHITE else None, line_w=1.5, radius=0.15)
    tf = tf_of(shp, anchor=MSO_ANCHOR.MIDDLE, m=0.06)
    para(tf, text, size=10.5, bold=True, color=tc, align=PP_ALIGN.CENTER,
         first=True, space_after=0)
def flow_dia(y, text):
    shp = add_shape(s, MSO_SHAPE.DIAMOND, fx + 0.45, y, 1.7, 1.0, fill=GOLD)
    tf = tf_of(shp, anchor=MSO_ANCHOR.MIDDLE, m=0.02)
    para(tf, text, size=10, bold=True, color=NAVY, align=PP_ALIGN.CENTER,
         first=True, space_after=0)
ys = [1.5, 2.25, 3.05, 4.3, 5.55]
flow_oval(ys[0], "START: Request raised")
flow_box(ys[1], "HOD reviews request")
flow_dia(ys[2], "HOD\napproves?")
flow_box(ys[3] - 0.25, "Forward to Principal", h=0.55)
flow_dia(ys[3] + 0.45, "Principal\napproves?")
connector(s, fx + 1.3, 2.1, fx + 1.3, 2.25, color=INDIGO, w=2)
connector(s, fx + 1.3, 2.87, fx + 1.3, 3.05, color=INDIGO, w=2)
# HOD no -> rejected (left)
connector(s, fx + 0.45, 3.55, 3.6, 3.55, color=RED, w=2)
label(s, 3.85, 3.28, 1.0, 0.35, "NO", size=9, bold=True, color=RED)
# HOD yes -> down
label(s, fx + 1.45, 3.75, 0.7, 0.35, "YES", size=9, bold=True, color=GREEN)
connector(s, fx + 1.3, 4.05, fx + 1.3, 4.3 - 0.25, color=INDIGO, w=2)
connector(s, fx + 1.3, 4.6, fx + 1.3, 4.75, color=INDIGO, w=2)
# Principal no -> rejected (right)
connector(s, fx + 2.15, 5.25, 9.0, 5.25, color=RED, w=2)
label(s, 8.15, 4.98, 1.0, 0.35, "NO", size=9, bold=True, color=RED)
connector(s, fx + 1.3, 5.75, fx + 1.3, 6.0, color=INDIGO, w=2)
label(s, fx + 1.45, 5.7, 0.7, 0.35, "YES", size=9, bold=True, color=GREEN)
flow_box(6.0, "APPROVED ✓  •  notify all  •  log history", fill=GREEN, tc=WHITE)
rej = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.5, 3.2, 2.6, 0.75, fill=RED, radius=0.2)
tf = tf_of(rej, anchor=MSO_ANCHOR.MIDDLE, m=0.06)
para(tf, "REJECTED ✕ + reason → notify", size=10.5, bold=True, color=WHITE,
     align=PP_ALIGN.CENTER, first=True, space_after=0)
rej2 = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 9.5, 4.9, 2.6, 0.75, fill=RED, radius=0.2)
tf = tf_of(rej2, anchor=MSO_ANCHOR.MIDDLE, m=0.06)
para(tf, "REJECTED ✕ + reason → notify", size=10.5, bold=True, color=WHITE,
     align=PP_ALIGN.CENTER, first=True, space_after=0)
box_text(s, 9.5, 1.55, 3.35, 2.9, "Stage machine",
         "PENDING → APPROVED_HOD →\nAPPROVED_PRINCIPAL\n(or REJECTED at any stage)\n\n• Comments at each stage\n• Timestamps + history\n• Task-requests auto-create\n  tasks on approval", accent=INDIGO,
         title_size=11.5, body_size=10)
box_text(s, 0.5, 4.35, 2.6, 2.0, "Actors", "Faculty / Staff raise →\nHOD reviews →\nPrincipal decides", accent=CYAN,
         title_size=11.5, body_size=10)
notes(s, "Every request passes a two-stage state machine: pending, HOD-approved, then principal-approved — or rejected with a recorded reason. Each transition notifies stakeholders.")

# ================================================================
# SLIDE 16 — TECHNOLOGY
# ================================================================
s = content_slide("5 · Technology Used", "Technology Stack & Justification", 16)
data = [
    ["Layer", "Technology", "Why this choice"],
    ["Frontend", "React 19 + TypeScript + Vite", "Actions/Suspense, type safety, instant HMR builds"],
    ["Styling / UX", "Tailwind CSS v4, Framer Motion, lucide-react", "Responsive, animated, consistent design system"],
    ["Calendar / Charts / DnD", "FullCalendar, Recharts, dnd-kit", "Production-grade calendar, analytics & Kanban"],
    ["Backend API", "FastAPI (Python), Pydantic v2", "Async, validated, auto OpenAPI docs at /docs"],
    ["Auth", "Firebase Auth + JWT (python-jose)", "Secure, stateless, role-checked sessions"],
    ["Database", "Cloud Firestore (NoSQL)", "Serverless scale, flexible docs, zero DB ops"],
    ["Storage / Scheduler", "Firebase Storage, APScheduler", "File attachments; daily 8 AM reminder cron"],
]
make_table(s, 0.45, 1.55, 12.43, 4.85, data, [2.7, 4.9, 4.83], font_size=10.5)
label(s, 0.45, 6.5, 12.43, 0.45,
      "Tooling: Git + GitHub  •  npm + pip  •  VS Code  •  Postman / OpenAPI for API testing  •  Vercel / Cloud Run-ready deploy targets",
      size=10, color=MUTED, bg=SOFT)
notes(s, "Our stack is modern and pragmatic: React with TypeScript, FastAPI for a documented REST API, and Firebase as a serverless backend — minimizing ops cost while staying extensible.")

# ================================================================
# SLIDE 17 — MODULES OVERVIEW
# ================================================================
s = content_slide("6 · Developed Modules", "Modules Developed — Status at Review-I", 17)
data = [
    ["#", "Module", "Key capability delivered", "Status"],
    ["M1", "Auth & RBAC", "Login/register, JWT, 10 roles, protected routes", "✔ Done 100%"],
    ["M2", "Employee Mgmt", "Faculty CRUD, profiles, department mapping", "✔ Done 95%"],
    ["M3", "Task Management", "Kanban, subtasks, priorities, progress, risk badges", "✔ Done 95%"],
    ["M4", "Events & Calendar", "FullCalendar views, types, reminders", "✔ Done 90%"],
    ["M5", "Approval Workflow", "HOD→Principal stages, comments, history", "✔ Done 90%"],
    ["M6", "Notifications", "Center, unread counts, scheduler + email hooks", "◐ 85%"],
    ["M7", "AI Assistant", "Chat, dashboard summary, report-gen, risk engine", "◐ 80%"],
    ["M8", "Analytics & Reports", "Stats, activity log, faculty performance, export", "◐ 85%"],
    ["M9", "Goals / Requests / Social", "Milestones, task-requests, comments, attachments", "✔ Done 90%"],
]
make_table(s, 0.45, 1.55, 12.43, 5.2, data, [0.6, 2.5, 6.6, 2.73], font_size=10.5)
notes(s, "Nine modules are implemented. Six are essentially complete; AI, notifications and analytics are at eighty-plus percent and under active polish.")

# ================================================================
# SLIDE 18 — MODULE DEEP-DIVE A
# ================================================================
s = content_slide("6 · Developed Modules", "Deep-Dive A — Tasks + AI Risk Engine", 18)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.55, 4.7, 5.1, fill=None)
tf = tf_of(tb, m=0.0)
para(tf, "TASK MANAGEMENT", size=11, bold=True, color=INDIGO, first=True,
     space_after=4)
bullets(tf, [
    "Kanban board with drag-and-drop (dnd-kit).",
    "Priorities, deadlines, subtasks, progress %.",
    ("Goal linking + approval-required tasks.", ""),
    "Comments with @mentions; file attachments.",
    "HOD vs Faculty dashboards with distinct views.",
], size=11.5)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 5.35, 1.55, 4.35, 5.1, fill=None)
tf = tf_of(tb, m=0.0)
para(tf, "AI RISK ENGINE (HEURISTIC)", size=11, bold=True, color=INDIGO,
     first=True, space_after=4)
bullets(tf, [
    ("Risk score 0–100 ", "from deadline gap, progress lag, workload."),
    ("Levels LOW / MEDIUM / HIGH ", "+ human-readable risk factors."),
    "Endpoints: /dashboard-summary, /chat, /generate-report.",
    "HOD action items: who needs help, what is late.",
    "No GPU/LLM cost — deterministic & explainable.",
], size=11.5)
try:
    s.shapes.add_picture(os.path.join(CHARTS, "risk_donut.png"),
                         Inches(9.95), Inches(1.7), Inches(3.0), Inches(2.3))
except Exception:
    pass
label(s, 9.95, 4.15, 3.0, 1.3,
      "Sample output: 62% tasks on track,\n25% need attention, 13% at risk\n→ HOD sees this before delay happens.",
      size=10, color=NAVY, bg=RGBColor(0xFE, 0xF3, 0xC7))
notes(s, "Tasks support Kanban, subtasks and attachments. On top sits our heuristic risk engine scoring every task zero to one hundred with explainable factors — no costly LLM needed.")

# ================================================================
# SLIDE 19 — MODULE DEEP-DIVE B
# ================================================================
s = content_slide("6 · Developed Modules", "Deep-Dive B — Approvals, Analytics, Alerts", 19)
box_text(s, 0.45, 1.55, 3.9, 3.1, "✓  Approvals",
         "• HOD → Principal stages\n• Comments & decision history\n• Pending / approved / rejected views\n• Task-requests convert to tasks", accent=GOLD)
box_text(s, 4.6, 1.55, 3.9, 3.1, "◐  Analytics & Reports",
         "• Dashboard stats + activity log\n• Faculty performance table\n• Completion & on-time metrics\n• One-click report export", accent=INDIGO)
box_text(s, 8.75, 1.55, 3.9, 3.1, "◐  Notifications",
         "• In-app center + unread badge\n• Task / approval / event alerts\n• Daily 8 AM scheduler cron\n• Email hook ready", accent=CYAN)
try:
    s.shapes.add_picture(os.path.join(CHARTS, "module_progress.png"),
                         Inches(1.6), Inches(4.75), Inches(10.1), Inches(1.85))
except Exception:
    label(s, 1.6, 4.75, 10.1, 1.85, "[Module progress chart]", size=12,
          color=MUTED, bg=SOFT)
notes(s, "Approvals, analytics and notifications close the loop: decisions are tracked, performance is measured, and nobody misses an update thanks to scheduled reminders.")

# ================================================================
# SLIDE 20 — ADVANTAGES
# ================================================================
s = content_slide("7 · Advantages & Applications", "Advantages", 20)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.55, 6.3, 5.1, fill=None)
tf = tf_of(tb, m=0.0)
bullets(tf, [
    ("Single source of truth: ", "one workspace replaces registers, chats and sheets."),
    ("Faster decisions: ", "approval cycles shrink from days to hours (est.)."),
    ("Full accountability: ", "who did/approved what, with timestamps."),
    ("Proactive, not reactive: ", "reminders + AI delay-risk alerts."),
    ("Data-driven leadership: ", "workload balance + NAAC-ready reports."),
    ("Low cost & secure: ", "serverless Firebase, zero per-seat AI fees (vs $7–20/user/mo suites); JWT + per-request role checks."),
], size=12)
try:
    s.shapes.add_picture(os.path.join(CHARTS, "efficiency.png"),
                         Inches(7.1), Inches(1.6), Inches(5.7), Inches(3.25))
except Exception:
    pass
label(s, 7.1, 4.95, 5.7, 0.75,
      "Estimated admin effort per cycle drops ~80–90% across approvals, tracking and reporting.",
      size=10.5, color=NAVY, bold=True, bg=RGBColor(0xFE, 0xF3, 0xC7))
notes(s, "The payoff: one accountable workspace, far faster approvals, proactive alerts, leadership dashboards — at serverless cost with strong access control.")

# ================================================================
# SLIDE 21 — APPLICATIONS & FUTURE
# ================================================================
s = content_slide("7 · Advantages & Applications", "Applications & Future Scope", 21)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.55, 6.2, 5.1, fill=None)
tf = tf_of(tb, m=0.0)
para(tf, "WHERE IT APPLIES", size=11, bold=True, color=GREEN, first=True,
     space_after=4)
bullets(tf, [
    "Department task & event governance (any branch).",
    "Leave, purchase & resource approvals.",
    "Accreditation (NAAC/NBA) documentation.",
    "Faculty appraisal & workload inputs.",
    "Student clubs, labs & multi-department roll-out.",
], size=12)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 6.95, 1.55, 5.9, 5.1, fill=None)
tf = tf_of(tb, m=0.0)
para(tf, "FUTURE SCOPE", size=11, bold=True, color=INDIGO, first=True,
     space_after=4)
bullets(tf, [
    "Mobile app / PWA + push notifications.",
    "ML-based delay prediction on history.",
    "Timetable & attendance integration.",
    "Email/SMS gateway; offline mode.",
    "Multi-college SaaS + institute console.",
], size=12)
notes(s, "Beyond our department, the system fits any academic unit and accreditation workflows. Planned extensions include mobile support, ML prediction and multi-college scale.")

# ================================================================
# SLIDE 22 — PROGRESS & PLAN
# ================================================================
s = content_slide("Review Seminar – I", "Progress Status & Plan Ahead", 22)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.55, 6.0, 2.9, fill=None)
tf = tf_of(tb, m=0.0)
para(tf, "✔  COMPLETED (IN REPO TODAY)", size=11, bold=True, color=GREEN,
     first=True, space_after=4)
bullets(tf, [
    "Full-stack scaffold: React SPA + FastAPI + Firebase wired.",
    "17 API routers live; 13+ pages with RBAC guards.",
    "Approvals, tasks, events, scheduler, AI heuristics.",
], size=11.5, bullet="✔  ")
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 6.8, 1.55, 5.9, 2.9, fill=None)
tf = tf_of(tb, m=0.0)
para(tf, "◐  IN PROGRESS", size=11, bold=True, color=GOLD_D, first=True,
     space_after=4)
bullets(tf, [
    "AI chat polish + richer report formats.",
    "UI polish, validations & test coverage.",
    "Cloud deployment + user acceptance testing.",
], size=11.5, bullet="◐  ")
data = [
    ["Phase", "Milestone", "Target", "Status"],
    ["Review – I", "Core platform + 9 modules demonstrable", "Sept 2026", "✔ ~90% done"],
    ["Hardening", "Testing, AI tuning, deployment", "Oct 2026", "◐ Planned"],
    ["Review – II", "Deployed pilot + docs + feedback fixes", "Nov 2026", "○ Next"],
    ["Final", "Final demo, report & publication", "Dec 2026", "○ Next"],
]
make_table(s, 0.45, 4.6, 12.43, 2.0, data, [2.2, 6.0, 2.0, 2.23], font_size=11)
notes(s, "As of today, about ninety percent of core scope is implemented and visible in our repository. Hardening and deployment lead to Review Two, then final demonstration.")

# ================================================================
# SLIDE 23 — REFERENCES
# ================================================================
s = content_slide("8 · References", "References", 23)
refs = [
    "[1]  “A Detailed Analysis of College ERP Software Systems,” IEEE Xplore, doc. 10743425. https://ieeexplore.ieee.org/document/10743425/",
    "[2]  S. Swain et al., “College ERP Management System,” IJERT, vol. 15, no. 04, Apr. 2026, DOI: 10.5281/zenodo.19731754.",
    "[3]  S. Tripathi et al., “College ERP System,” IJCRT, paper IJCRT1812344. https://www.ijcrt.org/papers/IJCRT1812344.pdf",
    "[4]  R. Salunke et al., “ERP Management System” (Django, RBAC), IJARSCT. https://www.ijarsct.co.in/Paper25814.pdf",
    "[5]  S. A. Khairullah et al., “Implementing AI in academic and administrative processes…,” Front. Educ., 2025. https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1548104/full",
    "[6]  “The Future of AI Agents in Higher Education,” ResearchGate, 2025. https://www.researchgate.net/publication/394249334",
    "[7]  “Automating Higher Education Administrative Processes with AI-Powered Workflows,” ResearchGate. https://www.researchgate.net/publication/399184231",
    "[8]  J. Buele et al., “Transformations in academic work and faculty perceptions of AI,” Front. Educ., 2025. https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2025.1603763/full",
    "[9]  “8 Best AI for Project Management in 2026 (Compared by a PM),” Dupple, 2026. https://dupple.com/learn/best-ai-for-project-management",
    "[10]  FastAPI, Firebase, React & Vite official docs; Project repo: https://github.com/Parthwadekar40/Hiera_Sync",
]
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.55, 1.5, 12.25, 5.3, fill=None)
tf = tf_of(tb, m=0.0)
for i, r in enumerate(refs):
    para(tf, r, size=10.5, color=DARK, first=(i == 0), space_after=6)
notes(s, "Our references combine three peer-reviewed works on college ERP systems with official documentation of our stack and our own public repository.")

# ================================================================
# SLIDE 24 — CONCLUSION
# ================================================================
s = content_slide("9 · Conclusion", "Conclusion", 24)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 0.5, 1.55, 7.6, 5.2, fill=None)
tf = tf_of(tb, m=0.0)
bullets(tf, [
    ("We built a unified, role-aware platform ", "covering the department's real workflows end-to-end."),
    ("Approvals are digitized & auditable; ", "follow-ups are automated; nothing falls through cracks."),
    ("AI adds foresight: ", "risk scores and summaries help HODs act before delays."),
    ("All 5 objectives are demonstrable live ", "— the system runs from our repository today."),
], size=13)
ps = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 8.4, 1.7, 4.0, 3.4, fill=NAVY,
               radius=0.06)
tf = tf_of(ps, anchor=MSO_ANCHOR.MIDDLE, m=0.2)
para(tf, "\u201C HieraSync turns departmental chaos into a calm, transparent workflow. \u201D",
     size=15, bold=False, color=GOLD, align=PP_ALIGN.CENTER, first=True,
     space_after=0, italic=True)
notes(s, "In conclusion, HieraSync delivers every objective: unified workspace, auditable approvals, automation, AI foresight and analytics — all running live for demonstration.")

# ================================================================
# SLIDE 25 — THANK YOU
# ================================================================
s = new_slide(NAVY)
add_shape(s, MSO_SHAPE.OVAL, 10.6, -2.2, 5.0, 5.0, fill=NAVY2)
add_shape(s, MSO_SHAPE.OVAL, -2.0, 4.6, 4.6, 4.6, fill=NAVY2)
tb = add_shape(s, MSO_SHAPE.RECTANGLE, 1.0, 1.2, 11.33, 4.6, fill=None)
tf = tf_of(tb, anchor=MSO_ANCHOR.MIDDLE, m=0.0)
para(tf, "Thank You!", size=54, bold=True, color=WHITE, align=PP_ALIGN.CENTER,
     first=True, space_after=4)
para(tf, "Open for Live Demonstration & Questions", size=20, color=GOLD,
     align=PP_ALIGN.CENTER, space_after=14)
para(tf, "HieraSync AI  •  Smart Academic Workflow & Event Management System",
     size=13, color=RGBColor(0xC7, 0xD2, 0xFE), align=PP_ALIGN.CENTER,
     space_after=4)
para(tf, "github.com / Parthwadekar40 / Hiera_Sync", size=12.5, bold=True,
     color=CYAN, align=PP_ALIGN.CENTER, space_after=10)
para(tf, "[Your Name]  •  Guided by [Guide Name]  •  CSE (AI & ML), SBJIT Nagpur",
     size=12, color=RGBColor(0x94, 0xA3, 0xB8), align=PP_ALIGN.CENTER,
     space_after=8)
para(tf, "Backup slides 26–30 follow for Q&A", size=11, bold=True, color=CYAN, align=PP_ALIGN.CENTER, space_after=0)
notes(s, "Thank the panel, offer a live demo: login as HOD, create a task, approve a request, show AI risk and analytics. Invite questions.")

# ================================================================
# SLIDE 26 — APPENDIX A: SEQUENCE DIAGRAM
# ================================================================
s = content_slide("Appendix · Backup for Q&A", "Appendix A — Sequence Diagram (Approval Flow)", 26)
heads = [("Faculty\nBrowser", 0.6, 2.7), ("FastAPI\nServer", 3.8, 2.7),
         ("Firestore\nDB", 7.0, 2.4), ("HOD / Principal\nApp", 9.9, 2.4)]
centers = []
for title, x, w in heads:
    box_text(s, x, 1.55, w, 0.75, title, None, center=True, title_size=11,
             accent=INDIGO)
    centers.append(x + w / 2)
    connector(s, x + w / 2, 2.3, x + w / 2, 6.1, color=BORDER, w=1.25,
              arrow=False)
FC, API, DB, HP = centers
msgs = [
    (FC, API, 2.62, "1   POST /approvals {title, …}", INDIGO),
    (API, DB, 2.95, "2   save: status = PENDING", INDIGO),
    (DB, API, 3.25, "3   ack", MUTED),
    (API, FC, 3.55, "4   201 Created", GREEN),
    (HP, API, 3.88, "5   PUT /{id}/approve  (HOD)", INDIGO),
    (API, DB, 4.2, "6   stage = APPROVED_HOD", INDIGO),
    (API, HP, 4.52, "7   notify: HOD ✓, faculty ✓", GREEN),
    (HP, API, 4.84, "8   PUT /{id}/approve  (Principal)", INDIGO),
    (API, DB, 5.14, "9   status = APPROVED_PRINCIPAL", INDIGO),
    (API, FC, 5.46, "10   notify all + activity log", GREEN),
]
for x1, x2, y, txt, col in msgs:
    d = 0.06 if x2 > x1 else -0.06
    connector(s, x1 + d, y, x2 - d, y, color=col, w=2)
    mx = (x1 + x2) / 2
    label(s, mx - 1.45, y - 0.29, 2.9, 0.27, txt, size=8.5, bold=True,
          color=col)
label(s, 0.45, 6.3, 12.43, 0.45,
      "Synchronous REST/JSON  •  every mutating call carries JWT + role check  •  failures return 4xx with no state change",
      size=10, color=NAVY, bold=True, bg=SOFT)
notes(s, "Backup slide. The sequence shows a request flowing from the faculty browser to FastAPI to Firestore, then HOD and principal approvals, each persisting stage changes and fanning out notifications.")

# ================================================================
# SLIDE 27 — APPENDIX B: STATE DIAGRAM + RISK FORMULA
# ================================================================
s = content_slide("Appendix · Backup for Q&A", "Appendix B — Task Lifecycle & Risk Formula", 27)
states = ["TODO", "IN_PROGRESS", "IN_REVIEW", "COMPLETED"]
for i, st in enumerate(states):
    y = 1.6 + i * 1.1
    done = (st == "COMPLETED")
    shp = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 0.6, y, 2.6, 0.7,
                    fill=(GREEN if done else WHITE),
                    line=(None if done else INDIGO), line_w=1.5, radius=0.3)
    tf = tf_of(shp, anchor=MSO_ANCHOR.MIDDLE, m=0.05)
    para(tf, st, size=12, bold=True, color=(WHITE if done else NAVY),
         align=PP_ALIGN.CENTER, first=True, space_after=0)
    if i < 3:
        connector(s, 1.9, y + 0.7, 1.9, y + 1.1, color=INDIGO, w=2)
box_text(s, 3.7, 3.0, 2.4, 1.45, "OVERDUE", "auto-flagged when\ndeadline passes;\nreturns to flow on update",
         center=True, title_size=12, body_size=10, accent=RED)
connector(s, 3.2, 3.05, 3.7, 3.5, color=RED, w=2)
label(s, 2.45, 2.72, 1.7, 0.32, "deadline passes", size=8.5, bold=True,
      color=RED)
LGHT = RGBColor(0xC7, 0xD2, 0xFE)
fx = add_shape(s, MSO_SHAPE.ROUNDED_RECTANGLE, 6.6, 1.6, 6.25, 5.0,
               fill=NAVY, radius=0.05)
tf = tf_of(fx, anchor=MSO_ANCHOR.TOP, m=0.2)
para(tf, "RISK FORMULA  ·  calculate_task_risk()  ·  tasks.py", size=11,
     bold=True, color=CYAN, first=True, space_after=5)
for txt, col, b in [
        ("Completed / Awaiting Approval  →  R = 0  (LOW)", GOLD, True),
        ("Otherwise:  R = clamp(D + G + P + W, 5, 95)", WHITE, True),
        ("D  =  90 overdue  ·  50 if ≤2d  ·  30 if ≤5d", WHITE, False),
        ("G  =  25 if progress < 50% and ≤3 days left", WHITE, False),
        ("P  =  15 if priority High  ·  W = 20 if load > 3", WHITE, False),
        ("HIGH if R > 70  ·  MEDIUM if R > 40  ·  LOW else", CYAN, True),
        ("e.g. 2d left · 30% done · High · load 5", LGHT, False),
        ("→ 50+25+15+20 = 110 → capped 95 → HIGH ✓", GOLD, True)]:
    para(tf, txt, size=11.5, bold=b, color=col, space_after=4)
notes(s, "Backup slide. Tasks move through four states with an overdue branch. The risk formula is exactly as implemented: deadline pressure plus progress gap plus priority plus workload, clamped and banded into three levels.")

# ================================================================
# SLIDE 28 — APPENDIX C: TESTING
# ================================================================
s = content_slide("Appendix · Backup for Q&A", "Appendix C — Testing & Results (Review-I)", 28)
data = [
    ["ID", "Test scenario", "Expected result", "Status"],
    ["T1", "Valid HOD login", "JWT issued, dashboard loads", "✔ Pass"],
    ["T2", "Invalid password", "401 error, stays on login", "✔ Pass"],
    ["T3", "Faculty opens HOD-only page", "Blocked / redirected", "✔ Pass"],
    ["T4", "HOD assigns task", "Appears in faculty Kanban + alert", "✔ Pass"],
    ["T5", "Faculty updates progress", "% saved, activity logged", "✔ Pass"],
    ["T6", "HOD → Principal approval", "Stage advances, comments stored", "✔ Pass"],
    ["T7", "Overdue task scored", "HIGH badge + factor strings", "✔ Pass"],
    ["T8", "Daily 8 AM scheduler run", "Deadline reminders created", "✔ Pass"],
    ["T9", "Report export", "Department summary downloads", "◐ Partial"],
]
make_table(s, 0.45, 1.55, 12.43, 4.8, data, [0.7, 4.2, 5.0, 2.53],
           font_size=11)
label(s, 0.45, 6.5, 12.43, 0.45,
      "Method: manual functional testing via auto OpenAPI docs (/docs) + per-role UI walkthroughs  •  Automated suite + UAT in hardening phase (Oct)",
      size=10, color=MUTED, bg=SOFT)
notes(s, "Backup slide. Nine functional test cases cover login, role guards, tasks, approvals, risk scoring, scheduler and export. Run each live before the seminar and keep this table honest.")

# ================================================================
# SLIDE 29 — APPENDIX D: FEATURE MATRIX
# ================================================================
s = content_slide("Appendix · Backup for Q&A", "Appendix D — Feature Matrix vs Alternatives", 29)
data = [
    ["Capability", "Manual /\nExcel", "College\nERP", "Asana-class\n2026", "HieraSync"],
    ["Academic role hierarchy", "✖", "◐", "✖", "✔"],
    ["HOD → Principal e-approvals", "✖", "◐", "✖", "✔"],
    ["AI delay-risk alerts", "✖", "✖", "◐ paid", "✔ free"],
    ["Department analytics", "✖", "◐", "◐ generic", "✔ academic"],
    ["Zero per-seat AI cost", "✔", "✖", "✖", "✔"],
    ["Tasks + events unified", "✖", "◐", "◐", "✔"],
    ["Full audit trail", "✖", "✔", "✔", "✔"],
    ["Open & customizable", "—", "✖", "✖", "✔"],
]
gf = make_table(s, 0.45, 1.55, 12.43, 4.65, data, [4.5, 1.95, 1.95, 1.95, 2.08],
                font_size=11.5)
for r in range(len(data)):
    for c in range(5):
        for p in gf.table.cell(r, c).text_frame.paragraphs:
            p.alignment = PP_ALIGN.CENTER
label(s, 0.45, 6.35, 12.43, 0.5,
      "✔ full   •   ◐ partial   •   ✖ missing        →   Only HieraSync combines hierarchy + approvals + free AI risk + academic analytics",
      size=11, color=NAVY, bold=True, bg=RGBColor(0xFE, 0xF3, 0xC7))
notes(s, "Backup slide. Use this when asked what is novel: no alternative covers academic hierarchy, two-stage approvals, free AI risk alerts and department analytics together.")

# ================================================================
# SLIDE 30 — APPENDIX E: GANTT
# ================================================================
s = content_slide("Appendix · Backup for Q&A", "Appendix E — Project Timeline (Gantt)", 30)
try:
    s.shapes.add_picture(os.path.join(CHARTS, "gantt.png"),
                         Inches(0.45), Inches(1.5), width=Inches(12.43))
except Exception:
    label(s, 0.45, 1.5, 12.43, 4.3, "[Gantt chart]", size=12, color=MUTED,
          bg=SOFT)
label(s, 0.45, 6.05, 12.43, 0.6,
      "TARGET DEPLOYMENT:   Browser → Vercel / Firebase Hosting (SPA) → Cloud Run (FastAPI) → Firestore + Auth + Storage   •   env-based config   •   HTTPS everywhere",
      size=10.5, color=WHITE, bold=True, bg=NAVY)
notes(s, "Backup slide. The Gantt shows design to final demo across July to December, with Review One marked today, plus the target cloud deployment chain.")


out = os.path.join(BASE, "HieraSync_Review_Seminar_I.pptx")
prs.save(out)
print("Saved:", out)

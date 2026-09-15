"""Generate charts for HieraSync Review Seminar-I PPT."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

OUT = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(OUT, exist_ok=True)

NAVY = "#0B1E3B"
INDIGO = "#4F46E5"
CYAN = "#06B6D4"
GOLD = "#F59E0B"
GREEN = "#10B981"
AMBER = "#F59E0B"
SLATE = "#64748B"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "axes.edgecolor": "#CBD5E1",
    "axes.grid": True,
    "grid.color": "#E2E8F0",
    "grid.linewidth": 0.7,
    "axes.axisbelow": True,
})

# ---------- Chart 1: module progress (horizontal bars) ----------
modules = [
    "Authentication & RBAC",
    "Employee Management",
    "Task Management",
    "Events & Calendar",
    "Approval Workflow",
    "Notifications",
    "AI Assistant & Risk Engine",
    "Analytics & Reports",
    "Goals & Milestones",
    "Comments & Attachments",
]
progress = [100, 95, 95, 90, 90, 85, 80, 85, 90, 90]

fig, ax = plt.subplots(figsize=(10, 5.6))
y = np.arange(len(modules))
colors = [GREEN if p >= 90 else (AMBER if p >= 80 else INDIGO) for p in progress]
bars = ax.barh(y, progress, height=0.55, color=colors, edgecolor="none", zorder=3)
ax.set_yticks(y)
ax.set_yticklabels(modules, fontsize=11, color=NAVY)
ax.set_xlabel("Completion (%)", fontsize=11, color=SLATE)
ax.set_xlim(0, 110)
ax.set_xticks([0, 20, 40, 60, 80, 100])
ax.set_title("Module-wise Implementation Progress (Review Seminar – I)",
             fontsize=13, fontweight="bold", color=NAVY, pad=14)
ax.invert_yaxis()
for bar, p in zip(bars, progress):
    ax.text(bar.get_width() + 1.2, bar.get_y() + bar.get_height() / 2,
            f"{p}%", va="center", ha="left", fontsize=11,
            fontweight="bold", color=NAVY)
ax.axvline(100, color="#CBD5E1", linestyle="--", linewidth=1)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "module_progress.png"), dpi=200, bbox_inches="tight")
plt.close(fig)

# ---------- Chart 2: manual vs HieraSync time comparison ----------
cats = ["Approval cycle", "Task status\ntracking", "Report\npreparation", "Reminders &\nfollow-ups"]
manual = [48, 10, 8, 6]
hiera = [6, 2, 1, 0.5]

fig, ax = plt.subplots(figsize=(10, 5.6))
x = np.arange(len(cats))
w = 0.34
b1 = ax.bar(x - w / 2, manual, width=w, label="Manual process (hrs)",
            color="#94A3B8", edgecolor="white", zorder=3)
b2 = ax.bar(x + w / 2, hiera, width=w, label="With HieraSync (hrs)",
            color=INDIGO, edgecolor="white", zorder=3)
ax.set_xticks(x)
ax.set_xticklabels(cats, fontsize=11, color=NAVY)
ax.set_ylabel("Time (hours, per typical cycle)", fontsize=11, color=SLATE)
ax.set_title("Estimated Administrative Effort: Manual vs HieraSync",
             fontsize=13, fontweight="bold", color=NAVY, pad=14)
ax.legend(frameon=True, facecolor="white", edgecolor="#CBD5E1",
          fontsize=10, loc="upper right")
for bar in list(b1) + list(b2):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.6,
            f"{bar.get_height():g}h", ha="center", va="bottom",
            fontsize=10, fontweight="bold", color=NAVY)
ax.set_ylim(0, 56)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "efficiency.png"), dpi=200, bbox_inches="tight")
plt.close(fig)

# ---------- Chart 3: task risk distribution (donut) ----------
labels = ["On track (LOW)", "Needs attention (MEDIUM)", "At risk (HIGH)"]
sizes = [62, 25, 13]
pie_colors = [GREEN, AMBER, "#EF4444"]
fig, ax = plt.subplots(figsize=(7, 5.2))
wedges, texts, autotexts = ax.pie(
    sizes, labels=labels, autopct="%1.0f%%", startangle=90,
    colors=pie_colors, pctdistance=0.75,
    wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    textprops=dict(fontsize=11, color=NAVY))
for t in autotexts:
    t.set_color("white")
    t.set_fontweight("bold")
    t.set_fontsize(11)
ax.set_title("AI Risk Engine — Sample Task Risk Distribution",
             fontsize=12, fontweight="bold", color=NAVY, pad=14)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "risk_donut.png"), dpi=200, bbox_inches="tight")
plt.close(fig)

print("Charts written to", OUT)

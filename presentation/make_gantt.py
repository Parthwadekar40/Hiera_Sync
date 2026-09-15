"""Gantt chart for HieraSync Review Seminar-I PPT (Appendix E)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

OUT = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(OUT, exist_ok=True)

NAVY = "#0B1E3B"
INDIGO = "#4F46E5"
GOLD = "#F59E0B"
GREEN = "#10B981"
SLATE = "#94A3B8"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "axes.edgecolor": "#CBD5E1",
})

phases = [
    ("Planning & Design", 7.0, 0.7, GREEN),
    ("Auth + Employees + Tasks", 7.5, 1.3, INDIGO),
    ("Events + Approvals + Notify", 8.4, 1.0, INDIGO),
    ("AI engine + Analytics + Goals", 8.9, 1.2, GOLD),
    ("Testing + Cloud deployment", 10.1, 1.0, SLATE),
    ("Review-II + Final demo", 11.0, 1.5, SLATE),
]

fig, ax = plt.subplots(figsize=(12, 4.0))
n = len(phases)
for i, (name, start, dur, col) in enumerate(phases):
    ax.broken_barh([(start, dur)], (n - 1 - i - 0.3, 0.6),
                   facecolors=col, edgecolor="white", linewidth=1.5)
ax.set_ylim(-0.5, n - 0.5)
ax.set_yticks(range(n))
ax.set_yticklabels([p[0] for p in reversed(phases)], fontsize=10.5, color=NAVY)
ax.set_xlim(7, 12.6)
ax.set_xticks([7, 8, 9, 10, 11, 12])
ax.set_xticklabels(["Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                   fontsize=10.5, color=NAVY)
ax.set_xlabel("2026", fontsize=10, color="#64748B")
ax.axvline(9.45, color=GOLD, linestyle="--", linewidth=2)
ax.text(9.45, n - 0.55, " Review–I (today) ", fontsize=10, fontweight="bold",
        color=NAVY, va="top", ha="left",
        bbox=dict(facecolor="#FEF3C7", edgecolor="none",
                  boxstyle="round,pad=0.3"))
ax.set_title("Project Gantt — July to December 2026",
             fontsize=13, fontweight="bold", color=NAVY, pad=10)
ax.grid(True, axis="x", color="#E2E8F0", linewidth=0.7)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "gantt.png"), dpi=200, bbox_inches="tight")
plt.close(fig)
print("Gantt written to", OUT)

"""Figures for presentation/outline.md. Every number is copied from results/FINDINGS.md (section noted)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).parent / "figures"
ACCENT = "#4F81BD"
GREY = "#7F7F7F"
RED = "#C0504D"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 13})


def fig_baselines(path):
    # FINDINGS section 2, 3,545 common test rows, RPS
    names = ["Stage 1\nstatic Dixon-Coles", "Stage 2\nsequential filter", "Closing market\naverage"]
    rps = [0.2057245, 0.2060203, 0.1926041]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    bars = ax.bar(names, rps, color=[GREY, ACCENT, RED], width=0.55)
    for b, v in zip(bars, rps):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.0004, f"{v:.4f}", ha="center")
    ax.set_ylim(0.18, 0.21)
    ax.set_ylabel("RPS (lower is better)")
    ax.set_title("Retrospective TEST, 3,545 common rows", fontsize=13)
    fig.text(0.01, 0.01, "Source: FINDINGS section 2. Y axis truncated at 0.18. Market is later than T-60: benchmark only.",
             fontsize=8, color=GREY)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=200)


def fig_gate_b(path):
    # FINDINGS section 4
    rows = [("c_att", 0.0950, 0.0487, 0.1413), ("c_def", -0.0022, -0.0413, 0.0368)]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for i, (n, est, lo, hi) in enumerate(rows):
        ax.errorbar(est, i, xerr=[[est - lo], [hi - est]], fmt="o", color=ACCENT, capsize=5, lw=2)
        ax.text(hi + 0.004, i, f"{est:+.4f}  [{lo:.4f}, {hi:.4f}]", va="center", fontsize=11)
    ax.axvline(0, color=GREY, ls="--", lw=1)
    ax.set_yticks([0, 1]); ax.set_yticklabels([r[0] for r in rows]); ax.set_ylim(-0.6, 1.6)
    ax.set_xlim(-0.06, 0.28)
    ax.set_xlabel("coefficient (95% CI)")
    ax.set_title("Lineup Gate B: FAILED (2026-10-19)", fontsize=13)
    fig.text(0.01, 0.01, "Source: FINDINGS section 4. c_def interval includes 0.", fontsize=8, color=GREY)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=200)


def fig_p1_test(path):
    # FINDINGS section 6, primary: log-loss difference P1 minus Stage 2, all 3,829 TEST rows
    est, lo, hi = -0.012828, -0.015519, -0.010091
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.errorbar(est, 0, xerr=[[est - lo], [hi - est]], fmt="o", color=ACCENT, capsize=6, lw=2.5, ms=9)
    ax.axvline(0, color=RED, ls="--", lw=1.2)
    ax.text(0.0004, 0.28, "0 = no change", color=RED, fontsize=10)
    ax.text(est, -0.3, f"{est:.6f}  [{lo:.6f}, {hi:.6f}]", ha="center", fontsize=11)
    ax.set_yticks([]); ax.set_ylim(-0.55, 0.55); ax.set_xlim(-0.02, 0.004)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("log-loss difference, P1 minus Stage 2 (negative = P1 better)")
    ax.set_title("One-shot TEST (retrospective, 3,829 rows): week-block 95% CI", fontsize=12)
    fig.text(0.01, 0.01, "Source: FINDINGS section 6. TEST window was examined in Stages 1-5 before this scoring.",
             fontsize=8, color=GREY)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=200)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    fig_baselines(OUT / "baselines_rps.png")
    fig_gate_b(OUT / "gate_b.png")
    fig_p1_test(OUT / "p1_test.png")

"""Plot derived monthly wealth paths; no price acquisition or strategy fitting."""
from pathlib import Path
import argparse
from io import BytesIO
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def build(folder, preview=None):
    monthly_path = folder / "monthly_paths.csv"
    if not monthly_path.exists():
        monthly_path = folder / "monthly_paths.csv.gz"
    if monthly_path.exists():
        monthly = pd.read_csv(monthly_path)
    else:
        from analysis_2026.theory_lab.restore_exports import read_raw
        monthly = pd.read_csv(BytesIO(read_raw(folder)))
    plt.rcParams.update({"font.size": 10, "svg.fonttype": "none", "svg.hashsalt": "theory-lab"})
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), layout="constrained")
    stock = [("C4", "C4_sso_gold", "50% SSO / 50% gold", "#176087"),
             ("C3", "C3_global", "Global momentum", "#bc6d19"),
             ("C4", "hold_benchmark", "SPY", "#54565a"),
             ("C4", "spy_gold50", "50% SPY / 50% gold", "#58a189")]
    crypto = [("C5", "C5_crypto", "BTC/ETH leadership", "#176087"),
              ("C5", "hold_benchmark", "Hold BTC", "#54565a"),
              ("C5", "crypto_equal", "Monthly 50% BTC / 50% ETH", "#58a189"),
              ("C5", "moneyline_slots", "Moneyline, two independent slots", "#bc6d19")]
    groups = [(axes[0], stock, "Stocks / gold: January 2007–December 2025", .0002),
              (axes[1], crypto, "Crypto: January 2019–December 2025", .0015)]
    for ax, items, title, fee in groups:
        for family, policy, label, color in items:
            data = monthly[monthly.family.eq(family) & monthly.policy.eq(policy)
                           & monthly.window.eq("full") & monthly.fee.eq(fee)
                           & monthly.lag.eq(1) & monthly.cash_rate.eq(0)]
            if data.empty:
                raise ValueError(f"Missing primary path: {family}/{policy}")
            ax.plot(pd.to_datetime(data.month + "-01"), data.ending_equity / 100000,
                    label=label, color=color, lw=1.8)
        ax.set_yscale("log")
        ax.set_ylabel("Growth of $1 (log scale)")
        ax.set_title(title, loc="left", weight="bold")
        ax.grid(alpha=.18)
        ax.legend(loc="upper left", frameon=False, ncol=2, fontsize=9)
    fig.suptitle("Five fixed hypotheses: the three identified primary histories", fontsize=15, weight="bold")
    fig.supxlabel("After modeled trading costs; before taxes. Stock selectors C1/C2 have unidentified long histories.", fontsize=9)
    fig.savefig(folder / "primary_growth.svg", metadata={"Date": None})
    if preview:
        fig.savefig(preview, dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "results_theory_lab")
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    build(args.output, args.preview)

"""
Counterplay Visual Analytics
Generates matplotlib charts for the Streamlit UI and PDF report.
All functions return matplotlib Figure objects.
"""

import io
from datetime import datetime, timezone
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from reportlab.platypus import Image as RLImage


# ── Brand color palette ──────────────────────────────────────────────

BRAND_COLORS = ["#e94560", "#1a1a2e", "#4a90d9"]
DARK = "#1a1a2e"
ACCENT = "#e94560"
SUBTLE = "#6b7280"
LIGHT_BG = "#f5f5f7"

FUNNEL_COLORS = {
    "Awareness": "#60a5fa",
    "Consideration": "#3b82f6",
    "Conversion": "#f97316",
    "Retention": "#ef4444",
}


def _apply_style(fig, ax):
    """Apply consistent minimal styling to charts."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d1d5db")
    ax.spines["bottom"].set_color("#d1d5db")
    ax.tick_params(colors=SUBTLE, labelsize=8)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")


def _no_data_figure(title: str = "No data available") -> plt.Figure:
    """Return a placeholder figure when there's no data."""
    fig, ax = plt.subplots(figsize=(8, 2))
    ax.text(0.5, 0.5, title, ha="center", va="center",
            fontsize=12, color=SUBTLE, transform=ax.transAxes)
    ax.set_axis_off()
    fig.tight_layout()
    return fig


# ── Chart 1: Creative Archetype Distribution ─────────────────────────


def archetype_distribution_chart(brand_data: dict) -> plt.Figure:
    """Grouped horizontal bar chart of creative archetypes per brand."""
    brands = list(brand_data.keys())
    if not brands:
        return _no_data_figure("No brand data for archetype chart")

    # Count archetypes per brand
    brand_counts = {}
    all_archetypes = Counter()
    for brand in brands:
        clfs = brand_data[brand].get("classifications", [])
        counts = Counter(c.get("creative_archetype", "Unknown") for c in clfs)
        brand_counts[brand] = counts
        all_archetypes.update(counts)

    if not all_archetypes:
        return _no_data_figure("No classifications available")

    # Sort archetypes by total frequency, take top 8 for readability
    top_archetypes = [a for a, _ in all_archetypes.most_common(8)]

    n_brands = len(brands)
    bar_height = 0.8 / n_brands
    y_pos = np.arange(len(top_archetypes))

    fig, ax = plt.subplots(figsize=(8, max(3, len(top_archetypes) * 0.5)))

    for i, brand in enumerate(brands):
        counts = [brand_counts[brand].get(a, 0) for a in top_archetypes]
        offset = (i - n_brands / 2 + 0.5) * bar_height
        bars = ax.barh(y_pos + offset, counts, bar_height * 0.9,
                       label=brand, color=BRAND_COLORS[i % len(BRAND_COLORS)],
                       alpha=0.85)
        for bar, count in zip(bars, counts):
            if count > 0:
                ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                        str(count), va="center", fontsize=7, color=SUBTLE)

    ax.set_yticks(y_pos)
    ax.set_yticklabels([a[:25] for a in top_archetypes], fontsize=8)
    ax.set_xlabel("Number of Ads", fontsize=9, color=SUBTLE)
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("Creative Archetype Distribution", fontsize=11,
                 fontweight="bold", color=DARK, pad=12)
    _apply_style(fig, ax)
    ax.invert_yaxis()
    fig.tight_layout()
    return fig


# ── Chart 2: Funnel Stage Breakdown ──────────────────────────────────


def funnel_stage_chart(brand_data: dict) -> plt.Figure:
    """Stacked 100% horizontal bar chart of funnel stages per brand."""
    brands = list(brand_data.keys())
    if not brands:
        return _no_data_figure("No brand data for funnel chart")

    stages = ["Awareness", "Consideration", "Conversion", "Retention"]

    fig, ax = plt.subplots(figsize=(8, max(2, len(brands) * 0.8 + 1)))

    for i, brand in enumerate(brands):
        clfs = brand_data[brand].get("classifications", [])
        if not clfs:
            continue
        total = len(clfs)
        stage_counts = Counter(c.get("funnel_stage", "Unknown") for c in clfs)

        left = 0
        for stage in stages:
            count = stage_counts.get(stage, 0)
            pct = count / total * 100 if total else 0
            bar = ax.barh(i, pct, left=left, height=0.5,
                          color=FUNNEL_COLORS.get(stage, "#999"),
                          label=stage if i == 0 else "")
            if pct > 10:
                ax.text(left + pct / 2, i, f"{pct:.0f}%",
                        ha="center", va="center", fontsize=7,
                        color="white", fontweight="bold")
            left += pct

    ax.set_yticks(range(len(brands)))
    ax.set_yticklabels(brands, fontsize=9)
    ax.set_xlabel("% of Ads", fontsize=9, color=SUBTLE)
    ax.set_xlim(0, 100)
    ax.legend(fontsize=8, frameon=False, loc="upper center",
              bbox_to_anchor=(0.5, -0.15), ncol=4)
    ax.set_title("Funnel Stage Balance", fontsize=11,
                 fontweight="bold", color=DARK, pad=12)
    _apply_style(fig, ax)
    fig.tight_layout()
    return fig


# ── Chart 3: Message Lever Heatmap ───────────────────────────────────


def message_lever_heatmap(brand_data: dict) -> plt.Figure:
    """Heatmap matrix: brands (rows) x message levers (columns)."""
    brands = list(brand_data.keys())
    if not brands:
        return _no_data_figure("No brand data for heatmap")

    # Collect all levers that appear
    all_levers = Counter()
    brand_lever_counts = {}
    for brand in brands:
        clfs = brand_data[brand].get("classifications", [])
        counts = Counter(c.get("message_lever", "Unknown") for c in clfs)
        brand_lever_counts[brand] = counts
        all_levers.update(counts)

    if not all_levers:
        return _no_data_figure("No classification data for heatmap")

    # Top levers by frequency
    levers = [l for l, _ in all_levers.most_common(8)]

    matrix = []
    for brand in brands:
        row = [brand_lever_counts[brand].get(l, 0) for l in levers]
        matrix.append(row)

    matrix = np.array(matrix)

    fig, ax = plt.subplots(figsize=(max(6, len(levers) * 0.9), max(2, len(brands) * 0.7 + 1.5)))

    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("accent", ["#ffffff", "#fca5a5", ACCENT])

    im = ax.imshow(matrix, cmap=cmap, aspect="auto")

    ax.set_xticks(range(len(levers)))
    ax.set_xticklabels([l[:18] for l in levers], fontsize=7, rotation=35, ha="right")
    ax.set_yticks(range(len(brands)))
    ax.set_yticklabels(brands, fontsize=9)

    # Annotate cells
    for i in range(len(brands)):
        for j in range(len(levers)):
            val = matrix[i, j]
            if val > 0:
                text_color = "white" if val > matrix.max() * 0.6 else DARK
                ax.text(j, i, str(int(val)), ha="center", va="center",
                        fontsize=8, fontweight="bold", color=text_color)

    ax.set_title("Message Lever Heatmap", fontsize=11,
                 fontweight="bold", color=DARK, pad=12)
    fig.colorbar(im, ax=ax, shrink=0.6, label="Ad Count")
    fig.tight_layout()
    return fig


# ── Chart 4: Creative Freshness Histogram ────────────────────────────


def creative_freshness_histogram(brand_data: dict) -> plt.Figure:
    """Overlaid histograms of ad age in days per brand."""
    brands = list(brand_data.keys())
    if not brands:
        return _no_data_figure("No brand data for freshness chart")

    now = datetime.now(timezone.utc)
    bins = [0, 7, 14, 30, 60, 90, 180, 365]
    bin_labels = ["0-7d", "7-14d", "14-30d", "30-60d", "60-90d", "90-180d", "180d+"]

    fig, ax = plt.subplots(figsize=(8, 3.5))

    has_data = False
    for i, brand in enumerate(brands):
        ads = brand_data[brand].get("ads", [])
        ages = []
        for ad in ads:
            start = ad.get("start_date", "")
            if start:
                try:
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    ages.append((now - start_dt).days)
                except (ValueError, TypeError):
                    pass

        if ages:
            has_data = True
            ax.hist(ages, bins=bins, alpha=0.6, label=brand,
                    color=BRAND_COLORS[i % len(BRAND_COLORS)],
                    edgecolor="white", linewidth=0.5)

    if not has_data:
        plt.close(fig)
        return _no_data_figure("No date data available")

    ax.set_xlabel("Ad Age (days)", fontsize=9, color=SUBTLE)
    ax.set_ylabel("Number of Ads", fontsize=9, color=SUBTLE)
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("Creative Freshness — Ad Age Distribution", fontsize=11,
                 fontweight="bold", color=DARK, pad=12)
    _apply_style(fig, ax)
    fig.tight_layout()
    return fig


# ── Chart 5: CTA Type Distribution ──────────────────────────────────


def cta_type_chart(brand_data: dict) -> plt.Figure:
    """Grouped vertical bar chart of CTA types per brand."""
    brands = list(brand_data.keys())
    if not brands:
        return _no_data_figure("No brand data for CTA chart")

    all_ctas = Counter()
    brand_cta_counts = {}
    for brand in brands:
        clfs = brand_data[brand].get("classifications", [])
        counts = Counter(c.get("cta_type", "Unknown") for c in clfs)
        brand_cta_counts[brand] = counts
        all_ctas.update(counts)

    if not all_ctas:
        return _no_data_figure("No CTA data available")

    top_ctas = [c for c, _ in all_ctas.most_common(6)]
    n_brands = len(brands)
    bar_width = 0.8 / n_brands
    x_pos = np.arange(len(top_ctas))

    fig, ax = plt.subplots(figsize=(8, 3.5))

    for i, brand in enumerate(brands):
        counts = [brand_cta_counts[brand].get(c, 0) for c in top_ctas]
        offset = (i - n_brands / 2 + 0.5) * bar_width
        ax.bar(x_pos + offset, counts, bar_width * 0.9,
               label=brand, color=BRAND_COLORS[i % len(BRAND_COLORS)],
               alpha=0.85)

    ax.set_xticks(x_pos)
    ax.set_xticklabels([c[:15] for c in top_ctas], fontsize=8, rotation=20, ha="right")
    ax.set_ylabel("Number of Ads", fontsize=9, color=SUBTLE)
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("CTA Type Distribution", fontsize=11,
                 fontweight="bold", color=DARK, pad=12)
    _apply_style(fig, ax)
    fig.tight_layout()
    return fig


# ── Chart 6: Strategic Positioning Scatter ───────────────────────────


def strategic_positioning_scatter(brand_data: dict) -> plt.Figure:
    """2D scatter: x = % high-polish, y = % with offer."""
    brands = list(brand_data.keys())
    if not brands:
        return _no_data_figure("No brand data for positioning map")

    fig, ax = plt.subplots(figsize=(6, 5))

    points = []
    for i, brand in enumerate(brands):
        clfs = brand_data[brand].get("classifications", [])
        if not clfs:
            continue
        total = len(clfs)
        high_polish = sum(1 for c in clfs
                          if "high" in (c.get("production_quality") or "").lower()
                          or "premium" in (c.get("production_quality") or "").lower())
        offers = sum(1 for c in clfs if c.get("has_offer"))
        x = high_polish / total * 100
        y = offers / total * 100
        points.append((x, y, brand, i))

    if not points:
        plt.close(fig)
        return _no_data_figure("No classification data for positioning")

    # Quadrant lines
    ax.axhline(y=50, color="#e5e7eb", linewidth=1, linestyle="--", zorder=0)
    ax.axvline(x=50, color="#e5e7eb", linewidth=1, linestyle="--", zorder=0)

    # Quadrant labels
    ax.text(25, 85, "Promo\nGrinders", ha="center", va="center",
            fontsize=8, color="#d1d5db", fontstyle="italic")
    ax.text(75, 85, "Premium\nPromo", ha="center", va="center",
            fontsize=8, color="#d1d5db", fontstyle="italic")
    ax.text(25, 15, "Raw\nPerformers", ha="center", va="center",
            fontsize=8, color="#d1d5db", fontstyle="italic")
    ax.text(75, 15, "Premium\nBuilders", ha="center", va="center",
            fontsize=8, color="#d1d5db", fontstyle="italic")

    for x, y, brand, i in points:
        ax.scatter(x, y, s=200, color=BRAND_COLORS[i % len(BRAND_COLORS)],
                   zorder=5, alpha=0.85, edgecolors="white", linewidths=1.5)
        ax.annotate(brand, (x, y), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=9,
                    fontweight="bold", color=DARK)

    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.set_xlabel("Production Quality (% high-polish)", fontsize=9, color=SUBTLE)
    ax.set_ylabel("Offer Dependency (% with offer)", fontsize=9, color=SUBTLE)
    ax.set_title("Strategic Positioning Map", fontsize=11,
                 fontweight="bold", color=DARK, pad=12)
    _apply_style(fig, ax)
    fig.tight_layout()
    return fig


# ── Sample Ad Selector ───────────────────────────────────────────────


def select_sample_ads(ads: list, classifications: list, n: int = 3) -> list[dict]:
    """
    Select n diverse sample ads by matching classifications to ads.
    Returns list of merged dicts (ad fields + classification fields).
    """
    if not ads or not classifications:
        return []

    # Build lookup: ad_id -> classification
    clf_map = {}
    for clf in classifications:
        aid = str(clf.get("ad_id", ""))
        if aid:
            clf_map[aid] = clf

    # Merge ads with classifications
    merged = []
    for ad in ads:
        ad_id = str(ad.get("id", ""))
        clf = clf_map.get(ad_id, {})
        if clf:
            merged.append({**ad, **clf})

    if not merged:
        # Fallback: positional matching
        for i, (ad, clf) in enumerate(zip(ads, classifications)):
            merged.append({**ad, **clf})
            if i >= n * 2:
                break

    if not merged:
        return []

    # Select diverse archetypes
    seen_archetypes = set()
    selected = []
    for item in merged:
        arch = item.get("creative_archetype", "")
        if arch not in seen_archetypes:
            selected.append(item)
            seen_archetypes.add(arch)
            if len(selected) >= n:
                break

    # Fill remaining slots if needed
    if len(selected) < n:
        for item in merged:
            if item not in selected:
                selected.append(item)
                if len(selected) >= n:
                    break

    return selected[:n]


# ── Figure to ReportLab Image ────────────────────────────────────────


def fig_to_image_flowable(fig: plt.Figure, width_inches: float = 6.0) -> RLImage:
    """Convert a matplotlib Figure to a ReportLab Image flowable."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)

    # Compute height from aspect ratio
    fig_w, fig_h = fig.get_size_inches()
    aspect = fig_h / fig_w
    from reportlab.lib.units import inch
    width = width_inches * inch
    height = width * aspect

    return RLImage(buf, width=width, height=height)

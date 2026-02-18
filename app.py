"""
COUNTERPLAY
Competitive Creative Intelligence

A free tool for marketers to analyze competitive advertising landscapes.
Built by Anshul Sinha.
"""

import streamlit as st
from datetime import datetime
from html import escape as html_escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scraper.meta import fetch_landscape
from analysis.engine import run_full_analysis
from output.pdf_generator import generate_pdf
from output.charts import (
    archetype_distribution_chart,
    funnel_stage_chart,
    message_lever_heatmap,
    creative_freshness_histogram,
    cta_type_chart,
    strategic_positioning_scatter,
    select_sample_ads,
)
from config import MARKETS
from usage import (
    get_usage,
    increment_usage,
    can_use,
    validate_email,
    is_approved,
    is_admin_email,
    approve_email,
    remove_approved_email,
    get_all_approved_users,
    verify_admin_key,
    ANALYSIS_LIMIT,
)


# ── Page config ───────────────────────────────────────────────────────

st.set_page_config(
    page_title="Counterplay — Competitive Creative Intelligence",
    page_icon="⚔️",
    layout="centered",
    initial_sidebar_state="expanded",
)


# ── Admin mode detection ──────────────────────────────────────────────

query_params = st.query_params
admin_key = query_params.get("admin", "")
is_admin = verify_admin_key(admin_key) if admin_key else False


# ── Custom CSS ────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        font-size: 2.8rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0;
        letter-spacing: -1px;
    }

    .sub-header {
        font-size: 1.1rem;
        color: #6b7280;
        margin-top: -8px;
        margin-bottom: 24px;
    }

    .accent-line {
        width: 60px;
        height: 4px;
        background: #e94560;
        margin: 8px 0 20px 0;
        border-radius: 2px;
    }

    .brand-pill {
        display: inline-block;
        background: #1a1a2e;
        color: white;
        padding: 4px 14px;
        border-radius: 16px;
        font-size: 0.85rem;
        margin-right: 6px;
        font-weight: 600;
    }

    .status-box {
        background: #f0fdf4;
        border-left: 4px solid #22c55e;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 12px 0;
    }

    .warning-box {
        background: #fefce8;
        border-left: 4px solid #eab308;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin: 12px 0;
    }

    div[data-testid="stSidebar"] {
        background: #fafafa;
    }

    .stDownloadButton > button {
        background: #e94560 !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 8px 24px !important;
        border-radius: 8px !important;
    }

    .stDownloadButton > button:hover {
        background: #d63851 !important;
    }

    section[data-testid="stSidebar"] .stTextInput input {
        font-size: 0.85rem;
    }

    .footer-text {
        text-align: center;
        color: #9ca3af;
        font-size: 0.8rem;
        margin-top: 40px;
        padding-top: 20px;
        border-top: 1px solid #e5e7eb;
    }

    .ad-card {
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
        background: #1e1e2e;
    }

    .ad-card .ad-body {
        font-size: 0.85rem;
        color: #d1d5db;
        margin-bottom: 8px;
        line-height: 1.4;
    }

    .ad-card .ad-title {
        font-weight: 600;
        color: #f3f4f6;
        margin-bottom: 6px;
        font-size: 0.9rem;
    }

    .ad-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.7rem;
        margin-right: 4px;
        margin-top: 6px;
        font-weight: 600;
    }

    .ad-badge.archetype { background: #3b1f2b; color: #e94560; }
    .ad-badge.funnel { background: #1e293b; color: #60a5fa; }
    .ad-badge.media { background: #1a2e1a; color: #4ade80; }
    .ad-badge.tone { background: #2e2a1a; color: #fbbf24; }

    .ad-card a {
        color: #e94560;
        font-size: 0.78rem;
        text-decoration: none;
        font-weight: 600;
    }

    .ad-card a:hover { text-decoration: underline; }

    .access-box {
        background: #fef3c7;
        border: 1px solid #f59e0b;
        border-radius: 10px;
        padding: 20px 24px;
        text-align: center;
        margin: 24px 0;
    }

    .access-box h3 {
        color: #92400e;
        margin-bottom: 8px;
    }

    .access-box p {
        color: #78350f;
        font-size: 0.95rem;
    }

    .access-box a {
        display: inline-block;
        background: #0a66c2;
        color: white !important;
        padding: 8px 20px;
        border-radius: 6px;
        text-decoration: none;
        font-weight: 600;
        margin-top: 10px;
    }

    .access-box a:hover {
        background: #084e96;
    }

    .admin-badge {
        display: inline-block;
        background: #dc2626;
        color: white;
        padding: 2px 10px;
        border-radius: 10px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 1px;
        margin-left: 8px;
        vertical-align: middle;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════════════════════════════

if is_admin:
    st.markdown(
        '<h1 class="main-header">COUNTERPLAY <span class="admin-badge">ADMIN</span></h1>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="accent-line"></div>', unsafe_allow_html=True)
    st.markdown("Manage approved users and monitor usage.")

    st.markdown("---")

    # ── Add new approved email ────────────────────────────────────────
    st.markdown("### Add Approved User")
    add_col1, add_col2 = st.columns([2, 1])
    with add_col1:
        new_email = st.text_input("Email to approve", placeholder="user@example.com")
    with add_col2:
        new_note = st.text_input("Note (optional)", placeholder="LinkedIn DM")

    if st.button("Approve Email", type="primary"):
        if not new_email or not validate_email(new_email):
            st.error("Enter a valid email address.")
        else:
            added = approve_email(new_email, new_note)
            if added:
                st.success(f"Approved: {new_email.strip().lower()}")
            else:
                st.warning(f"Already approved: {new_email.strip().lower()}")
            st.rerun()

    st.markdown("---")

    # ── Approved users table ──────────────────────────────────────────
    st.markdown("### Approved Users")
    users = get_all_approved_users()

    if users:
        st.caption(f"{len(users)} approved users")

        for user in users:
            col1, col2, col3, col4 = st.columns([3, 1, 2, 1])
            with col1:
                st.markdown(f"**{user['email']}**")
                if user["note"]:
                    st.caption(user["note"])
            with col2:
                used = user["usage_count"]
                st.markdown(f"**{used}/{ANALYSIS_LIMIT}** used")
            with col3:
                approved_dt = user["approved_at"][:10] if user["approved_at"] else "—"
                last_use = user["last_use"][:10] if user["last_use"] else "never"
                st.caption(f"Approved: {approved_dt} | Last use: {last_use}")
            with col4:
                if st.button("Remove", key=f"rm_{user['email']}"):
                    remove_approved_email(user["email"])
                    st.rerun()
            st.markdown("---")
    else:
        st.info("No approved users yet. Add emails above.")

    # Footer
    st.markdown(
        '<p class="footer-text">'
        'COUNTERPLAY ADMIN PANEL<br>'
        'Built by <a href="https://linkedin.com/in/anshul-sinha-7bb3b7101" '
        'target="_blank">Anshul Sinha</a>'
        '</p>',
        unsafe_allow_html=True,
    )

    st.stop()  # Don't render the main app when in admin mode


# ══════════════════════════════════════════════════════════════════════
# MAIN APP (user-facing)
# ══════════════════════════════════════════════════════════════════════


# ── Sidebar: user identification ─────────────────────────────────────

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    st.markdown("---")

    user_email = st.text_input(
        "Your Email",
        placeholder="you@company.com",
        help="Enter the email you were approved with.",
    )

    # Show approval + usage status
    if user_email and validate_email(user_email):
        approved = is_approved(user_email)

        if approved:
            usage_info = get_usage(user_email)
            used = usage_info["usage_count"]
            remaining = usage_info["remaining"]
            admin_user = is_admin_email(user_email)

            st.markdown("✅ **Access approved**")
            if admin_user:
                st.caption(f"**{used}** analyses run — **Unlimited**")
            else:
                st.caption(f"**{used}** of **{ANALYSIS_LIMIT}** analyses used")
                st.progress(min(used / ANALYSIS_LIMIT, 1.0))

                if remaining == 0:
                    st.error("All analyses used. DM for more access.")
                elif remaining == 1:
                    st.warning("1 analysis remaining.")
        else:
            st.markdown("🔒 **Access not approved**")
            st.caption("DM on LinkedIn to request access.")

    st.markdown("---")
    st.markdown(
        '<p style="color: #9ca3af; font-size: 0.75rem;">Built by '
        '<a href="https://linkedin.com/in/anshul-sinha-7bb3b7101" target="_blank">'
        'Anshul Sinha</a></p>',
        unsafe_allow_html=True,
    )


# ── Main content ──────────────────────────────────────────────────────

st.markdown('<h1 class="main-header">COUNTERPLAY</h1>', unsafe_allow_html=True)
st.markdown('<div class="accent-line"></div>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">'
    'Competitive creative intelligence for marketers. '
    'Analyze what your competitors are running, how they differ, and where the gaps are.'
    '</p>',
    unsafe_allow_html=True,
)


# ── Gate check: show request-access CTA if not approved ──────────────

email_valid = user_email and validate_email(user_email)
user_approved = email_valid and is_approved(user_email)
user_has_quota = email_valid and can_use(user_email)

if email_valid and not user_approved:
    st.markdown(
        """
        <div class="access-box">
            <h3>🔒 Access Required</h3>
            <p>
                Counterplay is currently invite-only.<br>
                Drop me a message on LinkedIn with your email and I'll get you set up.
            </p>
            <a href="https://linkedin.com/in/anshul-sinha-7bb3b7101" target="_blank">
                Message on LinkedIn
            </a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


# ── Input form ────────────────────────────────────────────────────────

with st.container():
    col1, col2 = st.columns(2)

    with col1:
        market = st.selectbox(
            "Market",
            options=list(MARKETS.keys()),
            index=0,
            help="Which country's ad landscape do you want to analyze?",
        )

    with col2:
        category = st.text_input(
            "Category",
            placeholder="e.g. Quick Commerce, D2C Skincare, Fintech",
            help="What category or vertical are these brands in?",
        )

    st.markdown("##### Brands to analyze (2-3)")
    brand_cols = st.columns(3)

    brands = []
    for i, col in enumerate(brand_cols):
        with col:
            brand = st.text_input(
                f"Brand {i+1}",
                placeholder=f"Brand name",
                key=f"brand_{i}",
                label_visibility="collapsed",
            )
            if brand.strip():
                brands.append(brand.strip())

    # Validation
    can_run = True
    if len(brands) < 2:
        can_run = False
    if not category:
        can_run = False
    if not user_email or not validate_email(user_email):
        can_run = False
    elif not can_use(user_email):
        can_run = False

    run_button = st.button(
        "⚔️ Run Counterplay",
        type="primary",
        disabled=not can_run,
        use_container_width=True,
    )

    if not can_run:
        missing = []
        if len(brands) < 2:
            missing.append("at least 2 brand names")
        if not category:
            missing.append("a category")
        if not user_email:
            missing.append("your email address (sidebar)")
        elif not validate_email(user_email):
            missing.append("a valid email address")
        elif not user_has_quota:
            missing.append("analysis quota (all 3 used)")
        if missing:
            st.caption(f"Need: {', '.join(missing)}")


# ── Analysis execution ────────────────────────────────────────────────

if run_button and can_run:
    country_code = MARKETS[market]

    st.markdown("---")

    with st.status("Running Counterplay analysis...", expanded=True) as status:

        # Step 1: Fetch ads
        st.write(f"🔍 Fetching ads from Meta Ad Library for {len(brands)} brands in {market}... (this may take 30-60s per brand)")
        try:
            ads_by_brand = fetch_landscape(
                brands=brands,
                country_code=country_code,
                ads_per_brand=50,
            )
        except Exception as e:
            st.error(f"Failed to fetch ads: {str(e)}")
            st.stop()

        # Show fetch results
        total_ads = sum(len(v) for v in ads_by_brand.values())
        for brand, ads in ads_by_brand.items():
            st.write(f"  → {brand}: {len(ads)} active ads found")

        if total_ads == 0:
            st.error(
                "No ads found for any brand. Check that the brand names match "
                "their Meta/Facebook page names. The Ad Library may also be "
                "temporarily rate-limiting requests — try again in a minute."
            )
            st.stop()

        # Step 2: Run analysis
        st.write("🧠 Analyzing creative strategies with Claude...")
        try:
            results = run_full_analysis(
                brands=brands,
                country_code=country_code,
                market_name=market,
                category=category,
                ads_by_brand=ads_by_brand,
            )
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            st.stop()

        # Step 3: Generate PDF
        st.write("📄 Generating landscape brief...")
        try:
            pdf_bytes = generate_pdf(results)
        except Exception as e:
            st.error(f"PDF generation failed: {str(e)}")
            pdf_bytes = None

        # Increment usage counter after successful analysis
        increment_usage(user_email)

        status.update(label="Analysis complete!", state="complete", expanded=False)

    # ── Results display ───────────────────────────────────────────────

    st.markdown("---")
    st.markdown("## 📊 Landscape Brief")

    # Download button
    if pdf_bytes:
        filename = (
            f"counterplay_{category.lower().replace(' ', '-')}"
            f"_{market.lower().replace(' ', '-')}"
            f"_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        st.download_button(
            label="⬇️ Download Full PDF Report",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            use_container_width=True,
        )

    st.markdown("---")

    # Overview stats
    st.markdown("### Snapshot")
    stat_cols = st.columns(len(brands))
    for i, brand in enumerate(brands):
        data = results["brand_data"].get(brand, {})
        ads = data.get("ads", [])
        clfs = data.get("classifications", [])
        with stat_cols[i]:
            st.metric(label=brand, value=f"{len(ads)} ads")
            if clfs:
                offers = sum(1 for c in clfs if c.get("has_offer"))
                st.caption(f"Offer rate: {offers/len(clfs)*100:.0f}%")

    # ── Visual analytics charts ─────────────────────────────────────
    st.markdown("---")

    st.markdown("### Creative Mix")
    fig = archetype_distribution_chart(results["brand_data"])
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("### Funnel Balance")
    fig = funnel_stage_chart(results["brand_data"])
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("### Message Levers")
    fig = message_lever_heatmap(results["brand_data"])
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("### Creative Freshness")
    fig = creative_freshness_histogram(results["brand_data"])
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("### CTA Distribution")
    fig = cta_type_chart(results["brand_data"])
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("### Strategic Positioning")
    fig = strategic_positioning_scatter(results["brand_data"])
    st.pyplot(fig)
    plt.close(fig)

    st.markdown("---")

    # Brand profiles
    st.markdown("### Brand Profiles")
    for brand, profile in results["brand_profiles"].items():
        with st.expander(f"**{brand}**", expanded=True):
            st.markdown(profile)

            # Sample ad preview cards
            brand_ads = results["brand_data"].get(brand, {}).get("ads", [])
            brand_clfs = results["brand_data"].get(brand, {}).get("classifications", [])
            samples = select_sample_ads(brand_ads, brand_clfs, n=3)
            if samples:
                st.markdown("#### 📋 Sample Ads from Library")
                for s in samples:
                    body = (s.get("body_text") or "")[:150]
                    if len(s.get("body_text") or "") > 150:
                        body += "..."
                    body = html_escape(body) if body else ""
                    title = html_escape(s.get("title") or "") if s.get("title") else ""
                    archetype = s.get("creative_archetype") or ""
                    funnel = s.get("funnel_stage") or ""
                    media = s.get("media_type") or ""
                    tone = s.get("emotional_tone") or ""
                    snap_url = s.get("snapshot_url") or ""

                    card_html = f"""
                    <div class="ad-card">
                        {f'<div class="ad-title">{title}</div>' if title else ''}
                        <div class="ad-body">{body if body else '<i>No ad copy</i>'}</div>
                        <div>
                            {f'<span class="ad-badge media">{media}</span>' if media else ''}
                            {f'<span class="ad-badge archetype">{archetype}</span>' if archetype else ''}
                            {f'<span class="ad-badge funnel">{funnel}</span>' if funnel else ''}
                            {f'<span class="ad-badge tone">{tone}</span>' if tone else ''}
                        </div>
                        {f'<div style="margin-top:8px"><a href="{snap_url}" target="_blank">View in Ad Library →</a></div>' if snap_url else ''}
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)

    st.markdown("---")

    # Landscape brief
    st.markdown("### Competitive Landscape")
    st.markdown(results["landscape_brief"])

    # Footer
    st.markdown(
        '<p class="footer-text">'
        'COUNTERPLAY — Competitive Creative Intelligence<br>'
        'Built by <a href="https://linkedin.com/in/anshul-sinha-7bb3b7101" '
        'target="_blank">Anshul Sinha</a>'
        '</p>',
        unsafe_allow_html=True,
    )

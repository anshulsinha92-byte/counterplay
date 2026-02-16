"""
Counterplay Analysis Engine
Uses Claude to perform deep qualitative + quantitative analysis
of competitive creative landscapes.
"""

import json
import os
from pathlib import Path
import anthropic
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load .env from the project root (parent of analysis/)
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)


# ── Taxonomy definitions ──────────────────────────────────────────────

CREATIVE_ARCHETYPES = [
    "UGC / creator-led",
    "Studio / professional shoot",
    "Lifestyle / aspirational",
    "Product hero / packshot",
    "Testimonial / review",
    "Comparison / vs competitor",
    "Meme / culture-jack",
    "Educational / how-to",
    "Founder-led / brand story",
    "Data / stat-driven",
    "Offer / promo-first",
    "Event / seasonal",
]

MESSAGE_LEVERS = [
    "Price / value",
    "Speed / convenience",
    "Quality / premium",
    "Selection / variety",
    "Trust / social proof",
    "Aspiration / status",
    "Fear / urgency / FOMO",
    "Innovation / newness",
    "Community / belonging",
    "Health / wellness",
]

FUNNEL_STAGES = ["Awareness", "Consideration", "Conversion", "Retention"]

PRODUCTION_QUALITY = ["Lo-fi / raw", "Mid-tier", "High-polish / premium"]


# ── Classification prompt ─────────────────────────────────────────────

CLASSIFY_PROMPT = """You are an expert performance marketing analyst. Analyze each ad below and classify it according to the taxonomy.

For each ad, return a JSON object with these fields:
- "ad_id": the ad ID
- "creative_archetype": one of {archetypes}
- "message_lever": primary one of {levers}
- "secondary_message": secondary message lever if present, else null
- "funnel_stage": one of {funnel_stages}
- "production_quality": one of {production_quality}
- "has_offer": boolean
- "offer_type": if has_offer, describe briefly (e.g. "20% off", "free delivery"), else null
- "cta_type": the call-to-action type (e.g. "Shop Now", "Learn More", "Download", "Sign Up", "No CTA")
- "key_benefit_claim": the single main benefit being communicated in 5-10 words
- "emotional_tone": 1-2 words describing the emotional register (e.g. "urgent", "aspirational", "playful", "authoritative")
- "notable_elements": any standout creative choices in 10 words or less

Ads to analyze:

{ads_text}

Return ONLY a JSON array of objects. No other text."""

# ── Brand profile prompt ──────────────────────────────────────────────

BRAND_PROFILE_PROMPT = """You are a senior marketing strategist analyzing {brand_name}'s advertising in {market}.

Here is quantitative data on their active ad portfolio:
{quant_summary}

Here are the classified ads with their taxonomy tags:
{classifications}

Write a sharp, opinionated brand creative profile covering:

1. **Strategic posture**: What is this brand's advertising strategy in one sentence? Are they playing offense or defense? Building brand or harvesting demand?

2. **Creative DNA**: What are the dominant creative patterns? What does their typical ad look like? What production values do they default to?

3. **Messaging architecture**: What benefits are they leading with? Is there a coherent messaging hierarchy or are they throwing everything at the wall?

4. **Funnel balance**: How are they distributing effort across awareness/consideration/conversion? Are they top-heavy or bottom-heavy?

5. **Offer dependency**: How reliant are they on promotional offers to drive action? Is this sustainable?

6. **Creative freshness**: Based on start dates, are they actively refreshing creative or running stale ads? Any signs of creative fatigue?

7. **Standout moves**: Any creative choices that are genuinely distinctive or surprising?

8. **Blind spots**: What are they NOT doing that they probably should be?

Be direct. Be specific. Use data from the analysis to back up every claim. No generic observations — everything should be grounded in what you actually see in their ads. Write as if briefing a CMO who needs to compete against this brand tomorrow."""

# ── Landscape comparison prompt ───────────────────────────────────────

LANDSCAPE_PROMPT = """You are a senior competitive strategy advisor. You've just analyzed the advertising landscape for the {category} category in {market}.

Here are the individual brand profiles:

{brand_profiles}

Here is the comparative data:
{comparative_data}

Now write the competitive landscape brief. This is the document a Head of Marketing would screenshot and send to their team. Be sharp, be opinionated, be useful.

Structure your analysis as follows:

## LANDSCAPE OVERVIEW
A 3-4 sentence executive summary of the competitive creative landscape. Who's dominant? What's the prevailing category playbook? Is there genuine strategic differentiation or is everyone doing the same thing?

## HEAD-TO-HEAD: STRATEGY COMPARISON
Compare the brands directly across key dimensions:
- Creative strategy (who's doing what differently)
- Messaging approach (where are they converging vs diverging)
- Funnel emphasis (who's investing in brand vs performance)
- Production investment (who's spending on creative quality)
- Offer dependency (who can sell without discounting)

## CATEGORY PATTERNS
What are the dominant patterns across ALL brands? What has become table stakes in this category? What creative approaches has the entire category converged on?

## THE WHITE SPACE
This is the most important section. Based on what everyone IS doing, identify what NOBODY is doing. These are the creative territories, messaging angles, or strategic approaches that represent genuine opportunity. Be specific — don't say "more brand advertising." Say exactly what kind of brand advertising, targeting what emotional territory, using what creative approach.

## PLATFORM INTELLIGENCE
How are brands using Meta differently? Are they running identical creative across Facebook and Instagram or tailoring by placement? Any platform-specific patterns worth noting?

## VERDICT
In 2-3 sentences: if you were entering this market to compete in this category tomorrow, what would your creative strategy be and why?

Ground everything in the data. No generic marketing platitudes. Every insight should be traceable to specific patterns in the ads you analyzed."""


def _build_ad_text_block(ads: list[dict], max_ads: int = 40) -> str:
    """Build a text representation of ads for Claude to analyze."""
    blocks = []
    for i, ad in enumerate(ads[:max_ads]):
        block = f"""--- Ad {i+1} (ID: {ad['id']}) ---
Body: {ad['body_text'][:500] if ad['body_text'] else '[no body text]'}
Title: {ad['title'] if ad['title'] else '[no title]'}
Description: {ad['description'] if ad['description'] else '[no description]'}
Media type: {ad['media_type']}
Start date: {ad['start_date'] if ad['start_date'] else 'unknown'}
Platforms: {', '.join(ad['publisher_platforms']) if ad['publisher_platforms'] else 'unknown'}"""
        blocks.append(block)
    return "\n\n".join(blocks)


def _build_quant_summary(ads: list[dict]) -> str:
    """Generate quantitative summary stats from ads."""
    if not ads:
        return "No ads found."

    total = len(ads)

    # Media type breakdown
    media_types = {}
    for ad in ads:
        mt = ad.get("media_type", "unknown")
        media_types[mt] = media_types.get(mt, 0) + 1

    # Platform breakdown
    platforms = {}
    for ad in ads:
        for p in ad.get("publisher_platforms", []):
            platforms[p] = platforms.get(p, 0) + 1

    # Creative age analysis
    now = datetime.now(timezone.utc)
    ages_days = []
    for ad in ads:
        start = ad.get("start_date", "")
        if start:
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                age = (now - start_dt).days
                ages_days.append(age)
            except (ValueError, TypeError):
                pass

    age_summary = ""
    if ages_days:
        avg_age = sum(ages_days) / len(ages_days)
        oldest = max(ages_days)
        newest = min(ages_days)
        over_90 = sum(1 for a in ages_days if a > 90)
        age_summary = f"""
Creative age:
- Average ad age: {avg_age:.0f} days
- Oldest active ad: {oldest} days
- Newest ad: {newest} days
- Ads running >90 days: {over_90} ({over_90/total*100:.0f}% — potential creative fatigue)"""

    media_str = ", ".join(f"{k}: {v} ({v/total*100:.0f}%)" for k, v in sorted(media_types.items(), key=lambda x: -x[1]))
    platform_str = ", ".join(f"{k}: {v}" for k, v in sorted(platforms.items(), key=lambda x: -x[1]))

    return f"""Total active ads: {total}
Media types: {media_str}
Platform distribution: {platform_str}{age_summary}"""


def classify_ads(
    ads: list[dict],
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514",
) -> list[dict]:
    """
    Send ads to Claude for taxonomy classification.
    Returns list of classification dicts.
    """
    if not ads:
        return []

    ads_text = _build_ad_text_block(ads)

    prompt = CLASSIFY_PROMPT.format(
        archetypes=json.dumps(CREATIVE_ARCHETYPES),
        levers=json.dumps(MESSAGE_LEVERS),
        funnel_stages=json.dumps(FUNNEL_STAGES),
        production_quality=json.dumps(PRODUCTION_QUALITY),
        ads_text=ads_text,
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Clean potential markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        classifications = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON array from response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            classifications = json.loads(text[start:end])
        else:
            classifications = []

    return classifications


def generate_brand_profile(
    brand_name: str,
    market: str,
    ads: list[dict],
    classifications: list[dict],
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """Generate a deep qualitative brand profile."""
    quant_summary = _build_quant_summary(ads)

    prompt = BRAND_PROFILE_PROMPT.format(
        brand_name=brand_name,
        market=market,
        quant_summary=quant_summary,
        classifications=json.dumps(classifications, indent=2)[:8000],
    )

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def generate_landscape_brief(
    category: str,
    market: str,
    brand_profiles: dict[str, str],
    brand_data: dict[str, dict],
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """
    Generate the full competitive landscape brief.
    brand_profiles: {brand_name: profile_text}
    brand_data: {brand_name: {"ads": [...], "classifications": [...]}}
    """
    # Build profiles section
    profiles_text = ""
    for brand, profile in brand_profiles.items():
        profiles_text += f"\n### {brand}\n{profile}\n"

    # Build comparative data
    comparative = "## Comparative Metrics\n\n"
    comparative += "| Brand | Active Ads | Media Mix | Avg Creative Age |\n"
    comparative += "|-------|-----------|-----------|------------------|\n"

    for brand, data in brand_data.items():
        ads = data["ads"]
        total = len(ads)
        
        # Media mix
        media = {}
        for ad in ads:
            mt = ad.get("media_type", "unknown")
            media[mt] = media.get(mt, 0) + 1
        media_str = ", ".join(f"{k}:{v}" for k, v in media.items())

        # Avg age
        ages = []
        now = datetime.now(timezone.utc)
        for ad in ads:
            start = ad.get("start_date", "")
            if start:
                try:
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    ages.append((now - start_dt).days)
                except (ValueError, TypeError):
                    pass
        avg_age = f"{sum(ages)/len(ages):.0f}d" if ages else "N/A"

        comparative += f"| {brand} | {total} | {media_str} | {avg_age} |\n"

    # Classification comparison
    comparative += "\n## Classification Comparison\n\n"
    for brand, data in brand_data.items():
        clfs = data.get("classifications", [])
        if not clfs:
            continue

        archetypes = {}
        levers = {}
        funnel = {}
        offer_count = 0

        for c in clfs:
            arch = c.get("creative_archetype", "unknown")
            archetypes[arch] = archetypes.get(arch, 0) + 1
            lever = c.get("message_lever", "unknown")
            levers[lever] = levers.get(lever, 0) + 1
            stage = c.get("funnel_stage", "unknown")
            funnel[stage] = funnel.get(stage, 0) + 1
            if c.get("has_offer"):
                offer_count += 1

        total_clfs = len(clfs)
        comparative += f"\n**{brand}**\n"
        comparative += f"- Top archetypes: {', '.join(f'{k} ({v})' for k, v in sorted(archetypes.items(), key=lambda x: -x[1])[:3])}\n"
        comparative += f"- Primary message levers: {', '.join(f'{k} ({v})' for k, v in sorted(levers.items(), key=lambda x: -x[1])[:3])}\n"
        comparative += f"- Funnel distribution: {', '.join(f'{k}: {v/total_clfs*100:.0f}%' for k, v in sorted(funnel.items(), key=lambda x: -x[1]))}\n"
        comparative += f"- Offer dependency: {offer_count}/{total_clfs} ads ({offer_count/total_clfs*100:.0f}%) carry promotional offers\n"

    prompt = LANDSCAPE_PROMPT.format(
        category=category,
        market=market,
        brand_profiles=profiles_text,
        comparative_data=comparative,
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text.strip()


def run_full_analysis(
    brands: list[str],
    country_code: str,
    market_name: str,
    category: str,
    ads_by_brand: dict[str, list[dict]],
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """
    Run the full Counterplay analysis pipeline.
    Returns a dict with all analysis components.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Set it in your .env file or environment."
        )
    client = anthropic.Anthropic(api_key=api_key)

    brand_data = {}
    brand_profiles = {}

    for brand in brands:
        ads = ads_by_brand.get(brand, [])
        if not ads:
            brand_profiles[brand] = f"No active ads found for {brand} in {market_name}."
            brand_data[brand] = {"ads": [], "classifications": []}
            continue

        # Step 1: Classify ads
        classifications = classify_ads(ads, client, model)

        brand_data[brand] = {
            "ads": ads,
            "classifications": classifications,
            "quant_summary": _build_quant_summary(ads),
        }

        # Step 2: Generate brand profile
        profile = generate_brand_profile(
            brand_name=brand,
            market=market_name,
            ads=ads,
            classifications=classifications,
            client=client,
            model=model,
        )
        brand_profiles[brand] = profile

    # Step 3: Generate landscape brief
    landscape_brief = generate_landscape_brief(
        category=category,
        market=market_name,
        brand_profiles=brand_profiles,
        brand_data=brand_data,
        client=client,
        model=model,
    )

    return {
        "brands": brands,
        "market": market_name,
        "country_code": country_code,
        "category": category,
        "brand_data": brand_data,
        "brand_profiles": brand_profiles,
        "landscape_brief": landscape_brief,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

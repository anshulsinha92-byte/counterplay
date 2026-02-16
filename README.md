# ⚔️ COUNTERPLAY

**Competitive Creative Intelligence for Marketers**

Counterplay analyzes what your competitors are running across ad platforms, how their strategies differ, and where the gaps are. Input 2-3 brands and a market — get a downloadable competitive landscape brief.

## What It Does

1. **Fetches** active ads from Meta Ad Library for your selected brands and market
2. **Classifies** every ad using AI across a deep taxonomy: creative archetype, message lever, funnel stage, production quality, offer dependency, and more
3. **Profiles** each brand's creative strategy with sharp, opinionated analysis
4. **Compares** brands head-to-head and identifies category patterns
5. **Finds the white space** — creative territories nobody is occupying
6. **Generates** a downloadable PDF landscape brief

## Quick Start

```bash
# Clone the repo
git clone <your-repo-url>
cd counterplay

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## Setup Requirements

### Meta Access Token (free)
1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Create a new app (choose "Business" type)
3. Go to **Tools** → **Graph API Explorer**
4. Generate a **User Access Token**
5. No special permissions needed — Ad Library is publicly accessible
6. Note: tokens expire after ~1 hour

### Anthropic API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account → **API Keys** → **Create Key**
3. Analysis costs ~$0.05-0.15 per landscape run

## Deploy to Streamlit Cloud

1. Push to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo
4. Set `app.py` as the main file
5. Deploy

Users provide their own API keys via the sidebar — no secrets needed in deployment.

## Project Structure

```
counterplay/
├── app.py                    # Streamlit UI
├── config.py                 # Market/country mappings
├── requirements.txt
├── scraper/
│   ├── meta.py              # Meta Ad Library API client
│   └── __init__.py
├── analysis/
│   ├── engine.py            # Claude-powered analysis pipeline
│   └── __init__.py
└── output/
    ├── pdf_generator.py     # PDF report generation
    └── __init__.py
```

## Analysis Taxonomy

Each ad is classified across:
- **Creative archetype**: UGC, studio, lifestyle, product-hero, testimonial, comparison, meme, educational, founder-led, data-driven, offer-first, seasonal
- **Message lever**: Price, speed, quality, selection, trust, aspiration, urgency, innovation, community, health
- **Funnel stage**: Awareness, consideration, conversion, retention
- **Production quality**: Lo-fi, mid-tier, high-polish
- **Offer dependency**: Offer present, offer type, CTA type
- **Strategic signals**: Key benefit claim, emotional tone, notable elements

## Roadmap

- [x] Meta Ad Library integration
- [ ] LinkedIn Ad Library scraping
- [ ] Google Ads Transparency Center scraping
- [ ] Multi-market comparison mode
- [ ] Creative screenshot capture via ad snapshot URLs
- [ ] Trend tracking over time

## Built By

[Anshul Sinha](https://linkedin.com/in/anshul-sinha-7bb3b7101) — Marketing leader with 12+ years building growth engines for consumer brands across international markets.

---

*Counterplay is a free tool for the marketing community. Use it, share it, break it.*

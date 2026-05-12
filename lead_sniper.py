"""
╔══════════════════════════════════════════════════════════╗
║           LEAD SNIPER - By Faizan                        ║
║   Reddit + Upwork Monitor → Instant Telegram Alerts      ║
╚══════════════════════════════════════════════════════════╝

Monitors Reddit & Upwork RSS feeds for matching keywords
and sends instant Telegram notifications with quick-copy pitch.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import feedparser
import httpx
import schedule
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

# ─── Setup ──────────────────────────────────────────────────────────────────

load_dotenv()
console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        RichHandler(console=console, rich_tracebacks=True, markup=True),
        logging.FileHandler("logs/lead_sniper.log"),
    ],
)
log = logging.getLogger("lead_sniper")

# ─── Config ─────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

KEYWORDS = [
    "shopify", "logo design", "logo designer", "web app", "web application",
    "web developer", "web development", "seo specialist", "seo expert",
    "brand designer", "brand design", "wordpress", "ecommerce", "e-commerce",
    "landing page", "responsive design", "frontend developer", "ui design",
    "need developer", "looking for developer", "hire developer",
]

# Reddit subreddits to monitor (RSS feeds - fully public, no auth needed)
REDDIT_FEEDS = [
    {
        "name":      "r/forhire",
        "url":       "https://www.reddit.com/r/forhire/new/.rss",
        "icon":      "🟠",
    },
    {
        "name":      "r/webdev",
        "url":       "https://www.reddit.com/r/webdev/new/.rss",
        "icon":      "🟠",
    },
    {
        "name":      "r/shopify",
        "url":       "https://www.reddit.com/r/shopify/new/.rss",
        "icon":      "🟠",
    },
    {
        "name":      "r/entrepreneur",
        "url":       "https://www.reddit.com/r/entrepreneur/new/.rss",
        "icon":      "🟠",
    },
    {
        "name":      "r/hiring",
        "url":       "https://www.reddit.com/r/hiring/new/.rss",
        "icon":      "🟠",
    },
]

# Upwork RSS feeds (public job feeds by category)
UPWORK_FEEDS = [
    {
        "name": "Upwork: Web Dev",
        "url":  "https://www.upwork.com/ab/feed/jobs/rss?q=web+developer&sort=recency&paging=0%3B10",
        "icon": "🟢",
    },
    {
        "name": "Upwork: Shopify",
        "url":  "https://www.upwork.com/ab/feed/jobs/rss?q=shopify&sort=recency&paging=0%3B10",
        "icon": "🟢",
    },
    {
        "name": "Upwork: Logo Design",
        "url":  "https://www.upwork.com/ab/feed/jobs/rss?q=logo+design&sort=recency&paging=0%3B10",
        "icon": "🟢",
    },
    {
        "name": "Upwork: SEO",
        "url":  "https://www.upwork.com/ab/feed/jobs/rss?q=seo+specialist&sort=recency&paging=0%3B10",
        "icon": "🟢",
    },
    {
        "name": "Upwork: Web App",
        "url":  "https://www.upwork.com/ab/feed/jobs/rss?q=web+application+developer&sort=recency&paging=0%3B10",
        "icon": "🟢",
    },
]

PITCH_MESSAGE = """Hi, I'm Faizan – Web Developer & Brand Designer.
I've built 50+ websites and specialize in:
• Web Apps & Shopify: Fast, premium, and high-converting.
• SEO & Ranking: Technical SEO and high-authority content writing.
• Visual Identity: Modern Logo Design and Brand Aesthetics.
• Development: Clean HTML/CSS & Responsive layouts.
🌐 Portfolio: https://faizan-digital-architect-wuq5.vercel.app/
Let's build your brand from scratch. Message me to start!"""

SCAN_INTERVAL_SECONDS = 90   # Scan every 90 seconds
SEEN_POSTS_FILE       = Path("data/seen_posts.json")
DAILY_REPORT_FILE     = Path("data/daily_stats.json")

# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class Lead:
    id:          str
    title:       str
    url:         str
    source:      str
    source_icon: str
    author:      str
    published:   datetime
    matched_kws: list[str]
    snippet:     str = ""

@dataclass
class DailyStats:
    date:            str   = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    posts_scanned:   int   = 0
    leads_found:     int   = 0
    alerts_sent:     int   = 0
    sources_hit:     dict  = field(default_factory=dict)
    keywords_hit:    dict  = field(default_factory=dict)

# ─── State Management ────────────────────────────────────────────────────────

class StateManager:
    def __init__(self):
        SEEN_POSTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        DAILY_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.seen: set[str]  = self._load_seen()
        self.stats: DailyStats = self._load_stats()

    def _load_seen(self) -> set[str]:
        if SEEN_POSTS_FILE.exists():
            try:
                data = json.loads(SEEN_POSTS_FILE.read_text())
                # Only keep IDs from the last 7 days to prevent unbounded growth
                cutoff = (datetime.now() - timedelta(days=7)).isoformat()
                return set(v for v, ts in data.items() if ts > cutoff)
            except Exception:
                return set()
        return set()

    def _load_stats(self) -> DailyStats:
        today = datetime.now().strftime("%Y-%m-%d")
        if DAILY_REPORT_FILE.exists():
            try:
                data = json.loads(DAILY_REPORT_FILE.read_text())
                if data.get("date") == today:
                    return DailyStats(**data)
            except Exception:
                pass
        return DailyStats(date=today)

    def save(self):
        # Save seen post IDs with timestamps
        existing = {}
        if SEEN_POSTS_FILE.exists():
            try:
                existing = json.loads(SEEN_POSTS_FILE.read_text())
            except Exception:
                pass
        now = datetime.now().isoformat()
        for pid in self.seen:
            if pid not in existing:
                existing[pid] = now
        SEEN_POSTS_FILE.write_text(json.dumps(existing, indent=2))

        # Save daily stats
        DAILY_REPORT_FILE.write_text(json.dumps(self.stats.__dict__, indent=2))

    def already_seen(self, post_id: str) -> bool:
        return post_id in self.seen

    def mark_seen(self, post_id: str):
        self.seen.add(post_id)

    def record_lead(self, lead: Lead):
        self.stats.leads_found += 1
        self.stats.alerts_sent += 1
        src = lead.source
        self.stats.sources_hit[src] = self.stats.sources_hit.get(src, 0) + 1
        for kw in lead.matched_kws:
            self.stats.keywords_hit[kw] = self.stats.keywords_hit.get(kw, 0) + 1

# ─── Feed Parser ─────────────────────────────────────────────────────────────

class FeedMonitor:
    def __init__(self, state: StateManager):
        self.state = state
        self.headers = {
            "User-Agent": "Mozilla/5.0 (compatible; LeadSniper/1.0; personal-use-bot)"
        }

    def _make_id(self, url: str, title: str) -> str:
        return hashlib.md5(f"{url}{title}".encode()).hexdigest()

    def _find_keywords(self, text: str) -> list[str]:
        text_lower = text.lower()
        return [kw for kw in KEYWORDS if kw in text_lower]

    def _parse_date(self, entry) -> Optional[datetime]:
        for attr in ("published_parsed", "updated_parsed", "created_parsed"):
            t = getattr(entry, attr, None)
            if t:
                try:
                    return datetime(*t[:6])
                except Exception:
                    pass
        return datetime.now()

    def _clean_html(self, text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:400]

    async def fetch_feed(self, feed_config: dict) -> list[Lead]:
        leads = []
        name = feed_config["name"]
        url  = feed_config["url"]
        icon = feed_config["icon"]

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                raw = resp.text
        except Exception as e:
            log.warning(f"[yellow]Feed fetch failed [{name}]: {e}[/yellow]")
            return leads

        parsed = feedparser.parse(raw)
        self.state.stats.posts_scanned += len(parsed.entries)

        cutoff = datetime.now() - timedelta(minutes=30)  # Look back 30 min on each scan

        for entry in parsed.entries:
            title   = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or ""
            link    = getattr(entry, "link",  "") or ""
            author  = getattr(entry, "author", "Unknown") or "Unknown"
            pub     = self._parse_date(entry)

            # Skip old posts
            if pub and pub < cutoff:
                continue

            full_text = f"{title} {summary}"
            matched   = self._find_keywords(full_text)

            if not matched:
                continue

            post_id = self._make_id(link, title)
            if self.state.already_seen(post_id):
                continue

            self.state.mark_seen(post_id)

            lead = Lead(
                id          = post_id,
                title       = title[:200],
                url         = link,
                source      = name,
                source_icon = icon,
                author      = author,
                published   = pub,
                matched_kws = matched,
                snippet     = self._clean_html(summary),
            )
            leads.append(lead)

        return leads

# ─── Telegram Notifier ───────────────────────────────────────────────────────

class TelegramNotifier:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    async def send(self, text: str, parse_mode: str = "HTML") -> bool:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            log.error("[red]Telegram credentials not set in .env![/red]")
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id":    TELEGRAM_CHAT_ID,
                        "text":       text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": False,
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    log.error(f"[red]Telegram error: {data}[/red]")
                    return False
                return True
        except Exception as e:
            log.error(f"[red]Telegram send failed: {e}[/red]")
            return False

    def format_lead_alert(self, lead: Lead) -> str:
        kw_str     = ", ".join(f"<code>{k}</code>" for k in lead.matched_kws[:4])
        ago_secs   = int((datetime.now() - lead.published).total_seconds())
        if ago_secs < 60:
            age_str = f"{ago_secs}s ago"
        else:
            age_str = f"{ago_secs // 60}m ago"

        pitch_escaped = PITCH_MESSAGE.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        return f"""🎯 <b>NEW LEAD DETECTED!</b>

{lead.source_icon} <b>Source:</b> {lead.source}
🕐 <b>Posted:</b> {age_str}
👤 <b>Author:</b> {lead.author}

📌 <b>{lead.title}</b>

{f'📝 {lead.snippet[:250]}...' if lead.snippet else ''}

🔍 <b>Keywords matched:</b> {kw_str}

🔗 <a href="{lead.url}">Open Post →</a>

─────────────────────────
📋 <b>QUICK-COPY PITCH:</b>
─────────────────────────
<code>{pitch_escaped}</code>"""

    async def send_lead(self, lead: Lead) -> bool:
        msg = self.format_lead_alert(lead)
        return await self.send(msg)

    async def send_daily_report(self, stats: DailyStats):
        top_kws = sorted(stats.keywords_hit.items(), key=lambda x: x[1], reverse=True)[:5]
        top_src = sorted(stats.sources_hit.items(), key=lambda x: x[1], reverse=True)[:5]

        kw_lines  = "\n".join(f"  • <code>{k}</code>: {v} hits" for k, v in top_kws) or "  None"
        src_lines = "\n".join(f"  • {k}: {v} leads"            for k, v in top_src) or "  None"

        msg = f"""📊 <b>DAILY LEAD SNIPER REPORT</b>
📅 {stats.date}

━━━━━━━━━━━━━━━━━━━━━
📬 Posts Scanned:   <b>{stats.posts_scanned}</b>
🎯 Leads Found:     <b>{stats.leads_found}</b>
✅ Alerts Sent:     <b>{stats.alerts_sent}</b>

🔑 <b>Top Keywords:</b>
{kw_lines}

📡 <b>Top Sources:</b>
{src_lines}
━━━━━━━━━━━━━━━━━━━━━
Keep grinding, Faizan! 💪"""

        await self.send(msg)

    async def send_startup_ping(self):
        await self.send(
            "🚀 <b>Lead Sniper is ONLINE</b>\n\n"
            f"Monitoring <b>{len(REDDIT_FEEDS)} Reddit</b> + <b>{len(UPWORK_FEEDS)} Upwork</b> feeds\n"
            f"🔍 Tracking <b>{len(KEYWORDS)}</b> keywords\n"
            f"⏱ Scan interval: every <b>{SCAN_INTERVAL_SECONDS}s</b>\n\n"
            "You'll be notified the instant a lead appears. 🎯"
        )

# ─── Orchestrator ────────────────────────────────────────────────────────────

class LeadSniper:
    def __init__(self):
        self.state    = StateManager()
        self.monitor  = FeedMonitor(self.state)
        self.telegram = TelegramNotifier()
        self.all_feeds = REDDIT_FEEDS + UPWORK_FEEDS

    async def scan_once(self):
        log.info(f"[cyan]🔍 Scanning {len(self.all_feeds)} feeds...[/cyan]")
        scan_start = time.time()

        tasks = [self.monitor.fetch_feed(f) for f in self.all_feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_leads = 0
        for result in results:
            if isinstance(result, Exception):
                log.warning(f"[yellow]Feed error: {result}[/yellow]")
                continue
            for lead in result:
                total_leads += 1
                log.info(
                    f"[green]🎯 LEAD: [{lead.source}] {lead.title[:60]}...[/green]\n"
                    f"   Keywords: {lead.matched_kws}"
                )
                sent = await self.telegram.send_lead(lead)
                if sent:
                    self.state.record_lead(lead)
                await asyncio.sleep(1)  # Brief pause between Telegram messages

        elapsed = time.time() - scan_start
        self.state.save()

        if total_leads:
            log.info(f"[green]✅ Scan done in {elapsed:.1f}s — {total_leads} leads found![/green]")
        else:
            log.info(f"[dim]✅ Scan done in {elapsed:.1f}s — no new leads[/dim]")

    async def send_daily_report(self):
        log.info("[blue]📊 Sending daily report...[/blue]")
        await self.telegram.send_daily_report(self.state.stats)
        # Reset for next day
        self.state.stats = DailyStats()
        self.state.save()

    def print_banner(self):
        console.print(Panel.fit(
            "[bold cyan]🎯 LEAD SNIPER[/bold cyan]\n"
            "[dim]Reddit + Upwork → Telegram Alerts[/dim]\n\n"
            f"[white]Feeds:[/white]  {len(self.all_feeds)} sources\n"
            f"[white]Keywords:[/white] {len(KEYWORDS)} tracked\n"
            f"[white]Interval:[/white] {SCAN_INTERVAL_SECONDS}s",
            border_style="cyan",
            title="[bold]Faizan's Lead Machine[/bold]",
        ))

    async def run(self):
        self.print_banner()

        # Validate credentials
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            console.print("[bold red]❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID in .env[/bold red]")
            console.print("See README.md for setup instructions.")
            return

        await self.telegram.send_startup_ping()

        # Schedule daily report at midnight
        schedule.every().day.at("00:00").do(
            lambda: asyncio.create_task(self.send_daily_report())
        )

        log.info(f"[bold green]✅ Lead Sniper running. First scan in 5 seconds...[/bold green]")
        await asyncio.sleep(5)

        while True:
            try:
                await self.scan_once()
                # Run any scheduled tasks (daily report)
                schedule.run_pending()
            except KeyboardInterrupt:
                log.info("[yellow]Shutting down gracefully...[/yellow]")
                await self.telegram.send("⛔ Lead Sniper has been stopped manually.")
                break
            except Exception as e:
                log.error(f"[red]Unexpected error in main loop: {e}[/red]")
                await asyncio.sleep(30)  # Wait before retrying

            await asyncio.sleep(SCAN_INTERVAL_SECONDS)


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        asyncio.run(LeadSniper().run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Lead Sniper stopped.[/yellow]")

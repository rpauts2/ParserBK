"""
Advanced Betting Odds Parser Framework
Target: RF Bookmakers (Baltbet, Bettery, Zenit, Betcity, Betboom, 1xStavka)
Tech Stack: Python 3.12+, Playwright Async, playwright_stealth
"""

import asyncio
import json
import random
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page, ProxySettings
from playwright_stealth import stealth_async

# --- Configuration & Constants ---

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
]

# Mapping for normalizing team names (Example placeholder)
TEAM_MAPPING = {
    "спартак москва": "Спартак М",
    "зенит санкт-петербург": "Зенит СПБ",
    "цска москва": "ЦСКА",
    # Add more mappings as needed
}

class ParsingError(Exception):
    pass

class CaptchaDetectedError(Exception):
    pass

# --- Stealth Infrastructure ---

async def get_stealth_context(browser, proxy: Optional[ProxySettings] = None) -> BrowserContext:
    """
    Creates a highly stealthy browser context to bypass Cloudflare, PerimeterX, etc.
    """
    context = await browser.new_context(
        proxy=proxy,
        user_agent=random.choice(USER_AGENTS),
        viewport=random.choice(VIEWPORTS),
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        permissions=["geolocation"],
        geolocation={"latitude": 55.7558, "longitude": 37.6173}, # Moscow
        color_scheme="light",
    )

    # Apply stealth scripts
    page = await context.new_page()
    await stealth_async(page)
    
    # Additional evasion techniques
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru'] });
        
        // Override the chrome property
        window.chrome = { runtime: {} };
        
        // Fix for Headless detection
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)
    
    await page.close() # We don't need the page yet, just the context setup
    return context

# --- Base Parser Class ---

class BaseParser(ABC):
    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.browser = None
        self.context = None
        self.page = None
        self.bookmaker_name = self.__class__.__name__.replace("Parser", "")

    async def start(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True, # Set to False for debugging
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )
        
        proxy_settings = None
        if self.proxy:
            proxy_settings = {"server": self.proxy}
            
        self.context = await get_stealth_context(self.browser, proxy_settings)
        self.page = await self.context.new_page()

    async def close(self):
        if self.browser:
            await self.browser.close()

    async def fetch_page(self, url: str, timeout: int = 30000):
        """
        Loads page with random delays and human-like behavior.
        """
        try:
            # Random delay before request
            await asyncio.sleep(random.uniform(1.5, 4.0))
            
            response = await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            
            if not response or response.status >= 400:
                raise ParsingError(f"Failed to load {url}, status: {response.status if response else 'No Response'}")

            # Check for common CAPTCHA indicators or blocking pages
            content = await self.page.content()
            if "captcha" in content.lower() or "access denied" in content.lower():
                raise CaptchaDetectedError(f"Captcha detected on {self.bookmaker_name}")

            # Wait for network idle to ensure dynamic content loads
            try:
                await self.page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass # Continue even if not fully idle
            
            # Random scroll to mimic human behavior
            await self.page.evaluate(f"window.scrollTo(0, {random.randint(100, 500)})")
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await self.page.evaluate("window.scrollTo(0, 0)")

        except Exception as e:
            print(f"[{self.bookmaker_name}] Error fetching page: {e}")
            raise

    @abstractmethod
    async def parse_odds(self) -> List[Dict[str, Any]]:
        """
        Extracts odds data. Must be implemented by subclasses.
        Returns list of dicts: {"match": "...", "odds": {...}, ...}
        """
        pass

    def normalize_team_name(self, name: str) -> str:
        """
        Normalizes team names using a mapping dictionary.
        """
        clean_name = re.sub(r'\s+', ' ', name.strip()).lower()
        return TEAM_MAPPING.get(clean_name, name)

    def normalize_data(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Standardizes the output format.
        """
        normalized = []
        for item in raw_data:
            try:
                teams = item.get("match", "").split(" vs ")
                if len(teams) == 2:
                    team1 = self.normalize_team_name(teams[0])
                    team2 = self.normalize_team_name(teams[1])
                    match_name = f"{team1} vs {team2}"
                else:
                    match_name = item.get("match")

                normalized_item = {
                    "bk": self.bookmaker_name,
                    "match": match_name,
                    "odds": item.get("odds", {}),
                    "timestamp": datetime.now().isoformat(),
                    "url": item.get("url", "")
                }
                normalized.append(normalized_item)
            except Exception as e:
                print(f"[{self.bookmaker_name}] Error normalizing data: {e}")
                continue
        return normalized

# --- Specific Implementations ---

class BaltbetParser(BaseParser):
    def __init__(self, proxy=None):
        super().__init__(proxy)
        self.base_url = "https://baltbet.ru" # Placeholder URL

    async def parse_odds(self) -> List[Dict[str, Any]]:
        results = []
        try:
            # NOTE: Selectors below are examples. Must be updated via DevTools.
            # Baltbet often uses standard class names or data attributes.
            matches = await self.page.query_selector_all(".match-item") 
            
            for match in matches:
                try:
                    team1_el = await match.query_selector(".team-home")
                    team2_el = await match.query_selector(".team-away")
                    
                    if not team1_el or not team2_el:
                        continue

                    team1 = await team1_el.inner_text()
                    team2 = await team2_el.inner_text()
                    
                    # Extracting Main Odds (1X2)
                    odds_1 = await match.query_selector(".odd-1 .value")
                    odds_x = await match.query_selector(".odd-x .value")
                    odds_2 = await match.query_selector(".odd-2 .value")
                    
                    odds_data = {}
                    if odds_1: odds_data["1"] = float(await odds_1.inner_text())
                    if odds_x: odds_data["X"] = float(await odds_x.inner_text())
                    if odds_2: odds_data["2"] = float(await odds_2.inner_text())

                    results.append({
                        "match": f"{team1} vs {team2}",
                        "odds": odds_data,
                        "url": self.base_url
                    })
                except Exception as e:
                    print(f"Error parsing single match in Baltbet: {e}")
                    continue
        except Exception as e:
            print(f"Baltbet parsing failed: {e}")
        
        return results

class BetteryParser(BaseParser):
    def __init__(self, proxy=None):
        super().__init__(proxy)
        self.base_url = "https://bettery.ru"

    async def parse_odds(self) -> List[Dict[str, Any]]:
        results = []
        try:
            # Bettery might use React/Vue, so waiting for specific data-testid is safer
            await self.page.wait_for_selector("[data-testid='match-row']", timeout=10000)
            matches = await self.page.query_selector_all("[data-testid='match-row']")

            for match in matches:
                # Implementation depends on actual DOM structure
                # Placeholder logic
                text_content = await match.inner_text()
                # Simple regex extraction example if DOM is too obfuscated
                # This is a fallback strategy
                pass 
                
            # Real implementation requires inspecting current DOM
            print("[Bettery] DOM inspection required for current selectors.")
            
        except Exception as e:
            print(f"Bettery parsing failed: {e}")
        return results

class ZenitParser(BaseParser):
    def __init__(self, proxy=None):
        super().__init__(proxy)
        self.base_url = "https://zenit.bet"

    async def parse_odds(self) -> List[Dict[str, Any]]:
        results = []
        try:
            # Zenit often uses complex nested structures
            selector = ".c-events-list__item" # Example selector
            await self.page.wait_for_selector(selector, timeout=15000)
            matches = await self.page.query_selector_all(selector)

            for match in matches:
                # Extract teams
                t1 = await match.query_selector(".c-events-list__team_name--home")
                t2 = await match.query_selector(".c-events-list__team_name--away")
                
                if not t1 or not t2: continue
                
                # Extract coefficients
                # Usually stored in data-coeff or inner text of buttons
                btns = await match.query_selector_all(".c-bets__val")
                
                odds = {}
                if len(btns) >= 3:
                    try:
                        odds["1"] = float(await btns[0].inner_text())
                        odds["X"] = float(await btns[1].inner_text())
                        odds["2"] = float(await btns[2].inner_text())
                    except ValueError:
                        pass

                results.append({
                    "match": f"{await t1.inner_text()} vs {await t2.inner_text()}",
                    "odds": odds,
                    "url": self.base_url
                })
        except Exception as e:
            print(f"Zenit parsing failed: {e}")
        return results

class BetcityParser(BaseParser):
    def __init__(self, proxy=None):
        super().__init__(proxy)
        self.base_url = "https://betcity.ru"

    async def parse_odds(self) -> List[Dict[str, Any]]:
        results = []
        try:
            # Betcity has very deep DOM nesting and dynamic classes
            # Strategy: Wait for the main event container
            await self.page.wait_for_selector(".game-row", timeout=20000)
            matches = await self.page.query_selector_all(".game-row")

            for match in matches:
                try:
                    # Teams
                    teams = await match.query_selector_all(".team-name")
                    if len(teams) < 2: continue
                    
                    # Odds - often in spans with specific aria-labels or indices
                    odds_container = await match.query_selector(".main-markets")
                    if not odds_container: continue
                    
                    odd_vals = await odds_container.query_selector_all(".odd-value")
                    
                    odds = {}
                    if len(odd_vals) >= 3:
                        odds["1"] = float(await odd_vals[0].inner_text())
                        odds["X"] = float(await odd_vals[1].inner_text())
                        odds["2"] = float(await odd_vals[2].inner_text())

                    results.append({
                        "match": f"{await teams[0].inner_text()} vs {await teams[1].inner_text()}",
                        "odds": odds,
                        "url": self.base_url
                    })
                except Exception as e:
                    continue
        except Exception as e:
            print(f"Betcity parsing failed: {e}")
        return results

class BetboomParser(BaseParser):
    def __init__(self, proxy=None):
        super().__init__(proxy)
        self.base_url = "https://betboom.ru"

    async def parse_odds(self) -> List[Dict[str, Any]]:
        results = []
        try:
            # Betboom uses SSR sometimes, but mostly client-side rendering
            await self.page.wait_for_selector(".event-card", timeout=15000)
            matches = await self.page.query_selector_all(".event-card")

            for match in matches:
                # Logic similar to Betcity but different classes
                # Placeholder for specific Betboom selectors
                pass
            print("[Betboom] Selectors need update based on live DOM.")
        except Exception as e:
            print(f"Betboom parsing failed: {e}")
        return results

class OneXBetParser(BaseParser):
    """
    Special handling for 1xStavka/1xBet due to heavy obfuscation and WebSocket usage.
    Direct DOM parsing is unreliable. Preferred method: Intercept Network Requests.
    """
    def __init__(self, proxy=None):
        super().__init__(proxy)
        self.base_url = "https://1xstavka.ru"
        self.api_data = []

    async def start(self):
        await super().start()
        # Intercept API responses
        self.page.on("response", self.handle_response)

    def handle_response(self, response):
        """
        Intercepts specific JSON API calls containing odds data.
        URL patterns must be identified via DevTools Network tab (e.g., /liveEvents`, `getOdds`)
        """
        url = response.url
        if "champs" in url or "events" in url and "json" in url:
            try:
                # Check if response is JSON
                if "application/json" in response.headers.get("content-type", ""):
                    # Asynchronously process data to avoid blocking
                    asyncio.create_task(self.process_api_response(response))
            except Exception:
                pass

    async def process_api_response(self, response):
        try:
            data = await response.json()
            # Structure of 'data' varies wildly. Needs specific parsing logic based on actual payload.
            # This is where you map the JSON keys to our standard format.
            # Example pseudo-logic:
            # for event in data.get('events', []):
            #    self.api_data.append({...})
            pass
        except Exception:
            pass

    async def parse_odds(self) -> List[Dict[str, Any]]:
        # For 1xStavka, we rely on the intercepted data rather than DOM scraping
        # Wait a bit for events to trigger
        await asyncio.sleep(5) 
        
        # Fallback to DOM if API interception yields nothing (less reliable)
        # Implement DOM scraping here as backup
        
        return self.api_data

# --- Main Execution Orchestrator ---

async def run_parsers():
    # Configuration: Add real proxy strings if available (e.g., "http://user:pass@ip:port")
    PROXY_LIST = [None]  # No proxy by default
    
    parsers = [
        BaltbetParser(),
        # BetteryParser(), # Uncomment when selectors are verified
        ZenitParser(),
        BetcityParser(),
        BetboomParser(),
        OneXBetParser()
    ]

    all_results = []

    for parser in parsers:
        print(f"Starting {parser.bookmaker_name}...")
        try:
            await parser.start()
            
            # Define target URLs (Live or Pre-match)
            # These URLs must be valid and currently accessible
            urls = [parser.base_url] 
            
            for url in urls:
                try:
                    await parser.fetch_page(url)
                    raw_data = await parser.parse_odds()
                    normalized_data = parser.normalize_data(raw_data)
                    all_results.extend(normalized_data)
                    print(f"[OK] {parser.bookmaker_name}: Found {len(normalized_data)} matches.")
                except CaptchaDetectedError:
                    print(f"[FAIL] {parser.bookmaker_name}: Captcha detected. Stopping.")
                    break
                except Exception as e:
                    print(f"[FAIL] {parser.bookmaker_name}: {e}")
            
            await parser.close()
        except Exception as e:
            print(f"[CRITICAL] Failed to initialize {parser.bookmaker_name}: {e}")

    # Output Results
    output_file = "odds_output.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\nParsing complete. Results saved to {output_file}")
    print(f"Total matches collected: {len(all_results)}")

if __name__ == "__main__":
    # Run the async loop
    asyncio.run(run_parsers())

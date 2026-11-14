import os
import sys
import time
import json
import re
import urllib.request
import urllib.parse
import tempfile
from bs4 import BeautifulSoup

def clean_html_to_markdown(html_content: str, max_chars: int = 6000) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "iframe", "form"]):
        tag.decompose()
        
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    
    # Extract readable structured text
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    result = f"# {title}\n\n{text}" if title else text
    return result[:max_chars]

def surf_search(query: str, max_results: int = 5) -> dict:
    """
    Performs an ultra-fast web search (<1s) using lightweight search endpoints.
    Cross-platform: Windows, macOS, Linux.
    Returns clean titles, target URLs, and contextual snippets.
    """
    t0 = time.time()
    query_clean = query.strip()
    if not query_clean:
        return {"status": "error", "message": "Search query cannot be empty"}

    # Primary Engine: DuckDuckGo Lite (High reliability, zero CAPTCHAs, instant)
    try:
        url = "https://lite.duckduckgo.com/lite/"
        post_data = urllib.parse.urlencode({"q": query_clean}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            soup = BeautifulSoup(resp.read(), "html.parser")
            results = []
            for tr in soup.select("tr"):
                link = tr.select_one("a.result-link")
                if link:
                    title = link.get_text(strip=True)
                    raw = link.get("href", "")
                    m = re.search(r"uddg=([^&]+)", raw)
                    dest = urllib.parse.unquote(m.group(1)) if m else raw
                    next_tr = tr.find_next_sibling("tr")
                    snip_td = next_tr.select_one("td.result-snippet") if next_tr else None
                    snippet = snip_td.get_text(strip=True) if snip_td else ""
                    if dest.startswith("http"):
                        results.append({"title": title, "url": dest, "snippet": snippet})
                        if len(results) >= max_results:
                            break
                            
            if results:
                return {
                    "status": "success",
                    "query": query_clean,
                    "count": len(results),
                    "results": results,
                    "duration_seconds": round(time.time() - t0, 3)
                }
    except Exception:
        pass

    # Secondary Engine: Wikipedia / Instant Knowledge fallback
    try:
        encoded = urllib.parse.quote_plus(query_clean)
        api_url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        api_req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(api_req, timeout=5) as api_resp:
            api_data = json.loads(api_resp.read().decode("utf-8", errors="ignore"))
            results = []
            if api_data.get("AbstractText"):
                results.append({
                    "title": api_data.get("Heading", query_clean),
                    "url": api_data.get("AbstractURL", ""),
                    "snippet": api_data.get("AbstractText", "")
                })
            for topic in api_data.get("RelatedTopics", [])[:max_results]:
                if "Text" in topic and "FirstURL" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:60],
                        "url": topic.get("FirstURL", ""),
                        "snippet": topic.get("Text", "")
                    })
            if results:
                return {
                    "status": "success",
                    "query": query_clean,
                    "count": len(results),
                    "results": results,
                    "duration_seconds": round(time.time() - t0, 3)
                }
    except Exception as e:
        return {
            "status": "error",
            "query": query_clean,
            "message": f"Search could not complete: {str(e)}",
            "duration_seconds": round(time.time() - t0, 3)
        }

    return {
        "status": "success",
        "query": query_clean,
        "count": 0,
        "results": [],
        "duration_seconds": round(time.time() - t0, 3)
    }

def surf_read(url: str, max_chars: int = 6000) -> dict:
    """
    Tier 1 Instant Web Page Reader (<1s):
    Fetches raw HTML, strips noise, formats clean Markdown/text.
    Falls back to sandboxed Playwright if JavaScript rendering is mandatory.
    """
    t0 = time.time()
    url_clean = url.strip()
    if not url_clean.startswith("http"):
        url_clean = f"https://{url_clean}"
        
    req = urllib.request.Request(
        url_clean,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")
            content = clean_html_to_markdown(raw_html, max_chars)
            
            # If substantial readable content is extracted, return instantly
            if len(content.strip()) > 150:
                return {
                    "status": "success",
                    "url": url_clean,
                    "content": content,
                    "length": len(content),
                    "duration_seconds": round(time.time() - t0, 3)
                }
    except Exception:
        pass

def get_browser_user_data_dir(profile_name: str = "default") -> str:
    """
    Returns a persistent cross-platform directory for browser automation profiles.
    Keeps user login sessions (Render, Vercel, Supabase, GitHub, etc.) saved permanently across reboots.
    Compatible across Windows, macOS, and Linux.
    """
    safe_profile = re.sub(r'[^a-zA-Z0-9_-]', '_', profile_name or "default")
    if sys.platform == "win32":
        appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        base_dir = os.path.join(appdata, "Tilux", "browser_profiles", safe_profile)
    elif sys.platform == "darwin":
        base_dir = os.path.expanduser(f"~/Library/Application Support/Tilux/browser_profiles/{safe_profile}")
    else:
        config_home = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        base_dir = os.path.join(config_home, "tilux", "browser_profiles", safe_profile)
        
    try:
        os.makedirs(base_dir, exist_ok=True)
        return base_dir
    except Exception:
        fallback = os.path.join(tempfile.gettempdir(), "tilux_browser_sandbox", safe_profile)
        os.makedirs(fallback, exist_ok=True)
        return fallback

    # Tier 2 Fallback: Sandboxed Headless Playwright (Policy compliant: silent, persistent profile)
    try:
        from playwright.sync_api import sync_playwright
        user_data_dir = get_browser_user_data_dir("default")
        
        with sync_playwright() as p:
            context = None
            for ch in ["chrome", "msedge", None]:
                try:
                    kwargs = {
                        "user_data_dir": user_data_dir,
                        "headless": True,
                        "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
                    }
                    if ch:
                        kwargs["channel"] = ch
                    context = p.chromium.launch_persistent_context(**kwargs)
                    break
                except Exception:
                    continue
            page = context.pages[0] if context.pages else context.new_page()
            
            # Resource optimization: block media & font files to load 3x faster
            def _filter_resources(route):
                if route.request.resource_type in ["image", "media", "font"]:
                    route.abort()
                else:
                    route.continue_()
            page.route("**/*", _filter_resources)
            
            page.goto(url_clean, wait_until="domcontentloaded", timeout=12000)
            rendered_html = page.content()
            title = page.title()
            context.close()
            
            md = clean_html_to_markdown(rendered_html, max_chars)
            return {
                "status": "success",
                "url": url_clean,
                "title": title,
                "content": md,
                "length": len(md),
                "duration_seconds": round(time.time() - t0, 3)
            }
    except Exception as pe:
        return {
            "status": "error",
            "url": url_clean,
            "message": f"Web read error: {str(pe)}",
            "duration_seconds": round(time.time() - t0, 3)
        }

def surf_interact(url: str, steps: list = None, timeout_ms: int = 15000, profile_name: str = "default", channel: str = None) -> dict:
    """
    Tier 2 Fast Web Automation:
    Executes form filling, clicking, and DOM inspection across Windows, macOS, and Linux.
    Preserves all policies:
      - Uses persistent profile directory so logins (Render, Vercel, etc.) stay logged in
      - Silent background first (headless)
      - Attaches to port 9222 CDP if active browser session is open
      - Automatically detects installed Google Chrome or Microsoft Edge binaries
      - Resource blocking (aborts images/fonts) for maximum interaction speed
    """
    t0 = time.time()
    url_clean = url.strip() if url else ""
    if url_clean and not url_clean.startswith("http"):
        url_clean = f"https://{url_clean}"
        
    steps = steps or []
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "error", "message": "Playwright is not available in the current environment."}
        
    user_data_dir = get_browser_user_data_dir(profile_name)
    
    executed_steps = []
    try:
        with sync_playwright() as p:
            browser = None
            context = None
            is_cdp = False
            
            # Fast-path: Check for active Chrome/Edge CDP on port 9222 (instant connection)
            try:
                import urllib.request
                with urllib.request.urlopen("http://localhost:9222/json/version", timeout=0.8) as cdp_check:
                    if cdp_check.status == 200:
                        browser = p.chromium.connect_over_cdp("http://localhost:9222")
                        context = browser.contexts[0] if browser.contexts else browser.new_context()
                        is_cdp = True
            except Exception:
                pass
                
            if not context:
                launch_channels = [channel] if channel else ["chrome", "msedge", None]
                for ch in launch_channels:
                    try:
                        kwargs = {
                            "user_data_dir": user_data_dir,
                            "headless": True,
                            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
                        }
                        if ch:
                            kwargs["channel"] = ch
                        context = p.chromium.launch_persistent_context(**kwargs)
                        break
                    except Exception:
                        continue
                
            page = context.pages[0] if context.pages else context.new_page()
            
            # Resource optimization: block non-essential media & fonts
            def _filter_reqs(route):
                if route.request.resource_type in ["image", "media", "font"]:
                    route.abort()
                else:
                    route.continue_()
            page.route("**/*", _filter_reqs)
            
            if url_clean:
                page.goto(url_clean, wait_until="domcontentloaded", timeout=timeout_ms)
                executed_steps.append(f"Navigated to {url_clean}")
                
            # Execute batched interaction steps
            for step in steps:
                stype = step.get("type", "").lower().strip()
                selector = step.get("selector", "")
                val = step.get("value", "")
                
                if stype in ["click", "press_button"]:
                    page.locator(selector).first.click(timeout=8000)
                    executed_steps.append(f"Clicked: {selector}")
                elif stype in ["fill", "type", "input"]:
                    page.locator(selector).first.fill(str(val), timeout=8000)
                    executed_steps.append(f"Filled: {selector}")
                elif stype == "press":
                    page.keyboard.press(str(val or "Enter"))
                    executed_steps.append(f"Pressed key: {val or 'Enter'}")
                elif stype == "wait":
                    wait_sec = min(float(val or 1.0), 5.0)
                    time.sleep(wait_sec)
                    executed_steps.append(f"Waited {wait_sec}s")
                elif stype == "wait_selector":
                    page.wait_for_selector(selector, timeout=8000)
                    executed_steps.append(f"Waited for selector: {selector}")
                    
            title = page.title()
            current_url = page.url
            
            # Extract actionable elements (interactive overview without vision OCR)
            interactive_elements = page.eval_on_selector_all(
                "button, input, select, textarea, a[href]",
                """elements => elements.slice(0, 30).map(e => ({
                    tag: e.tagName.toLowerCase(),
                    type: e.type || '',
                    id: e.id || '',
                    name: e.name || '',
                    text: (e.innerText || e.value || e.placeholder || e.ariaLabel || '').trim().slice(0, 50),
                    href: e.href || ''
                }))"""
            )
            
            if not is_cdp:
                context.close()
                
            return {
                "status": "success",
                "title": title,
                "current_url": current_url,
                "executed_steps": executed_steps,
                "interactive_elements": interactive_elements,
                "duration_seconds": round(time.time() - t0, 3)
            }
    except Exception as e:
        return {
            "status": "error",
            "executed_steps": executed_steps,
            "message": f"Browser interaction error: {str(e)}",
            "duration_seconds": round(time.time() - t0, 3)
        }

def run_browser_task(payload: dict) -> dict:
    """
    Unified entrypoint for category task routing and fast browser surfing.
    Compatible across Windows, macOS, and Linux.
    """
    action = payload.get("action", "").lower().strip()
    query_or_url = payload.get("query_or_url") or payload.get("url") or payload.get("query") or ""
    steps = payload.get("steps") or payload.get("interaction_steps") or []
    
    if action in ["search", "google", "find"]:
        return surf_search(query_or_url, max_results=payload.get("max_results", 5))
    elif action in ["read", "fetch", "scrape", "get"]:
        return surf_read(query_or_url, max_chars=payload.get("max_chars", 6000))
    elif action in ["interact", "automate", "click", "fill"]:
        prof = payload.get("profile_name") or payload.get("user_profile") or "default"
        ch = payload.get("channel") or payload.get("browser_channel")
        return surf_interact(query_or_url, steps=steps, timeout_ms=payload.get("timeout_ms", 15000), profile_name=prof, channel=ch)
    else:
        # Auto-detect intent: if starts with http or domain format, read it; otherwise search it
        if query_or_url.startswith("http://") or query_or_url.startswith("https://") or ("." in query_or_url and "/" in query_or_url):
            return surf_read(query_or_url)
        else:
            return surf_search(query_or_url)

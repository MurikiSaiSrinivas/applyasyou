// content_wellfound.js — Wellfound jobs scraper. Two modes by URL:
//
//   1. LISTING mode  — on wellfound.com/jobs (the cards page).
//      Triggered by popup via GET_WELLFOUND_JOBS message. Returns array of
//      card metadata (title, company, location, comp, snippet, link).
//
//   2. DETAIL mode   — on wellfound.com/jobs/<id>-<slug> (a single job).
//      Auto-runs on page load, waits for React to render the JD, then sends
//      the rendered document.documentElement.outerHTML to background.js
//      via WELLFOUND_JD_SCRAPED message. Background.js forwards the HTML to
//      sink /api/wellfound/jd which extracts the JD text via BeautifulSoup.
//
// Why detail-mode is content-script + tab-based instead of background fetch():
//   Wellfound's Cloudflare returns HTTP 403 to any fetch() that lacks a real
//   browser-navigation context (Sec-Fetch-Mode=navigate, valid Referer, etc).
//   Service-worker fetches get blocked even with credentials:"include". Opening
//   a real tab carries the full browser context and bypasses the block.

(() => {
  const MARKER = '[wellfound]';
  const log = (...args) => console.log(MARKER, ...args);

  const LISTING_URL_RE = /^https:\/\/wellfound\.com\/jobs(\/|$|\?)/i;
  const DETAIL_URL_RE = /^https:\/\/wellfound\.com\/jobs\/(\d+)-([a-z0-9-]+)/i;
  const JOB_LINK_RE = DETAIL_URL_RE;

  function isListing() {
    return LISTING_URL_RE.test(location.href) && !DETAIL_URL_RE.test(location.href);
  }
  function isDetail() {
    return DETAIL_URL_RE.test(location.href);
  }

  // ===================================================================
  // LISTING MODE
  // ===================================================================
  function findCard(anchor) {
    let el = anchor;
    for (let i = 0; i < 10 && el && el !== document.body; i++) {
      const text = (el.innerText || '').trim();
      const anchorCount = el.querySelectorAll('a').length;
      if (text.length >= 60 && text.length <= 1500 && anchorCount >= 1 && anchorCount <= 6) {
        return el;
      }
      el = el.parentElement;
    }
    return anchor.parentElement || anchor;
  }

  function extractCardFields(card, anchor) {
    const text = (card.innerText || '').trim();
    const lines = text.split('\n').map((s) => s.trim()).filter(Boolean);
    // Wellfound's anchor often wraps the whole card -- anchor.innerText then
    // returns the entire card text (role + company + comp + location). Take
    // only the FIRST line of anchor.innerText so the role field is the title
    // alone, not the multi-line card dump.
    const anchorText = (anchor.innerText || '').trim();
    const role = anchorText.split('\n')[0].trim() || lines[0] || '';

    let company = '', location = '', work_model = '';
    for (const line of lines) {
      if (line === role) continue;
      const dotIdx = line.indexOf('·');
      if (dotIdx > 0 && dotIdx < line.length - 1) {
        const left = line.slice(0, dotIdx).trim();
        const right = line.slice(dotIdx + 1).trim();
        if (/employees?$/i.test(right)) {
          company = left;
        } else {
          company = left;
          location = right;
        }
        break;
      }
    }
    if (!company) {
      const others = lines.filter((l) => l !== role);
      if (others.length) company = others[0];
    }

    let comp = '';
    for (const line of lines) {
      const m = line.match(/\$\s*\d+[.,]?\d*\s*[Kk]?\s*(?:[-–—]|to)\s*\$?\s*\d+[.,]?\d*\s*[Kk]?/);
      if (m) { comp = m[0].replace(/\s+/g, ' ').trim(); break; }
    }

    if (/\b(in office|onsite|on-site)\b/i.test(text)) work_model = 'onsite';
    else if (/\bhybrid\b/i.test(text)) work_model = 'hybrid';
    else if (/\bremote\b/i.test(text)) work_model = 'remote';

    if (!location) {
      const locMatch = text.match(/\b([A-Z][a-zA-Z\s.]+,\s*[A-Z]{2}\b|\b[A-Z][a-zA-Z\s]+,\s*[A-Z][a-zA-Z]+\b)/);
      if (locMatch) location = locMatch[1].trim();
    }

    const snippetLines = lines.filter((l) => l !== role && l !== company && !l.includes('·'));
    const snippet = snippetLines.join(' ').slice(0, 200);

    return { role, company, location, comp, work_model, snippet };
  }

  function collectListingJobs() {
    const anchors = Array.from(document.querySelectorAll('a[href]'))
      .filter((a) => JOB_LINK_RE.test(a.href));
    log(`listing: found ${anchors.length} job-link anchors`);

    const byLink = new Map();
    for (const anchor of anchors) {
      const link = anchor.href.split('?')[0].split('#')[0];
      if (byLink.has(link)) continue;
      const card = findCard(anchor);
      const fields = extractCardFields(card, anchor);
      if (!fields.role || !fields.company) continue;
      byLink.set(link, { link, ...fields });
    }

    const jobs = Array.from(byLink.values());
    log(`listing: ${jobs.length} unique jobs after dedup`);
    return { ok: true, jobs, url: location.href, scraped_at: new Date().toISOString() };
  }

  // ===================================================================
  // DETAIL MODE — runs automatically on page load, sends JD to background
  // ===================================================================
  function hasJsonLdJobPosting() {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const s of scripts) {
      try {
        const data = JSON.parse(s.textContent || '{}');
        const arr = Array.isArray(data) ? data : [data];
        for (const c of arr) {
          if (c && c['@type'] === 'JobPosting' && c.description) return true;
        }
      } catch {}
    }
    return false;
  }

  async function waitForRender(maxMs = 8000) {
    const interval = 300;
    const maxIters = Math.ceil(maxMs / interval);
    for (let i = 0; i < maxIters; i++) {
      if (hasJsonLdJobPosting()) return 'jsonld';
      // Fallback signal: H1 exists AND body has > 2000 chars (React rendered enough)
      if (document.querySelector('h1') && (document.body?.innerText?.length || 0) > 2000) {
        return 'h1_and_body';
      }
      await new Promise((r) => setTimeout(r, interval));
    }
    return 'timeout';
  }

  async function runDetailMode() {
    const renderSignal = await waitForRender(8000);
    const html = document.documentElement.outerHTML;
    const bodyChars = document.body?.innerText?.length || 0;
    log(`detail: render=${renderSignal} html=${html.length}b body=${bodyChars}c`);
    chrome.runtime.sendMessage({
      type: 'WELLFOUND_JD_SCRAPED',
      url: location.href.split('?')[0].split('#')[0],
      html,
      render_signal: renderSignal,
      body_chars: bodyChars,
    });
  }

  // ===================================================================
  // ROUTING
  // ===================================================================
  if (isDetail()) {
    log(`detail mode active on ${location.href}`);
    // Wait a tick so chrome.runtime is fully wired, then start render-wait
    setTimeout(runDetailMode, 100);
  } else if (isListing()) {
    log(`listing mode active on ${location.href}. Open extension popup and click "Scrape + fetch JDs".`);
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
      if (msg && msg.type === 'GET_WELLFOUND_JOBS') {
        try {
          sendResponse(collectListingJobs());
        } catch (e) {
          sendResponse({ ok: false, error: String(e), jobs: [] });
        }
        return true;
      }
    });
  }
})();

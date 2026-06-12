// content_linkedin.js — LinkedIn jobs scraper. URL-routed into 4 modes:
//
//   LISTING modes (popup-triggered via GET_LINKEDIN_JOBS):
//     search   — /jobs/search* or /jobs/collections*  (job search results)
//     saved    — /my-items/saved-jobs/*               (your saved jobs)
//     applied  — /my-items/* with cardType=APPLIED    (Easy Apply history)
//
//   DETAIL mode (auto-runs, sends WELLFOUND-style HTML back to bg):
//     /jobs/view/<id>/  — individual job page
//
// Same architecture as content_wellfound.js: listings collect metadata; the
// bg orchestrator opens each job URL in a background tab; this script's
// DETAIL handler waits for React to render, then ships outerHTML to sink
// for BeautifulSoup JD extraction + auto-score.
//
// LinkedIn risk note: LinkedIn detects unusual API patterns from the browser
// session. We mitigate by:
//   - Manual trigger (no auto-scrape on page load for listings)
//   - Sequential tab opens with throttle (handled bg-side)
//   - User-controlled volume (only scrapes what's currently rendered in DOM,
//     no infinite-scroll automation)

(() => {
  const MARKER = '[linkedin]';
  const log = (...args) => console.log(MARKER, ...args);

  const LISTING_URL_RE = /^https:\/\/(www\.)?linkedin\.com\/(jobs|my-items)/i;
  const DETAIL_URL_RE = /^https:\/\/(www\.)?linkedin\.com\/jobs\/view\/(\d+)/i;
  const POST_URL_RE = /^https:\/\/(www\.)?linkedin\.com\/(posts\/|feed\/update\/)/i;
  const JOB_LINK_RE = /^https?:\/\/(www\.)?linkedin\.com\/jobs\/view\/(\d+)/i;

  function isListing() {
    return LISTING_URL_RE.test(location.href) && !DETAIL_URL_RE.test(location.href);
  }
  function isDetail() {
    return DETAIL_URL_RE.test(location.href);
  }
  function isPost() {
    return POST_URL_RE.test(location.href);
  }

  // ===================================================================
  // POST MODE — extracts a LinkedIn post body + embedded URLs/emails
  // Triggered by GET_LINKEDIN_POST message from background.js (popup
  // "Process URL" feature). Waits for React, then walks DOM looking for
  // the post body container.
  // ===================================================================
  function extractEmails(text) {
    const re = /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/g;
    return Array.from(new Set((text || '').match(re) || []));
  }

  function extractPostBody() {
    // Look for the largest text-rich element with no nested feed items.
    // LinkedIn posts often render in <div role="article"> or in containers
    // matching feed-shared-update-v2*. Defensive: pick the biggest visible
    // div whose text isn't dominated by navigation/sidebar content.
    let best = '';
    const candidates = document.querySelectorAll(
      'div[role="article"], div[class*="feed-shared-update"], div[class*="feed-shared-text"], main article, main div'
    );
    for (const el of candidates) {
      const text = (el.innerText || '').trim();
      if (text.length > best.length && text.length < 8000) {
        best = text;
      }
    }
    if (best.length < 60) {
      // Fallback to body
      best = (document.body?.innerText || '').slice(0, 4000);
    }
    return best;
  }

  function extractEmbeddedUrls() {
    const urls = new Set();
    for (const a of document.querySelectorAll('a[href]')) {
      const h = a.href;
      if (!h || h.startsWith('javascript:')) continue;
      // Filter out LinkedIn nav, profile, share, like, comment links
      if (/linkedin\.com\/(in\/|company\/|feed|notifications|messaging|help|signup|jobs\/view|posts\/|pulse\/)/i.test(h)) continue;
      // Filter out anchors and obvious noise
      if (/^https?:\/\/(www\.)?linkedin\.com\//.test(h)) {
        // External links sometimes routed through linkedin.com/redir/redirect?url=
        const m = h.match(/[?&]url=([^&]+)/);
        if (m) {
          try { urls.add(decodeURIComponent(m[1])); } catch {}
        }
        continue;
      }
      urls.add(h.split('#')[0]);
    }
    return Array.from(urls).slice(0, 30);
  }

  async function runPostMode() {
    // Wait for post to render
    for (let i = 0; i < 20; i++) {
      const txt = (document.body?.innerText || '').length;
      if (txt > 2000) break;
      await new Promise((r) => setTimeout(r, 250));
    }
    const post_body = extractPostBody();
    const embedded_urls = extractEmbeddedUrls();
    const embedded_emails = extractEmails(post_body);
    log(`post mode: body=${post_body.length}c urls=${embedded_urls.length} emails=${embedded_emails.length}`);
    chrome.runtime.sendMessage({
      type: 'LINKEDIN_POST_SCRAPED',
      url: location.href.split('?')[0].split('#')[0],
      post_body,
      embedded_urls,
      embedded_emails,
    });
  }

  function detectListingMode() {
    const url = location.href.toLowerCase();
    if (/cardtype=applied/.test(url)) return 'applied';
    if (/\/my-items.*\/applied/.test(url)) return 'applied';
    if (/\/jobs\/applications/.test(url)) return 'applied';
    if (/\/my-items/.test(url)) return 'saved';
    if (/\/jobs\/(search|collections)/.test(url) || /\/jobs(\/|\?)/.test(url)) return 'search';
    return 'unknown';
  }

  // ===================================================================
  // LISTING MODE
  // ===================================================================
  function findCard(anchor) {
    let el = anchor;
    for (let i = 0; i < 10 && el && el !== document.body; i++) {
      const text = (el.innerText || '').trim();
      const anchorCount = el.querySelectorAll('a').length;
      if (text.length >= 40 && text.length <= 2000 && anchorCount >= 1 && anchorCount <= 8) {
        return el;
      }
      el = el.parentElement;
    }
    return anchor.parentElement || anchor;
  }

  function extractCardFields(card, anchor, mode) {
    const text = (card.innerText || '').trim();
    const lines = text.split('\n').map((s) => s.trim()).filter(Boolean);

    // Role: prefer the aria-label on the title anchor (it's the cleanest
    // single string, e.g. "Software Engineer I / II with verification"),
    // strip the " with verification" suffix LinkedIn appends for screen
    // readers. Fall back to anchor's visible text (first line), then card.
    let role = '';
    if (anchor && anchor.getAttribute) {
      const aria = anchor.getAttribute('aria-label') || '';
      role = aria.replace(/\s+with verification\s*$/i, '').trim();
    }
    if (!role && anchor) {
      const anchorText = (anchor.innerText || '').trim();
      role = anchorText.split('\n')[0].trim();
    }
    if (!role) role = lines[0] || '';

    // Company: LinkedIn renders it inside .artdeco-entity-lockup__subtitle
    let company = '';
    const subEl = card.querySelector('.artdeco-entity-lockup__subtitle');
    if (subEl) company = (subEl.innerText || '').trim();

    // Location: .artdeco-entity-lockup__caption (first line, since metadata
    // wrapper may contain multiple items)
    let location = '';
    const capEl = card.querySelector('.artdeco-entity-lockup__caption');
    if (capEl) {
      const capText = (capEl.innerText || '').trim();
      location = capText.split('\n')[0].trim();
    }

    // Fallback for company + location if class names changed
    if (!company || !location) {
      let pastRole = false;
      for (const line of lines) {
        if (line === role) { pastRole = true; continue; }
        if (!pastRole) continue;
        if (!company && line.length > 1 && line.length < 80 && !/\$|·|posted|applied|saved|viewed|easy apply|promoted/i.test(line)) {
          company = line;
          continue;
        }
        if (company && !location && line.length < 100 && !/\$|posted|applied|saved|viewed|easy apply|promoted/i.test(line)) {
          location = line;
          break;
        }
      }
    }

    // Per-card status detection (used by applied mode + by skip-filter on listings)
    let status_class = 'available';
    let status_text = '';
    const lower = text.toLowerCase();
    if (/\bapplication viewed\b|\bapplied \d+(d|w|mo|y)\b|\bapplied (yesterday|today|recently)\b|\bapplication sent\b|\byou applied/.test(lower)) {
      status_class = 'applied';
      const m = text.match(/(?:Application viewed|Applied [^\n]{0,30}|Application sent|You applied [^\n]{0,30})/i);
      status_text = m ? m[0].trim() : 'Applied';
    } else if (/\bsaved\b/.test(lower) && !mode === 'search') {
      // "Saved" pill only meaningful on saved/applied pages, not search results
      status_class = 'saved';
      status_text = 'Saved';
    }

    // Comp: any "$X-$YK" line
    let comp = '';
    for (const line of lines) {
      const m = line.match(/\$\s*\d+[.,]?\d*\s*[Kk]?\s*(?:[-–—]|to)\s*\$?\s*\d+[.,]?\d*\s*[Kk]?/);
      if (m) { comp = m[0].replace(/\s+/g, ' ').trim(); break; }
    }

    // Work model
    let work_model = '';
    if (/\bremote\b/i.test(text)) work_model = 'remote';
    else if (/\bhybrid\b/i.test(text)) work_model = 'hybrid';
    else if (/\b(on-site|onsite|on site)\b/i.test(text)) work_model = 'onsite';

    // Snippet: short blurb (LinkedIn doesn't show JD on listings)
    const snippet = lines.filter((l) => l !== role && l !== company && l !== location).join(' ').slice(0, 200);

    return { role, company, location, comp, work_model, snippet, status_class, status_text };
  }

  function collectListingJobs() {
    const mode = detectListingMode();
    if (mode === 'unknown') {
      return { ok: false, error: `cannot detect linkedin mode for ${location.href}`, jobs: [] };
    }

    // Primary path: LinkedIn marks each job card with [data-job-id="<id>"] or
    // wraps it in <li data-occludable-job-id="<id>">. Use these robust
    // selectors instead of walking up from the anchor (which fails when the
    // anchor is deeply nested and findCard's heuristic gets confused).
    const cardEls = Array.from(document.querySelectorAll(
      'li[data-occludable-job-id], div[data-job-id]'
    ));
    log(`${mode}: found ${cardEls.length} job cards via [data-job-id] / [data-occludable-job-id]`);

    const byJobId = new Map();
    for (const card of cardEls) {
      const jobId = card.getAttribute('data-job-id') || card.getAttribute('data-occludable-job-id');
      if (!jobId || !/^\d+$/.test(jobId)) continue;
      if (byJobId.has(jobId)) continue;
      // Find an anchor inside the card to pull a clean title from
      const anchor = card.querySelector('a[href*="/jobs/view/"]') || card.querySelector('a[href]');
      const link = `https://www.linkedin.com/jobs/view/${jobId}/`;
      const fields = extractCardFields(card, anchor || card, mode);
      if (!fields.role || !fields.company) continue;
      if (mode === 'applied' && fields.status_class !== 'applied') continue;
      byJobId.set(jobId, { link, job_id: jobId, ...fields });
    }

    // Fallback: anchor-walk in case LinkedIn changes the data-attribute names
    if (byJobId.size === 0) {
      log(`${mode}: data-attr path returned 0, falling back to anchor-walk`);
      const anchors = Array.from(document.querySelectorAll('a[href]'))
        .filter((a) => JOB_LINK_RE.test(a.href));
      log(`${mode}: anchor-walk found ${anchors.length} job-link anchors`);
      for (const anchor of anchors) {
        const m = anchor.href.match(JOB_LINK_RE);
        if (!m) continue;
        const jobId = m[2];
        const link = `https://www.linkedin.com/jobs/view/${jobId}/`;
        if (byJobId.has(jobId)) continue;
        const card = findCard(anchor);
        const fields = extractCardFields(card, anchor, mode);
        if (!fields.role || !fields.company) continue;
        if (mode === 'applied' && fields.status_class !== 'applied') continue;
        byJobId.set(jobId, { link, job_id: jobId, ...fields });
      }
    }

    const jobs = Array.from(byJobId.values());
    log(`${mode}: ${jobs.length} unique jobs after dedup + sanity filter`);
    return {
      ok: true,
      mode,
      jobs,
      url: location.href,
      scraped_at: new Date().toISOString(),
    };
  }

  // ===================================================================
  // DETAIL MODE — auto-runs on page load, sends HTML to background
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

  async function waitForRender(maxMs = 10000) {
    const interval = 350;
    const maxIters = Math.ceil(maxMs / interval);
    for (let i = 0; i < maxIters; i++) {
      if (hasJsonLdJobPosting()) return 'jsonld';
      // LinkedIn job detail signal: H1 with role + body has substantial content
      if (document.querySelector('h1') && (document.body?.innerText?.length || 0) > 3000) {
        return 'h1_and_body';
      }
      await new Promise((r) => setTimeout(r, interval));
    }
    return 'timeout';
  }

  async function runDetailMode() {
    const renderSignal = await waitForRender(10000);
    const html = document.documentElement.outerHTML;
    const bodyChars = document.body?.innerText?.length || 0;
    log(`detail: render=${renderSignal} html=${html.length}b body=${bodyChars}c`);
    chrome.runtime.sendMessage({
      type: 'LINKEDIN_JD_SCRAPED',
      url: location.href.split('?')[0].split('#')[0],
      html,
      render_signal: renderSignal,
      body_chars: bodyChars,
    });
  }

  // ===================================================================
  // ROUTING
  // ===================================================================
  // Unconditional load log so DevTools console confirms injection on every
  // linkedin.com page. Lets the user verify the extension is alive without
  // running anything.
  log(`loaded on ${location.href} (isListing=${isListing()} isDetail=${isDetail()} isPost=${isPost()})`);

  // Unconditional message listener -- the popup talks to us via this
  // regardless of which mode the page is in. Earlier the listener was inside
  // the isListing() branch which meant pages that didn't match the URL re
  // gave the popup a "connection failed" timeout instead of a useful error.
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === 'GET_LINKEDIN_JOBS') {
      try {
        if (!isListing()) {
          sendResponse({ ok: false, error: `not a listing page: ${location.href}`, jobs: [] });
        } else {
          sendResponse(collectListingJobs());
        }
      } catch (e) {
        sendResponse({ ok: false, error: String(e), jobs: [] });
      }
      return true;
    }
  });

  if (isDetail()) {
    log(`detail mode on ${location.href}`);
    setTimeout(runDetailMode, 200);
  } else if (isPost()) {
    log(`post mode on ${location.href}`);
    setTimeout(runPostMode, 200);
  } else if (isListing()) {
    const mode = detectListingMode();
    log(`listing mode=${mode} on ${location.href}. Open popup to scrape.`);
  }
})();

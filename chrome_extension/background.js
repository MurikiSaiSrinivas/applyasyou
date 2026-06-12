// Service worker — forwards POST_JOBS messages from the popup to local_sink.py.
// content.js cannot directly fetch() to localhost in MV3 (Cross-Origin Read Blocking);
// the service worker can, because host_permissions includes http://localhost:8765/*.

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "POST_JOBS") {
    fetch("http://localhost:8765/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.payload),
    })
      .then(r => r.json().then(j => ({ status: r.status, body: j })))
      .then(({ status, body }) => {
        if (status >= 200 && status < 300) {
          sendResponse({ ok: true, saved: body.saved || 0, total_batches: body.total_batches || 0 });
        } else {
          sendResponse({ ok: false, error: `http ${status}: ${body.error || JSON.stringify(body)}` });
        }
      })
      .catch(e => sendResponse({ ok: false, error: e.message || String(e) }));
    return true;
  }
  if (msg && msg.type === "PING_SINK") {
    fetch("http://localhost:8765/status")
      .then(r => r.json())
      .then(j => sendResponse({ ok: true, status: j }))
      .catch(e => sendResponse({ ok: false, error: e.message || String(e) }));
    return true;
  }
  // Wellfound pass 1: send metadata batch, get back list of URLs that need JDs
  if (msg && msg.type === "POST_WELLFOUND_SCRAPE") {
    fetch("http://localhost:8765/api/wellfound/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.payload),
    })
      .then(r => r.json().then(j => ({ status: r.status, body: j })))
      .then(({ status, body }) => {
        if (status >= 200 && status < 300) {
          sendResponse({
            ok: true,
            stats: body.stats || {},
            added_prospect_ids: body.added_prospect_ids || [],
            needs_jd_fetch: body.needs_jd_fetch || [],
          });
        } else {
          sendResponse({ ok: false, error: `http ${status}: ${body.error || JSON.stringify(body)}` });
        }
      })
      .catch(e => sendResponse({ ok: false, error: e.message || String(e) }));
    return true;
  }

  // Wellfound pass 2: open the job URL in a background tab so the browser
  // navigates as a real user (bypasses Cloudflare's bot detection that blocks
  // service-worker fetch). content_wellfound.js running in that tab waits
  // for React to render the JD, then sends back document.documentElement
  // .outerHTML via WELLFOUND_JD_SCRAPED. We forward the HTML to the sink for
  // BeautifulSoup extraction and close the tab.
  if (msg && msg.type === "FETCH_WELLFOUND_JD") {
    const { prospect_id, url } = msg.payload || {};
    if (!prospect_id || !url) {
      sendResponse({ ok: false, error: "prospect_id + url required" });
      return false;
    }
    openTabAndScrape(url, 25000, "WELLFOUND_JD_SCRAPED")
      .then(async (scrape) => {
        if (!scrape.ok) {
          sendResponse({ ok: false, error: scrape.error });
          return;
        }
        try {
          const r = await fetch("http://localhost:8765/api/wellfound/jd", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prospect_id, url, html: scrape.html }),
          });
          const body = await r.json().catch(() => ({}));
          if (r.ok && body.ok) {
            sendResponse({ ok: true, jd_chars: body.jd_chars || 0, render_signal: scrape.render_signal });
          } else {
            sendResponse({
              ok: false,
              error: body.warning || body.error || `sink http ${r.status}`,
              diag: body.diag || null,
              render_signal: scrape.render_signal,
            });
          }
        } catch (e) {
          sendResponse({ ok: false, error: "sink post failed: " + (e.message || String(e)) });
        }
      })
      .catch((e) => sendResponse({ ok: false, error: e.message || String(e) }));
    return true;
  }

  // LinkedIn pass 1: send metadata batch (with mode), get back list of URLs
  // that need JDs (search/saved/applied all use the same scrape endpoint;
  // the sink branches behavior by mode -- applied mode also dual-writes to
  // active.json).
  if (msg && msg.type === "POST_LINKEDIN_SCRAPE") {
    fetch("http://localhost:8765/api/linkedin/scrape", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.payload),
    })
      .then(r => r.json().then(j => ({ status: r.status, body: j })))
      .then(({ status, body }) => {
        if (status >= 200 && status < 300) {
          sendResponse({
            ok: true,
            stats: body.stats || {},
            added_prospect_ids: body.added_prospect_ids || [],
            added_active_ids: body.added_active_ids || [],
            needs_jd_fetch: body.needs_jd_fetch || [],
          });
        } else {
          sendResponse({ ok: false, error: `http ${status}: ${body.error || JSON.stringify(body)}` });
        }
      })
      .catch(e => sendResponse({ ok: false, error: e.message || String(e) }));
    return true;
  }

  // LinkedIn pass 2: open job URL in background tab, content_linkedin.js
  // DETAIL mode captures DOM, sink extracts JD + auto-scores.
  if (msg && msg.type === "FETCH_LINKEDIN_JD") {
    const { prospect_id, url } = msg.payload || {};
    if (!prospect_id || !url) {
      sendResponse({ ok: false, error: "prospect_id + url required" });
      return false;
    }
    openTabAndScrape(url, 25000, "LINKEDIN_JD_SCRAPED")
      .then(async (scrape) => {
        if (!scrape.ok) {
          sendResponse({ ok: false, error: scrape.error });
          return;
        }
        try {
          const r = await fetch("http://localhost:8765/api/linkedin/jd", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prospect_id, url, html: scrape.html }),
          });
          const body = await r.json().catch(() => ({}));
          if (r.ok && body.ok) {
            sendResponse({ ok: true, jd_chars: body.jd_chars || 0, verdict: body.verdict, match_pct: body.match_pct });
          } else {
            sendResponse({
              ok: false,
              error: body.warning || body.error || `sink http ${r.status}`,
              diag: body.diag || null,
            });
          }
        } catch (e) {
          sendResponse({ ok: false, error: "sink post failed: " + (e.message || String(e)) });
        }
      })
      .catch((e) => sendResponse({ ok: false, error: e.message || String(e) }));
    return true;
  }

  // LinkedIn post URL processor (Phase 2 feature). Popup sends a pasted URL.
  // We open it in a background tab, content_linkedin.js POST mode extracts
  // body text + embedded URLs + emails, then we POST that to sink which calls
  // Claude CLI to classify intent and return an action recommendation.
  if (msg && msg.type === "PROCESS_LINKEDIN_POST") {
    const { url } = msg.payload || {};
    if (!url) {
      sendResponse({ ok: false, error: "url required" });
      return false;
    }
    openTabAndScrape(url, 25000, "LINKEDIN_POST_SCRAPED")
      .then(async (scrape) => {
        if (!scrape.ok) {
          sendResponse({ ok: false, error: scrape.error });
          return;
        }
        try {
          const r = await fetch("http://localhost:8765/api/linkedin/process_post", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              url,
              post_body: scrape.post_body || "",
              embedded_urls: scrape.embedded_urls || [],
              embedded_emails: scrape.embedded_emails || [],
            }),
          });
          const body = await r.json().catch(() => ({}));
          if (r.ok && body.ok) {
            sendResponse({ ok: true, result: body.result || {} });
          } else {
            sendResponse({ ok: false, error: body.error || `sink http ${r.status}` });
          }
        } catch (e) {
          sendResponse({ ok: false, error: "sink post failed: " + (e.message || String(e)) });
        }
      })
      .catch((e) => sendResponse({ ok: false, error: e.message || String(e) }));
    return true;
  }

  // openTabAndScrape uses listener-based message capture; for LINKEDIN_POST_SCRAPED
  // the content script sends post_body / embedded_urls / embedded_emails along
  // with the html. The generic listener only forwards html/render_signal/body_chars
  // so we need a specialized listener for post mode. Patch: openTabAndScrape now
  // captures the FULL message (see implementation below).

  // LinkedIn pendingJds list (used by popup retry button)
  if (msg && msg.type === "GET_LINKEDIN_PENDING_JDS") {
    fetch("http://localhost:8765/api/linkedin/pending_jds")
      .then(r => r.json())
      .then(j => sendResponse(j))
      .catch(e => sendResponse({ ok: false, error: e.message || String(e) }));
    return true;
  }
});

// ---------- Tab orchestration for JD scraping (Wellfound + LinkedIn) ----------
//
// Opens `url` in a background tab. Waits for the tab's content_script to fire
// `expectedMsgType` (WELLFOUND_JD_SCRAPED or LINKEDIN_JD_SCRAPED) with the
// rendered DOM. Always closes the tab before resolving. Used by both
// FETCH_WELLFOUND_JD and FETCH_LINKEDIN_JD handlers.
function openTabAndScrape(url, timeoutMs, expectedMsgType) {
  return new Promise((resolve) => {
    let tabId = null;
    let resolved = false;

    const finish = (payload) => {
      if (resolved) return;
      resolved = true;
      chrome.runtime.onMessage.removeListener(onMsg);
      if (tabId != null) {
        chrome.tabs.remove(tabId).catch(() => {});
      }
      resolve(payload);
    };

    const onMsg = (m, sender) => {
      if (resolved || tabId == null) return;
      if (!sender || !sender.tab || sender.tab.id !== tabId) return;
      if (m && m.type === expectedMsgType) {
        // Forward all message fields (minus the type) so post-mode extras
        // like post_body / embedded_urls / embedded_emails come through
        const out = { ok: true };
        for (const k of Object.keys(m)) {
          if (k !== "type") out[k] = m[k];
        }
        finish(out);
      }
    };
    chrome.runtime.onMessage.addListener(onMsg);

    chrome.tabs.create({ url, active: false }, (tab) => {
      if (chrome.runtime.lastError) {
        finish({ ok: false, error: chrome.runtime.lastError.message });
        return;
      }
      tabId = tab.id;
    });

    setTimeout(() => {
      finish({ ok: false, error: `tab timeout after ${timeoutMs}ms` });
    }, timeoutMs);
  });
}

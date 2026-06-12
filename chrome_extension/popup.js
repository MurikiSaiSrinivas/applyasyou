// popup.js — scrape-only popup. Detects the current tab and shows the right panel:
// Google Jobs harvest, Wellfound scrape, LinkedIn scrape, or the LinkedIn post processor.

const SINK = "http://localhost:8765";

const $ = (id) => document.getElementById(id);
const banner = $("mode-banner");
const status = $("status");
const sinkStatus = $("sinkStatus");

function setStatus(text, cls) { status.textContent = text; status.className = cls || ""; }
function setMode(label, modeClass) {
  banner.textContent = label;
  banner.className = modeClass;
}

async function pingSink() {
  try {
    const r = await fetch(`${SINK}/status`);
    if (!r.ok) throw new Error(`http ${r.status}`);
    const j = await r.json();
    sinkStatus.textContent = `${j.total_in_raw} jobs / ${j.batches} batches`;
    sinkStatus.className = "ok";
    return j;
  } catch (e) {
    sinkStatus.textContent = "NOT REACHABLE";
    sinkStatus.className = "err";
    return null;
  }
}

function detectMode(url) {
  if (!url) return "other";
  if (/^https:\/\/www\.google\.com\/search/.test(url) && (/[?&]udm=8/.test(url) || /[?&]ibp=htl/.test(url))) return "google_jobs";
  if (/^https:\/\/wellfound\.com\/(jobs(\/|$|\?)|u\/[^/]+\/applications|applications)/.test(url)) return "wellfound";
  if (/^https:\/\/(www\.)?linkedin\.com\/(jobs|my-items)/.test(url)) return "linkedin";
  return "other";
}

async function loadLinkedinPendingJdsCount() {
  const pill = $("linkedinPendingPill");
  const retryBtn = $("linkedinRetry");
  try {
    const r = await fetch(`${SINK}/api/linkedin/pending_jds`);
    const j = await r.json();
    const n = (j && j.pending && j.pending.length) || 0;
    pill.textContent = n;
    if (n > 0) {
      pill.classList.add("has");
      retryBtn.textContent = `Retry ${n} pending JDs`;
      retryBtn.classList.remove("hidden");
    } else {
      pill.classList.remove("has");
      retryBtn.classList.add("hidden");
    }
    return n;
  } catch (e) {
    pill.textContent = "?";
    retryBtn.classList.add("hidden");
    return null;
  }
}

async function initLinkedin(tab) {
  setMode("Mode: LinkedIn jobs scrape", "mode-harvest");
  $("panelLinkedin").classList.remove("hidden");
  setStatus("Scanning page for jobs…");

  loadLinkedinPendingJdsCount();
  let scrapeResult = null;

  $("linkedinRetry").onclick = async () => {
    $("linkedinRetry").disabled = true;
    $("linkedinScrape").disabled = true;
    setStatus("Loading pending list from sink…");
    let pending;
    try {
      const r = await fetch(`${SINK}/api/linkedin/pending_jds`);
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "sink failed");
      pending = j.pending || [];
    } catch (e) {
      setStatus("Failed to load pending list: " + e.message, "err");
      $("linkedinRetry").disabled = false;
      $("linkedinScrape").disabled = false;
      return;
    }
    if (pending.length === 0) {
      setStatus("Nothing pending. All linkedin prospects have JDs.", "ok");
      $("linkedinRetry").disabled = false;
      $("linkedinScrape").disabled = false;
      return;
    }
    setStatus(`Retrying ${pending.length} pending JDs via background tabs…`);
    let fetched = 0, failed = 0;
    for (let i = 0; i < pending.length; i++) {
      const item = pending[i];
      $("linkedinJdProgress").textContent = `${i + 1}/${pending.length} (ok=${fetched} fail=${failed})`;
      try {
        const jdResp = await chrome.runtime.sendMessage({
          type: "FETCH_LINKEDIN_JD",
          payload: { prospect_id: item.prospect_id, url: item.url },
        });
        if (jdResp && jdResp.ok) fetched++;
        else failed++;
      } catch (e) {
        failed++;
      }
      if (i < pending.length - 1) await new Promise((r) => setTimeout(r, 1500));
    }
    $("linkedinJdProgress").textContent = `${fetched} ok, ${failed} fail`;
    setStatus(`Retry done. ${fetched} fetched, ${failed} failed.`, fetched > 0 ? "ok" : "warn");
    $("linkedinRetry").disabled = false;
    $("linkedinScrape").disabled = false;
    loadLinkedinPendingJdsCount();
  };

  $("linkedinScrape").onclick = async () => {
    if (!scrapeResult || !scrapeResult.jobs || scrapeResult.jobs.length === 0) {
      setStatus("No jobs detected on page. Scroll to render more cards (LinkedIn virtualizes), then reopen popup.", "warn");
      return;
    }
    $("linkedinScrape").disabled = true;
    setStatus(`Pass 1: sending ${scrapeResult.jobs.length} ${scrapeResult.mode} jobs to sink…`);
    let scrapeResp;
    try {
      scrapeResp = await chrome.runtime.sendMessage({
        type: "POST_LINKEDIN_SCRAPE",
        payload: { jobs: scrapeResult.jobs, mode: scrapeResult.mode, url: scrapeResult.url, scraped_at: scrapeResult.scraped_at },
      });
    } catch (e) {
      setStatus("Metadata send failed: " + e.message, "err");
      $("linkedinScrape").disabled = false;
      return;
    }
    if (!scrapeResp || !scrapeResp.ok) {
      setStatus("Sink rejected metadata: " + (scrapeResp ? scrapeResp.error : "unknown"), "err");
      $("linkedinScrape").disabled = false;
      return;
    }
    const s = scrapeResp.stats || {};
    const needsJd = scrapeResp.needs_jd_fetch || [];
    const modeSummary = scrapeResult.mode === "applied"
      ? `new=${s.new_prospects || 0} active=${s.new_active_rows || 0} existing=${s.matched_existing || 0} filtered=${s.filtered_out || 0}`
      : `new=${s.new_prospects || 0} existing=${s.matched_existing || 0} filtered=${s.filtered_out || 0}`;
    setStatus(`Pass 1 done (${modeSummary}). Pass 2: fetching JDs for ${needsJd.length} jobs…`, "ok");

    if (needsJd.length === 0) {
      $("linkedinJdProgress").textContent = "nothing to fetch";
      setStatus(`Done. ${modeSummary}. No JD fetch needed.`, "ok");
      pingSink();
      loadLinkedinPendingJdsCount();
      return;
    }

    let fetched = 0, failed = 0;
    for (let i = 0; i < needsJd.length; i++) {
      const item = needsJd[i];
      $("linkedinJdProgress").textContent = `${i + 1}/${needsJd.length} (ok=${fetched} fail=${failed})`;
      try {
        const jdResp = await chrome.runtime.sendMessage({
          type: "FETCH_LINKEDIN_JD",
          payload: { prospect_id: item.prospect_id, url: item.url },
        });
        if (jdResp && jdResp.ok) fetched++;
        else failed++;
      } catch (e) {
        failed++;
      }
      if (i < needsJd.length - 1) await new Promise((r) => setTimeout(r, 1500));
    }
    $("linkedinJdProgress").textContent = `${fetched} ok, ${failed} fail`;
    setStatus(`Done. ${modeSummary}. JDs: ${fetched} fetched, ${failed} failed.`, fetched > 0 ? "ok" : "warn");
    pingSink();
    loadLinkedinPendingJdsCount();
  };

  try {
    const res = await chrome.tabs.sendMessage(tab.id, { type: "GET_LINKEDIN_JOBS" });
    if (res && res.ok) {
      scrapeResult = res;
      $("linkedinMode").textContent = res.mode || "?";
      $("linkedinCount").textContent = `${res.jobs.length}`;
      if (res.jobs.length > 0) {
        setStatus(`Found ${res.jobs.length} ${res.mode} jobs on page. Click Scrape to ingest + fetch JDs.`, "ok");
      } else {
        setStatus(`Mode=${res.mode}, 0 jobs detected. LinkedIn virtualizes -- scroll the list to render cards, then reopen popup. (Retry pending JDs still works.)`, "warn");
      }
    } else {
      $("linkedinCount").textContent = "?";
      setStatus("Parse failed: " + (res ? res.error : "no response") + ". (Retry pending JDs still works.)", "warn");
    }
  } catch (e) {
    $("linkedinCount").textContent = "?";
    setStatus("Content script not reachable. Reload the LinkedIn tab to enable scraping. (Retry pending JDs still works.)", "warn");
  }
}

async function loadPendingJdsCount() {
  const pill = $("wellfoundPendingPill");
  const retryBtn = $("wellfoundRetry");
  try {
    const r = await fetch(`${SINK}/api/wellfound/pending_jds`);
    const j = await r.json();
    const n = (j && j.pending && j.pending.length) || 0;
    pill.textContent = n;
    if (n > 0) {
      pill.classList.add("has");
      retryBtn.textContent = `Retry ${n} pending JDs`;
      retryBtn.classList.remove("hidden");
    } else {
      pill.classList.remove("has");
      retryBtn.classList.add("hidden");
    }
    return n;
  } catch (e) {
    pill.textContent = "?";
    retryBtn.classList.add("hidden");
    return null;
  }
}

async function initWellfound(tab) {
  setMode("Mode: Wellfound jobs scrape", "mode-harvest");
  $("panelWellfound").classList.remove("hidden");
  setStatus("Scanning page for jobs…");

  loadPendingJdsCount();
  let scrapeResult = null;

  $("wellfoundRetry").onclick = async () => {
    $("wellfoundRetry").disabled = true;
    $("wellfoundScrape").disabled = true;
    setStatus("Loading pending list from sink…");
    let pending;
    try {
      const r = await fetch(`${SINK}/api/wellfound/pending_jds`);
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || "sink failed");
      pending = j.pending || [];
    } catch (e) {
      setStatus("Failed to load pending list: " + e.message, "err");
      $("wellfoundRetry").disabled = false;
      $("wellfoundScrape").disabled = false;
      return;
    }
    if (pending.length === 0) {
      setStatus("Nothing pending. All wellfound prospects have JDs.", "ok");
      $("wellfoundRetry").disabled = false;
      $("wellfoundScrape").disabled = false;
      return;
    }
    setStatus(`Retrying ${pending.length} pending JDs via background tabs…`);
    let fetched = 0, failed = 0;
    for (let i = 0; i < pending.length; i++) {
      const item = pending[i];
      $("wellfoundJdProgress").textContent = `${i + 1}/${pending.length} (ok=${fetched} fail=${failed})`;
      try {
        const jdResp = await chrome.runtime.sendMessage({
          type: "FETCH_WELLFOUND_JD",
          payload: { prospect_id: item.prospect_id, url: item.url },
        });
        if (jdResp && jdResp.ok) fetched++;
        else failed++;
      } catch (e) {
        failed++;
      }
      if (i < pending.length - 1) await new Promise((r) => setTimeout(r, 1000));
    }
    $("wellfoundJdProgress").textContent = `${fetched} ok, ${failed} fail`;
    setStatus(`Retry done. ${fetched} fetched, ${failed} failed.`, fetched > 0 ? "ok" : "warn");
    $("wellfoundRetry").disabled = false;
    $("wellfoundScrape").disabled = false;
    loadPendingJdsCount();
  };

  $("wellfoundScrape").onclick = async () => {
    if (!scrapeResult || !scrapeResult.jobs || scrapeResult.jobs.length === 0) {
      setStatus("No jobs detected on page. Scroll to load more cards, then reopen popup.", "warn");
      return;
    }
    $("wellfoundScrape").disabled = true;
    setStatus("Pass 1: sending metadata to sink…");
    let scrapeResp;
    try {
      scrapeResp = await chrome.runtime.sendMessage({
        type: "POST_WELLFOUND_SCRAPE",
        payload: { jobs: scrapeResult.jobs, url: scrapeResult.url, scraped_at: scrapeResult.scraped_at },
      });
    } catch (e) {
      setStatus("Metadata send failed: " + e.message, "err");
      $("wellfoundScrape").disabled = false;
      return;
    }
    if (!scrapeResp || !scrapeResp.ok) {
      setStatus("Sink rejected metadata: " + (scrapeResp ? scrapeResp.error : "unknown"), "err");
      $("wellfoundScrape").disabled = false;
      return;
    }
    const s = scrapeResp.stats || {};
    const needsJd = scrapeResp.needs_jd_fetch || [];
    setStatus(
      `Pass 1 done. new=${s.new_prospects || 0}, existing=${s.matched_existing || 0}. ` +
      `Pass 2: fetching JDs for ${needsJd.length} jobs…`,
      "ok"
    );

    if (needsJd.length === 0) {
      $("wellfoundJdProgress").textContent = "nothing to fetch";
      setStatus(`Done. new_prospects=${s.new_prospects || 0}, existing=${s.matched_existing || 0}. No JD fetch needed.`, "ok");
      pingSink();
      return;
    }

    let fetched = 0, failed = 0;
    for (let i = 0; i < needsJd.length; i++) {
      const item = needsJd[i];
      $("wellfoundJdProgress").textContent = `${i + 1}/${needsJd.length} (ok=${fetched} fail=${failed})`;
      try {
        const jdResp = await chrome.runtime.sendMessage({
          type: "FETCH_WELLFOUND_JD",
          payload: { prospect_id: item.prospect_id, url: item.url },
        });
        if (jdResp && jdResp.ok) fetched++;
        else failed++;
      } catch (e) {
        failed++;
      }
      if (i < needsJd.length - 1) {
        await new Promise((r) => setTimeout(r, 1000));
      }
    }
    $("wellfoundJdProgress").textContent = `${fetched} ok, ${failed} fail`;
    setStatus(
      `Done. Metadata: new=${s.new_prospects || 0}, existing=${s.matched_existing || 0}. ` +
      `JDs: ${fetched} fetched, ${failed} failed. Run \`score_prospects.py\` to add heuristic verdicts.`,
      fetched > 0 ? "ok" : "warn"
    );
    pingSink();
    loadPendingJdsCount();
  };

  try {
    const res = await chrome.tabs.sendMessage(tab.id, { type: "GET_WELLFOUND_JOBS" });
    if (res && res.ok) {
      scrapeResult = res;
      $("wellfoundCount").textContent = `${res.jobs.length}`;
      if (res.jobs.length > 0) {
        setStatus(`Found ${res.jobs.length} jobs on page. Click "Scrape + fetch JDs" to ingest + fetch JDs.`, "ok");
      } else {
        setStatus("0 jobs detected on page. Scroll to load more cards, then reopen popup. (Retry pending JDs still works.)", "warn");
      }
    } else {
      $("wellfoundCount").textContent = "?";
      setStatus("Parse failed: " + (res ? res.error : "no response") + ". (Retry pending JDs still works.)", "warn");
    }
  } catch (e) {
    $("wellfoundCount").textContent = "?";
    setStatus("Content script not reachable. Reload tab (Ctrl+R) to enable scraping. (Retry pending JDs still works.)", "warn");
  }
}

async function initHarvest(tab) {
  setMode("Mode: Google Jobs harvest", "mode-harvest");
  $("panelHarvest").classList.remove("hidden");
  setStatus(`URL: ${tab.url.substring(0, 90)}…`);
  let result;
  try {
    result = await chrome.tabs.sendMessage(tab.id, { type: "GET_JOBS" });
  } catch (e) {
    setStatus("Content script not reachable. Reload the tab and reopen this popup.\n" + e.message, "err");
    $("harvestSend").disabled = true;
    return;
  }
  if (!result) { setStatus("No data from content script.", "err"); return; }
  $("harvestCount").textContent = `${result.jobs.length} jobs`;
  $("harvestStrategy").textContent = result.strategy;
  if (result.jobs.length === 0) $("harvestSend").disabled = true;

  $("harvestSend").onclick = async () => {
    $("harvestSend").disabled = true;
    setStatus("Sending…");
    try {
      const resp = await chrome.runtime.sendMessage({
        type: "POST_JOBS",
        payload: { jobs: result.jobs, url: tab.url, scraped_at: new Date().toISOString(), strategy: result.strategy },
      });
      if (resp && resp.ok) {
        setStatus(`Sent ${result.jobs.length} jobs.`, "ok");
        pingSink();
      } else {
        setStatus("Error: " + (resp ? resp.error : "unknown"), "err");
        $("harvestSend").disabled = false;
      }
    } catch (e) {
      setStatus("Send failed: " + e.message, "err");
      $("harvestSend").disabled = false;
    }
  };
}

async function initOther(tab) {
  setMode("Mode: other (no panel)", "mode-other");
  setStatus("Open a Google Jobs search, a Wellfound jobs page, or a LinkedIn jobs page to scrape. The LinkedIn post processor below works anywhere.");
}

// ---------- LinkedIn post URL processor (always-visible panel) ----------
function wirePostUrlPanel() {
  const input = $("postUrlInput");
  const btn = $("postUrlProcess");
  const result = $("postUrlResult");
  const intentEl = $("postUrlIntent");
  const summaryEl = $("postUrlSummary");
  const actionsEl = $("postUrlActions");

  btn.addEventListener("click", async () => {
    const url = (input.value || "").trim();
    if (!url) { setStatus("Paste a LinkedIn post URL first.", "warn"); return; }
    if (!/^https:\/\/(www\.)?linkedin\.com\/(posts|feed)/i.test(url)) {
      setStatus("URL must be a linkedin.com/posts/... or /feed/update/... link.", "warn");
      return;
    }
    btn.disabled = true;
    result.classList.add("hidden");
    setStatus("Opening post in background tab and extracting…");
    let resp;
    try {
      resp = await chrome.runtime.sendMessage({
        type: "PROCESS_LINKEDIN_POST",
        payload: { url },
      });
    } catch (e) {
      setStatus("Process failed: " + e.message, "err");
      btn.disabled = false;
      return;
    }
    btn.disabled = false;
    if (!resp || !resp.ok) {
      setStatus("Process failed: " + (resp ? resp.error : "no response"), "err");
      return;
    }
    const r = resp.result || {};
    setStatus(`Intent: ${r.intent || '?'} (confidence ${r.confidence ?? '?'})`, "ok");
    intentEl.textContent = `${(r.intent || '?').toUpperCase()}  ·  ${r.company || '?'}${r.role ? ' — ' + r.role : ''}`;
    summaryEl.textContent = r.summary || '(no summary)';
    actionsEl.innerHTML = "";

    const addBtn = (label, handler) => {
      const b = document.createElement("button");
      b.textContent = label;
      b.style.cssText = "margin-top:6px;width:100%";
      b.onclick = handler;
      actionsEl.appendChild(b);
    };

    if (r.intent === "careers_page" && r.careers_url) {
      addBtn(`Open careers page: ${truncate(r.careers_url, 50)}`, () => {
        chrome.tabs.create({ url: r.careers_url, active: true });
      });
      addBtn("Copy careers URL", () => navigator.clipboard.writeText(r.careers_url));
    }
    if (r.intent === "email_resume" && r.contact_email) {
      const subject = encodeURIComponent(`Re: ${r.role || 'opportunity'} at ${r.company || ''} (via your LinkedIn post)`.trim());
      // Generic outreach body. Edit this to add your own snapshot + signature.
      const body = encodeURIComponent(
        `Hi${r.contact_name ? ' ' + r.contact_name.split(/\s+/)[0] : ''},\n\n` +
        `Saw your LinkedIn post about ${r.role ? 'the ' + r.role + ' role' : 'the opportunity'}` +
        `${r.company ? ' at ' + r.company : ''}. Sending my resume per your ask.\n\n` +
        `Resume attached. Happy to hop on a quick call if it's a fit.\n\nThanks`
      );
      const mailto = `mailto:${r.contact_email}?subject=${subject}&body=${body}`;
      addBtn(`Compose to ${r.contact_email}`, () => {
        chrome.tabs.create({ url: mailto });
      });
      addBtn("Copy email address", () => navigator.clipboard.writeText(r.contact_email));
    }
    if (r._source_post_url) {
      addBtn("Open original post", () => {
        chrome.tabs.create({ url: r._source_post_url, active: true });
      });
    }
    if (r.suggested_action) {
      const note = document.createElement("div");
      note.style.cssText = "margin-top:8px;padding:6px 8px;background:var(--surface-2);border:1px solid var(--line);border-radius:4px;font-size:11px;color:var(--text-2)";
      note.textContent = "Suggested: " + r.suggested_action;
      actionsEl.appendChild(note);
    }
    result.classList.remove("hidden");
  });
}

function truncate(s, n) { return s.length > n ? s.slice(0, n - 1) + "…" : s; }

async function init() {
  wirePostUrlPanel();
  await pingSink();

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) { setStatus("No active tab.", "err"); return; }

  const mode = detectMode(tab.url);
  if (mode === "google_jobs") return initHarvest(tab);
  if (mode === "wellfound")  return initWellfound(tab);
  if (mode === "linkedin")   return initLinkedin(tab);
  return initOther(tab);
}

init();

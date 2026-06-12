// Google Jobs Harvester — content script (v0.2.0)
// Runs on https://www.google.com/search* — only acts when URL has udm=8 (Jobs vertical).
// Selectors based on the rendered DOM dumped 2026-05-26:
//   div[jscontroller="b11o3b"].EimVGf      job card wrapper
//   .tNxQIb.PUpOsf                          title
//   .wHYlTd.MKCbgd.a3jPc                    company
//   .wHYlTd.FqK3wc.MKCbgd                   "location  •  via Source"
//   span.fLsjxc                             "3 days ago"
//   a.brKmxb[href][title^="Apply"]          inline apply links (1..8 per card)

const CARD_SELECTOR = 'div[jscontroller="b11o3b"].EimVGf';

// Aggregator hosts/labels that we want to *deprioritize* when picking the primary apply link.
// Prefer the canonical poster / ATS over aggregators like LinkedIn.
const AGGREGATOR_RE = /\b(linkedin|indeed|ziprecruiter|dice|glassdoor|simplyhired|monster|builtin|jobright|jora|jobs2careers|careerbuilder|jobcase|wfhbridge|remote\.co|getwork|talent\.com|joinrise|onlinejobhelp|jooble|appcast|nexxt|snagajob)\b/i;
const ATS_RE = /\b(workday|myworkdayjobs|greenhouse|lever\.co|ashbyhq|ashby|smartrecruiters|jobvite|icims|eightfold|rippling|workatastartup)\b/i;

function txt(el) {
  return (el ? (el.innerText || el.textContent || "") : "").trim();
}

function pickPrimaryApply(links, viaHint) {
  if (!links.length) return null;
  const hint = (viaHint || "").toLowerCase();

  // 1) Match the Google "via X" attribution — usually the canonical poster.
  if (hint) {
    const m = links.find(l => l.via.toLowerCase().includes(hint));
    if (m) return m;
  }
  // 2) Anything that looks like an ATS (Workday/Greenhouse/Lever/Ashby/etc.) — clean apply UX.
  const ats = links.find(l => ATS_RE.test(l.url));
  if (ats) return ats;
  // 3) Direct employer site = neither aggregator nor ATS host we recognize.
  const direct = links.find(l => !AGGREGATOR_RE.test(l.url + " " + l.via));
  if (direct) return direct;
  // 4) Fall back to first non-LinkedIn link (deprioritize LinkedIn as primary).
  const nonLi = links.find(l => !/linkedin/i.test(l.url));
  return nonLi || links[0];
}

function extractFromCard(el) {
  const title = txt(el.querySelector('.tNxQIb.PUpOsf'));
  const company = txt(el.querySelector('.wHYlTd.MKCbgd.a3jPc'));

  let location = "", via = "";
  const locSrc = el.querySelector('.wHYlTd.FqK3wc.MKCbgd');
  if (locSrc) {
    const raw = txt(locSrc).replace(/\s+/g, " ");
    const parts = raw.split(/\s*[•·]\s*/);
    location = (parts[0] || "").trim();
    via = (parts[1] || "").replace(/^via\s+/i, "").trim();
  }

  const dateEl = el.querySelector('span.fLsjxc');
  const datePosted = dateEl ? txt(dateEl) : "";

  const shareUrl = el.getAttribute("data-share-url") || "";

  const applyLinks = [];
  const seenUrls = new Set();
  for (const a of el.querySelectorAll('a.brKmxb[href]')) {
    const href = a.getAttribute("href") || "";
    if (!href || !href.startsWith("http") || seenUrls.has(href)) continue;
    seenUrls.add(href);
    const t = (a.getAttribute("title") || "").replace(/^Apply\s+(directly\s+)?on\s+/i, "").trim();
    applyLinks.push({ via: t, url: href });
  }
  const primary = pickPrimaryApply(applyLinks, via);

  return {
    company,
    role: title,
    location,
    via,                                              // Google's attribution ("LinkedIn", "Adobe Careers", ...)
    link: primary ? primary.url : shareUrl,
    link_provider: primary ? primary.via : "",
    apply_links: applyLinks,                          // full list so processor can re-pick
    date_posted_raw: datePosted,
    google_share_url: shareUrl,
  };
}

function extractJobs() {
  const cards = document.querySelectorAll(CARD_SELECTOR);
  if (!cards.length) {
    return { strategy: "none", jobs: [] };
  }
  const jobs = Array.from(cards).map(extractFromCard).filter(j => j.role && j.company);
  return { strategy: "EimVGf", jobs };
}

let cached = { strategy: "none", jobs: [] };

function detect() {
  cached = extractJobs();
  return cached;
}

function isJobsPage() {
  return location.search.includes("udm=8") || location.search.includes("ibp=htl;jobs");
}

if (isJobsPage()) {
  setTimeout(detect, 2500);
  setTimeout(detect, 5000);  // second pass after lazy-load
}

let lastUrl = location.href;
const obs = new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    if (isJobsPage()) setTimeout(detect, 1800);
  }
});
obs.observe(document.body, { childList: true, subtree: true });

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "GET_JOBS") {
    sendResponse(detect());
  }
  return false;
});

const DATA_URL = "data/articles.json";
const CLIENT_REFRESH_MS = 5 * 60 * 1000; // re-check data.json every 5 min (bot itself runs a few times/day)

let allArticles = [];
let activeSource = null; // null = all sources
let searchTerm = "";

const feedEl = document.getElementById("feed");
const sourceListEl = document.getElementById("sourceList");
const searchEl = document.getElementById("search");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const footerMeta = document.getElementById("footerMeta");

function timeAgo(iso) {
  const then = new Date(iso).getTime();
  const diffMin = Math.round((Date.now() - then) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
}

function renderSources() {
  const counts = {};
  allArticles.forEach(a => { counts[a.source] = (counts[a.source] || 0) + 1; });
  const sources = Object.keys(counts).sort();

  sourceListEl.innerHTML = "";
  const allBtn = document.createElement("li");
  allBtn.innerHTML = `<button class="source-toggle ${activeSource === null ? "active" : ""}" data-source="">
    <span>All sources</span><span class="count">${allArticles.length}</span></button>`;
  sourceListEl.appendChild(allBtn);

  sources.forEach(src => {
    const li = document.createElement("li");
    li.innerHTML = `<button class="source-toggle ${activeSource === src ? "active" : ""}" data-source="${src}">
      <span>${src}</span><span class="count">${counts[src]}</span></button>`;
    sourceListEl.appendChild(li);
  });

  sourceListEl.querySelectorAll(".source-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      activeSource = btn.dataset.source || null;
      renderSources();
      renderFeed();
    });
  });
}

function renderFeed() {
  const term = searchTerm.trim().toLowerCase();
  const filtered = allArticles.filter(a => {
    if (activeSource && a.source !== activeSource) return false;
    if (term && !(a.title.toLowerCase().includes(term) || a.summary.toLowerCase().includes(term))) return false;
    return true;
  });

  if (filtered.length === 0) {
    feedEl.innerHTML = `<p class="empty-state">Nothing matches yet. Try a different source or search term.</p>`;
    return;
  }

  feedEl.innerHTML = filtered.map(a => `
    <article class="article">
      <div class="article-meta">
        ${timeAgo(a.published)}
        <span class="source">${a.source}</span>
      </div>
      <div>
        <h2 class="article-title"><a href="${a.link}" target="_blank" rel="noopener">${a.title}</a></h2>
        <p class="article-summary">${a.summary || ""}</p>
      </div>
    </article>
  `).join("");
}

async function loadData() {
  try {
    const res = await fetch(`${DATA_URL}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    allArticles = data.articles || [];
    renderSources();
    renderFeed();

    if (data.generated_at) {
      statusDot.classList.add("live");
      statusText.textContent = `updated ${timeAgo(data.generated_at)}`;
      footerMeta.textContent = `${allArticles.length} articles · ${(data.sources_polled || []).length} sources polled · last run ${new Date(data.generated_at).toUTCString()}`;
    } else {
      statusText.textContent = "awaiting first bot run";
      footerMeta.textContent = "No automated run yet — check the GitHub Action.";
    }
  } catch (err) {
    statusDot.classList.remove("live");
    statusText.textContent = "data unavailable";
    console.error("Failed to load articles.json", err);
  }
}

searchEl.addEventListener("input", (e) => {
  searchTerm = e.target.value;
  renderFeed();
});

loadData();
setInterval(loadData, CLIENT_REFRESH_MS);

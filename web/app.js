"use strict";
// Strona ze statystykami: wszystko liczone w przeglądarce z data.json.

const NUM = new Intl.NumberFormat("pl-PL");
const fmt = n => NUM.format(n);
const time = s => {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
  return h ? `${fmt(h)} h ${m} min` : `${m} min`;
};
const dist = m => m >= 1000 ? `${(m / 1000).toLocaleString("pl-PL", {maximumFractionDigits: 1})} km` : `${fmt(m)} m`;
const hearts = n => `${fmt(n)} ❤`;

// Kategorie rankingów: klucz w data.json, nazwa, ikona, formatowanie.
const STATS = [
  {k: "play_time", t: "Czas gry", i: "⏱️", f: time},
  {k: "mined", t: "Wykopane bloki", i: "⛏️", f: fmt},
  {k: "mob_kills", t: "Zabite moby", i: "⚔️", f: fmt},
  {k: "deaths", t: "Zgony", i: "💀", f: fmt},
  {k: "distance", t: "Przebyty dystans", i: "🧭", f: dist},
  {k: "diamonds", t: "Wykopane diamenty", i: "💎", f: fmt},
  {k: "crafted", t: "Wytworzone przedmioty", i: "🛠️", f: fmt},
  {k: "player_kills", t: "Zabici gracze", i: "🗡️", f: fmt},
  {k: "jumps", t: "Skoki", i: "🐇", f: fmt},
  {k: "trades", t: "Handel z osadnikami", i: "💰", f: fmt},
  {k: "fish", t: "Złowione ryby", i: "🎣", f: fmt},
  {k: "bred", t: "Rozmnożone zwierzęta", i: "🐑", f: fmt},
  {k: "enchants", t: "Zaklęte przedmioty", i: "✨", f: fmt},
  {k: "ancient_debris", t: "Pradawne zgliszcza", i: "🔥", f: fmt},
  {k: "elytra", t: "Lot na elytrze", i: "🪽", f: dist},
  {k: "sleep", t: "Przespane noce", i: "🛏️", f: fmt},
  {k: "damage_dealt", t: "Zadane obrażenia", i: "🏹", f: hearts},
  {k: "damage_taken", t: "Otrzymane obrażenia", i: "🩹", f: hearts},
  {k: "chests", t: "Otwarte skrzynie", i: "📦", f: fmt},
];
const LISTS = [
  {k: "mined", t: "Najczęściej kopane", i: "⛏️"},
  {k: "killed", t: "Najczęściej zabijane", i: "⚔️"},
  {k: "killed_by", t: "Najczęściej ginął od", i: "💀"},
  {k: "crafted", t: "Najczęściej tworzone", i: "🛠️"},
  {k: "used", t: "Najczęściej używane", i: "✋"},
];

let DATA = null;
const app = document.getElementById("app");
const esc = s => String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const link = name => "#/gracz/" + encodeURIComponent(name);

// Pikselowy awatar z nicku (bez wysyłania czegokolwiek do zewnętrznych stron).
function avatar(name, size = 8) {
  let h = 2166136261;
  for (const ch of name) h = Math.imul(h ^ ch.codePointAt(0), 16777619);
  const rnd = () => ((h = Math.imul(h ^ (h >>> 15), 2246822507) ^ Math.imul(h ^ (h >>> 13), 3266489909)) >>> 0) / 4294967296;
  const hue = Math.floor(rnd() * 360);
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  g.fillStyle = `hsl(${hue} 35% 22%)`;
  g.fillRect(0, 0, size, size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size / 2; x++) {
    const r = rnd();
    if (r < 0.55) {
      g.fillStyle = `hsl(${(hue + (r < 0.2 ? 40 : 0)) % 360} ${55 + r * 30}% ${45 + r * 30}%)`;
      g.fillRect(x, y, 1, 1);
      g.fillRect(size - 1 - x, y, 1, 1);
    }
  }
  return c;
}
const avCache = {};
const avImg = name => `<img class="av" alt="" src="${avCache[name] ||= avatar(name).toDataURL()}">`;

function ago(iso) {
  if (!iso) return "nieznane";
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 600) return "przed chwilą";
  if (s < 3600) return `${Math.round(s / 60)} min temu`;
  if (s < 86400) return `${Math.round(s / 3600)} h temu`;
  const d = Math.round(s / 86400);
  if (d === 1) return "wczoraj";
  if (d < 30) return `${d} dni temu`;
  return new Date(iso).toLocaleDateString("pl-PL");
}
const recent = iso => iso && (Date.now() - new Date(iso)) < 60 * 60 * 1000;

function ranking(key) {
  return DATA.players.filter(p => p.totals[key] > 0).sort((a, b) => b.totals[key] - a.totals[key]);
}

function rows(list, st, limit) {
  return list.slice(0, limit).map((p, i) => `
    <a class="row p${i + 1}" href="${link(p.name)}">
      <span class="pos">${i + 1}</span>${avImg(p.name)}
      <span class="nm">${esc(p.name)}</span><span class="val">${st.f(p.totals[st.k])}</span>
    </a>`).join("");
}

function viewRankings() {
  const sum = k => DATA.players.reduce((a, p) => a + p.totals[k], 0);
  const tiles = [
    ["Graczy", fmt(DATA.players.length)],
    ["Łączny czas gry", time(sum("play_time"))],
    ["Wykopane bloki", fmt(sum("mined"))],
    ["Zabite moby", fmt(sum("mob_kills"))],
    ["Zgony", fmt(sum("deaths"))],
    ["Przebyty dystans", dist(sum("distance"))],
  ];
  const cards = STATS.map(st => {
    const list = ranking(st.k);
    if (!list.length) return "";
    return `<section class="card" data-k="${st.k}">
      <h3><span class="ico">${st.i}</span>${st.t}</h3>
      <div class="rows">${rows(list, st, 5)}</div>
      ${list.length > 5 ? `<button class="more">Pokaż wszystkich (${list.length})</button>` : ""}
    </section>`;
  }).join("");
  app.innerHTML = `
    <div class="tiles">${tiles.map(([t, v]) => `<div class="tile"><b>${v}</b><span>${t}</span></div>`).join("")}</div>
    <div class="grid">${cards || '<p class="empty">Brak statystyk.</p>'}</div>`;
  app.querySelectorAll(".more").forEach(btn => btn.onclick = () => {
    const card = btn.closest(".card"), st = STATS.find(s => s.k === card.dataset.k);
    const open = btn.dataset.open !== "1";
    card.querySelector(".rows").innerHTML = rows(ranking(st.k), st, open ? 1e9 : 5);
    btn.dataset.open = open ? "1" : "0";
    btn.textContent = open ? "Zwiń" : `Pokaż wszystkich (${ranking(st.k).length})`;
  });
}

let listState = {q: "", sort: "play_time"};
function viewPlayers() {
  const opts = [["play_time", "czasu gry"], ["last_seen", "ostatniej gry"], ["name", "nicku"], ["mined", "wykopanych bloków"], ["mob_kills", "zabitych mobów"], ["deaths", "zgonów"]];
  app.innerHTML = `
    <div class="toolbar">
      <input id="q" type="search" placeholder="Szukaj gracza…" value="${esc(listState.q)}" autocomplete="off">
      <select id="sort">${opts.map(([v, t]) => `<option value="${v}"${v === listState.sort ? " selected" : ""}>Sortuj według ${t}</option>`).join("")}</select>
    </div>
    <table><thead><tr><th>Gracz</th><th class="n">Czas gry</th><th class="n hide-sm">Wykopane</th><th class="n hide-sm">Zgony</th><th class="n">Ostatnio</th></tr></thead>
    <tbody id="tb"></tbody></table>`;
  const draw = () => {
    const q = listState.q.toLowerCase(), s = listState.sort;
    const list = DATA.players.filter(p => p.name.toLowerCase().includes(q)).sort((a, b) =>
      s === "name" ? a.name.localeCompare(b.name, "pl") :
      s === "last_seen" ? String(b.last_seen || "").localeCompare(String(a.last_seen || "")) :
      b.totals[s] - a.totals[s]);
    document.getElementById("tb").innerHTML = list.map(p => `
      <tr data-n="${esc(p.name)}">
        <td><span class="who">${avImg(p.name)}${esc(p.name)}</span></td>
        <td class="n">${time(p.totals.play_time)}</td>
        <td class="n hide-sm">${fmt(p.totals.mined)}</td>
        <td class="n hide-sm">${fmt(p.totals.deaths)}</td>
        <td class="n"><span class="dot${recent(p.last_seen) ? " on" : ""}"></span>${ago(p.last_seen)}</td>
      </tr>`).join("") || `<tr><td colspan="5" class="empty">Nie ma takiego gracza.</td></tr>`;
    document.querySelectorAll("#tb tr[data-n]").forEach(tr => tr.onclick = () => location.hash = link(tr.dataset.n));
  };
  document.getElementById("q").oninput = e => { listState.q = e.target.value; draw(); };
  document.getElementById("sort").onchange = e => { listState.sort = e.target.value; draw(); };
  draw();
}

function viewPlayer(name) {
  const p = DATA.players.find(x => x.name === name);
  if (!p) { app.innerHTML = `<a class="back" href="#/gracze">← Gracze</a><p class="empty">Nie ma takiego gracza.</p>`; return; }
  const place = k => { const i = ranking(k).indexOf(p); return i >= 0 ? `<em>#${i + 1}</em>` : ""; };
  const tiles = STATS.map(st => `<div class="tile"><b>${st.f(p.totals[st.k])}${place(st.k)}</b><span>${st.i} ${st.t}</span></div>`).join("");
  const lists = LISTS.map(l => {
    const items = p.top[l.k] || [];
    if (!items.length) return "";
    const max = items[0][1];
    return `<section class="card bars"><h3><span class="ico">${l.i}</span>${l.t}</h3>
      ${items.map(([n, v]) => `<div class="row"><span class="bar">${esc(n)}<i style="width:${Math.max(3, v / max * 100)}%"></i></span><span class="val">${fmt(v)}</span></div>`).join("")}
    </section>`;
  }).join("");
  app.innerHTML = `
    <a class="back" href="#/gracze">← Wszyscy gracze</a>
    <div class="profile"><span id="pav"></span><div><h1>${esc(p.name)}</h1>
      <p><span class="dot${recent(p.last_seen) ? " on" : ""}"></span>Ostatnio na serwerze: ${ago(p.last_seen)}</p></div></div>
    <div class="tiles">${tiles}</div>
    <div class="grid">${lists}</div>`;
  document.getElementById("pav").appendChild(avatar(p.name));
}

function route() {
  if (!DATA) return;
  const h = decodeURIComponent(location.hash.slice(1));
  const tab = h.startsWith("/gracz") ? "gracze" : "rankingi";
  document.querySelectorAll("[data-nav]").forEach(a => a.classList.toggle("on", a.dataset.nav === tab));
  if (h.startsWith("/gracz/")) viewPlayer(h.slice(7));
  else if (h === "/gracze") viewPlayers();
  else viewRankings();
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
fetch("data.json", {cache: "no-store"}).then(r => r.json()).then(d => {
  DATA = d;
  const upd = new Date(d.generated);
  document.getElementById("updated").textContent =
    `Zaktualizowano ${upd.toLocaleString("pl-PL", {dateStyle: "long", timeStyle: "short"})}. Statystyki odświeżają się co około 30 minut.`;
  route();
}).catch(() => app.innerHTML = '<p class="empty">Nie udało się wczytać statystyk. Spróbuj odświeżyć stronę.</p>');

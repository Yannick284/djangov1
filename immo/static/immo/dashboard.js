(function () {
  const cfg = window.IMMO_DASHBOARD || {};
  const propId = cfg.propId;
  if (!propId) return;

  const base = `/immo/properties/${propId}`;
  const endDate = cfg.endDate || null;
  const growth = cfg.growth || "0.0";

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(";").shift();
    return null;
  }

  function ymToIsoDate(ym) {
    if (!ym || ym.length < 7) return null;
    return `${ym}-01`;
  }

  // ---------- Helpers ----------
  const shortK = (v) => {
    const n = Number(v);
    if (Number.isNaN(n)) return v;
    if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1).replace(".0", "")}k`;
    return `${n}`;
  };

  // ---------------- GRAPHIQUE (SVG maison, sans bibliothèque externe) ----------------
  const NS = "http://www.w3.org/2000/svg";
  function el(name, attrs, parent) {
    const n = document.createElementNS(NS, name);
    for (const k in attrs || {}) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  const fmtEUR = (v) => `${Math.round(v).toLocaleString("fr-FR")} €`;
  const cssVar = (name, fallback) =>
    getComputedStyle(document.body).getPropertyValue(name).trim() || fallback;

  // Échelle « jolie » : renvoie [min, max, pas]
  function niceScale(min, max, ticks) {
    if (min === max) { min -= 1; max += 1; }
    const span = max - min;
    const raw = span / Math.max(1, ticks);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || 10 * mag;
    return [Math.floor(min / step) * step, Math.ceil(max / step) * step, step];
  }

  async function initChart() {
    const host = document.getElementById("marketChart");
    if (!host) return;

    let seriesData, beData = null;
    try {
      const r = await fetch(`${base}/market-series/`, { credentials: "same-origin" });
      if (!r.ok) throw new Error(r.status);
      seriesData = await r.json();
    } catch (e) {
      host.textContent = "Le graphique n'a pas pu être chargé.";
      return;
    }
    try {
      const beUrl = `${base}/breakeven/?${endDate ? `end=${encodeURIComponent(endDate)}&` : ""}growth=${encodeURIComponent(growth)}`;
      const r = await fetch(beUrl, { credentials: "same-origin" });
      if (r.ok) beData = await r.json();
    } catch (_) {}

    const pts = seriesData.series || [];
    if (pts.length === 0) {
      host.innerHTML = '<p class="muted">Pas encore de point de marché. Ajoute un mois et un prix au m² ci-dessous.</p>';
      return;
    }

    const labels = pts.map((p) => p.date);
    const market = pts.map((p) => Number(p.price_per_sqm));
    const net = pts.map((p) => (p.net_vendeur_per_sqm == null ? null : Number(p.net_vendeur_per_sqm)));
    const hasNet = net.some((v) => v !== null);
    const beDate = beData && beData.result && beData.result.date;
    const beIdx = beDate ? labels.indexOf(beDate) : -1;

    const cMarket = cssVar("--laiton", "#D6A845");
    const cNet = cssVar("--brume", "#E6EEE9");
    const cMuted = cssVar("--muted", "#9DB1A8");
    const cGrid = "rgba(230,238,233,.12)";

    const isMobile = window.matchMedia("(max-width: 560px)").matches;
    host.innerHTML = "";
    const tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.hidden = true;
    host.appendChild(tip);

    const svg = el("svg", { preserveAspectRatio: "none" }, host);
    const toggle = document.getElementById("toggleNet");
    const state = { showNet: !(isMobile) && (toggle ? toggle.checked : true) };
    if (toggle) toggle.checked = state.showNet && hasNet;
    if (!hasNet && toggle) toggle.parentElement.hidden = true;

    function draw() {
      const W = host.clientWidth || 600;
      const H = host.clientHeight || 300;
      svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
      svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
      while (svg.firstChild) svg.removeChild(svg.firstChild);

      const showNet = state.showNet && hasNet;
      const pad = { l: 52, r: showNet && !isMobile ? 56 : 12, t: 12, b: 28 };
      const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
      const n = pts.length;
      const x = (i) => pad.l + (n === 1 ? iw / 2 : (i * iw) / (n - 1));

      const mVals = market.filter((v) => !Number.isNaN(v));
      const [m0, m1, ms] = niceScale(Math.min(...mVals), Math.max(...mVals), 5);
      const yM = (v) => pad.t + ih - ((v - m0) / (m1 - m0)) * ih;

      let yN = null, n0 = 0, n1 = 1, ns = 1;
      if (showNet) {
        const nv = net.filter((v) => v !== null).concat([0]);
        [n0, n1, ns] = niceScale(Math.min(...nv), Math.max(...nv), 5);
        yN = (v) => pad.t + ih - ((v - n0) / (n1 - n0)) * ih;
      }

      // Grille + axe gauche (marché)
      for (let v = m0; v <= m1 + 1e-9; v += ms) {
        el("line", { x1: pad.l, x2: W - pad.r, y1: yM(v), y2: yM(v), stroke: cGrid }, svg);
        const t = el("text", { x: pad.l - 8, y: yM(v) + 4, "text-anchor": "end", fill: cMuted, "font-size": 11 }, svg);
        t.textContent = `${Math.round(v).toLocaleString("fr-FR")}`;
      }
      // Axe droit (net vendeur) + ligne du zéro
      if (yN) {
        for (let v = n0; v <= n1 + 1e-9; v += ns) {
          if (!isMobile) {
            const t = el("text", { x: W - pad.r + 8, y: yN(v) + 4, "text-anchor": "start", fill: cMuted, "font-size": 11 }, svg);
            t.textContent = `${Math.round(v).toLocaleString("fr-FR")}`;
          }
        }
        if (0 >= n0 && 0 <= n1) {
          el("line", { x1: pad.l, x2: W - pad.r, y1: yN(0), y2: yN(0), stroke: cNet, "stroke-dasharray": "5 5", opacity: 0.5 }, svg);
        }
      }
      // Axe des mois
      const every = Math.max(1, Math.ceil(n / (isMobile ? 3 : 8)));
      labels.forEach((lab, i) => {
        if (i !== n - 1 && (i % every !== 0 || n - 1 - i < every * 0.6)) return;
        const t = el("text", { x: x(i), y: H - 8, "text-anchor": i === 0 ? "start" : i === n - 1 ? "end" : "middle", fill: cMuted, "font-size": 11 }, svg);
        t.textContent = lab.slice(0, 7);
      });

      const path = (vals, yf) => {
        let d = "", pen = false;
        vals.forEach((v, i) => {
          if (v === null || Number.isNaN(v)) { pen = false; return; }
          d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${yf(v).toFixed(1)}`;
          pen = true;
        });
        return d;
      };
      el("path", { d: path(market, yM), fill: "none", stroke: cMarket, "stroke-width": 2, "stroke-linejoin": "round" }, svg);
      if (yN) el("path", { d: path(net, yN), fill: "none", stroke: cNet, "stroke-width": 2, "stroke-linejoin": "round" }, svg);
      if (n === 1) el("circle", { cx: x(0), cy: yM(market[0]), r: 4, fill: cMarket }, svg);

      // Point de rentabilité (break-even)
      if (yN && beIdx !== -1 && net[beIdx] !== null) {
        el("circle", { cx: x(beIdx), cy: yN(net[beIdx]), r: 5, fill: cMarket, stroke: cNet, "stroke-width": 1.5 }, svg);
      }

      // Survol : repère vertical + infobulle
      const guide = el("line", { y1: pad.t, y2: pad.t + ih, stroke: cMuted, "stroke-dasharray": "3 4", opacity: 0 }, svg);
      const hit = el("rect", { x: pad.l, y: pad.t, width: iw, height: ih, fill: "transparent" }, svg);
      const move = (ev) => {
        const box = svg.getBoundingClientRect();
        const px = ((ev.clientX - box.left) / box.width) * W;
        const i = Math.max(0, Math.min(n - 1, Math.round(((px - pad.l) / iw) * (n - 1))));
        guide.setAttribute("x1", x(i)); guide.setAttribute("x2", x(i)); guide.setAttribute("opacity", 1);
        let html = `<b>${labels[i].slice(0, 7)}</b><br>Marché : ${fmtEUR(market[i])}/m²`;
        if (showNet && net[i] !== null) html += `<br>Net vendeur : ${fmtEUR(net[i])}/m²`;
        if (i === beIdx) html += `<br>Rentabilité atteinte`;
        tip.innerHTML = html;
        tip.hidden = false;
        tip.style.left = `${(x(i) / W) * box.width}px`;
        tip.style.top = `${Math.max(40, (yM(market[i]) / H) * box.height - 8)}px`;
      };
      const leave = () => { guide.setAttribute("opacity", 0); tip.hidden = true; };
      hit.addEventListener("pointermove", move);
      hit.addEventListener("pointerleave", leave);
    }

    // Légende sous le graphique
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    legend.innerHTML = `<span><i style="background:${cMarket}"></i>Marché (€/m²)</span>` +
      (hasNet ? `<span><i style="background:${cNet}"></i>Net vendeur (€/m²)</span>` : "");
    host.insertAdjacentElement("afterend", legend);

    draw();
    let t; window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(draw, 120); });
    if (toggle) toggle.addEventListener("change", (e) => { state.showNet = e.target.checked; draw(); });
  }

  // -------------- MARKET POINTS (SAVE) --------------
  function initMarketPoints() {
    const mpDate = document.getElementById("mpDate");
    const mpPrice = document.getElementById("mpPrice");
    const mpSave = document.getElementById("mpSave");
    const mpMsg = document.getElementById("mpMsg");
    if (!mpSave || !mpDate || !mpPrice) return;

    const csrftoken = getCookie("csrftoken");

    mpSave.addEventListener("click", async (e) => {
      e.preventDefault();

      const ym = (mpDate.value || "").trim(); // YYYY-MM
      const v = (mpPrice.value || "").trim(); // 6532
      if (!ym || !v) return;

      const isoDate = ymToIsoDate(ym); // YYYY-MM-01
      if (!isoDate) return;

      mpSave.disabled = true;
      if (mpMsg) mpMsg.textContent = "…";

      let postRes;
      try {
        postRes = await fetch(`${base}/market-points/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken || "",
          },
          credentials: "same-origin",
          body: JSON.stringify({ date: isoDate, price_per_sqm: v }),
        });
      } catch (err) {
        console.error("market-points POST failed", err);
        mpSave.disabled = false;
        if (mpMsg) mpMsg.textContent = "Erreur réseau";
        return;
      }

      if (!postRes.ok) {
        const txt = await postRes.text().catch(() => "");
        console.error("market-points POST status", postRes.status, txt);
        mpSave.disabled = false;
        if (mpMsg) mpMsg.textContent = `Erreur (${postRes.status})`;
        return;
      }

      location.reload();
    });
  }

  // GO
  initMarketPoints();
  initChart();
})();
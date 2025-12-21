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

  // ------- Chart -------
  (async function initChart() {
    const canvas = document.getElementById("marketChart");
    if (!canvas) return;

    const seriesUrl = `${base}/market-series/`;
    const beUrl = endDate
      ? `${base}/breakeven/?end=${encodeURIComponent(endDate)}&growth=${encodeURIComponent(growth)}`
      : `${base}/breakeven/?growth=${encodeURIComponent(growth)}`;

    const [seriesRes, beRes] = await Promise.all([
      fetch(seriesUrl, { credentials: "same-origin" }),
      fetch(beUrl, { credentials: "same-origin" }).catch(() => null),
    ]);

    if (!seriesRes.ok) return;
    const seriesData = await seriesRes.json();

    const beData = beRes && beRes.ok ? await beRes.json() : null;
    const beDate = beData?.result?.date || null;

    const labels = (seriesData.series || []).map((p) => p.date);
    const market = (seriesData.series || []).map((p) => p.price_per_sqm);
    const net = (seriesData.series || []).map((p) => p.net_vendeur_per_sqm);

    const netVals = net.filter((v) => v !== null && v !== undefined && !Number.isNaN(v));
    const hasNet = netVals.length > 0;

    let bePoint = null;
    if (beDate && hasNet) {
      const idx = labels.indexOf(beDate);
      if (idx !== -1) {
        const maxNet = Math.max(...netVals);
        bePoint = labels.map((_, i) => (i === idx ? maxNet : null));
      }
    }

    const datasets = [
      { label: "Marché €/m²", data: market, tension: 0.25, pointRadius: 0, borderWidth: 2, yAxisID: "yMarket" },
      { label: "Net vendeur €/m²", data: net, tension: 0.25, pointRadius: 0, borderWidth: 2, yAxisID: "yNet" },
      { label: "Seuil 0 net vendeur", data: labels.map(() => 0), borderDash: [6, 6], borderWidth: 1, pointRadius: 0, yAxisID: "yNet" },
    ];
    if (bePoint) datasets.push({ label: "Break-even", data: bePoint, showLine: false, pointRadius: 5, borderWidth: 0, yAxisID: "yNet" });

    const ctx = canvas.getContext("2d");
    const chart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        plugins: { legend: { display: true } },
        scales: {
          x: { ticks: { maxTicksLimit: 8 } },
          yMarket: { position: "left", ticks: { callback: (v) => v + " €" }, title: { display: true, text: "Marché €/m²" } },
          yNet: {
            position: "right",
            grid: { drawOnChartArea: false },
            ticks: { callback: (v) => v + " €" },
            title: { display: true, text: "Net vendeur €/m²" },
            suggestedMin: -3000,
            suggestedMax: 3000,
          },
        },
      },
    });

    const toggle = document.getElementById("toggleNet");
    if (toggle) {
      toggle.addEventListener("change", (e) => {
        chart.setDatasetVisibility(1, e.target.checked);
        chart.update();
      });
    }
  })();

  // ------- Market points -------
  (async function initMarketPoints() {
    const tbody = document.getElementById("marketPointsBody");
    if (!tbody) return;

    const mpDate = document.getElementById("mpDate");
    const mpPrice = document.getElementById("mpPrice");
    const mpSave = document.getElementById("mpSave");
    const mpMsg = document.getElementById("mpMsg");

    const csrftoken = getCookie("csrftoken");

    async function loadPoints() {
      tbody.innerHTML = `<tr><td colspan="3" class="muted">Chargement…</td></tr>`;
      const res = await fetch(`${base}/market-points/`, { credentials: "same-origin" });
      if (!res.ok) {
        tbody.innerHTML = `<tr><td colspan="3" class="muted">Erreur chargement</td></tr>`;
        return;
      }

      const data = await res.json();
      const points = data.points || data.rows || [];

      if (!points.length) {
        tbody.innerHTML = `<tr><td colspan="3" class="muted">Aucun point marché</td></tr>`;
        return;
      }

      tbody.innerHTML = "";
      points.forEach((p) => {
        const tr = document.createElement("tr");
        const date = p.date || "";
        const ym = date.slice(0, 7);
        const val = p.price_per_sqm === null || p.price_per_sqm === undefined ? "" : Math.round(Number(p.price_per_sqm));

        tr.innerHTML = `
          <td class="muted">${ym}</td>
          <td><input class="mp-input" type="number" step="1" min="0" value="${val}"></td>
          <td style="text-align:right"><button class="btn">Save</button></td>
        `;

        const input = tr.querySelector("input");
        const btn = tr.querySelector("button");

        btn.addEventListener("click", async () => {
          const v = input.value.trim();
          if (!v) return;

          btn.disabled = true;
          btn.textContent = "…";

          const postRes = await fetch(`${base}/market-points/`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken || "" },
            credentials: "same-origin",
            body: JSON.stringify({ date: date, price_per_sqm: v }),
          });

          if (!postRes.ok) {
            btn.disabled = false;
            btn.textContent = "Erreur";
            return;
          }
          location.reload();
        });

        tbody.appendChild(tr);
      });
    }

    async function saveNewPoint() {
      const ym = (mpDate?.value || "").trim();
      const v = (mpPrice?.value || "").trim();
      if (!ym || !v) return;

      const isoDate = ymToIsoDate(ym);
      if (!isoDate) return;

      mpSave.disabled = true;
      if (mpMsg) mpMsg.textContent = "…";

      const postRes = await fetch(`${base}/market-points/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken || "" },
        credentials: "same-origin",
        body: JSON.stringify({ date: isoDate, price_per_sqm: v }),
      });

      if (!postRes.ok) {
        mpSave.disabled = false;
        if (mpMsg) mpMsg.textContent = "Erreur (CSRF ?)";
        return;
      }
      location.reload();
    }

    if (mpSave) mpSave.addEventListener("click", (e) => { e.preventDefault(); saveNewPoint(); });

    await loadPoints();
  })();
})();
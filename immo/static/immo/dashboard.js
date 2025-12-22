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

  // ---------------- CHART ----------------
  async function initChart() {
    const canvas = document.getElementById("marketChart");
    if (!canvas) return;

    const seriesUrl = `${base}/market-series/`;
    const beUrl = endDate
      ? `${base}/breakeven/?end=${encodeURIComponent(endDate)}&growth=${encodeURIComponent(growth)}`
      : `${base}/breakeven/?growth=${encodeURIComponent(growth)}`;

    let seriesRes;
    try {
      seriesRes = await fetch(seriesUrl, { credentials: "same-origin" });
    } catch (e) {
      console.error("market-series fetch failed", e);
      return;
    }
    if (!seriesRes.ok) {
      console.error("market-series status", seriesRes.status);
      return;
    }

    const seriesData = await seriesRes.json();

    let beData = null;
    try {
      const beRes = await fetch(beUrl, { credentials: "same-origin" });
      if (beRes.ok) beData = await beRes.json();
    } catch (_) {}

    const labels = (seriesData.series || []).map((p) => p.date);
    const market = (seriesData.series || []).map((p) => Number(p.price_per_sqm));
    const net = (seriesData.series || []).map((p) =>
      p.net_vendeur_per_sqm === null || p.net_vendeur_per_sqm === undefined
        ? null
        : Number(p.net_vendeur_per_sqm)
    );

    // si ton API renvoie des strings "6532.00", Number() règle ça
    const netVals = net.filter((v) => v !== null && !Number.isNaN(v));
    const hasNet = netVals.length > 0;

    const beDate = beData?.result?.date || null;
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

      const ym = (mpDate.value || "").trim();   // YYYY-MM
      const v = (mpPrice.value || "").trim();   // 6532
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
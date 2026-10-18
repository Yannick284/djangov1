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

  // ---------- Crosshair plugin ----------
  const crosshairPlugin = {
    id: "crosshair",
    afterDraw(chart) {
      const tooltip = chart.tooltip;
      if (!tooltip || !tooltip.getActiveElements) return;
      const actives = tooltip.getActiveElements();
      if (!actives || actives.length === 0) return;

      const { ctx, chartArea } = chart;
      const el = actives[0].element;
      const x = el.x;
      const y = el.y;

      ctx.save();
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "rgba(200,200,200,0.35)";

      // Vertical line
      ctx.beginPath();
      ctx.moveTo(x, chartArea.top);
      ctx.lineTo(x, chartArea.bottom);
      ctx.stroke();

      // Horizontal line (reticule)
      ctx.beginPath();
      ctx.moveTo(chartArea.left, y);
      ctx.lineTo(chartArea.right, y);
      ctx.stroke();

      ctx.restore();
    },
  };

  // Chart.register peut throw si Chart pas encore chargé (rare). On sécurise.
  function safeRegister(plugin) {
    try {
      if (window.Chart && Chart.register) Chart.register(plugin);
    } catch (_) {}
  }

  // ---------------- CHART ----------------
  async function initChart() {
    const canvas = document.getElementById("marketChart");
    if (!canvas || !window.Chart) return;

    safeRegister(crosshairPlugin);

    const isMobile = window.matchMedia("(max-width: 560px)").matches;

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

    const labels = (seriesData.series || []).map((p) => p.date); // "YYYY-MM-01"
    const market = (seriesData.series || []).map((p) => Number(p.price_per_sqm));
    const net = (seriesData.series || []).map((p) =>
      p.net_vendeur_per_sqm === null || p.net_vendeur_per_sqm === undefined
        ? null
        : Number(p.net_vendeur_per_sqm)
    );

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

    const baseLine = {
      tension: 0.25,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 4,
      pointHitRadius: 14,
    };

    const datasets = [
      {
        ...baseLine,
        label: "Marché €/m²",
        data: market,
        yAxisID: "yMarket",
      },
      {
        ...baseLine,
        label: "Net vendeur €/m²",
        data: net,
        yAxisID: "yNet",
      },
      {
        label: "Seuil 0 net vendeur",
        data: labels.map(() => 0),
        borderDash: [6, 6],
        borderWidth: 1,
        pointRadius: 0,
        pointHoverRadius: 0,
        pointHitRadius: 0,
        yAxisID: "yNet",
      },
    ];

    if (bePoint) {
      datasets.push({
        label: "Break-even",
        data: bePoint,
        showLine: false,
        pointRadius: 5,
        pointHoverRadius: 6,
        borderWidth: 0,
        yAxisID: "yNet",
      });
    }

    const ctx = canvas.getContext("2d");

    const chart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,

        // 🔥 accroche / tooltip propre (toutes séries au même x)
        interaction: {
          mode: "index",
          intersect: false,
        },

        plugins: {
          legend: {
            position: "bottom",
            labels: {
              boxWidth: isMobile ? 10 : 14,
              boxHeight: isMobile ? 10 : 14,
              padding: isMobile ? 10 : 16,
              font: { size: isMobile ? 10 : 12 },
              generateLabels(ch) {
                const items = Chart.defaults.plugins.legend.labels.generateLabels(ch);
                return items.map((it) => ({
                  ...it,
                  text: it.text
                    .replace("Marché €/m²", "Marché")
                    .replace("Net vendeur €/m²", "Net vendeur")
                    .replace("Seuil 0 net vendeur", "Seuil 0"),
                }));
              },
            },
          },

          tooltip: {
            enabled: true,
            mode: "index",
            intersect: false,
            callbacks: {
              title: (items) => {
                const d = items?.[0]?.label || "";
                return d ? d.slice(0, 7) : "";
              },
              label: (c) => `${c.dataset.label}: ${shortK(c.parsed.y)} €`,
            },
          },

          // ✅ Zoom/pan si plugin chargé (chartjs-plugin-zoom)
          zoom: window.ChartZoom
            ? {
                pan: {
                  enabled: true,
                  mode: "x",
                  modifierKey: "shift",
                },
                zoom: {
                  wheel: { enabled: true },
                  pinch: { enabled: true },
                  mode: "x",
                },
                limits: {
                  x: { min: 0, max: labels.length - 1 },
                },
              }
            : undefined,
        },

        scales: {
          x: {
            ticks: {
              maxTicksLimit: isMobile ? 3 : 8,
              autoSkip: true,
              maxRotation: 0,
              font: { size: isMobile ? 10 : 12 },
              callback: (val) => {
                const lab = labels?.[val] || "";
                return lab ? lab.slice(0, 7) : "";
              },
            },
          },

          yMarket: {
            position: "left",
            title: { display: !isMobile, text: "Marché €/m²" },
            ticks: {
              maxTicksLimit: isMobile ? 4 : 7,
              font: { size: isMobile ? 10 : 12 },
              callback: (v) => (isMobile ? `${shortK(v)} €` : `${v} €`),
            },
          },

          yNet: {
            position: "right",
            grid: { drawOnChartArea: false },
            title: { display: !isMobile, text: "Net vendeur €/m²" },
            ticks: {
              display: !isMobile,
              callback: (v) => `${v} €`,
            },
            suggestedMin: -3000,
            suggestedMax: 3000,
          },
        },
      },
    });

    // Toggle Net vendeur
    const toggle = document.getElementById("toggleNet");
    if (toggle) {
      if (isMobile) {
        toggle.checked = false;
        chart.setDatasetVisibility(1, false);
        chart.update();
      }
      toggle.addEventListener("change", (e) => {
        chart.setDatasetVisibility(1, e.target.checked);
        chart.update();
      });
    }

    // Reset zoom button (si présent + plugin zoom chargé)
    const resetBtn = document.getElementById("resetZoom");
    if (resetBtn && chart.resetZoom) {
      resetBtn.addEventListener("click", () => chart.resetZoom());
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
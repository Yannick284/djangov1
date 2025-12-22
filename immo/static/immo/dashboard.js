(function () {
  const cfg = window.IMMO_DASHBOARD || {};
  const propId = cfg.propId;
  if (!propId) return;

  const base = `/immo/properties/${propId}`;

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

  // ------- Market points -------
  (async function initMarketPoints() {
    const mpDate = document.getElementById("mpDate");
    const mpPrice = document.getElementById("mpPrice");
    const mpSave = document.getElementById("mpSave");
    const mpMsg = document.getElementById("mpMsg");

    const csrftoken = getCookie("csrftoken");

    async function saveNewPoint() {
      const ym = (mpDate?.value || "").trim();  // "YYYY-MM"
      const v = (mpPrice?.value || "").trim();  // "6532"
      if (!ym || !v) return;

      const isoDate = ymToIsoDate(ym);          // "YYYY-MM-01"
      if (!isoDate) return;

      mpSave.disabled = true;
      if (mpMsg) mpMsg.textContent = "…";

      const postRes = await fetch(`${base}/market-points/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken || "",
        },
        credentials: "same-origin",
        body: JSON.stringify({ date: isoDate, price_per_sqm: v }),
      });

      if (!postRes.ok) {
        mpSave.disabled = false;
        if (mpMsg) mpMsg.textContent = `Erreur (${postRes.status})`;
        return;
      }

      location.reload();
    }

    if (mpSave) {
      mpSave.addEventListener("click", (e) => {
        e.preventDefault();
        saveNewPoint();
      });
    }

    // --- Tableau existant (optionnel) ---
    const tbody = document.getElementById("marketPointsBody");
    if (!tbody) return;

    async function loadPoints() {
      tbody.innerHTML = `<tr><td colspan="3" class="muted">Chargement…</td></tr>`;

      const res = await fetch(`${base}/market-points/`, { credentials: "same-origin" });
      if (!res.ok) {
        tbody.innerHTML = `<tr><td colspan="3" class="muted">Erreur chargement (${res.status})</td></tr>`;
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
        const val =
          p.price_per_sqm === null || p.price_per_sqm === undefined
            ? ""
            : Math.round(Number(p.price_per_sqm));

        tr.innerHTML = `
          <td class="muted">${ym}</td>
          <td><input class="mp-input" type="number" step="1" min="0" value="${val}"></td>
          <td style="text-align:right"><button class="btn" type="button">Save</button></td>
        `;

        const input = tr.querySelector("input");
        const btn = tr.querySelector("button");

        btn.addEventListener("click", async () => {
          const v2 = input.value.trim();
          if (!v2) return;

          btn.disabled = true;
          btn.textContent = "…";

          const postRes = await fetch(`${base}/market-points/`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRFToken": csrftoken || "",
            },
            credentials: "same-origin",
            body: JSON.stringify({ date: date, price_per_sqm: v2 }),
          });

          if (!postRes.ok) {
            btn.disabled = false;
            btn.textContent = `Erreur (${postRes.status})`;
            return;
          }

          location.reload();
        });

        tbody.appendChild(tr);
      });
    }

    await loadPoints();
  })();
})();
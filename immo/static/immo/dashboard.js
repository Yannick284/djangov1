function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return null;
}

// ------- Market points -------


(async function initMarketPoints() {
  const mpDate = document.getElementById("mpDate");
  const mpPrice = document.getElementById("mpPrice");
  const mpSave = document.getElementById("mpSave");
  const mpMsg = document.getElementById("mpMsg");

  const csrftoken = getCookie("csrftoken");

  async function saveNewPoint() {
    const ym = (mpDate?.value || "").trim();   // "YYYY-MM"
    const v = (mpPrice?.value || "").trim();   // number as string
    if (!ym || !v) return;

    const isoDate = ymToIsoDate(ym);           // "YYYY-MM-01"
    if (!isoDate) return;

    if (mpSave) mpSave.disabled = true;
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
      if (mpSave) mpSave.disabled = false;
      if (mpMsg) mpMsg.textContent = `Erreur (${postRes.status})`;
      return;
    }

    location.reload();
  }

  // ✅ Le bouton marche même si tu n'affiches pas le tableau
  if (mpSave) {
    mpSave.addEventListener("click", (e) => {
      e.preventDefault();
      saveNewPoint();
    });
  }

  // --- Partie tableau (optionnelle) ---
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
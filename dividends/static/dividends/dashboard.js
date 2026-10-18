(function () {
  const modal = document.getElementById("dvModal");
  const root = document.querySelector(".hist-card[data-month-api]");
  const list = document.getElementById("dvList");

  if (!modal) {
    console.error("[dividends] Missing #dvModal in template");
    return;
  }
  if (!root) {
    console.error("[dividends] Missing .hist-card[data-month-api] in template");
    return;
  }
  if (!list) {
    console.error("[dividends] Missing #dvList in template");
    return;
  }

  const apiBase = root.dataset.monthApi;
  if (!apiBase) {
    console.error("[dividends] data-month-api is empty");
    return;
  }

  function openModal() {
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  }

  async function fetchMonth(year, month, growth) {
    const url =
      `${apiBase}?y=${encodeURIComponent(year)}` +
      `&m=${encodeURIComponent(month)}` +
      `&g=${encodeURIComponent(growth ?? "0")}`;

    const r = await fetch(url, { credentials: "same-origin" });

    // Important: on lit le body pour logger en cas d'erreur
    const txt = await r.text();

    if (!r.ok) {
      console.error("[dividends] API HTTP", r.status, url, txt);
      throw new Error("HTTP " + r.status);
    }

    let data;
    try {
      data = JSON.parse(txt);
    } catch (e) {
      console.error("[dividends] API returned non-JSON:", url, txt.slice(0, 500));
      throw new Error("Non JSON");
    }
    return data;
  }

  function render(data) {
    if (!data || data.ok !== true) {
      throw new Error((data && data.error) || "API failed");
    }

    const title = document.getElementById("dvTitle");
    if (title) title.textContent = `${data.month}/${data.year} — ${data.total}€`;

    list.innerHTML = "";

    if (!data.events || data.events.length === 0) {
      list.innerHTML = `<div class="dv-empty">Aucun dividende sur ce mois.</div>`;
      return;
    }

    for (const e of data.events) {
      const pay = e.pay_date || "—";
      const ex = e.ex_date || "—";
      const cur = e.currency || "";

      list.insertAdjacentHTML(
        "beforeend",
        `<div class="dv-row">
          <div class="dv-row-top">
            <b>${e.ticker}</b>
            <span class="dv-pill dv-pill-${e.status}">${e.status}</span>
          </div>
          <div class="dv-row-mid">
            <span>${e.amount_per_share} ${cur} / share</span>
            <span>${e.shares} shares</span>
          </div>
          <div class="dv-row-bot">
            <span>ex: ${ex}</span>
            <span>pay: ${pay}</span>
            <b>${e.amount} ${cur}</b>
          </div>
        </div>`
      );
    }
  }

  document.addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".dv-card-btn");
    if (btn) {
      const y = btn.dataset.year;
      const m = btn.dataset.month;
      const g = btn.dataset.growth ?? "0";

      try {
        openModal();
        list.innerHTML = `<div class="dv-loading">Chargement…</div>`;
        const data = await fetchMonth(y, m, g);
        render(data);
      } catch (e) {
        console.error("[dividends] detail modal error:", e);
        list.innerHTML = `<div class="dv-error">Impossible de charger le détail.</div>`;
      }
      return;
    }

    if (ev.target.closest("[data-close]")) {
      closeModal();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.classList.contains("is-open")) {
      closeModal();
    }
  });
})();
// Aperçu Markdown : envoie le texte au serveur, qui le convertit et le nettoie.
(function () {
  var form = document.querySelector("form[data-preview-url]");
  if (!form) return;
  var source = form.querySelector("[data-markdown-source]");
  var preview = form.querySelector("[data-md-preview]");
  var tabs = form.querySelectorAll("[data-md-tab]");
  if (!source || !preview) return;

  function show(mode) {
    tabs.forEach(function (t) {
      if (t.dataset.mdTab === mode) t.setAttribute("aria-current", "true");
      else t.removeAttribute("aria-current");
    });
    source.hidden = mode === "preview";
    preview.hidden = mode !== "preview";
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      if (tab.dataset.mdTab === "write") return show("write");
      preview.textContent = "Chargement…";
      show("preview");
      var token = form.querySelector("[name=csrfmiddlewaretoken]").value;
      var body = new URLSearchParams({ content: source.value });
      fetch(form.dataset.previewUrl, {
        method: "POST",
        headers: { "X-CSRFToken": token },
        body: body,
        credentials: "same-origin",
      })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(function (data) { preview.innerHTML = data.html || "<p>Rien à afficher.</p>"; })
        .catch(function () { preview.textContent = "L'aperçu n'a pas pu être chargé. Réessaie."; });
    });
  });
})();

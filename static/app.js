/* Menu mobile : ouverture, fermeture (bouton, fond, Échap, clic sur un lien),
   et retour du focus. Le panneau est `inert` tant qu'il est fermé. */
(() => {
  const toggle = document.querySelector("[data-nav-toggle]");
  const drawer = document.getElementById("site-drawer");
  const overlay = document.querySelector("[data-nav-overlay]");
  if (!toggle || !drawer || !overlay) return;

  const setOpen = (open, returnFocus = true) => {
    drawer.classList.toggle("is-open", open);
    overlay.classList.toggle("is-open", open);
    document.body.classList.toggle("nav-locked", open);
    toggle.setAttribute("aria-expanded", String(open));
    if (open) {
      drawer.removeAttribute("inert");
      drawer.querySelector("[data-nav-close]")?.focus();
    } else {
      drawer.setAttribute("inert", "");
      if (returnFocus) toggle.focus();
    }
  };

  toggle.addEventListener("click", () => setOpen(!drawer.classList.contains("is-open")));
  overlay.addEventListener("click", () => setOpen(false));
  drawer.querySelector("[data-nav-close]")?.addEventListener("click", () => setOpen(false));
  drawer.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => setOpen(false, false)));

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && drawer.classList.contains("is-open")) setOpen(false);
  });

  // Si on passe en largeur "bureau" menu ouvert, on referme proprement.
  window.matchMedia("(min-width: 860px)").addEventListener("change", (e) => {
    if (e.matches && drawer.classList.contains("is-open")) setOpen(false, false);
  });
})();

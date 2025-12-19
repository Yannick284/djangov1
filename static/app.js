const btn = document.querySelector(".nav-toggle");
const drawer = document.querySelector("#mobile-drawer");
const overlay = document.querySelector(".nav-overlay");

function openNav() {
  document.body.dataset.navOpen = "true";
  btn?.setAttribute("aria-expanded", "true");
  if (drawer) drawer.hidden = false;
  if (overlay) overlay.hidden = false;
}

function closeNav() {
  delete document.body.dataset.navOpen;
  btn?.setAttribute("aria-expanded", "false");
  if (drawer) drawer.hidden = true;
  if (overlay) overlay.hidden = true;
}

btn?.addEventListener("click", () => {
  const isOpen = document.body.dataset.navOpen === "true";
  isOpen ? closeNav() : openNav();
});

overlay?.addEventListener("click", closeNav);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeNav();
});

/* Séparateurs dans le drawer (demandé) */
if (drawer) {
  const links = Array.from(drawer.querySelectorAll("a"));
  links.forEach((a, i) => {
    if (i === links.length - 1) return;
    const sep = document.createElement("div");
    sep.className = "drawer-sep";
    sep.setAttribute("aria-hidden", "true");
    a.insertAdjacentElement("afterend", sep);
  });
}
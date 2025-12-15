const btn = document.querySelector(".nav-toggle");
const drawer = document.querySelector("#mobile-drawer");
const overlay = document.querySelector(".nav-overlay");

function openNav() {
  document.body.dataset.navOpen = "true";
  btn.setAttribute("aria-expanded", "true");
  drawer.hidden = false;
  overlay.hidden = false;
}

function closeNav() {
  delete document.body.dataset.navOpen;
  btn.setAttribute("aria-expanded", "false");
  drawer.hidden = true;
  overlay.hidden = true;
}

btn?.addEventListener("click", () => {
  const isOpen = document.body.dataset.navOpen === "true";
  isOpen ? closeNav() : openNav();
});

overlay?.addEventListener("click", closeNav);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeNav();
  
});
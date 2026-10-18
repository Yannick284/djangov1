/* Atlas : carte à gratter, « Où est-ce ? » et silhouettes.
   Tout se passe dans le navigateur : aucune donnée n'est envoyée au serveur. */
(function () {
  "use strict";

  var root = document.querySelector(".at");
  if (!root) return;

  var NS = "http://www.w3.org/2000/svg";
  var reduceMotion = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  var ROUNDS = 10;
  var FOIL = "#CBD2CE";

  // ---------- Petits outils ----------
  function $(sel, from) { return (from || root).querySelector(sel); }
  function $$(sel, from) { return Array.prototype.slice.call((from || root).querySelectorAll(sel)); }
  function svgEl(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function htmlEl(tag, attrs, text) {
    var n = document.createElement(tag);
    for (var k in attrs || {}) if (Object.prototype.hasOwnProperty.call(attrs, k)) n.setAttribute(k, attrs[k]);
    if (text) n.textContent = text;
    return n;
  }
  function norm(s) { return String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }
  function shuffle(a) {
    a = a.slice();
    for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; }
    return a;
  }
  function store(key, value) {
    try {
      if (arguments.length === 1) { var v = localStorage.getItem(key); return v === null ? null : JSON.parse(v); }
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) { /* stockage indisponible : on continue sans */ }
    return null;
  }
  function plural(n, one, many) { return n + " " + (n > 1 ? many : one); }

  // ---------- État ----------
  var data, W, H;
  var byCode = {};      // code -> entrée
  var els = {};         // code -> éléments SVG
  var order = [];       // codes triés (pour le lien de partage)
  var contColor = {}, contName = {};
  var statesTotal = 0;
  var names = {};       // nom normalisé -> code
  var state = { mode: "scratch", region: "monde", visited: {}, shared: false };
  var game = null;
  var mapSvg, wrap, tip, overlay, dotNodes = [];
  var cur;              // viewBox courant [x, y, w, h]
  var raf = 0;

  var REGION_NAMES = { monde: "Monde", europe: "Europe", afrique: "Afrique", asie: "Asie", "amerique-nord": "Amérique du Nord", "amerique-sud": "Amérique du Sud", oceanie: "Océanie" };

  // ---------- Chargement ----------
  fetch(root.getAttribute("data-world"))
    .then(function (r) { if (!r.ok) throw new Error("http"); return r.json(); })
    .then(init)
    .catch(function () { setStatus("La carte n'a pas pu être chargée. Rechargez la page pour réessayer."); });

  function setStatus(text) {
    var s = $("#at-status");
    s.textContent = text || "";
    s.hidden = !text;
  }

  function init(d) {
    data = d; W = d.w; H = d.h;
    d.continents.forEach(function (c) { contColor[c.id] = c.color; contName[c.id] = c.name; });
    d.countries.forEach(function (c) {
      byCode[c.c] = c;
      names[norm(c.n)] = c.c;
      if (c.s) statesTotal++;
    });
    order = d.countries.map(function (c) { return c.c; }).sort();

    buildMap();
    buildList();
    buildDatalist();
    loadVisited();
    bindUI();
    setStatus("");
    setMode("scratch");
    renderScratch();
  }

  // ---------- Carte ----------
  function buildMap() {
    mapSvg = $("#at-map"); wrap = $("#at-mapwrap"); tip = $("#at-tip");
    mapSvg.setAttribute("viewBox", "0 0 " + W + " " + H);

    var defs = svgEl("defs", {}, mapSvg);
    var pat = svgEl("pattern", { id: "at-foil", width: 3.2, height: 3.2, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, defs);
    svgEl("rect", { width: 3.2, height: 3.2, fill: FOIL }, pat);
    svgEl("line", { x1: 0, y1: 0, x2: 0, y2: 3.2, stroke: "#BDC6C1", "stroke-width": 1.1 }, pat);

    var land = svgEl("g", {}, mapSvg);
    if (data.bg) svgEl("path", { d: data.bg, class: "bg" }, land);

    // Les grands pays d'abord : les petits restent cliquables par-dessus.
    var shapes = data.countries.filter(function (c) { return c.d; }).sort(function (a, b) { return b.a - a.a; });
    shapes.forEach(function (c) {
      var p = svgEl("path", { d: c.d, class: "ctry" + (c.s ? "" : " terr"), "data-code": c.c }, land);
      p.style.setProperty("--c", contColor[c.k]);
      (els[c.c] = els[c.c] || []).push(p);
    });
    data.countries.filter(function (c) { return c.dot; }).forEach(function (c) {
      var n = svgEl("circle", { cx: c.dot[0], cy: c.dot[1], r: 2.6, class: "ctry dot", "data-code": c.c }, land);
      n.style.setProperty("--c", contColor[c.k]);
      (els[c.c] = els[c.c] || []).push(n);
      dotNodes.push(n);
    });
    overlay = svgEl("g", { id: "at-overlay" }, mapSvg);
    cur = [0, 0, W, H];
  }

  function clampVB(v) {
    var w = Math.min(W, Math.max(W / 14, v[2]));
    var h = w * H / W;
    return [Math.min(W - w, Math.max(0, v[0])), Math.min(H - h, Math.max(0, v[1])), w, h];
  }
  function setVB(v) {
    v = clampVB(v); cur = v;
    mapSvg.setAttribute("viewBox", v.map(function (n) { return Math.round(n * 100) / 100; }).join(" "));
    var k = v[2] / W;
    dotNodes.forEach(function (n) { n.setAttribute("r", (2.6 * Math.max(k, 0.12)).toFixed(2)); });
    var zoomed = v[2] < W * 0.98;
    mapSvg.classList.toggle("is-zoomed", zoomed);
    mapSvg.style.touchAction = zoomed ? "none" : "pan-y";
  }
  function animateTo(target, ms) {
    target = clampVB(target);
    cancelAnimationFrame(raf);
    if (reduceMotion || !ms) { setVB(target); return; }
    var from = cur.slice(), t0 = performance.now();
    (function step(now) {
      var t = Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - t, 3);
      setVB(from.map(function (f, i) { return f + (target[i] - f) * e; }));
      if (t < 1) raf = requestAnimationFrame(step);
    })(t0);
  }
  function zoomAt(factor, cx, cy) {
    var rect = mapSvg.getBoundingClientRect();
    var fx = cur[0] + ((cx === undefined ? rect.left + rect.width / 2 : cx) - rect.left) / rect.width * cur[2];
    var fy = cur[1] + ((cy === undefined ? rect.top + rect.height / 2 : cy) - rect.top) / rect.height * cur[3];
    var nw = Math.min(W, Math.max(W / 14, cur[2] * factor)), r = nw / cur[2];
    if (state.mode === "scratch") markRegion(null);
    animateTo([fx - (fx - cur[0]) * r, fy - (fy - cur[1]) * r, nw, nw * H / W], 180);
  }
  function focusOn(code) {
    var c = byCode[code]; var m = c && (c.m || (c.dot && [c.dot[0], c.dot[1], 4]));
    if (!m) return;
    var w = Math.min(W, Math.max(m[2] * 6, 90));
    if (state.mode === "scratch") markRegion(null);
    animateTo([m[0] - w / 2, m[1] - w * H / W / 2, w, w * H / W], 450);
  }
  function markRegion(id) {
    $$("[data-region]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-region") === id)); });
  }
  function setRegion(id) {
    state.region = id;
    markRegion(id);
    if (state.mode !== "shape" && data) animateTo(data.regions[id] || [0, 0, W, H], 500);
    if (state.mode !== "scratch") resetGame();
  }

  // Glisser pour déplacer (quand la carte est zoomée)
  var drag = null, suppressClick = false;
  function bindMapEvents() {
    mapSvg.addEventListener("pointerdown", function (e) {
      if (e.button !== 0 || cur[2] >= W * 0.98) return;
      drag = { x: e.clientX, y: e.clientY, vb: cur.slice(), moved: false, rect: mapSvg.getBoundingClientRect() };
      window.addEventListener("pointermove", onDrag);
      window.addEventListener("pointerup", endDrag);
      window.addEventListener("pointercancel", endDrag);
    });
    mapSvg.addEventListener("click", function (e) {
      if (suppressClick) { suppressClick = false; return; }
      var n = e.target.closest && e.target.closest(".ctry");
      if (n) onCountry(n.getAttribute("data-code"));
    });
    mapSvg.addEventListener("pointermove", onHover);
    mapSvg.addEventListener("pointerleave", function () { tip.hidden = true; });
    mapSvg.addEventListener("wheel", function (e) {
      if (!(e.ctrlKey || e.metaKey)) return;      // la molette seule fait défiler la page
      e.preventDefault();
      zoomAt(e.deltaY < 0 ? 0.8 : 1.25, e.clientX, e.clientY);
    }, { passive: false });
    $$("[data-zoom]").forEach(function (b) {
      b.addEventListener("click", function () { zoomAt(b.getAttribute("data-zoom") === "in" ? 0.6 : 1.7); });
    });
  }
  function onDrag(e) {
    if (!drag) return;
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 5) return;
    if (!drag.moved) { drag.moved = true; mapSvg.classList.add("is-dragging"); tip.hidden = true; if (state.mode === "scratch") markRegion(null); }
    cancelAnimationFrame(raf);
    var u = drag.vb[2] / drag.rect.width;
    setVB([drag.vb[0] - dx * u, drag.vb[1] - dy * u, drag.vb[2], drag.vb[3]]);
  }
  function endDrag() {
    if (drag && drag.moved) suppressClick = true;
    drag = null;
    mapSvg.classList.remove("is-dragging");
    window.removeEventListener("pointermove", onDrag);
    window.removeEventListener("pointerup", endDrag);
    window.removeEventListener("pointercancel", endDrag);
    setTimeout(function () { suppressClick = false; }, 0);
  }
  function onHover(e) {
    if (state.mode !== "scratch" || e.pointerType !== "mouse" || drag) { tip.hidden = true; return; }
    var n = e.target.closest && e.target.closest(".ctry");
    if (!n) { tip.hidden = true; return; }
    var c = byCode[n.getAttribute("data-code")];
    tip.textContent = c.n;
    if (state.visited[c.c]) tip.appendChild(htmlEl("small", {}, "visité"));
    else if (!c.s) tip.appendChild(htmlEl("small", {}, "territoire"));
    var r = wrap.getBoundingClientRect();
    tip.style.left = (e.clientX - r.left) + "px";
    tip.style.top = (e.clientY - r.top) + "px";
    tip.hidden = false;
  }

  // ---------- Pays visités ----------
  function encode() {
    var n = BigInt(0);
    order.forEach(function (code, i) { if (state.visited[code]) n |= BigInt(1) << BigInt(i); });
    return n.toString(36);
  }
  function decode(str) {
    var n = BigInt(0), v = {};
    for (var i = 0; i < str.length; i++) { var d = parseInt(str[i], 36); if (isNaN(d)) return null; n = n * BigInt(36) + BigInt(d); }
    order.forEach(function (code, i) { if ((n >> BigInt(i)) & BigInt(1)) v[code] = true; });
    return v;
  }
  function hashValue() { var m = /^#v1\.([0-9a-z]{1,80})$/.exec(location.hash); return m ? m[1] : null; }

  function loadVisited() {
    var h = hashValue(), shared = null;
    if (h && typeof BigInt === "function") { try { shared = decode(h); } catch (e) { shared = null; } }
    if (shared) { state.visited = shared; state.shared = true; }
    else { state.visited = localVisited(); state.shared = false; }
    paintAll();
  }
  function localVisited() {
    var saved = store("atlas:visited"), v = {};
    (Array.isArray(saved) ? saved : []).forEach(function (code) { if (byCode[code]) v[code] = true; });
    return v;
  }
  function persist() {
    if (state.shared) {
      try { history.replaceState(null, "", location.pathname + location.search + "#v1." + encode()); } catch (e) { /* ignoré */ }
    } else {
      store("atlas:visited", Object.keys(state.visited));
    }
  }
  function paintAll() {
    Object.keys(els).forEach(function (code) { paintCountry(code); });
  }
  function paintCountry(code) {
    var on = !!state.visited[code];
    (els[code] || []).forEach(function (n) { n.classList.toggle("on", on); });
  }
  function setVisited(code, on, announce) {
    if (!byCode[code]) return;
    if (on) state.visited[code] = true; else delete state.visited[code];
    paintCountry(code);
    (els[code] || []).forEach(function (n) {
      n.classList.remove("pop"); void n.getBoundingClientRect(); n.classList.add("pop");
      n.addEventListener("animationend", function h() { n.classList.remove("pop"); n.removeEventListener("animationend", h); });
    });
    persist();
    renderScratch();
    if (announce) {
      var c = byCode[code], t = counts();
      $("#at-caption").textContent = c.n + (on ? " ajouté" : " retiré") + (c.s ? " · " + plural(t.states, "pays", "pays") : " (territoire)");
    }
  }

  function counts() {
    var per = {}, states = 0, terr = 0;
    data.continents.forEach(function (c) { per[c.id] = { v: 0, t: 0 }; });
    data.countries.forEach(function (c) {
      if (c.s) { per[c.k].t++; if (state.visited[c.c]) { per[c.k].v++; states++; } }
      else if (state.visited[c.c]) terr++;
    });
    return { per: per, states: states, terr: terr, continents: data.continents.filter(function (c) { return per[c.id].v > 0; }).length };
  }

  function renderScratch() {
    var t = counts();
    $("#at-n").textContent = t.states;
    var pct = Math.round(t.states / statesTotal * 100);
    $("#at-sub").textContent = "sur " + statesTotal + ", soit " + pct + " % du monde" + (t.terr ? " · + " + plural(t.terr, "territoire", "territoires") : "");
    var bars = $("#at-bars");
    if (!bars.children.length) {
      data.continents.forEach(function (c) {
        var li = htmlEl("li", { "data-cont": c.id });
        li.style.setProperty("--c", c.color);
        li.appendChild(htmlEl("span", {}, c.name));
        var track = htmlEl("span", { class: "track" }); track.appendChild(htmlEl("span", { class: "fill" })); li.appendChild(track);
        li.appendChild(htmlEl("b", {}));
        bars.appendChild(li);
      });
    }
    data.continents.forEach(function (c) {
      var li = $('[data-cont="' + c.id + '"]', bars), p = t.per[c.id];
      $(".fill", li).style.width = (p.t ? p.v / p.t * 100 : 0) + "%";
      $("b", li).textContent = p.v + "/" + p.t;
      var sum = $('[data-sum="' + c.id + '"]');
      if (sum) sum.textContent = p.v + "/" + p.t;
    });
    var tsum = $('[data-sum="territoires"]');
    if (tsum) tsum.textContent = String(t.terr);
    $$(".at-checks input").forEach(function (cb) { cb.checked = !!state.visited[cb.value]; });
    $("#at-shared").hidden = !(state.shared && state.mode === "scratch");
  }

  function buildList() {
    var host = $("#at-list");
    function group(id, title, color, items) {
      var det = htmlEl("details", { class: "at-cont" });
      var sum = htmlEl("summary");
      var sw = htmlEl("span", { class: "sw" }); sum.appendChild(sw);
      sum.appendChild(htmlEl("span", {}, title));
      sum.appendChild(htmlEl("small", { "data-sum": id }));
      det.style.setProperty("--c", color);
      det.appendChild(sum);
      var ul = htmlEl("ul", { class: "at-checks" });
      items.forEach(function (c) {
        var li = htmlEl("li"), lab = htmlEl("label"), cb = htmlEl("input", { type: "checkbox", value: c.c });
        cb.addEventListener("change", function () { setVisited(c.c, cb.checked, true); });
        lab.appendChild(cb); lab.appendChild(document.createTextNode(c.n));
        li.appendChild(lab); ul.appendChild(li);
      });
      det.appendChild(ul); host.appendChild(det);
    }
    data.continents.forEach(function (k) {
      group(k.id, k.name, k.color, data.countries.filter(function (c) { return c.s && c.k === k.id; }));
    });
    group("territoires", "Territoires et régions", "#9AAEA5", data.countries.filter(function (c) { return !c.s; }));
  }
  function buildDatalist() {
    var dl = $("#at-names");
    data.countries.forEach(function (c) { dl.appendChild(htmlEl("option", { value: c.n })); });
  }

  function onSearch(commit) {
    var input = $("#at-search"), code = names[norm(input.value)];
    if (!code) { if (commit && input.value.trim()) $("#at-caption").textContent = "Pays introuvable : vérifiez l'orthographe ou choisissez dans la liste."; return; }
    setVisited(code, true, true);
    focusOn(code);
    input.value = "";
  }

  // ---------- Actions : lien, image, effacement ----------
  function flash(text) {
    var p = $("#at-copied"); p.textContent = text; p.hidden = false;
    clearTimeout(flash.t); flash.t = setTimeout(function () { p.hidden = true; }, 2600);
  }
  function copyText(text, done) {
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () { window.prompt("Copiez ce texte :", text); });
    else window.prompt("Copiez ce texte :", text);
  }
  function shareUrl() { return location.origin + location.pathname + "#v1." + encode(); }

  function exportPNG() {
    var t = counts(), CW = 1600, pad = 40, scale = (CW - 2 * pad) / W, mapH = Math.round(H * scale), top = 150, bottom = 80;
    var c = document.createElement("canvas"); c.width = CW; c.height = top + mapH + bottom;
    var g = c.getContext("2d");
    g.fillStyle = "#EDF0EE"; g.fillRect(0, 0, c.width, c.height);
    g.fillStyle = "#12202B"; g.font = "500 54px Newsreader, Georgia, serif"; g.textBaseline = "alphabetic";
    g.fillText("Ma carte du monde", pad, 78);
    g.fillStyle = "#4B5B64"; g.font = "400 26px 'IBM Plex Sans', system-ui, sans-serif";
    g.fillText(plural(t.states, "pays", "pays") + " · " + Math.round(t.states / statesTotal * 100) + " % du monde · " + t.continents + " continents sur 6", pad, 122);
    g.fillStyle = "#F6F8F7"; g.fillRect(pad, top, CW - 2 * pad, mapH);
    g.save(); g.beginPath(); g.rect(pad, top, CW - 2 * pad, mapH); g.clip();
    g.translate(pad, top); g.scale(scale, scale);
    g.lineJoin = "round"; g.lineWidth = 1.1 / scale; g.strokeStyle = "#F6F8F7";
    if (data.bg) { g.globalAlpha = 0.6; g.fillStyle = FOIL; g.fill(new Path2D(data.bg)); g.globalAlpha = 1; }
    data.countries.filter(function (x) { return x.d; }).sort(function (a, b) { return b.a - a.a; }).forEach(function (x) {
      var p = new Path2D(x.d);
      g.fillStyle = state.visited[x.c] ? contColor[x.k] : FOIL;
      g.fill(p); g.stroke(p);
    });
    data.countries.filter(function (x) { return x.dot; }).forEach(function (x) {
      g.beginPath(); g.arc(x.dot[0], x.dot[1], 2.6, 0, Math.PI * 2);
      g.fillStyle = state.visited[x.c] ? contColor[x.k] : FOIL; g.fill(); g.stroke();
    });
    g.restore();
    var lx = pad, ly = top + mapH + 48;
    g.font = "400 22px 'IBM Plex Sans', system-ui, sans-serif"; g.textAlign = "left";
    data.continents.forEach(function (k) {
      g.fillStyle = k.color; g.fillRect(lx, ly - 16, 18, 18);
      g.fillStyle = "#4B5B64"; g.fillText(k.name, lx + 26, ly);
      lx += 26 + g.measureText(k.name).width + 28;
    });
    g.textAlign = "right"; g.fillText(location.host + "/atlas/", CW - pad, ly);
    c.toBlob(function (blob) {
      if (!blob) { flash("L'image n'a pas pu être créée."); return; }
      var url = URL.createObjectURL(blob), a = document.createElement("a");
      a.href = url; a.download = "ma-carte-du-monde.png"; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
      flash("Image enregistrée.");
    }, "image/png");
  }

  // ---------- Modes ----------
  var TAB_ORDER = ["scratch", "where", "shape"];
  function setMode(mode) {
    state.mode = mode;
    root.setAttribute("data-mode", mode);
    $$(".at-tab").forEach(function (t) {
      var on = t.getAttribute("data-mode") === mode;
      t.setAttribute("aria-selected", String(on)); t.tabIndex = on ? 0 : -1;
    });
    $("#at-stage").setAttribute("aria-labelledby", "tab-" + mode);
    $$("[data-modes]").forEach(function (n) {
      if (n.id === "at-shared" || n.id === "at-hud") return;
      n.hidden = n.getAttribute("data-modes").split(" ").indexOf(mode) < 0;
    });
    $("#at-hud").hidden = mode === "scratch";
    $("#at-shared").hidden = !(state.shared && mode === "scratch");
    $("#at-zonelabel").textContent = mode === "scratch" ? "Zoom" : "Zone de jeu";
    tip.hidden = true;
    resetGame();
    markRegion(state.region);
    if (mode !== "shape") animateTo(data.regions[state.region] || [0, 0, W, H], 0);
  }

  // ---------- Jeux ----------
  function hudSection(name) {
    $$("[data-hud]").forEach(function (s) { s.hidden = s.getAttribute("data-hud") !== name; });
  }
  function bestKey() { return "atlas:best:" + state.mode + ":" + state.region; }
  function clearReveal() {
    $$(".ctry.ok, .ctry.ko", mapSvg).forEach(function (n) { n.classList.remove("ok", "ko"); });
    while (overlay.firstChild) overlay.removeChild(overlay.firstChild);
  }
  function resetGame() {
    game = null;
    if (!data) return;
    clearReveal();
    if (state.mode === "scratch") return;
    var zone = REGION_NAMES[state.region];
    var best = store(bestKey());
    var n = Math.min(ROUNDS, poolFor().length);
    $("[data-lead]").textContent = state.mode === "where"
      ? n + " pays à retrouver sur la carte (" + zone + "). Cliquez sur le bon pays, sans chrono."
      : n + " silhouettes à reconnaître (" + zone + "). Quatre choix à chaque fois.";
    $("[data-best]").textContent = best ? "Meilleur score dans cette zone : " + best.score + " / " + best.of : "Pas encore de score dans cette zone.";
    hudSection("intro");
  }
  function poolFor() {
    return data.countries.filter(function (c) {
      return c.g && (state.mode !== "shape" || c.sil) && (state.region === "monde" || c.k === state.region);
    });
  }
  function startGame() {
    var pool = shuffle(poolFor());
    if (pool.length < 2) { $("[data-lead]").textContent = "Pas assez de pays dans cette zone."; return; }
    game = { kind: state.mode, qs: pool.slice(0, Math.min(ROUNDS, pool.length)), i: 0, score: 0, streak: 0, bestStreak: 0, answered: false, zone: state.region };
    hudSection("play");
    nextQuestion();
  }
  function nextQuestion() {
    clearReveal();
    game.answered = false;
    var c = game.qs[game.i], q = $("[data-question]"), sil = $("[data-sil]"), ch = $("[data-choices]");
    $("[data-feedback]").textContent = ""; $("[data-feedback]").className = "at-feedback";
    $("[data-next]").hidden = true; $("[data-skip]").hidden = false;
    updateStats();
    if (game.kind === "where") {
      q.textContent = ""; q.appendChild(document.createTextNode("Cliquez sur : ")); q.appendChild(htmlEl("b", {}, c.n));
      sil.setAttribute("hidden", ""); ch.hidden = true;
      return;
    }
    q.textContent = "Quel est ce pays ?";
    sil.removeAttribute("hidden"); sil.setAttribute("class", "at-sil"); $("path", sil).setAttribute("d", c.sil);
    var same = poolFor().filter(function (x) { return x.k === c.k && x.c !== c.c; });
    var others = shuffle(same).slice(0, 3);
    if (others.length < 3) {
      var more = shuffle(data.countries.filter(function (x) { return x.g && x.sil && x.c !== c.c && others.indexOf(x) < 0; }));
      others = others.concat(more.slice(0, 3 - others.length));
    }
    var options = shuffle([c].concat(others));
    ch.textContent = ""; ch.hidden = false;
    options.forEach(function (o, idx) {
      var b = htmlEl("button", { type: "button", class: "ui-btn at-choice", "data-code": o.c });
      b.appendChild(htmlEl("kbd", {}, String(idx + 1))); b.appendChild(document.createTextNode(o.n));
      b.addEventListener("click", function () { answerShape(o.c); });
      ch.appendChild(b);
    });
  }
  function updateStats() {
    $("[data-count]").textContent = "Question " + (game.i + 1) + " / " + game.qs.length;
    $("[data-score]").textContent = plural(game.score, "bonne réponse", "bonnes réponses");
    $("[data-streak]").textContent = game.streak > 1 ? "Série de " + game.streak : "";
  }
  function showRing(code) {
    var c = byCode[code], m = c.m || (c.dot && [c.dot[0], c.dot[1], 3]);
    if (!m || m[2] > 60) return;
    var k = cur[2] / W;
    svgEl("circle", { class: "at-ring", cx: m[0], cy: m[1], r: Math.max(m[2] * 1.1 + 5 * k, 9 * k) }, overlay);
  }
  function settle(ok, correctName, extra) {
    game.answered = true;
    if (ok) { game.score++; game.streak++; game.bestStreak = Math.max(game.bestStreak, game.streak); }
    else game.streak = 0;
    var f = $("[data-feedback]");
    f.className = "at-feedback " + (ok ? "ok" : "ko");
    f.textContent = ok ? "Bravo, c'est bien " + correctName + "." : (extra || "Raté") + " La réponse : " + correctName + ".";
    $("[data-skip]").hidden = true;
    var next = $("[data-next]"); next.hidden = false;
    next.textContent = game.i + 1 >= game.qs.length ? "Voir mon score" : "Suivant";
    next.focus({ preventScroll: true });
    updateStats();
  }
  function onCountry(code) {
    if (state.mode === "scratch") { setVisited(code, !state.visited[code], true); return; }
    if (state.mode === "where" && game && !game.answered) {
      var target = game.qs[game.i], ok = code === target.c;
      (els[code] || []).forEach(function (n) { n.classList.add(ok ? "ok" : "ko"); });
      if (!ok) { (els[target.c] || []).forEach(function (n) { n.classList.add("ok"); }); showRing(target.c); }
      settle(ok, target.n, ok ? "" : "Vous avez cliqué sur " + byCode[code].n + ".");
    }
  }
  function answerShape(code) {
    if (!game || game.kind !== "shape" || game.answered) return;
    var target = game.qs[game.i], ok = code === target.c;
    $$(".at-choice").forEach(function (b) {
      b.disabled = true;
      if (b.getAttribute("data-code") === target.c) b.classList.add("ok");
      else if (b.getAttribute("data-code") === code) b.classList.add("ko");
    });
    $("[data-sil]").classList.add(ok ? "ok" : "ko");
    settle(ok, target.n, "Raté.");
  }
  function skip() {
    if (!game || game.answered) return;
    var target = game.qs[game.i];
    if (game.kind === "where") { (els[target.c] || []).forEach(function (n) { n.classList.add("ok"); }); showRing(target.c); }
    else $$(".at-choice").forEach(function (b) { b.disabled = true; if (b.getAttribute("data-code") === target.c) b.classList.add("ok"); });
    settle(false, target.n, "Passé.");
  }
  function advance() {
    if (!game || !game.answered) return;
    game.i++;
    if (game.i >= game.qs.length) finish(); else nextQuestion();
  }
  function finish() {
    clearReveal();
    var n = game.qs.length, s = game.score, ratio = s / n;
    var key = "atlas:best:" + game.kind + ":" + game.zone, prev = store(key), record = !prev || s > prev.score;
    if (record) store(key, { score: s, of: n });
    $("[data-endscore]").textContent = s + " / " + n;
    $("[data-endmsg]").textContent = ratio >= 0.9 ? "Un vrai globe-trotter." : ratio >= 0.6 ? "Solide : la carte n'a plus beaucoup de secrets." : ratio >= 0.3 ? "Pas mal, il reste de quoi explorer." : "Cap sur l'atlas : on retente ?";
    var best = record ? { score: s, of: n } : prev;
    $("[data-endbest]").textContent = (record && prev ? "Nouveau record. " : "") + "Meilleur score dans cette zone : " + best.score + " / " + best.of + (game.bestStreak > 1 ? " · meilleure série : " + game.bestStreak : "");
    hudSection("end");
  }
  function copyScore() {
    var label = game ? (game.kind === "where" ? "Où est-ce ?" : "Silhouettes") : "";
    var text = "Atlas · " + label + " · " + REGION_NAMES[game.zone] + " : " + game.score + "/" + game.qs.length + " — " + location.origin + location.pathname;
    copyText(text, function () { var c = $("[data-copied]"); c.hidden = false; setTimeout(function () { c.hidden = true; }, 2200); });
  }

  // ---------- Liaisons ----------
  function bindUI() {
    bindMapEvents();
    setVB([0, 0, W, H]);

    $$(".at-tab").forEach(function (t) {
      t.addEventListener("click", function () { setMode(t.getAttribute("data-mode")); });
      t.addEventListener("keydown", function (e) {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        var i = TAB_ORDER.indexOf(state.mode) + (e.key === "ArrowRight" ? 1 : -1);
        i = (i + TAB_ORDER.length) % TAB_ORDER.length;
        setMode(TAB_ORDER[i]); $("#tab-" + TAB_ORDER[i]).focus();
      });
    });
    $$("[data-region]").forEach(function (b) { b.addEventListener("click", function () { setRegion(b.getAttribute("data-region")); }); });

    $("[data-start]").addEventListener("click", startGame);
    $("[data-restart]").addEventListener("click", startGame);
    $("[data-next]").addEventListener("click", advance);
    $("[data-skip]").addEventListener("click", skip);
    $("[data-copyscore]").addEventListener("click", copyScore);
    document.addEventListener("keydown", function (e) {
      if (!game || e.altKey || e.ctrlKey || e.metaKey) return;
      if (game.kind === "shape" && !game.answered && /^[1-4]$/.test(e.key)) {
        var b = $$(".at-choice")[Number(e.key) - 1]; if (b) answerShape(b.getAttribute("data-code"));
      }
    });

    var search = $("#at-search");
    search.addEventListener("change", function () { onSearch(true); });
    search.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); onSearch(true); } });
    search.addEventListener("input", function (e) { if (!e.inputType || e.inputType === "insertReplacementText") onSearch(false); });

    $("#at-copy").addEventListener("click", function () { copyText(shareUrl(), function () { flash("Lien copié : il contient votre carte."); }); });
    $("#at-png").addEventListener("click", exportPNG);
    var reset = $("#at-reset"), confirmTimer;
    reset.addEventListener("click", function () {
      if (reset.getAttribute("data-confirm") !== "1") {
        reset.setAttribute("data-confirm", "1"); reset.textContent = "Confirmer l'effacement";
        confirmTimer = setTimeout(function () { reset.removeAttribute("data-confirm"); reset.textContent = "Tout effacer"; }, 4000);
        return;
      }
      clearTimeout(confirmTimer); reset.removeAttribute("data-confirm"); reset.textContent = "Tout effacer";
      state.visited = {}; paintAll(); persist(); renderScratch();
      $("#at-caption").textContent = "Carte effacée.";
    });

    $$("[data-shared]").forEach(function (b) {
      b.addEventListener("click", function () {
        if (b.getAttribute("data-shared") === "back") state.visited = localVisited();
        state.shared = false; paintAll(); persist();
        try { history.replaceState(null, "", location.pathname + location.search); } catch (e) { /* ignoré */ }
        renderScratch();
      });
    });

    window.addEventListener("hashchange", function () {
      if (hashValue() && state.mode === "scratch") { loadVisited(); renderScratch(); }
    });
  }
})();

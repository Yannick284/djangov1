import fs from "node:fs";
import { createRequire } from "node:module";
import * as topo from "topojson-client";
import { presimplify, simplify, sphericalTriangleArea } from "topojson-simplify";
import { geoPath, geoCentroid, geoArea, geoAzimuthalEqualArea, geoNaturalEarth1 } from "d3-geo";

const require = createRequire(import.meta.url);
const countriesInfo = require("world-countries");
const raw = JSON.parse(fs.readFileSync("node_modules/world-atlas/countries-50m.json", "utf8"));
const MAP_WEIGHT = Number(process.env.MAP_WEIGHT || 6e-6);   // carte : ~0,3 px d'écart
const SIL_WEIGHT = Number(process.env.SIL_WEIGHT || 4e-7);   // silhouettes : plus de détail
const lighten = (w) => topo.feature(simplify(presimplify(structuredClone(raw), sphericalTriangleArea), w), raw.objects.countries).features;
const features = lighten(MAP_WEIGHT);
const silFeatures = new Map(lighten(SIL_WEIGHT).map((f, i) => [f.id === undefined ? "x" + i : String(f.id) + "|" + f.properties.name, f]));

const W = 1000;
const CONTINENTS = [
  { id: "europe", name: "Europe", color: "#4C5BA8" },
  { id: "afrique", name: "Afrique", color: "#E0A526" },
  { id: "asie", name: "Asie", color: "#C8553D" },
  { id: "amerique-nord", name: "Amérique du Nord", color: "#1F8A70" },
  { id: "amerique-sud", name: "Amérique du Sud", color: "#8A5FB0" },
  { id: "oceanie", name: "Océanie", color: "#3FA9C9" },
];
const continentOf = (c) => {
  if (c.region === "Europe") return "europe";
  if (c.region === "Africa") return "afrique";
  if (c.region === "Asia") return "asie";
  if (c.region === "Oceania") return "oceanie";
  if (c.region === "Americas") return c.subregion === "South America" ? "amerique-sud" : "amerique-nord";
  return null; // Antarctique
};

// --- Projection ajustée au monde habité (sans l'Antarctique)
const proj = geoNaturalEarth1();
const frame = { type: "MultiPoint", coordinates: [[-180, 0], [180, 0], [0, 84], [0, -58]] };
proj.fitExtent([[2, 2], [W - 2, 1000]], frame);
const [[x0, y0], [x1, y1]] = geoPath(proj).bounds(frame);
const H = Math.ceil(y1 - y0) + 4;
proj.fitExtent([[2, 2], [W - 2, H - 2]], frame);
const path = geoPath(proj).digits(1);

// --- Cas particuliers : formes sans id, rattachées à un pays voisin
const ALIAS = { Somaliland: "SOM", Kosovo: "UNK", "N. Cyprus": "CYP" };
const BACKGROUND = new Set(["Indian Ocean Ter.", "Siachen Glacier"]);
const EXTRA_STATES = new Set(["PSE", "TWN", "UNK"]); // comptés comme « pays » avec les 194 États indépendants

const infoByCcn3 = new Map(countriesInfo.filter((c) => c.ccn3).map((c) => [c.ccn3, c]));
const infoByCca3 = new Map(countriesInfo.map((c) => [c.cca3, c]));

const groups = new Map(); // cca3 -> [features]
const bg = [];
for (const f of features) {
  let info = f.id !== undefined ? infoByCcn3.get(String(f.id)) : null;
  if (!info && f.properties.name in ALIAS) info = infoByCca3.get(ALIAS[f.properties.name]);
  if (!info || BACKGROUND.has(f.properties.name) || info.region === "Antarctic") {
    if (info?.region !== "Antarctic" && f.properties.name !== "Antarctica") bg.push(f);
    continue;
  }
  if (!groups.has(info.cca3)) groups.set(info.cca3, []);
  groups.get(info.cca3).push(f);
}

const detailed = (feats) => feats.map((f) => silFeatures.get(f.id === undefined ? null : String(f.id) + "|" + f.properties.name) || f);
const polysOf = (feats) => feats.flatMap((f) => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates));

// Silhouette : le plus grand morceau + ses voisins proches, dans une projection locale
function silhouette(feats) {
  const polys = polysOf(feats).map((coordinates) => {
    const g = { type: "Polygon", coordinates };
    return { g, area: geoArea(g), c: geoCentroid(g) };
  });
  const main = polys.reduce((a, b) => (b.area > a.area ? b : a));
  const dist = (a, b) => {
    const dx = Math.abs(a[0] - b[0]); const dl = Math.min(dx, 360 - dx);
    return Math.hypot(dl, a[1] - b[1]);
  };
  const keep = polys.filter((p) => p === main || (p.area >= main.area * 0.02 && dist(p.c, main.c) < 35));
  const geom = { type: "MultiPolygon", coordinates: keep.map((p) => p.g.coordinates) };
  const local = geoAzimuthalEqualArea().rotate([-main.c[0], -main.c[1]]);
  local.fitExtent([[6, 6], [194, 194]], geom);
  return geoPath(local).digits(0)(geom);
}

// Plus grand morceau d'un tracé projeté : centre et rayon [cx, cy, r]
function mainMark(d) {
  let best = null;
  for (const sub of d.split("M").filter(Boolean)) {
    const pts = sub.replace(/Z/g, "").split("L").map((p) => p.split(",").map(Number)).filter((p) => p.length === 2 && !p.some(Number.isNaN));
    if (pts.length < 3) continue;
    let a = 0;
    for (let i = 0; i < pts.length; i++) { const [x1, y1] = pts[i], [x2, y2] = pts[(i + 1) % pts.length]; a += x1 * y2 - x2 * y1; }
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const box = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    if (!best || Math.abs(a) > best.a) best = { a: Math.abs(a), box };
  }
  if (!best) return undefined;
  const [x0, y0, x1, y1] = best.box;
  return [Math.round((x0 + x1) * 5) / 10, Math.round((y0 + y1) * 5) / 10, Math.round(Math.max(x1 - x0, y1 - y0) * 5) / 10];
}

const out = [];
for (const info of countriesInfo) {
  const feats = groups.get(info.cca3) || [];
  const isState = info.independent === true || EXTRA_STATES.has(info.cca3);
  const k = continentOf(info);
  if (!k) continue;
  if (!isState && feats.length === 0) continue; // territoire sans forme : ignoré
  const area = info.area || 0;
  let d = "";
  let bbox = null;
  if (feats.length) {
    d = feats.map((f) => path(f)).filter(Boolean).join("");
    const all = feats.map((f) => path.bounds(f));
    bbox = [Math.min(...all.map((b) => b[0][0])), Math.min(...all.map((b) => b[0][1])), Math.max(...all.map((b) => b[1][0])), Math.max(...all.map((b) => b[1][1]))];
  }
  const small = !bbox || (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) < 12;
  const micro = isState && area < 2000;
  const entry = { c: info.cca3, n: info.translations.fra.common, k, s: isState ? 1 : 0, a: Math.round(area) };
  if (d) {
    entry.d = d;
    // Repère du plus grand morceau : centre et rayon (pour l'anneau de révélation et le zoom)
    entry.m = mainMark(d);
  }
  if (isState && (small || micro)) {
    const p = proj([info.latlng[1], info.latlng[0]]);
    if (p) entry.dot = [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10];
  }
  // Cibles de jeu : États indépendants de taille raisonnable
  if (info.independent === true && area >= 2000 && feats.length) {
    entry.g = 1;
    entry.sil = silhouette(detailed(feats));
  }
  out.push(entry);
}
out.sort((a, b) => a.n.localeCompare(b.n, "fr"));

// --- Cadres de zoom par région (lon/lat -> pixels)
const BOXES = {
  monde: null,
  europe: [-25, 34, 45, 72],
  afrique: [-20, -36, 52, 38],
  asie: [26, -11, 146, 56],
  "amerique-nord": [-170, 7, -52, 72],
  "amerique-sud": [-83, -57, -33, 13],
  oceanie: [110, -48, 180, 2],
};
const regions = { monde: [0, 0, W, H] };
for (const [id, b] of Object.entries(BOXES)) {
  if (!b) continue;
  const pts = [];
  for (let i = 0; i <= 20; i++) {
    const lon = b[0] + ((b[2] - b[0]) * i) / 20; const lat = b[1] + ((b[3] - b[1]) * i) / 20;
    pts.push(proj([lon, b[1]]), proj([lon, b[3]]), proj([b[0], lat]), proj([b[2], lat]));
  }
  const xs = pts.map((p) => p[0]); const ys = pts.map((p) => p[1]);
  let [ax, ay, bx, by] = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  let w = bx - ax, h = by - ay; const pad = 0.05;
  ax -= w * pad; bx += w * pad; ay -= h * pad; by += h * pad; w = bx - ax; h = by - ay;
  const ratio = W / H;
  if (w / h < ratio) { const nw = h * ratio; ax -= (nw - w) / 2; w = nw; } else { const nh = w / ratio; ay -= (nh - h) / 2; h = nh; }
  regions[id] = [Math.round(ax), Math.round(ay), Math.round(w), Math.round(h)];
}

const data = {
  w: W, h: H, continents: CONTINENTS, regions, bg: bg.map((f) => path(f)).filter(Boolean).join(""),
  countries: out,
};
const target = process.argv[2] || "out/world.json";
fs.mkdirSync(target.split("/").slice(0, -1).join("/") || ".", { recursive: true });
fs.writeFileSync(target, JSON.stringify(data));
const states = out.filter((c) => c.s), game = out.filter((c) => c.g);
console.log({ H, entries: out.length, etats: states.length, territoires: out.length - states.length, cibles: game.length, points: out.filter((c) => c.dot).length, sansForme: out.filter((c) => !c.d).map((c) => c.c) });
console.log("octets", fs.statSync(target).size);

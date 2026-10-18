# Régénérer les données de la carte

`atlas/static/atlas/world.json` est généré, pas écrit à la main. Il n'est utile de le refaire que
pour changer le niveau de détail, ajouter un pays ou corriger un nom.

```bash
mkdir /tmp/atlasbuild && cd /tmp/atlasbuild
cp <projet>/atlas/tools/build_world.mjs build.mjs
npm init -y
npm install world-atlas@2 topojson-client@3 topojson-simplify@3 d3-geo@3 world-countries@5
node build.mjs <projet>/atlas/static/atlas/world.json
```

Sources : fond de carte Natural Earth 1:50m via `world-atlas` (domaine public), noms français,
continents et superficies via `world-countries` (mledoze/countries, licence ODbL : à citer).

Réglages : `MAP_WEIGHT` (détail de la carte, 6e-6 par défaut) et `SIL_WEIGHT` (détail des silhouettes,
4e-7), en variables d'environnement. Plus petit = plus de détail = fichier plus lourd.

Format du fichier : `w`/`h` (taille du cadre), `continents`, `regions` (cadres de zoom),
`bg` (formes sans pays), `countries` avec `c` (code ISO3), `n` (nom), `k` (continent), `s` (1 = compté
comme pays), `a` (superficie km²), `d` (tracé), `m` (centre et rayon du plus grand morceau),
`dot` (point pour les micro-États), `g` (1 = cible de jeu), `sil` (silhouette).

import json
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

DATA = Path(__file__).resolve().parent / "static" / "atlas" / "world.json"


class AtlasPageTests(TestCase):
    def test_page_publique(self):
        r = self.client.get(reverse("atlas"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "data-world=")
        for mode in ("scratch", "where", "shape"):
            self.assertContains(r, f'data-mode="{mode}"')

    def test_fichiers_statiques_trouves(self):
        for name in ("atlas/world.json", "atlas/atlas.js", "atlas/atlas.css"):
            self.assertIsNotNone(finders.find(name), name)

    def test_lien_dans_le_menu_et_sur_l_accueil(self):
        self.assertContains(self.client.get(reverse("atlas")), 'href="/atlas/"')
        self.assertContains(self.client.get(reverse("starting-page")), 'href="/atlas/"')


class DonneesCarteTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data = json.loads(DATA.read_text(encoding="utf-8"))
        cls.by_code = {c["c"]: c for c in cls.data["countries"]}

    def test_poids_raisonnable(self):
        self.assertLess(DATA.stat().st_size, 700_000)

    def test_cadre_et_regions(self):
        d = self.data
        self.assertEqual(d["w"], 1000)
        self.assertTrue(300 < d["h"] < 600)
        self.assertEqual(
            set(d["regions"]), {"monde", "europe", "afrique", "asie", "amerique-nord", "amerique-sud", "oceanie"}
        )
        for name, (x, y, w, h) in d["regions"].items():
            self.assertGreater(w, 0, name)
            self.assertAlmostEqual(w / h, d["w"] / d["h"], delta=0.05, msg=name)

    def test_codes_uniques_et_champs_obligatoires(self):
        codes = [c["c"] for c in self.data["countries"]]
        self.assertEqual(len(codes), len(set(codes)))
        continents = {k["id"] for k in self.data["continents"]}
        self.assertEqual(len(continents), 6)
        for c in self.data["countries"]:
            self.assertTrue(c["n"].strip(), c["c"])
            self.assertIn(c["k"], continents, c["c"])
            self.assertIn(c["s"], (0, 1))
            self.assertTrue(c.get("d") or c.get("dot"), f"{c['c']} sans forme ni point")

    def test_nombre_de_pays_comptes(self):
        self.assertEqual(sum(c["s"] for c in self.data["countries"]), 197)

    def test_noms_francais_et_cas_particuliers(self):
        b = self.by_code
        self.assertEqual(b["FRA"]["n"], "France")
        self.assertEqual(b["DEU"]["n"], "Allemagne")
        self.assertEqual(b["CIV"]["n"], "Côte d'Ivoire")
        self.assertEqual(b["USA"]["n"], "États-Unis")
        self.assertEqual(b["GRL"]["s"], 0)           # le Groenland est un territoire
        self.assertEqual(b["TWN"]["s"], 1)
        self.assertEqual(b["UNK"]["s"], 1)
        self.assertNotIn("ATA", b)                    # pas d'Antarctique
        self.assertIn("dot", b["VAT"])                # micro-État : repérable par un point
        self.assertIn("dot", b["TUV"])
        self.assertNotIn("d", b["TUV"])               # Tuvalu n'a pas de forme dans le fond de carte

    def test_cibles_de_jeu(self):
        targets = [c for c in self.data["countries"] if c.get("g")]
        self.assertGreater(len(targets), 150)
        for c in targets:
            self.assertEqual(c["s"], 1, c["c"])
            self.assertTrue(c["sil"].startswith("M"), c["c"])
            self.assertGreaterEqual(c["a"], 2000, c["c"])
        # Chaque région de jeu a assez de pays pour une manche et des leurres (l'Océanie n'en a que 7 :
        # la manche y est plus courte, le jeu s'adapte)
        for k in {c["k"] for c in targets}:
            self.assertGreaterEqual(len([c for c in targets if c["k"] == k]), 6, k)

    def test_repere_principal_et_points_dans_le_cadre(self):
        w, h = self.data["w"], self.data["h"]
        for c in self.data["countries"]:
            if c.get("d"):
                cx, cy, r = c["m"]
                self.assertTrue(-5 <= cx <= w + 5 and -5 <= cy <= h + 5, c["c"])
                self.assertGreaterEqual(r, 0)
            if c.get("dot"):
                x, y = c["dot"]
                self.assertTrue(0 <= x <= w and 0 <= y <= h, c["c"])

    def test_la_france_n_a_pas_de_repere_en_amerique_du_sud(self):
        # Le plus grand morceau de la France est la métropole, pas la Guyane.
        cx, cy, r = self.by_code["FRA"]["m"]
        self.assertTrue(480 < cx < 530 and 90 < cy < 120, (cx, cy))
        # La Russie traverse l'antiméridien : son repère reste du côté européen/asiatique.
        cx, cy, r = self.by_code["RUS"]["m"]
        self.assertTrue(550 < cx < 900, (cx, cy))

# Mise en production (Render)

## Variables d'environnement à définir sur Render (Environment)
| Variable | Valeur |
|---|---|
| `ENV` | `prod` |
| `SECRET_KEY` | une longue chaîne aléatoire (`python -c "import secrets;print(secrets.token_urlsafe(50))"`) — **obligatoire, le site refuse de démarrer sans** |
| `DATABASE_URL` | l'URL de ta base Postgres Render |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | tes clés S3 (images des articles) |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | ton serveur SMTP (facultatif mais nécessaire pour la réinitialisation de mot de passe et les alertes dividendes). Sans `EMAIL_HOST`, les e-mails s'affichent seulement dans les logs. |
| `DEFAULT_FROM_EMAIL` | adresse d'expédition, ex. `Yannick Wahl <contact@yannickwahl.fr>` (facultatif) |

## Commandes du service
- **Build** : `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- **Start** : `gunicorn my_site.wsgi`

## Nouvelles dépendances et migrations
`requirements.txt` ajoute `markdown` et `nh3` (rendu Markdown sécurisé). Les migrations
(`blog` 0011 à 0013, `dividends` 0012) s'appliquent toutes seules avec la commande de build.
La 0013 règle le domaine du site sur `yannickwahl.fr` (utilisé dans les e-mails et le flux RSS).

## Tâches planifiées (Render → Cron Jobs, même dépôt, mêmes variables)
| Commande | Rythme conseillé | Rôle |
|---|---|---|
| `python manage.py sync_prices` | tous les jours (soir) | cours des titres |
| `python manage.py sync_dividends_declared` | une fois par semaine | dividendes annoncés |
| `python manage.py notify_dividends` | tous les jours (matin) | e-mail la veille d'un versement, pour les comptes qui l'ont activé dans « Profil » |

`notify_dividends --dry-run` montre ce qui serait envoyé sans rien envoyer.

## Utilisation au quotidien
- **Écrire un article** : seul un compte avec la permission `blog.add_post` peut publier (à donner dans l'admin, `/admin/`). Texte en Markdown avec aperçu.
- **Commentaires** : ils arrivent « à valider ». Tu les approuves ou supprimes directement sous l'article.
- **Projets** : ajoute-les dans l'admin (« Projets »). Ils apparaissent sur `/projects/` et sur l'accueil.
- **Reels** : la miniature automatique est faite au mieux ; Instagram la bloque souvent, mets alors une image à la main.
- **Flux RSS** : `/rss.xml`.

## Atlas (`/atlas/`)
Outil public, entièrement côté navigateur : carte à gratter des pays visités, jeux « Où est-ce ? » et « Silhouettes ».
- Rien à configurer : pas de variable d'environnement, pas de migration, pas de service externe.
- Il charge un fichier statique de ~0,5 Mo (`atlas/static/atlas/world.json`), servi par WhiteNoise comme le reste (`collectstatic` suffit).
- Cartes et scores restent dans le navigateur du visiteur (`localStorage`) ; le lien de partage contient la carte dans l'adresse (`#v1...`).
- Crédits à conserver : Natural Earth (domaine public) et mledoze/countries (ODbL), déjà cités en bas de la page.
- Pour régénérer les données : `atlas/tools/README.md`.

## Compte administrateur
Ne plus utiliser l'ancien mot de passe en dur. Soit tu changes le mot de passe du compte existant
(`python manage.py changepassword yannick` dans le Shell Render), soit tu définis
`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD`
et tu lances `python manage.py shell < my_site/create_superuser.py`.

## Après le déploiement
1. Ouvre le site, vérifie accueil / articles / CV / connexion.
2. Vérifie qu'une image d'article s'affiche (S3).
3. Plus tard, quand tout est stable : activer HSTS (`SECURE_HSTS_SECONDS`).

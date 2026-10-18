# Mise en production (Render)

## Variables d'environnement à définir sur Render (Environment)
| Variable | Valeur |
|---|---|
| `ENV` | `prod` |
| `SECRET_KEY` | une longue chaîne aléatoire (`python -c "import secrets;print(secrets.token_urlsafe(50))"`) — **obligatoire, le site refuse de démarrer sans** |
| `DATABASE_URL` | l'URL de ta base Postgres Render |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | tes clés S3 (images des articles) |

## Commandes du service
- **Build** : `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- **Start** : `gunicorn my_site.wsgi`

## Compte administrateur
Ne plus utiliser l'ancien mot de passe en dur. Soit tu changes le mot de passe du compte existant
(`python manage.py changepassword yannick` dans le Shell Render), soit tu définis
`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD`
et tu lances `python manage.py shell < my_site/create_superuser.py`.

## Après le déploiement
1. Ouvre le site, vérifie accueil / articles / CV / connexion.
2. Vérifie qu'une image d'article s'affiche (S3).
3. Plus tard, quand tout est stable : activer HSTS (`SECURE_HSTS_SECONDS`).

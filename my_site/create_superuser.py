"""
Crée le compte administrateur au déploiement, SANS mot de passe écrit dans le code.

À définir dans les variables d'environnement Render :
    DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, DJANGO_SUPERUSER_PASSWORD

Sans ces variables, le script ne fait rien.
Lancement : python manage.py shell < my_site/create_superuser.py
"""
import os

from django.contrib.auth import get_user_model

User = get_user_model()

username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

if not (username and password):
    print(">>> Variables DJANGO_SUPERUSER_* absentes : aucun compte créé")
elif User.objects.filter(username=username).exists():
    print(">>> Superuser already exists")
else:
    User.objects.create_superuser(username=username, email=email, password=password)
    print(">>> Superuser created")

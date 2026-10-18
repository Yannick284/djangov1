#!/usr/bin/env bash
# Lance le site en local : ./lancer.sh   (puis ouvre http://127.0.0.1:8000)
set -e
cd "$(dirname "$0")"

PY=$(command -v python3.13 || command -v python3.12 || command -v python3)
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' \
  || { echo "Django 6 demande Python 3.12 ou plus (trouvé : $("$PY" -V))."; exit 1; }

[ -d .venv ] || "$PY" -m venv .venv
source .venv/bin/activate
pip install -q -r requirements.txt

python manage.py migrate

# Premier lancement : propose de créer ton compte administrateur
if [ ! -f .admin_cree ]; then
  echo
  echo "Création de ton compte administrateur (Ctrl+C pour passer) :"
  python manage.py createsuperuser && touch .admin_cree || true
fi

echo
echo "Site sur http://127.0.0.1:8000   (Ctrl+C pour arrêter)"
python manage.py runserver

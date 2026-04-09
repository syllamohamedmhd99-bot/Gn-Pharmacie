#!/bin/bash
echo "--- Lancement du script de démarrage PharmaCloud ---"
echo "Environnement: $FLASK_ENV"
echo "Port: $PORT"

python init_prod.py || echo "Attention: init_prod a échoué, on tente de lancer le serveur quand même."

echo "Démarrage de Gunicorn..."
gunicorn -b 0.0.0.0:$PORT --timeout 120 manage:app

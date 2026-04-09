#!/bin/bash
echo "--- Lancement du script de démarrage PharmaCloud ---"
python init_prod.py || echo "Attention: init_prod a échoué, on tente de lancer le serveur quand même."
gunicorn -b 0.0.0.0:$PORT --timeout 120 run:app

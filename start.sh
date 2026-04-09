#!/bin/bash
echo "--- Lancement du script de démarrage PharmaCloud ---"
echo "Environnement: $FLASK_ENV"
echo "Port: $PORT"

# Exécuter le diagnostic pour capturer les erreurs dans les logs
python diagnostic.py || echo "Attention: Le diagnostic a détecté une erreur critique."

# Vérification impérative de DATABASE_URL sur Railway
if [ -n "$RAILWAY_STATIC_URL" ] && [ -z "$DATABASE_URL" ]; then
    echo "!!! ERREUR CRITIQUE : DATABASE_URL est manquante !!!"
    echo "L'application ne peut pas démarrer en production sans base de données."
    echo "Veuillez LIER votre service Postgres à votre service web dans le tableau de bord Railway."
    exit 1
fi

# Réparations, Création des tables et Seeding (SuperAdmin)
# On le fait AVANT le upgrade pour créer les tables si elles manquent (Catch-22 fix)
python init_prod.py || echo "Attention: L'initialisation/réparation a échoué."

# Appliquer les migrations de base de données (Sera ignoré si stampé par init_prod)
export FLASK_APP=manage.py
flask db upgrade || echo "Attention: flask db upgrade a échoué, on continue quand même."

echo "Démarrage de Gunicorn..."
gunicorn -b 0.0.0.0:$PORT --timeout 120 manage:app

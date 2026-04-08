import os
import sys

# Ajoute le dossier parent au chemin de recherche pour trouver 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# Point d'entrée pour Vercel (si Root Directory = pharma_cloud_erp)
app = create_app('production')

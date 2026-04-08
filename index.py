import os
import sys

# Ajoute le dossier pharma_cloud_erp au chemin de recherche
root_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(root_dir, 'pharma_cloud_erp')
sys.path.append(app_dir)

from app import create_app

# Point d'entrée pour Vercel
app = create_app('production')

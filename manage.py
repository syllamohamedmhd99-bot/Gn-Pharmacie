import os
import sys

# Ajoute le dossier pharma_cloud_erp au chemin de recherche
root_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.join(root_dir, 'pharma_cloud_erp')
sys.path.append(app_dir)

# Import de l'application et des commandes
from pharma_cloud_erp.manage import app, seed

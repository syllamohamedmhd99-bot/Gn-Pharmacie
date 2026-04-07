import sqlite3
import os

DB_PATH = 'g:/Gn pharmacie/pharma_cloud_erp/app.db'

def fix_schema():
    print(f"Connexion à {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Liste des colonnes à ajouter
    updates = [
        # Table pharmacies
        ("pharmacies", "logo_url", "TEXT"),
        ("pharmacies", "invoice_header", "TEXT"),
        ("pharmacies", "invoice_footer", "TEXT"),
        ("pharmacies", "subscription_plan", "TEXT DEFAULT 'Essai'"),
        ("pharmacies", "subscription_end_date", "DATETIME"),
        
        # Table users
        ("users", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        
        # Autres tables (Multi-tenancy)
        ("medicines", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("batches", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("suppliers", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("sales", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("sale_items", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("shifts", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("time_clocks", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("payroll_records", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("salary_advances", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
        ("purchase_orders", "pharmacy_id", "INTEGER REFERENCES pharmacies(id)"),
    ]
    
    for table, col, col_type in updates:
        try:
            print(f"Ajout de {col} à {table}...")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            print(f"   [INFO] {col} existe déjà dans {table}.")
            
    conn.commit()
    conn.close()
    print("--- SCHÉMA RÉPARÉ ---")

if __name__ == "__main__":
    fix_schema()

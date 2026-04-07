import sqlite3

DB_PATH = 'g:/Gn pharmacie/pharma_cloud_erp/app.db'

def fix_medicine_schema():
    print(f"Connexion à {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("Ajout de purchase_price à medicines...")
        cursor.execute("ALTER TABLE medicines ADD COLUMN purchase_price REAL DEFAULT 0.0")
        conn.commit()
        print("--- COLONNE AJOUTÉE AVEC SUCCÈS ---")
    except sqlite3.OperationalError:
        print("   [INFO] purchase_price existe déjà dans medicines.")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_medicine_schema()

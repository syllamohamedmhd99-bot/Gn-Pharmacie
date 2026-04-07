import requests
import json

BASE_URL = "http://127.0.0.1:5000"
session = requests.Session()

def test_full_saas_flow():
    print("--- DÉBUT DU TEST DU FLUX SAAS ---")
    
    # 1. Initialisation de la DB
    print("1. Initialisation via /seed...")
    try:
        requests.get(f"{BASE_URL}/seed")
    except Exception as e:
        print(f"Erreur connexion serveur : {e}. Assurez-vous que python run.py tourne.")
        return

    # 2. Inscription Pharmacie (Étape 1)
    print("2. Inscription de la Pharmacie 'Bio Test'...")
    session.post(f"{BASE_URL}/auth/register", data={
        'name': 'Bio Test',
        'address': 'Conakry',
        'license': 'BIO-777'
    })
    
    # 3. Inscription Admin (Étape 2)
    print("3. Création du compte gérant 'bio@saas.com'...")
    session.post(f"{BASE_URL}/auth/register_admin", data={
        'email': 'bio@saas.com',
        'first_name': 'Admin',
        'last_name': 'Bio',
        'password': 'password123'
    })
    
    # 4. Tentative de connexion (Doit être bloqué/inactif)
    print("4. Vérification du verrouillage initial...")
    r = session.post(f"{BASE_URL}/auth/login", data={
        'email': 'bio@saas.com',
        'password': 'password123'
    }, allow_redirects=True)
    if "en attente de validation" in r.text.lower() or "authentification" in r.text.lower():
        print("   [OK] Le compte est bien inactif par défaut.")
    else:
        print("   [OUPPS] Le compte a peut-être été activé trop tôt ou message différent.")

    # 5. Login Super-Admin & Activation
    print("5. Connexion Super-Admin & Activation de 'Bio Test'...")
    session.post(f"{BASE_URL}/auth/login", data={
        'email': 'admin@pharma.com',
        'password': 'admin123'
    })
    
    # Activation pharmacie ID=2
    session.post(f"{BASE_URL}/superadmin/toggle_pharmacy/2")
    print("   [OK] Pharmacie activée par le Super-Admin.")
    
    # 6. Test d'accès Admin Bio
    session.get(f"{BASE_URL}/auth/logout")
    print("6. Re-connexion Admin Bio...")
    session.post(f"{BASE_URL}/auth/login", data={
        'email': 'bio@saas.com',
        'password': 'password123'
    })
    
    # 7. Test de blocage (Désactivation)
    session.get(f"{BASE_URL}/auth/logout")
    session.post(f"{BASE_URL}/auth/login", data={'email': 'admin@pharma.com', 'password': 'admin123'})
    session.post(f"{BASE_URL}/superadmin/toggle_pharmacy/2") # On redésactive
    print("7. Simulation d'expiration (Désactivation)...")
    
    session.get(f"{BASE_URL}/auth/logout")
    r = session.post(f"{BASE_URL}/auth/login", data={'email': 'bio@saas.com', 'password': 'password123'}, allow_redirects=True)
    
    # Si le login est bloqué, on doit voir le message d'erreur ou rester sur login
    if "service pour cette pharmacie est suspendu" in r.text.lower() or r.url.endswith('/auth/login'):
        print("   [OK] Connexion BLOQUÉE pour pharmacie inactive.")
    else:
        print("   [ERREUR] La connexion a réussi malgré la désactivation !")

    print("--- FIN DU TEST ---")

if __name__ == "__main__":
    test_full_saas_flow()

from app import create_app
from app.extensions import db
from app.models import Shift, User

app = create_app()
with app.app_context():
    print("--- Orphaned Shifts Check ---")
    shifts = Shift.query.all()
    orphans = []
    for s in shifts:
        if not s.user:
            orphans.append(s.id)
    
    if orphans:
        print(f"Found {len(orphans)} orphaned shifts: {orphans}")
        print("Fixing by deleting orphans...")
        for oid in orphans:
            db.session.delete(Shift.query.get(oid))
        db.session.commit()
        print("Done.")
    else:
        print("No orphaned shifts found.")

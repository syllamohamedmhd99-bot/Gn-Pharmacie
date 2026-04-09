from app import create_app
from app.extensions import db
from sqlalchemy import inspect
import os

app = create_app()
with app.app_context():
    print("--- Database Inspection ---")
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Tables: {tables}")
    
    if 'shifts' in tables:
        print("\n--- Shift Table Columns ---")
        columns = inspector.get_columns('shifts')
        for column in columns:
            print(f"- {column['name']}: {column['type']}")
    else:
        print("\nERROR: Table 'shifts' IS MISSING!")

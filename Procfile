web: python -c "from app import create_app, db; app=create_app('production'); with app.app_context(): db.create_all()" && gunicorn run:app

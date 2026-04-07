web: (python -c "from app import create_app, db; app=create_app('production'); with app.app_context(): db.create_all()" || true) && gunicorn -b 0.0.0.0:$PORT --timeout 120 run:app

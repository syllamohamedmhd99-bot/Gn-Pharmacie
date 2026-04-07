from app import create_app
import os

# Create the app instance for Vercel Serverless Function
# We use 'production' config for Vercel deployment
app = create_app('production')

# Export app for Vercel
# Vercel needs the 'app' variable to be available in this module
# or the module itself to be named 'index.py' in /api/

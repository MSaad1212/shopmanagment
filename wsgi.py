import sys
import os

# Add the project path so PythonAnywhere can find the app
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

# Convert FastAPI (ASGI) to PythonAnywhere's required format (WSGI)
from a2wsgi import ASGIMiddleware
from run import app

# PythonAnywhere specifically looks for a variable named 'application'
application = ASGIMiddleware(app)

import sys
import os

# Add the root directory to path so Vercel can find the app module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from run import app

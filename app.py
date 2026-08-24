# projects/app.py
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import NotFound

# Import the three apps (they're all named 'app')
import sys
import os

# Add project root to path if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import each app with an alias
from av_cut.app import app as av_cut_app
from bfc.app import app as bfc_app
from vd3.app import app as vd3_app

# Create main Flask app
app = Flask(__name__)

# Mount the apps at different URL prefixes
app.wsgi_app = DispatcherMiddleware(
    NotFound(),
    {
        '/av_cut': av_cut_app,
        '/bfc': bfc_app,
        '/vd3': vd3_app,
    }
)

if __name__ == '__main__':
    app.run(debug=True, port=5010)

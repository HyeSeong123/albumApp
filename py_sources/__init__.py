from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def create_app() :
    app = Flask(__name__)
    
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'album.db')}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    app.static_folder = os.path.join(BASE_DIR, 'resources')
    app.static_url_path = '/static'
    
    app.template_folder = os.path.join(BASE_DIR, 'templates')
    
    db.init_app(app)
    
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    with app.app_context():
        db.create_all()
        
    return app
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', "dev-key")

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///coursehub.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
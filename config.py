import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'payshield-in-msme-defense-key-v1-2026')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f"sqlite:///{BASE_DIR / 'payshield.db'}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload settings
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max limit
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'csv', 'xlsx', 'txt'}
    
    # Generated static charts & SVGs
    GENERATED_FOLDER = BASE_DIR / 'static' / 'generated'
    
    # Multilingual Concept Registry
    # Canonical Concept Layer: Financial/legal phrases are never translated loosely.
    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'hi': 'हिन्दी (Hindi)',
        'bn': 'বাংলা (Bengali)',
        'ta': 'தமிழ் (Tamil)',
        'te': 'తెలుగు (Telugu)',
        'mr': 'मराठी (Marathi)'
    }
    
    # Security & DPDP Rules 2025
    DPDP_RETENTION_DAYS = 365 * 3
    TENANT_ISOLATION_STRICT = True
    
    # Demo and Sandbox Mode Flag
    SANDBOX_MODE = True
    
    @classmethod
    def init_app(cls, app):
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(cls.GENERATED_FOLDER, exist_ok=True)

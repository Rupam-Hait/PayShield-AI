"""
Flask Application Route & Server-Side Rendering Smoke Test Suite
Verifies all 18 views and endpoints render 200 OK without client-side JavaScript.
"""

import pytest
from app import app, db_session
from models import Invoice

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_all_18_pages_render_successfully(client):
    """Smoke test ensuring every view renders valid HTML."""
    routes = [
        '/',
        '/dashboard',
        '/invoices',
        '/buyers/dna',
        '/buyers/graph',
        '/cashflow',
        '/simulator',
        '/actions',
        '/treds',
        '/odr',
        '/evidence',
        '/assistant',
        '/privacy',
        '/model/health',
        '/learning',
        '/system/rules',
        '/data/health',
        '/onboarding',
        '/login'
    ]

    for route in routes:
        resp = client.get(route)
        assert resp.status_code == 200, f"Route {route} failed with status {resp.status_code}"
        assert b"PayShield AI" in resp.data or b"Enterprise Authentication" in resp.data

def test_language_switching_server_roundtrip(client):
    """Test switching languages to Hindi, Bengali, Tamil, Telugu, and Marathi."""
    langs = ['hi', 'bn', 'ta', 'te', 'mr', 'en']
    for lang in langs:
        post_resp = client.post('/language/set', data={'lang': lang, 'return_url': '/dashboard'}, follow_redirects=True)
        assert post_resp.status_code == 200
        # Verify page renders in target language
        if lang == 'hi':
            assert "पे-शील्ड".encode('utf-8') in post_resp.data

def test_rescue_simulation_post_roundtrip(client):
    """Test What-If form submission triggers full server calculation."""
    resp = client.post('/simulator/run', data={
        'extra_delay_days': '45',
        'starting_cash': '1000000',
        'safety_threshold': '500000'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Stress simulation recalculation complete" in resp.data
    assert b"45D DELAY APPLIED" in resp.data

def test_assistant_query_roundtrip(client):
    """Test assistant semantic query."""
    resp = client.post('/assistant/query', data={'query': 'What is my cash runway?'}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Grounded System Finding" in resp.data

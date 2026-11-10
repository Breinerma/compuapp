from pathlib import Path
import ssl
from app.database import database_settings

ROOT = Path(__file__).resolve().parents[2]

def test_database_secrets_and_rds_tls(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    for key, value in {
        'DB_HOST': 'test.us-east-2.rds.amazonaws.com', 'DB_USER': 'naturalens',
        'DB_PASSWORD': 'test-only:@/#?%', 'DB_NAME': 'naturalens',
        'DB_SSL_CA': str(ROOT / 'api/certs/global-bundle.pem'),
    }.items():
        monkeypatch.setenv(key, value)
    url, options = database_settings()
    assert url.password == 'test-only:@/#?%'
    assert url.host == 'test.us-east-2.rds.amazonaws.com'
    assert options['ssl'].verify_mode == ssl.CERT_REQUIRED
    assert options['ssl'].check_hostname
    assert options['ssl'].cert_store_stats()['x509_ca'] > 0

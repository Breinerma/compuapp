"""Pruebas con SQLite temporal y el modelo REAL (sin predicciones simuladas)."""
import os
import tempfile
from io import BytesIO
from pathlib import Path

temporary = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite:///' + (Path(temporary.name) / 'test.db').as_posix()
os.environ['UPLOAD_DIR'] = str(Path(temporary.name) / 'photos')
os.environ['COOKIE_SECURE'] = 'false'
os.environ['S3_BUCKET'] = ''

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, User, LoginSession, now
from app.classifier import prepare_photo
from sqlalchemy import select

def test_image_contract():
    photo = BytesIO()
    Image.new('RGB', (300, 500), (120, 45, 230)).save(photo, 'PNG')
    tensor, jpeg = prepare_photo(photo.getvalue())
    assert tensor.shape == (1, 224, 224, 3)
    assert tensor.dtype.name == 'float32'
    assert tensor[0, 0, 0].tolist() == [120., 45., 230.]
    assert jpeg.startswith(b'\xff\xd8')
    with pytest.raises(ValueError):
        prepare_photo(b'not an image')

def test_real_model_private_history_and_sessions():
    with TestClient(app) as owner:
        assert owner.get('/api/health').json()['species'] > 3
        assert owner.get('/api/captures').status_code == 401
        body = {'name': 'Exploradora', 'phone': '3001234567', 'password': 'PruebaSegura123!'}
        registered = owner.post('/api/auth/register', json=body)
        assert registered.status_code == 201, registered.text
        assert registered.json()['user']['phone'] == '+573001234567'
        assert 'HttpOnly' in registered.headers['set-cookie']
        csrf = {'X-CSRF-Token': registered.json()['csrf']}
        assert owner.post('/api/auth/register', json=body).status_code == 409
        assert owner.post('/api/captures/1/view').status_code == 403
        assert owner.post('/api/captures', files={'file': ('bad.jpg', b'bad', 'image/jpeg')}, headers=csrf).status_code == 422
        oversized = b'x' * (10 * 1024 * 1024 + 1)
        assert owner.post('/api/captures', files={'file': ('big.jpg', oversized, 'image/jpeg')}, headers=csrf).status_code == 413
        data = BytesIO()
        Image.new('RGB', (480, 320), (85, 120, 60)).save(data, 'JPEG')
        created = owner.post('/api/captures', files={'file': ('foto.jpg', data.getvalue(), 'image/jpeg')}, headers=csrf)
        assert created.status_code == 201, created.text
        capture = created.json()
        assert len(capture['predictions']) == 3
        assert 0 <= capture['predictions'][0]['confidence'] <= 1
        assert owner.get(capture['photo_url']).status_code == 200
        assert owner.get('/api/captures').json()['total'] == 1
        assert owner.post(f"/api/captures/{capture['id']}/view", headers=csrf).status_code == 200
        assert owner.get('/api/views').json()['total'] == 1
        # Segundo navegador independiente: no debe acceder a la foto ni al historial ajeno.
        with TestClient(app) as other:
            other_body = {**body, 'phone': '+573009876543', 'name': 'Otro usuario'}
            other_registration = other.post('/api/auth/register', json=other_body)
            other_csrf = {'X-CSRF-Token': other_registration.json()['csrf']}
            assert other.get('/api/captures').json()['total'] == 0
            assert other.get(capture['photo_url']).status_code == 404
            assert other.post(f"/api/captures/{capture['id']}/view", headers=other_csrf).status_code == 404
            assert other.delete(f"/api/captures/{capture['id']}", headers=other_csrf).status_code == 404
        # Sesión persiste al abrir otro cliente con la misma cookie.
        with TestClient(app) as restored:
            restored.cookies.update(owner.cookies)
            assert restored.get('/api/auth/me').status_code == 200
        assert owner.delete(f"/api/captures/{capture['id']}", headers=csrf).status_code == 200
        assert owner.get(capture['photo_url']).status_code == 404
        assert owner.get('/api/views').json()['total'] == 0
        assert list((Path(temporary.name) / 'photos').iterdir()) == []
        assert owner.post('/api/auth/logout', headers=csrf).status_code == 200
        assert owner.get('/api/auth/me').status_code == 401
        assert owner.post('/api/auth/login', json={**body, 'password': 'Incorrecta123'}).status_code == 401
        login = owner.post('/api/auth/login', json=body)
        assert login.status_code == 200
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.phone == '+573001234567'))
            assert user.password_hash != body['password']
            session = db.scalar(select(LoginSession).where(LoginSession.user_id == user.id))
            from datetime import timedelta
            session.expires_at = now() - timedelta(seconds=1)
            db.commit()
        assert owner.get('/api/auth/me').status_code == 401

def test_s3_storage_contract(monkeypatch):
    import boto3
    from app.storage import Storage
    class Bucket:
        def __init__(self):
            self.objects = {}
        def put_object(self, **kwargs):
            assert kwargs['ServerSideEncryption'] == 'AES256'
            assert kwargs['ContentType'] == 'image/jpeg'
            assert 'ACL' not in kwargs
            self.objects[kwargs['Key']] = kwargs['Body']
        def get_object(self, **kwargs):
            return {'Body': BytesIO(self.objects[kwargs['Key']])}
        def delete_object(self, **kwargs):
            self.objects.pop(kwargs['Key'], None)
    bucket = Bucket()
    monkeypatch.setenv('S3_BUCKET', 'test-private-bucket')
    monkeypatch.setattr(boto3, 'client', lambda *args, **kwargs: bucket)
    storage = Storage()
    storage.save('test.jpg', b'photo')
    assert storage.read('test.jpg') == b'photo'
    storage.delete('test.jpg')
    assert not bucket.objects

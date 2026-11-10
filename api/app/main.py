import hashlib
import logging
import os
import re
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import timedelta
from threading import Lock
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from pwdlib import PasswordHash
from sqlalchemy import select, delete, func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from .database import Base, engine, get_db, User, LoginSession, Capture, View, now
from .classifier import Classifier, prepare_photo
from .storage import Storage

logger = logging.getLogger(__name__)
passwords = PasswordHash.recommended()
dummy_hash = passwords.hash(secrets.token_urlsafe(32))
secure = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
attempts = defaultdict(deque)
attempt_lock = Lock()

@asynccontextmanager
async def lifespan(app):
    # ECS puede iniciar la API antes de que MySQL termine su primer arranque.
    for attempt in range(20):
        try:
            Base.metadata.create_all(engine)
            break
        except OperationalError:
            if attempt == 19:
                raise
            logger.warning('Esperando a que MySQL esté disponible (%d/20).', attempt + 1)
            time.sleep(3)
    app.state.storage = Storage()
    app.state.classifier = Classifier()
    try:
        yield
    finally:
        engine.dispose()

app = FastAPI(title='Naturalens · Mamíferos del Tolima', lifespan=lifespan, docs_url='/api/docs', openapi_url='/api/openapi.json')

@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.exception_handler(Exception)
async def unexpected(request, exc):
    logger.error('Error procesando solicitud', exc_info=exc)
    return JSONResponse(status_code=500, content={'detail': 'No se pudo completar la operación. Intenta de nuevo.'})

class Credentials(BaseModel):
    phone: str = Field(max_length=30)
    password: str = Field(min_length=8, max_length=128)

    @field_validator('phone')
    @classmethod
    def normalize_phone(cls, value):
        value = re.sub(r'[\s().-]', '', value)
        if re.fullmatch(r'3\d{9}', value):
            value = '+57' + value
        if not re.fullmatch(r'\+[1-9]\d{7,14}', value):
            raise ValueError('Usa el indicativo del país, por ejemplo +573001234567.')
        return value

class Registration(Credentials):
    name: str = Field(min_length=2, max_length=80)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Escribe tu nombre.')
        return value

def rate_limit(request):
    # Una sola instancia de API. Para escalar, mover este límite a Redis/WAF.
    key = request.client.host if request.client else 'unknown'
    stamp = now().timestamp()
    with attempt_lock:
        for old in list(attempts):
            if not attempts[old] or attempts[old][-1] < stamp - 900:
                del attempts[old]
        queue = attempts[key]
        while queue and queue[0] < stamp - 900:
            queue.popleft()
        if len(queue) >= 20:
            raise HTTPException(429, 'Demasiados intentos. Espera 15 minutos.')
        queue.append(stamp)

def public_user(user):
    return {'id': user.id, 'name': user.name, 'phone': user.phone}

def login_response(user, db, response):
    db.execute(delete(LoginSession).where(LoginSession.expires_at < now()))
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, csrf=csrf, expires_at=now() + timedelta(days=7)))
    db.commit()
    response.set_cookie('naturalens_session', token, max_age=604800, httponly=True, secure=secure, samesite='strict', path='/')
    return {'user': public_user(user), 'csrf': csrf}

def current(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get('naturalens_session', '')
    session = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not session or session.expires_at <= now():
        raise HTTPException(401, 'Inicia sesión para continuar.')
    if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.csrf):
            raise HTTPException(403, 'Sesión inválida. Recarga la página.')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, 'La cuenta no está disponible.')
    return user, session

@app.get('/api/health')
def health(request: Request, db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'species': len(request.app.state.classifier.labels)}

@app.post('/api/auth/register', status_code=201)
def register(data: Registration, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(request)
    user = User(name=data.name, phone=data.phone, password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Ese teléfono ya tiene una cuenta.')
    return login_response(user, db, response)

@app.post('/api/auth/login')
def login(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(request)
    user = db.scalar(select(User).where(User.phone == data.phone))
    valid = passwords.verify(data.password, user.password_hash if user else dummy_hash)
    if not user or not valid:
        raise HTTPException(401, 'Teléfono o contraseña incorrectos.')
    return login_response(user, db, response)

@app.get('/api/auth/me')
def me(auth=Depends(current)):
    user, session = auth
    return {'user': public_user(user), 'csrf': session.csrf}

@app.post('/api/auth/logout')
def logout(response: Response, auth=Depends(current), db: Session = Depends(get_db)):
    db.delete(auth[1])
    db.commit()
    response.delete_cookie('naturalens_session', path='/')
    return {'ok': True}

def owned(db, capture_id, user):
    capture = db.scalar(select(Capture).where(Capture.id == capture_id, Capture.user_id == user.id))
    if not capture:
        raise HTTPException(404, 'Captura no encontrada.')
    return capture

def serialize(capture):
    return {'id': capture.id, 'predictions': capture.predictions, 'created_at': capture.created_at.isoformat() + 'Z', 'inference_ms': capture.inference_ms, 'photo_url': f'/api/captures/{capture.id}/photo'}

@app.post('/api/captures', status_code=201)
def classify(request: Request, file: UploadFile = File(...), auth=Depends(current), db: Session = Depends(get_db)):
    raw = file.file.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, 'La foto debe pesar menos de 10 MB.')
    try:
        tensor, photo = prepare_photo(raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    predictions, elapsed = request.app.state.classifier.predict(tensor)
    key = f'{uuid4().hex}.jpg'
    storage = request.app.state.storage
    storage.save(key, photo)
    capture = Capture(user_id=auth[0].id, photo_key=key, predictions=predictions, inference_ms=elapsed)
    try:
        db.add(capture)
        db.commit()
        db.refresh(capture)
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    return serialize(capture)

@app.get('/api/captures')
def history(page: int = 1, auth=Depends(current), db: Session = Depends(get_db)):
    page = max(1, page)
    total = db.scalar(select(func.count()).select_from(Capture).where(Capture.user_id == auth[0].id))
    rows = db.scalars(select(Capture).where(Capture.user_id == auth[0].id).order_by(Capture.id.desc()).offset((page - 1) * 12).limit(12))
    return {'items': [serialize(row) for row in rows], 'total': total, 'page': page}

@app.get('/api/captures/{capture_id}/photo')
def photo(capture_id: int, request: Request, auth=Depends(current), db: Session = Depends(get_db)):
    capture = owned(db, capture_id, auth[0])
    return Response(request.app.state.storage.read(capture.photo_key), media_type='image/jpeg', headers={'Cache-Control': 'private, no-store'})

@app.post('/api/captures/{capture_id}/view')
def view_capture(capture_id: int, auth=Depends(current), db: Session = Depends(get_db)):
    capture = owned(db, capture_id, auth[0])
    db.add(View(user_id=auth[0].id, capture_id=capture.id))
    db.commit()
    return serialize(capture)

@app.get('/api/views')
def views(page: int = 1, auth=Depends(current), db: Session = Depends(get_db)):
    page = max(1, page)
    total = db.scalar(select(func.count()).select_from(View).where(View.user_id == auth[0].id))
    rows = db.execute(select(View, Capture).join(Capture, Capture.id == View.capture_id).where(View.user_id == auth[0].id).order_by(View.id.desc()).offset((page - 1) * 12).limit(12))
    return {'items': [{**serialize(capture), 'viewed_at': event.viewed_at.isoformat() + 'Z'} for event, capture in rows], 'total': total, 'page': page}

@app.delete('/api/captures/{capture_id}')
def remove(capture_id: int, request: Request, auth=Depends(current), db: Session = Depends(get_db)):
    capture = owned(db, capture_id, auth[0])
    request.app.state.storage.delete(capture.photo_key)
    db.execute(delete(View).where(View.capture_id == capture.id))
    db.delete(capture)
    db.commit()
    return {'ok': True}

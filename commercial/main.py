from __future__ import annotations

import asyncio
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.database import QueryGateway, create_business_engine
from backend.app.llm import EXAMPLE_QUESTIONS, TextToSqlProvider
from backend.app.metadata import MetadataCatalog
from backend.app.pipeline import QuestionPipeline
from backend.app.schemas import ApprovalRequest, QuestionCreate
from backend.app.sql_guard import SqlGuard

from .excel_export import build_query_workbook
from .repository import Repository, password_hash, password_matches, token_hash


class Login(BaseModel):
    username: str = Field(min_length=1,max_length=64)
    password: str = Field(min_length=1,max_length=256)

class UserCreate(BaseModel):
    username: str = Field(pattern=r'^[a-zA-Z0-9_.-]{3,40}$')
    display_name: str = Field(min_length=1,max_length=60)
    password: str = Field(min_length=12,max_length=256)
    role: Literal['admin','analyst','viewer'] = 'analyst'

class UserUpdate(BaseModel):
    active: bool | None = None
    role: Literal['admin','analyst','viewer'] | None = None

class PasswordChange(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(min_length=12,max_length=256)

class Favorite(BaseModel):
    title: str = Field(min_length=1,max_length=100)
    question: str = Field(min_length=2,max_length=2000)

def create_app(path: Path | None = None):
    repository=Repository(path or Path(os.getenv('PLATFORM_DB_PATH', str(Path(__file__).resolve().parents[1]/'.runtime/platform/retail-platform.sqlite3'))))
    settings=get_settings()
    engine=create_business_engine(settings)
    gateway=QueryGateway(settings,engine)
    catalog=MetadataCatalog(settings,engine)
    pipeline=QuestionPipeline(settings,repository,catalog,TextToSqlProvider(settings),SqlGuard(settings),gateway)
    app=FastAPI(title='Data Agent Internal Platform',version='1.0.0',docs_url=None,redoc_url=None,openapi_url=None)
    app.state.repository=repository
    approval_lock=asyncio.Lock()
    query_slots=asyncio.Semaphore(4)

    @app.middleware('http')
    async def security_headers(request, call_next):
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        return response

    def current(request: Request):
        user=repository.session(request.cookies.get('data_agent_session',''))
        if not user:
            raise HTTPException(401,'请先登录')
        if request.method not in ('GET','HEAD','OPTIONS'):
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),user['csrf']):
                raise HTTPException(403,'请求校验失败，请刷新后重试')
        return user

    def admin(user=Depends(current)):
        if user['role']!='admin': raise HTTPException(403,'需要管理员权限')
        return user

    def can_query(user=Depends(current)):
        if user['role']=='viewer': raise HTTPException(403,'浏览员不能执行查询')
        return user

    def owned(key,user):
        record=repository.get_question(key)
        if not record or (record.requested_by!=user['username'] and user['role']!='admin'):
            raise HTTPException(404,'查询记录不存在')
        return record

    @app.get('/live')
    def live(): return {'status':'ok'}

    @app.post('/api/v1/auth/login')
    def login(payload: Login,request: Request,response: Response):
        identity=f'{request.client.host if request.client else "local"}:{payload.username.lower()}'
        now=time.time()
        with repository.connect() as c:
            c.execute('DELETE FROM login_attempts WHERE at<?',(now-900,))
            count=c.execute('SELECT COUNT(*) FROM login_attempts WHERE identity=?',(identity,)).fetchone()[0]
            if count>=5: raise HTTPException(429,'登录失败次数过多，请15分钟后重试')
            c.execute('INSERT INTO login_attempts VALUES (?,?)',(identity,now))
        with repository.connect() as c:
            user=c.execute('SELECT * FROM users WHERE username=?',(payload.username,)).fetchone()
            # Equal-cost verification for unknown accounts.
            stored=user['password_hash'] if user else '00'*16+':'+'00'*64
            valid=password_matches(payload.password,stored)
            if not user or not valid or not user['active']:
                repository.event(payload.username,'login_failed')
                raise HTTPException(401,'用户名或密码错误')
            token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(24)
            c.execute('DELETE FROM sessions WHERE expires<?',(now,))
            c.execute('DELETE FROM login_attempts WHERE identity=?',(identity,))
            c.execute('INSERT INTO sessions VALUES (?,?,?,?)',(token_hash(token),user['id'],csrf,now+28800))
        response.set_cookie('data_agent_session',token,httponly=True,samesite='strict',secure=os.getenv('PLATFORM_HTTPS')=='1',max_age=28800,path='/')
        repository.event(user['username'],'login')
        return {'user':{k:user[k] for k in ('id','username','display_name','role')},'csrf_token':csrf}

    @app.get('/api/v1/auth/me')
    def me(user=Depends(current)):
        return {'user':{k:v for k,v in user.items() if k!='csrf'},'csrf_token':user['csrf']}

    @app.post('/api/v1/auth/logout')
    def logout(request: Request,response: Response,user=Depends(current)):
        with repository.connect() as c: c.execute('DELETE FROM sessions WHERE token=?',(token_hash(request.cookies.get('data_agent_session','')),))
        response.delete_cookie('data_agent_session',path='/')
        repository.event(user['username'],'logout'); return {'ok':True}

    @app.post('/api/v1/auth/password')
    def change_password(payload: PasswordChange,user=Depends(current)):
        with repository.connect() as c:
            row=c.execute('SELECT password_hash FROM users WHERE id=?',(user['id'],)).fetchone()
            if not password_matches(payload.current_password,row[0]): raise HTTPException(400,'当前密码不正确')
            c.execute('UPDATE users SET password_hash=? WHERE id=?',(password_hash(payload.new_password),user['id']))
            c.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        repository.event(user['username'],'password_changed'); return {'ok':True}

    @app.get('/api/v1/health')
    def health(user=Depends(current)):
        database=gateway.status()
        return {'status':'ok' if database['connected'] else 'degraded','database':database,'text_to_sql_mode':settings.text_to_sql_mode}

    @app.get('/api/v1/examples')
    def examples(user=Depends(current)): return {'questions':EXAMPLE_QUESTIONS}

    @app.get('/api/v1/metadata/tables')
    def metadata(user=Depends(current)):
        return {'database':settings.business_db_name,'tables':catalog.snapshot()['tables']}

    @app.post('/api/v1/questions')
    async def ask(payload: QuestionCreate,user=Depends(can_query)):
        async with query_slots:
            record=await pipeline.submit(payload.question,user['username'],payload.preferred_chart)
        repository.event(user['username'],'query',record.id,str(record.status))
        return record

    @app.get('/api/v1/questions/{key}')
    def detail(key:str,user=Depends(current)): return owned(key,user)

    @app.post('/api/v1/questions/{key}/approve')
    async def approve(key:str,payload:ApprovalRequest,user=Depends(can_query)):
        async with approval_lock:
            record=owned(key,user)
            try:
                async with query_slots:
                    result=await pipeline.approve(record,payload.sql_hash,user['role'])
            except PermissionError as e: raise HTTPException(403,str(e)) from e
            except ValueError as e: raise HTTPException(409,str(e)) from e
        repository.event(user['username'],'approve',key); return result

    @app.post('/api/v1/questions/{key}/cancel')
    async def cancel(key:str,user=Depends(can_query)):
        async with approval_lock:
            record=owned(key,user)
            try: result=await pipeline.cancel(record)
            except ValueError as e: raise HTTPException(409,str(e)) from e
        repository.event(user['username'],'cancel',key); return result

    @app.get('/api/v1/questions/{key}/export')
    def export(key:str,user=Depends(current)):
        record=owned(key,user)
        if not record.result: raise HTTPException(409,'当前查询没有可导出的结果')
        content=build_query_workbook(record,user['username'])
        repository.event(user['username'],'export_excel',key)
        return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={
            'Content-Disposition':f'attachment; filename="queryx-{key}.xlsx"',
            'X-Content-Type-Options':'nosniff',
        })

    @app.get('/api/v1/history')
    def history(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str=Query('',max_length=200),status:str='',user=Depends(current)):
        clauses=['1=1']; values=[]
        if user['role']!='admin': clauses.append('owner=?'); values.append(user['username'])
        if search: clauses.append('json_extract(body,\'$.question\') LIKE ?'); values.append('%'+search+'%')
        if status: clauses.append('status=?'); values.append(status)
        where=' AND '.join(clauses)
        with repository.connect() as c:
            total=c.execute(f'SELECT COUNT(*) FROM questions WHERE {where}',values).fetchone()[0]
            rows=c.execute(f'SELECT body FROM questions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?',[*values,page_size,(page-1)*page_size]).fetchall()
        import json
        return {'total':total,'items':[json.loads(row['body']) for row in rows]}

    @app.get('/api/v1/favorites')
    def favorites(user=Depends(current)):
        with repository.connect() as c: rows=c.execute('SELECT id,title,question FROM favorites WHERE owner=? ORDER BY id DESC',(user['username'],)).fetchall()
        return {'items':[dict(row) for row in rows]}

    @app.post('/api/v1/favorites')
    def save_favorite(payload:Favorite,user=Depends(current)):
        with repository.connect() as c:
            c.execute('INSERT INTO favorites(owner,title,question) VALUES (?,?,?) ON CONFLICT(owner,title) DO UPDATE SET question=excluded.question',(user['username'],payload.title,payload.question))
        repository.event(user['username'],'favorite_saved',payload.title); return {'ok':True}

    @app.delete('/api/v1/favorites/{key}')
    def delete_favorite(key:int,user=Depends(current)):
        with repository.connect() as c: c.execute('DELETE FROM favorites WHERE id=? AND owner=?',(key,user['username']))
        repository.event(user['username'],'favorite_deleted',key); return {'ok':True}

    @app.get('/api/v1/users')
    def users(user=Depends(admin)):
        with repository.connect() as c: rows=c.execute('SELECT id,username,display_name,role,active,created_at FROM users ORDER BY id').fetchall()
        return {'items':[dict(row) for row in rows]}

    @app.post('/api/v1/users')
    def add_user(payload:UserCreate,user=Depends(admin)):
        try:
            with repository.connect() as c:
                c.execute('INSERT INTO users(username,display_name,role,password_hash,created_at) VALUES (?,?,?,?,?)',
                          (payload.username,payload.display_name,payload.role,password_hash(payload.password),time.time()))
        except sqlite3.IntegrityError as e: raise HTTPException(409,'用户名已存在') from e
        repository.event(user['username'],'user_created',payload.username,payload.role); return {'ok':True}

    @app.patch('/api/v1/users/{key}')
    def update_user(key:int,payload:UserUpdate,user=Depends(admin)):
        with repository.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            target=c.execute('SELECT * FROM users WHERE id=?',(key,)).fetchone()
            if not target: raise HTTPException(404,'用户不存在')
            active=target['active'] if payload.active is None else int(payload.active)
            role=payload.role or target['role']
            if target['role']=='admin' and target['active'] and (not active or role!='admin'):
                if c.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1: raise HTTPException(409,'不能停用或降级最后一位管理员')
            c.execute('UPDATE users SET active=?,role=? WHERE id=?',(active,role,key))
            c.execute('DELETE FROM sessions WHERE user_id=?',(key,))
        repository.event(user['username'],'user_updated',key,f'{role},active={active}'); return {'ok':True}

    @app.get('/api/v1/audit')
    def audit(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user=Depends(admin)):
        with repository.connect() as c:
            total=c.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
            rows=c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT ? OFFSET ?',(page_size,(page-1)*page_size)).fetchall()
        return {'total':total,'items':[dict(row) for row in rows]}

    @app.get('/api/v1/overview')
    def overview(user=Depends(current)):
        with repository.connect() as c:
            condition='1=1' if user['role']=='admin' else 'owner=?'; params=() if user['role']=='admin' else (user['username'],)
            states={row['status']:row['n'] for row in c.execute(f'SELECT status,COUNT(*) n FROM questions WHERE {condition} GROUP BY status',params)}
            count=c.execute('SELECT COUNT(*) FROM favorites WHERE owner=?',(user['username'],)).fetchone()[0]
        # Fixed, reviewed read-only SQL; never concatenate user input or credentials.
        try:
            with engine.connect() as c:
                metrics=dict(c.execute(text("SELECT COUNT(*) orders, SUM(CASE WHEN status='PAID' THEN amount ELSE 0 END) revenue, COUNT(DISTINCT customer_id) customers FROM orders")).mappings().one())
                trend=[dict(row) for row in c.execute(text("SELECT DATE_FORMAT(created_at,'%Y-%m') month, ROUND(SUM(amount),2) revenue FROM orders WHERE status='PAID' GROUP BY month ORDER BY month")).mappings()]
        except Exception:
            metrics=None; trend=[]
        return {'query_states':states,'favorites':count,'metrics':metrics,'trend':trend,'demo_data':True}

    dist=Path(__file__).resolve().parents[1]/'frontend-vben/apps/web-business/dist'

    @app.get('/{asset:path}',include_in_schema=False)
    def frontend(asset:str):
        if asset.startswith('api/') or not dist.exists():
            raise HTTPException(404,'页面不存在，请先构建前端')
        resolved=(dist/asset).resolve()
        if not resolved.is_relative_to(dist.resolve()):
            raise HTTPException(404,'页面不存在')
        if resolved.is_file(): return FileResponse(resolved)
        if '.' in Path(asset).name: raise HTTPException(404,'文件不存在')
        return FileResponse(dist/'index.html')

    return app

app=create_app() if os.getenv('PLATFORM_NO_DEFAULT_APP')!='1' else None

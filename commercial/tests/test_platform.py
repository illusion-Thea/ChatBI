import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from commercial.main import create_app


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('PLATFORM_ADMIN_PASSWORD', 'Correct-Password-2026!')
    from backend.app.config import Settings
    monkeypatch.setattr('commercial.main.get_settings', lambda: Settings(_env_file=None, mock_mode=True, allowed_tables={'orders'}))
    app = create_app(tmp_path / 'platform.sqlite3')
    with TestClient(app) as client:
        yield app, client

def login(client, name='admin', password='Correct-Password-2026!'):
    response = client.post('/api/v1/auth/login', json={'username':name,'password':password})
    assert response.status_code == 200, response.text
    return {'X-CSRF-Token': response.json()['csrf_token']}

def test_authentication_and_csrf(setup):
    _, client = setup
    assert client.get('/api/v1/history').status_code == 401
    assert client.post('/api/v1/auth/login',json={'username':'admin','password':'wrong'}).status_code == 401
    headers = login(client)
    assert client.get('/api/v1/auth/me').json()['user']['role'] == 'admin'
    assert client.post('/api/v1/auth/logout').status_code == 403
    assert client.post('/api/v1/auth/logout',headers=headers).status_code == 200
    assert client.get('/api/v1/auth/me').status_code == 401

def test_rbac_and_identity_headers_are_not_trusted(setup):
    app, client = setup
    headers=login(client)
    response=client.post('/api/v1/users',headers=headers,json={'username':'viewer1','password':'Viewer-Password-2026!','role':'viewer','display_name':'Viewer'})
    assert response.status_code == 200, response.text
    client.post('/api/v1/auth/logout',headers=headers)
    headers=login(client,'viewer1','Viewer-Password-2026!')
    assert client.get('/api/v1/users',headers={'X-Role':'admin'}).status_code == 403
    assert client.post('/api/v1/questions',headers={**headers,'X-Role':'admin','X-User':'admin'},json={'question':'今年每个月的已支付销售额是多少？'}).status_code == 403

def test_persistent_ownership_favorites_and_excel(setup):
    app, client = setup
    headers=login(client)
    response=client.post('/api/v1/questions',headers=headers,json={'question':'今年每个月的已支付销售额是多少？'})
    assert response.status_code==200,response.text
    record=response.json(); assert record['requested_by']=='admin'
    assert app.state.repository.get_question(record['id']) is not None
    assert client.get('/api/v1/history').json()['total']==1
    assert client.post('/api/v1/favorites',headers=headers,json={'title':'Monthly','question':record['question']}).status_code==200
    assert len(client.get('/api/v1/favorites').json()['items'])==1
    from commercial.repository import Repository
    assert Repository(app.state.repository.path).get_question(record['id']) is not None
    assert client.get('/api/v1/audit').json()['total']>=2
    if record['result']:
        export=client.get(f"/api/v1/questions/{record['id']}/export")
        assert export.status_code==200
        assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in export.headers['content-type']
        assert export.headers['content-disposition'].endswith('.xlsx"')
        with zipfile.ZipFile(io.BytesIO(export.content)) as workbook:
            assert {'xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml','xl/sharedStrings.xml'} <= set(workbook.namelist())
            shared=workbook.read('xl/sharedStrings.xml').decode('utf-8')
            assert 'QueryX 查询结果' in shared
            assert '月份' in shared
            assert '已支付销售额（元）' in shared
            assert '业务含义' in shared

def test_cannot_disable_last_admin(setup):
    _,client=setup; headers=login(client)
    user=client.get('/api/v1/auth/me').json()['user']
    assert client.patch(f"/api/v1/users/{user['id']}",headers=headers,json={'active':False}).status_code==409

def test_cross_user_access_and_session_revocation(setup):
    app,client=setup; headers=login(client)
    from backend.app.schemas import QueryResult, QuestionRecord
    record=QuestionRecord(id='owned-private',question='Private query',requested_by='admin',result=QueryResult(columns=['value'],rows=[{'value':'=HYPERLINK("evil")'}],row_count=1,elapsed_ms=0))
    app.state.repository.save_question(record)
    export=client.get('/api/v1/questions/owned-private/export')
    assert export.status_code==200
    assert 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in export.headers['content-type']
    with zipfile.ZipFile(io.BytesIO(export.content)) as workbook:
        shared=workbook.read('xl/sharedStrings.xml').decode('utf-8')
        sheet=workbook.read('xl/worksheets/sheet1.xml').decode('utf-8')
        assert '=HYPERLINK' in shared
        assert '<f>' not in sheet
    client.post('/api/v1/users',headers=headers,json={'username':'analyst1','display_name':'Analyst','password':'Analyst-Password-2026!','role':'analyst'})
    with TestClient(app) as other:
        login(other,'analyst1','Analyst-Password-2026!')
        assert other.get('/api/v1/questions/owned-private').status_code==404
        assert other.get('/api/v1/questions/owned-private/export').status_code==404
        assert other.get('/api/v1/history').json()['total']==0
        uid=next(x['id'] for x in client.get('/api/v1/users').json()['items'] if x['username']=='analyst1')
        assert client.patch(f'/api/v1/users/{uid}',headers=headers,json={'active':False}).status_code==200
        assert other.get('/api/v1/auth/me').status_code==401

def test_failed_login_is_rate_limited(setup):
    _,client=setup
    for _ in range(5):
        assert client.post('/api/v1/auth/login',json={'username':'unknown','password':'bad'}).status_code==401
    assert client.post('/api/v1/auth/login',json={'username':'unknown','password':'bad'}).status_code==429

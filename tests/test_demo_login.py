import hashlib
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.store import now

TOKEN='a'*43

@pytest.fixture
def demo(tmp_path):
    s=Settings(data_dir=tmp_path,demo_login_token_sha256=hashlib.sha256(TOKEN.encode()).hexdigest(),
               demo_login_email='demo@example.test',demo_login_course_id='demo-course')
    app=create_app(s)
    st=app.state.store
    for uid,email in [('demo','demo@example.test'),('other','other@example.test')]:
        st.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uid,email,'no-password-login',uid,now()))
    for cid,uid in [('demo-course','demo'),('private-course','other')]:
        st.execute('INSERT INTO courses VALUES(?,?,?)',(cid,cid,now()))
        st.execute('INSERT INTO course_owners VALUES(?,?)',(cid,uid))
    with TestClient(app) as c:
        yield c,s

def test_demo_link_reusable_and_only_sees_demo_course(demo):
    c,s=demo
    first=c.post('/api/auth/demo-login',json={'token':TOKEN})
    assert first.status_code==200
    assert first.json()['demo_course_id']=='demo-course'
    assert first.json()['user']['id']=='demo'
    assert 'httponly' in first.headers['set-cookie'].lower()
    csrf=first.json()['csrf_token']
    second=c.post('/api/auth/demo-login',json={'token':TOKEN},headers={'X-CSRF-Token':csrf})
    assert second.status_code==200 and second.json()['csrf_token']==csrf
    # Opening the same demo link in another tab leaves existing writes usable.
    assert c.post('/api/courses',json={'name':'new'},headers={'X-CSRF-Token':csrf}).status_code==201
    assert c.get('/api/auth/session').json()['user']['id']=='demo'
    assert 'private-course' not in [x['id'] for x in c.get('/api/courses').json()]
    assert c.get('/api/documents',params={'course_id':'private-course'}).status_code==404
    assert c.post('/api/courses',json={'name':'new'}).status_code==403
    s.demo_login_token_sha256=''
    assert c.post('/api/auth/demo-login',json={'token':TOKEN},headers={'X-CSRF-Token':second.json()['csrf_token']}).status_code==404

def test_wrong_bearer_and_cross_origin_are_rejected(demo):
    c,s=demo
    assert c.post('/api/auth/demo-login',json={'token':'b'*43}).status_code==401
    assert c.post('/api/auth/demo-login',json={'token':TOKEN},headers={'Origin':'https://evil.example'}).status_code==403
    assert c.get('/api/courses').status_code==401

def test_no_client_selected_account_and_disabled_by_default(demo):
    c,s=demo
    assert c.post('/api/auth/demo-login',json={'token':TOKEN,'email':'other@example.test'}).status_code==422
    s.demo_login_token_sha256=''
    assert c.post('/api/auth/demo-login',json={'token':TOKEN}).status_code==404

def test_existing_demo_session_still_requires_the_valid_bearer(demo):
    c,s=demo
    first=c.post('/api/auth/demo-login',json={'token':TOKEN});csrf=first.json()['csrf_token']
    invalid=c.post('/api/auth/demo-login',json={'token':'b'*43},headers={'X-CSRF-Token':csrf})
    assert invalid.status_code==401
    assert c.get('/api/auth/session').json()['csrf_token']==csrf

def test_page_bootstrap_reuses_cookie_without_exposing_bearer_and_escapes_profile(demo):
    import json,re
    c,s=demo
    anonymous=c.get('/')
    extract=lambda page:json.loads(re.search(r'<script type="application/json" id="session-bootstrap">(.*?)</script>',page.text,re.S).group(1))
    assert extract(anonymous)['user'] is None
    assert 'demo_course_id' not in extract(anonymous)
    login=c.post('/api/auth/demo-login',json={'token':TOKEN});login.raise_for_status()
    token=c.cookies.get(s.auth_cookie_name)
    display='</script><script>alert("profile")</script>'
    c.app.state.store.execute('UPDATE users SET display_name=? WHERE id=?',(display,'demo'))
    page=c.get('/')
    assert extract(page)['user']['display_name']==display
    assert extract(page)['csrf_token']==login.json()['csrf_token']
    assert extract(page)['demo_course_id']=='demo-course'
    assert token not in page.text and display not in page.text
    assert page.headers['cache-control']=='no-store'
    assert '正在检查登录状态' not in page.text
    assert '正在打开工作空间' not in page.text
    assert 'Opening your workspace' not in page.text
    assert 'A demo link may switch away from a different account' in page.text

def test_demo_course_marker_requires_both_demo_identity_and_course_ownership(demo):
    import json,re
    c,s=demo
    login=c.post('/api/auth/demo-login',json={'token':TOKEN});login.raise_for_status()
    assert c.get('/api/auth/session').json()['demo_course_id']=='demo-course'
    s.demo_login_course_id='private-course'
    assert 'demo_course_id' not in c.get('/api/auth/session').json()
    page=c.get('/')
    payload=json.loads(re.search(r'<script type="application/json" id="session-bootstrap">(.*?)</script>',page.text,re.S).group(1))
    assert 'demo_course_id' not in payload

def test_demo_bearer_enters_with_existing_cookie_without_extra_status_check(demo):
    c,s=demo
    first=c.post('/api/auth/demo-login',json={'token':TOKEN})
    second=c.post('/api/auth/demo-login',json={'token':TOKEN})
    assert second.status_code==200 and second.json()['csrf_token']==first.json()['csrf_token']
    assert c.post('/api/auth/demo-login',json={'token':'b'*43}).status_code==401
    assert c.post('/api/auth/demo-login',json={'token':TOKEN},headers={'Origin':'https://evil.example'}).status_code==403

"""Local academic prototype. Start with: python server.py"""
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, unquote
import pandas as pd
from model import load_transactions, forecast

ROOT = Path(__file__).parent
DB = Path(os.environ.get('CASHFLOW_DB', str(ROOT / 'data' / 'app.sqlite3')))
DB.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(DB) as db:
    db.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE,password TEXT,salt TEXT,name TEXT);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER,expires REAL);
    CREATE TABLE IF NOT EXISTS datasets(user_id INTEGER PRIMARY KEY,months TEXT,metadata TEXT);''')

def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def respond(self, status, payload, cookie=None):
        body = json.dumps(payload, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def user(self, db):
        jar = cookies.SimpleCookie(self.headers.get('Cookie', ''))
        token = jar.get('session')
        return db.execute('SELECT u.id,u.email,u.name FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?', (token.value if token else '', time.time())).fetchone()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/me':
            with sqlite3.connect(DB) as db:
                u = self.user(db)
                data = db.execute('SELECT metadata FROM datasets WHERE user_id=?', (u[0],)).fetchone() if u else None
            return self.respond(200, {'user': {'email':u[1], 'name':u[2]} if u else None, 'dataset':json.loads(data[0]) if data else None})
        files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/style.css': ('style.css', 'text/css'), '/template.csv': ('template.csv', 'text/csv')}
        if path not in files:
            return self.respond(404, {'error':'Not found'})
        name, mime = files[path]
        content = (ROOT/'static'/name).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime+'; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        # Browser mutation requests must come from this origin and use our custom header.
        origin = self.headers.get('Origin')
        if (origin and origin != 'http://' + self.headers.get('Host','')) or self.headers.get('X-Cashflow-Request') != '1':
            return self.respond(403, {'error':'Invalid request origin.'})
        try:
            length = int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 30*1024*1024:
                return self.respond(413, {'error':'Upload must be between 1 byte and 30 MB.'})
            raw = self.rfile.read(length)
            path = urlparse(self.path).path
            body = {} if path == '/api/upload' else json.loads(raw)
            with sqlite3.connect(DB) as db:
                if path in ('/api/login','/api/register'):
                    email = str(body.get('email','')).strip().lower()
                    password = str(body.get('password',''))
                    if '@' not in email or len(email)>254 or not 8 <= len(password) <= 256:
                        raise ValueError('Enter a valid email and a password of 8–256 characters.')
                    if path == '/api/register':
                        name = str(body.get('name','')).strip()[:80]
                        if not name:
                            raise ValueError('Enter your shop name.')
                        salt = secrets.token_hex(16)
                        try:
                            db.execute('INSERT INTO users(email,password,salt,name) VALUES(?,?,?,?)',(email,password_hash(password,salt),salt,name))
                        except sqlite3.IntegrityError:
                            raise ValueError('An account with this email already exists. Sign in instead.')
                    row = db.execute('SELECT id,password,salt FROM users WHERE email=?',(email,)).fetchone()
                    if not row or not secrets.compare_digest(row[1],password_hash(password,row[2])):
                        return self.respond(401, {'error':'Email or password is incorrect.'})
                    token = secrets.token_urlsafe(32)
                    db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
                    db.execute('INSERT INTO sessions VALUES(?,?,?)',(token,row[0],time.time()+28800))
                    return self.respond(200, {'ok':True}, f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
                user = self.user(db)
                if not user:
                    return self.respond(401, {'error':'Please sign in to continue.'})
                if path == '/api/logout':
                    jar = cookies.SimpleCookie(self.headers.get('Cookie',''))
                    db.execute('DELETE FROM sessions WHERE token=?',(jar['session'].value,))
                    return self.respond(200, {'ok':True}, 'session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if path in ('/api/upload','/api/demo'):
                    if path == '/api/demo':
                        monthly = pd.read_csv(ROOT/'data'/'demo-monthly.csv', index_col=0, parse_dates=True).cashflow
                        meta = {'rows':51318,'duplicates':20,'filename':'Sample shop · 2011–2014','demo':True}
                    else:
                        filename = unquote(self.headers.get('X-Filename','upload.csv'))
                        monthly, meta = load_transactions(raw, filename)
                        meta.update(filename=Path(filename).name, demo=False)
                    meta.update(months=len(monthly), first=monthly.index[0].strftime('%Y-%m'), last=monthly.index[-1].strftime('%Y-%m'))
                    data = {d.strftime('%Y-%m-%d'):float(v) for d,v in monthly.items()}
                    db.execute('INSERT OR REPLACE INTO datasets VALUES(?,?,?)',(user[0],json.dumps(data),json.dumps(meta)))
                    return self.respond(200, meta)
                if path == '/api/forecast':
                    row = db.execute('SELECT months FROM datasets WHERE user_id=?',(user[0],)).fetchone()
                    if not row:
                        raise ValueError('Upload a dataset or load the sample first.')
                    data = json.loads(row[0])
                    monthly = pd.Series(list(data.values()), index=pd.to_datetime(list(data.keys()))).sort_index()
                    return self.respond(200, forecast(monthly,body.get('end','')))
                return self.respond(404, {'error':'Not found'})
        except (ValueError, KeyError, TypeError) as e:
            self.respond(400, {'error':str(e) or 'Invalid request.'})
        except Exception:
            self.respond(400, {'error':'Could not process this file. Check the format and try a valid Excel or CSV workbook.'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT','8000'))
    http = ThreadingHTTPServer(('127.0.0.1',port), Handler)
    if os.environ.get('SHOPFLOW_OPEN_BROWSER') == '1':
        import threading
        import webbrowser
        threading.Timer(0.5, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    print(f'ShopFlow is running at http://127.0.0.1:{port}', flush=True)
    http.serve_forever()

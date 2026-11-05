"""Persistent local watch metadata. No satellite rasters are stored in this database."""
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime,timezone
from .config import RUNTIME

def connect():
    RUNTIME.mkdir(exist_ok=True)
    db=sqlite3.connect(RUNTIME/'watch.sqlite',timeout=15)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS areas (id TEXT PRIMARY KEY, config TEXT NOT NULL, created REAL NOT NULL, next_due REAL NOT NULL, state TEXT NOT NULL, error TEXT, satellite TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, area_id TEXT NOT NULL, created REAL NOT NULL, payload TEXT NOT NULL)')
    db.execute('CREATE INDEX IF NOT EXISTS by_area_time ON snapshots(area_id,created)')
    if 'direct' not in [r[1] for r in db.execute('PRAGMA table_info(areas)')]:db.execute('ALTER TABLE areas ADD COLUMN direct TEXT')
    return db

def list_areas():
    with connect() as db:
        rows=db.execute('SELECT * FROM areas ORDER BY created').fetchall()
        result=[]
        for row in rows:
            item=dict(row);item['config']=json.loads(item['config']);item['satellite']=json.loads(item['satellite']) if item['satellite'] else None;item['direct']=json.loads(item['direct']) if item['direct'] else {}
            last=db.execute('SELECT id,created,payload FROM snapshots WHERE area_id=? ORDER BY id DESC LIMIT 1',(item['id'],)).fetchone()
            item['latest']={**json.loads(last['payload']),'snapshot_id':last['id']} if last else None
            result.append(item)
        return result

def get_area(identifier):
    return next((a for a in list_areas() if a['id']==identifier),None)

def create(config):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        count=db.execute('SELECT count(*) FROM areas').fetchone()[0]
        if count>=int(os.getenv('WATCH_MAX_AREAS','12')): raise ValueError('Watchlist is full. Remove an area before adding another.')
        identifier=secrets.token_hex(12)
        db.execute('INSERT INTO areas(id,config,created,next_due,state) VALUES(?,?,?,?,?)',(identifier,json.dumps(config),time.time(),time.time(),'queued'))
    return identifier

def state(identifier,value,error=None):
    with connect() as db:
        db.execute('UPDATE areas SET state=?,error=? WHERE id=?',(value,error,identifier))
        if value=='failed':db.execute('UPDATE areas SET next_due=? WHERE id=?',(time.time()+1800,identifier))

def set_enabled(identifier,enabled,auto_satellite=None):
    with connect() as db:
        row=db.execute('SELECT config FROM areas WHERE id=?',(identifier,)).fetchone()
        if not row:return False
        config=json.loads(row['config']);config['enabled']=enabled
        if auto_satellite is not None:config['auto_satellite']=auto_satellite
        db.execute('UPDATE areas SET config=?,next_due=?,state=? WHERE id=?',(json.dumps(config),time.time(),'queued' if enabled else 'paused',identifier))
        return True

def save_snapshot(identifier,payload,reschedule=True):
    with connect() as db:
        row=db.execute('SELECT config FROM areas WHERE id=?',(identifier,)).fetchone()
        if not row:return False
        config=json.loads(row['config'])
        db.execute('INSERT INTO snapshots(area_id,created,payload) VALUES(?,?,?)',(identifier,time.time(),json.dumps(payload,allow_nan=False)))
        if reschedule:db.execute('UPDATE areas SET next_due=? WHERE id=?',(time.time()+config['interval_hours']*3600,identifier))
        db.execute('UPDATE areas SET state=?,error=NULL WHERE id=?',('ready' if config['enabled'] else 'paused',identifier))
        db.execute('DELETE FROM snapshots WHERE area_id=? AND id NOT IN (SELECT id FROM snapshots WHERE area_id=? ORDER BY id DESC LIMIT 90)',(identifier,identifier))
        return True

def save_satellite(identifier,payload):
    payload.setdefault('checked_at',datetime.now(timezone.utc).isoformat())
    with connect() as db:db.execute('UPDATE areas SET satellite=? WHERE id=?',(json.dumps(payload,allow_nan=False),identifier))

def save_direct(identifier,provider,payload):
    with connect() as db:
        row=db.execute('SELECT direct FROM areas WHERE id=?',(identifier,)).fetchone()
        if not row:return
        data=json.loads(row['direct']) if row['direct'] else {};data[provider]=payload
        db.execute('UPDATE areas SET direct=? WHERE id=?',(json.dumps(data,allow_nan=False),identifier))

def history(identifier):
    with connect() as db:
        return [{**json.loads(r['payload']),'snapshot_id':r['id']} for r in db.execute('SELECT id,payload FROM snapshots WHERE area_id=? ORDER BY id DESC LIMIT 90',(identifier,)).fetchall()][::-1]

def remove(identifier):
    with connect() as db:
        db.execute('DELETE FROM snapshots WHERE area_id=?',(identifier,))
        return bool(db.execute('DELETE FROM areas WHERE id=?',(identifier,)).rowcount)

def recover():
    with connect() as db:db.execute("UPDATE areas SET state='queued' WHERE state IN ('checking','queued')")

"""SanitaSmart: API REST con SQLite, login e ruoli.

Avvio: python app.py
Account demo: admin@sanitasmart.test / Admin123!
              segreteria@sanitasmart.test / Segreteria123!
              medico@sanitasmart.test / Medico123!
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib, json, mimetypes, secrets, sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT=Path(__file__).parent; DATABASE=ROOT/"sanitasmart.db"
SLOTS=tuple(f"{h:02d}:{m:02d}" for h in range(9,18) for m in (0,30) if h!=13)

def required_text(data,*keys):
    if not isinstance(data,dict) or not all(isinstance(data.get(k),str) and data[k].strip() for k in keys):
        raise ValueError("Campi obbligatori mancanti o non validi: "+", ".join(keys))
    return {k:data[k].strip() for k in keys}

def patient_identifier(data):
    value=data.get("patientId")
    if isinstance(value,bool) or not isinstance(value,(int,str)):
        raise ValueError("Identificativo paziente non valido")
    try: value=int(value)
    except ValueError as exc: raise ValueError("Identificativo paziente non valido") from exc
    if value<1: raise ValueError("Identificativo paziente non valido")
    return value
def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+"$"+hashlib.pbkdf2_hmac("sha256",password.encode(),salt.encode(),100000).hex()
def valid_password(password,encoded):
    salt,_=encoded.split("$",1); return secrets.compare_digest(hash_password(password,salt),encoded)

class ClinicRepository:
    def __init__(self,database=DATABASE): self.database=str(database); self.initialize()
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.database); db.row_factory=sqlite3.Row; db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:yield db
        finally:db.close()
    def initialize(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','segreteria','medico')));
            CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL,phone TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY,patient_id INTEGER NOT NULL REFERENCES patients(id),doctor TEXT NOT NULL,specialty TEXT NOT NULL,date TEXT NOT NULL,time TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Confermata');
            CREATE UNIQUE INDEX IF NOT EXISTS active_doctor_slot ON appointments(doctor,date,time) WHERE status='Confermata';
            CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY,patient_id INTEGER NOT NULL REFERENCES patients(id),date TEXT NOT NULL,type TEXT NOT NULL,outcome TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Disponibile');""")
            if not db.execute("SELECT 1 FROM users").fetchone():
                db.executemany("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",[("Amministratore","admin@sanitasmart.test",hash_password("Admin123!"),"admin"),("Sara Segreteria","segreteria@sanitasmart.test",hash_password("Segreteria123!"),"segreteria"),("Dott.ssa Conti","medico@sanitasmart.test",hash_password("Medico123!"),"medico")])
                db.executemany("INSERT INTO patients(name,email,phone) VALUES(?,?,?)",[("Giulia Rossi","giulia.rossi@example.test","333 000 0101"),("Luca Bianchi","luca.bianchi@example.test","333 000 0102")])
                db.executemany("INSERT INTO appointments(patient_id,doctor,specialty,date,time) VALUES(?,?,?,?,?)",[(1,"Dott.ssa Conti","Cardiologia","2026-09-18","09:30"),(2,"Dott. Serra","Dermatologia","2026-09-19","15:00")])
                db.execute("INSERT INTO reports(patient_id,date,type,outcome) VALUES(?,?,?,?)",(1,"2026-09-05","ECG","Esame nei limiti"))
    @staticmethod
    def list(cursor): return [dict(row) for row in cursor.fetchall()]
    def authenticate(self,email,password):
        if not isinstance(email,str) or not isinstance(password,str):raise ValueError("Email e password devono essere stringhe")
        with self.connect() as db: user=db.execute("SELECT * FROM users WHERE email=?",(email.strip().lower(),)).fetchone()
        if not user or not valid_password(password,user["password_hash"]): raise PermissionError("Credenziali non valide")
        return {k:user[k] for k in ("id","name","email","role")}
    def dashboard(self):
        with self.connect() as db: return {"patients":db.execute("SELECT COUNT(*) FROM patients").fetchone()[0],"appointments":db.execute("SELECT COUNT(*) FROM appointments WHERE status='Confermata'").fetchone()[0],"reports":db.execute("SELECT COUNT(*) FROM reports").fetchone()[0],"today":datetime.now().strftime("%d/%m/%Y")}
    def patients(self):
        with self.connect() as db:return self.list(db.execute("SELECT id,name,email,phone FROM patients ORDER BY name"))
    def appointments(self):
        with self.connect() as db:return self.list(db.execute("SELECT a.id,a.patient_id patientId,p.name patientName,a.doctor,a.specialty,a.date,a.time,a.status FROM appointments a JOIN patients p ON p.id=a.patient_id ORDER BY a.date,a.time"))
    def reports(self):
        with self.connect() as db:return self.list(db.execute("SELECT r.id,r.patient_id patientId,p.name patientName,r.date,r.type,r.outcome,r.status FROM reports r JOIN patients p ON p.id=r.patient_id ORDER BY r.date DESC"))
    def add_patient(self,data):
        if not all(isinstance(data.get(k),str) and data[k].strip() for k in ("name","email","phone")):raise ValueError("nome, email e telefono sono obbligatori")
        record={k:data[k].strip() for k in ("name","email","phone")}
        with self.connect() as db:record["id"]=db.execute("INSERT INTO patients(name,email,phone) VALUES(:name,:email,:phone)",record).lastrowid
        return record
    def availability(self,doctor,date):
        if not doctor or not date:raise ValueError("medico e data sono obbligatori")
        date=datetime.strptime(date,"%Y-%m-%d").strftime("%Y-%m-%d")
        with self.connect() as db:booked={r[0] for r in db.execute("SELECT time FROM appointments WHERE doctor=? AND date=? AND status='Confermata'",(doctor,date))}
        return {"doctor":doctor,"date":date,"available":[s for s in SLOTS if s not in booked],"booked":sorted(booked)}
    def add_appointment(self,data):
        data={**data,**required_text(data,"doctor","specialty","date","time")}
        try:patient_id=patient_identifier(data);data["date"]=datetime.strptime(data["date"],"%Y-%m-%d").strftime("%Y-%m-%d");data["time"]=datetime.strptime(data["time"],"%H:%M").strftime("%H:%M")
        except (TypeError,ValueError) as exc:raise ValueError("paziente, data o ora non validi") from exc
        if data["time"] not in SLOTS:raise ValueError("Orario fuori dagli slot previsti")
        with self.connect() as db:
            patient=db.execute("SELECT name FROM patients WHERE id=?",(patient_id,)).fetchone()
            if not patient:raise LookupError("Paziente non trovato")
            try:ident=db.execute("INSERT INTO appointments(patient_id,doctor,specialty,date,time) VALUES(?,?,?,?,?)",(patient_id,data["doctor"].strip(),data["specialty"].strip(),data["date"],data["time"])).lastrowid
            except sqlite3.IntegrityError as exc:raise ValueError("Il medico ha gia una visita in questo orario") from exc
        return {"id":ident,"patientId":patient_id,"patientName":patient["name"],"doctor":data["doctor"].strip(),"specialty":data["specialty"].strip(),"date":data["date"],"time":data["time"],"status":"Confermata"}
    def cancel(self,ident):
        with self.connect() as db:
            if not db.execute("UPDATE appointments SET status='Annullata' WHERE id=?",(ident,)).rowcount:raise LookupError("Appuntamento non trovato")
        return {"id":ident,"status":"Annullata"}
    def add_report(self,data):
        data={**data,**required_text(data,"date","type","outcome")}
        try:patient_id=patient_identifier(data);data["date"]=datetime.strptime(data["date"],"%Y-%m-%d").strftime("%Y-%m-%d")
        except (TypeError,ValueError) as exc:raise ValueError("paziente o data non validi") from exc
        with self.connect() as db:
            patient=db.execute("SELECT name FROM patients WHERE id=?",(patient_id,)).fetchone()
            if not patient:raise LookupError("Paziente non trovato")
            ident=db.execute("INSERT INTO reports(patient_id,date,type,outcome) VALUES(?,?,?,?)",(patient_id,data["date"],data["type"].strip(),data["outcome"].strip())).lastrowid
        return {"id":ident,"patientId":patient_id,"patientName":patient["name"],"date":data["date"],"type":data["type"].strip(),"outcome":data["outcome"].strip(),"status":"Disponibile"}

class ApiHandler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):print("%s - %s"%(self.address_string(),fmt%args))
    def response(self,status,payload):
        if status==204:
            self.send_response(status);self.end_headers();return
        body=json.dumps(payload,ensure_ascii=False).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(body)));self.end_headers();self.wfile.write(body)
    def data(self):
        try:
            data=json.loads(self.rfile.read(int(self.headers.get("Content-Length",0))).decode())
            if not isinstance(data,dict):raise ValueError("Il corpo JSON deve essere un oggetto")
            return data
        except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise ValueError("Corpo JSON non valido") from exc
    def require(self,*roles):
        user=self.server.sessions.get(self.headers.get("Authorization","").removeprefix("Bearer "))
        if not user:raise PermissionError("Effettua l accesso per continuare")
        if roles and user["role"] not in roles:raise PermissionError("Il tuo ruolo non puo eseguire questa operazione")
        return user
    def static(self,path):
        target=(ROOT/"static"/path).resolve();base=(ROOT/"static").resolve()
        if (base not in target.parents and target!=base) or not target.is_file():return self.send_error(404)
        content=target.read_bytes();self.send_response(200);self.send_header("Content-Type",mimetypes.guess_type(str(target))[0] or "application/octet-stream");self.send_header("Content-Length",str(len(content)));self.end_headers();self.wfile.write(content)
    def do_GET(self):
        path=urlparse(self.path).path
        try:
            if path=="/api/me":return self.response(200,self.require())
            if path=="/api/dashboard":self.require();return self.response(200,self.server.repository.dashboard())
            if path=="/api/patients":self.require();return self.response(200,self.server.repository.patients())
            if path=="/api/appointments":self.require();return self.response(200,self.server.repository.appointments())
            if path=="/api/reports":self.require();return self.response(200,self.server.repository.reports())
            if path=="/api/availability":
                self.require();q=parse_qs(urlparse(self.path).query);return self.response(200,self.server.repository.availability(q.get("doctor",[""])[0],q.get("date",[""])[0]))
            return self.static("index.html" if path=="/" else path.lstrip("/"))
        except PermissionError as exc:return self.response(401,{"error":str(exc)})
        except ValueError as exc:return self.response(400,{"error":str(exc)})
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            if path=="/api/logout":
                self.server.sessions.pop(self.headers.get("Authorization","").removeprefix("Bearer "),None)
                return self.response(204,{})
            data=self.data()
            if path=="/api/login":
                user=self.server.repository.authenticate(data.get("email",""),data.get("password",""));token=secrets.token_urlsafe(32);self.server.sessions[token]=user;return self.response(200,{"token":token,"user":user})
            if path=="/api/patients":self.require("admin","segreteria");return self.response(201,self.server.repository.add_patient(data))
            if path=="/api/appointments":self.require("admin","segreteria");return self.response(201,self.server.repository.add_appointment(data))
            if path=="/api/reports":self.require("admin","medico");return self.response(201,self.server.repository.add_report(data))
            return self.response(404,{"error":"Endpoint non trovato"})
        except PermissionError as exc:return self.response(401,{"error":str(exc)})
        except LookupError as exc:return self.response(404,{"error":str(exc)})
        except ValueError as exc:return self.response(400,{"error":str(exc)})
    def do_PATCH(self):
        parts=urlparse(self.path).path.strip("/").split("/")
        try:
            if len(parts)==4 and parts[:2]==["api","appointments"] and parts[3]=="cancel":self.require("admin","segreteria");return self.response(200,self.server.repository.cancel(int(parts[2])))
            return self.response(404,{"error":"Endpoint non trovato"})
        except PermissionError as exc:return self.response(401,{"error":str(exc)})
        except (LookupError,ValueError) as exc:return self.response(404,{"error":str(exc)})
def create_server(port=8000,database=DATABASE):
    repository=ClinicRepository(database)
    server=ThreadingHTTPServer(("127.0.0.1",port),ApiHandler)
    server.repository=repository
    server.sessions={}
    return server

def run(port=8000):
    with create_server(port) as server:
        print(f"SanitaSmart disponibile su http://127.0.0.1:{server.server_port}")
        server.serve_forever()
if __name__=="__main__":run()

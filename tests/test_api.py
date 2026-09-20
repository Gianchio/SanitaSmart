"""Verifiche HTTP con database temporaneo indipendente per ogni prova."""
import concurrent.futures
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import shutil
import uuid
from http.client import HTTPConnection
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

class TestDirectory:
    """Cartella di prova locale con permessi ereditati, anche su Windows."""
    def __init__(self, **unused):
        self.root = Path(__file__).resolve().parent / '.tmp'
        self.root.mkdir(exist_ok=True)
        self.path = self.root / uuid.uuid4().hex
        self.path.mkdir()
        self.name = str(self.path)
    def cleanup(self):
        assert self.path.resolve().parent == self.root.resolve()
        shutil.rmtree(self.path)
    def __enter__(self):return self.name
    def __exit__(self, *args):self.cleanup()

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TestDirectory()
        self.database = Path(self.temp.name) / 'test.db'
        self.server = app.create_server(0, self.database)
        self.server.RequestHandlerClass.log_message = lambda *args: None
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.tokens = {}
        for role, password in (('admin', 'Admin123!'), ('segreteria', 'Segreteria123!'), ('medico', 'Medico123!')):
            status, data = self.request('POST', '/api/login', {'email': role + '@sanitasmart.test', 'password': password}, token=None)
            self.assertEqual(status, 200)
            self.tokens[role] = data['token']
        self.token = self.tokens['segreteria']

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, payload=None, token='default', raw=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Content-Type': 'application/json'}
        if token == 'default': token = self.token
        if token: headers['Authorization'] = 'Bearer ' + token
        body = raw if raw is not None else (json.dumps(payload) if payload is not None else None)
        try:
            conn.request(method, path, body, headers)
            response = conn.getresponse()
            content = response.read()
            return response.status, json.loads(content) if content else None
        finally: conn.close()

    def appointment(self, **changes):
        data = dict(patientId=1, doctor='Dott. Blu', specialty='Ortopedia', date='2026-10-01', time='10:00')
        return self.request('POST', '/api/appointments', {**data, **changes})

    def test_dashboard_and_read_routes(self):
        status, data = self.request('GET', '/api/dashboard')
        self.assertEqual((status, data['patients'], data['appointments'], data['reports']), (200, 2, 2, 1))
        for route in ('patients', 'appointments', 'reports'):
            status, rows = self.request('GET', '/api/' + route)
            self.assertEqual(status, 200)
            self.assertGreater(len(rows), 0)

    def test_anonymous_read_is_rejected(self):
        for route in ('me', 'dashboard', 'patients', 'appointments', 'reports', 'availability?doctor=X&date=2026-10-01'):
            with self.subTest(route=route): self.assertEqual(self.request('GET', '/api/' + route, token=None)[0], 401)

    def test_login_invalid_credentials_and_profile(self):
        self.assertEqual(self.request('POST', '/api/login', {'email': 'medico@sanitasmart.test', 'password': 'errata'}, token=None)[0], 401)
        status, user = self.request('GET', '/api/me')
        self.assertEqual((status, user['role']), (200, 'segreteria'))
        self.assertNotIn('password_hash', user)

    def test_patient_creation_and_persistence(self):
        status, patient = self.request('POST', '/api/patients', {'name': ' Anna Neri ', 'email': 'anna@example.test', 'phone': '333 000 0103'})
        self.assertEqual((status, patient['name']), (201, 'Anna Neri'))
        self.assertIn(patient, app.ClinicRepository(self.database).patients())

    def test_missing_patient_fields(self):
        for data in ({}, {'name': ''}, {'name': 'A', 'email': ' ', 'phone': '1'}):
            self.assertEqual(self.request('POST', '/api/patients', data)[0], 400)

    def test_booking_conflict_and_cancellation_releases_slot(self):
        status, appointment = self.appointment()
        self.assertEqual(status, 201)
        self.assertEqual(self.appointment()[0], 400)
        status, available = self.request('GET', '/api/availability?doctor=Dott.%20Blu&date=2026-10-01')
        self.assertIn('10:00', available['booked'])
        self.assertNotIn('10:00', available['available'])
        self.assertEqual(self.request('PATCH', f'/api/appointments/{appointment["id"]}/cancel')[0], 200)
        self.assertEqual(self.appointment()[0], 201)
        rows = self.request('GET', '/api/appointments')[1]
        self.assertEqual(next(a for a in rows if a['id'] == appointment['id'])['status'], 'Annullata')

    def test_competing_bookings_only_one_succeeds(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.appointment(), range(2)))
        self.assertEqual(sorted(status for status, _ in responses), [201, 400])

    def test_unknown_patient_and_appointment(self):
        self.assertEqual(self.appointment(patientId=99999)[0], 404)
        self.assertEqual(self.request('PATCH', '/api/appointments/99999/cancel')[0], 404)

    def test_date_time_normalization_prevents_duplicate(self):
        self.assertEqual(self.appointment(date='2026-10-1', time='9:00')[0], 201)
        self.assertEqual(self.appointment(date='2026-10-01', time='09:00')[0], 400)

    def test_invalid_or_out_of_schedule_slot(self):
        for change in (dict(time='13:00'), dict(time='10:15'), dict(time='25:00'), dict(date='2026-02-30')):
            with self.subTest(change=change): self.assertEqual(self.appointment(**change)[0], 400)

    def test_invalid_types_and_whitespace(self):
        for change in (dict(doctor=3), dict(doctor=' '), dict(specialty=[]), dict(patientId=True), dict(patientId=1.5)):
            with self.subTest(change=change): self.assertEqual(self.appointment(**change)[0], 400)
        self.assertEqual(self.request('POST', '/api/login', {'email': [], 'password': 3})[0], 400)

    def test_malformed_and_non_object_json(self):
        for raw in ('{', '[]', 'null', '"test"'):
            with self.subTest(raw=raw): self.assertEqual(self.request('POST', '/api/patients', raw=raw)[0], 400)

    def test_role_matrix(self):
        patient = {'name': 'Anna', 'email': 'anna@example.test', 'phone': '123'}
        report = {'patientId': 1, 'date': '2026-10-01', 'type': 'ECG', 'outcome': 'Esempio'}
        self.assertEqual(self.request('POST', '/api/patients', patient, token=self.tokens['medico'])[0], 401)
        self.assertEqual(self.request('PATCH', '/api/appointments/1/cancel', token=self.tokens['medico'])[0], 401)
        self.assertEqual(self.request('POST', '/api/reports', report)[0], 401)
        for role in ('medico', 'admin'):
            status, created = self.request('POST', '/api/reports', report, token=self.tokens[role])
            self.assertEqual((status, created['patientName']), (201, 'Giulia Rossi'))
        self.assertEqual(self.request('POST', '/api/patients', patient, token=self.tokens['admin'])[0], 201)

    def test_report_validation_and_missing_patient(self):
        report = dict(patientId=1, date='2026-10-01', type='ECG', outcome='Esempio')
        for changes, expected in ((dict(outcome=' '), 400), (dict(type=2), 400), (dict(patientId=9999), 404)):
            self.assertEqual(self.request('POST', '/api/reports', {**report, **changes}, token=self.tokens['medico'])[0], expected)

    def test_logout_revokes_token_preserves_other_sessions_and_database(self):
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        self.assertEqual(self.request('POST', '/api/logout'), (204, None))
        self.assertEqual(self.request('GET', '/api/me')[0], 401)
        self.assertEqual(self.request('GET', '/api/me', token=self.tokens['medico'])[0], 200)
        self.assertEqual(self.request('POST', '/api/logout'), (204, None))
        self.assertEqual(before, hashlib.sha256(self.database.read_bytes()).hexdigest())

    def test_sql_text_is_stored_as_data(self):
        name = "O'Brien'); DROP TABLE patients; --"
        self.assertEqual(self.request('POST', '/api/patients', {'name': name, 'email': 'test@example.test', 'phone': '1'})[0], 201)
        self.assertEqual(len(self.request('GET', '/api/patients')[1]), 3)

    def test_availability_validation(self):
        self.assertEqual(self.request('GET', '/api/availability')[0], 400)
        self.assertEqual(self.request('GET', '/api/availability?doctor=X&date=invalid')[0], 400)

    def test_server_restart_persists_data_but_not_sessions(self):
        status, patient = self.request('POST', '/api/patients', {'name': 'Persistente', 'email': 'p@example.test', 'phone': '1'})
        with app.create_server(0, self.database) as second:
            self.assertIn(patient, second.repository.patients())
            self.assertEqual(second.sessions, {})

    def test_static_page(self):
        conn = HTTPConnection('127.0.0.1', self.server.server_port)
        conn.request('GET', '/')
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        self.assertIn(b'SanitaSmart', response.read())
        conn.close()

class ImportTests(unittest.TestCase):
    def test_import_does_not_create_database(self):
        with TestDirectory() as directory:
            (Path(directory) / 'app.py').write_bytes(Path(app.__file__).read_bytes())
            subprocess.run([sys.executable, '-c', 'import app'], cwd=directory, check=True)
            self.assertFalse((Path(directory) / 'sanitasmart.db').exists())

if __name__ == '__main__': unittest.main()

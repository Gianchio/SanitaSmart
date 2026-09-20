"""Test del gestore logout senza importare app, avviare server o aprire SQLite.

Verifica anche la risposta senza corpo e la revoca della sola sessione corrente.
"""
import ast
import io
import json
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from types import SimpleNamespace


class LogoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).parents[1] / "app.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        handler = next(node for node in tree.body
                       if isinstance(node, ast.ClassDef) and node.name == "ApiHandler")
        cls.sessions = {}
        namespace = {"BaseHTTPRequestHandler": BaseHTTPRequestHandler,
                     "json": json, "urlparse": urlparse, "SESSIONS": cls.sessions}
        # Esegue soltanto la definizione del gestore: niente inizializzazione database.
        exec(compile(ast.Module(body=[handler], type_ignores=[]), str(source), "exec"), namespace)
        cls.handler_type = namespace["ApiHandler"]

    def setUp(self):
        self.sessions.clear()
        self.sessions.update({"current": {"role": "segreteria"},
                              "other": {"role": "medico"}})

    def request(self, body=b"", token="current", path="/api/logout"):
        handler = self.handler_type.__new__(self.handler_type)
        handler.path = path
        handler.server = SimpleNamespace(sessions=self.sessions)
        handler.headers = {"Content-Length": str(len(body))}
        if token is not None:
            handler.headers["Authorization"] = "Bearer " + token
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        status, headers = [], {}
        handler.send_response = status.append
        handler.send_header = lambda name, value: headers.update({name: value})
        handler.end_headers = lambda: None
        handler.do_POST()
        return handler, status[0], headers

    def test_empty_body_revokes_only_current_session(self):
        handler, status, headers = self.request()
        self.assertEqual(status, 204)
        self.assertNotIn("current", self.sessions)
        self.assertIn("other", self.sessions)
        self.assertEqual(handler.wfile.getvalue(), b"")
        self.assertNotIn("Content-Length", headers)
        with self.assertRaises(PermissionError):
            handler.require()

    def test_json_body_is_supported(self):
        _, status, _ = self.request(b"{}")
        self.assertEqual(status, 204)
        self.assertNotIn("current", self.sessions)

    def test_repeated_or_missing_token_is_harmless(self):
        self.request()
        for token in ("current", None):
            _, status, _ = self.request(token=token)
            self.assertEqual(status, 204)
        self.assertEqual(set(self.sessions), {"other"})

    def test_invalid_json_still_rejected_for_login(self):
        handler, status, _ = self.request(b"{", path="/api/login")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(handler.wfile.getvalue()), {"error": "Corpo JSON non valido"})
        self.assertIn("current", self.sessions)


if __name__ == "__main__":
    unittest.main()

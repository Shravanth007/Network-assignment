import importlib.util
from importlib.machinery import SourceFileLoader
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

_loader = SourceFileLoader("bserve", os.path.join(HERE, "bserve"))
spec = importlib.util.spec_from_file_location("bserve", _loader.path, loader=_loader)
bserve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bserve)

HOST = "127.0.0.1"
PORT = 9091


def connect():
    return socket.create_connection((HOST, PORT), timeout=5)


def send_request(conn, path, headers=None):
    path_bytes = path.encode("utf-8")
    body = bytes([0x00]) + len(path_bytes).to_bytes(2, "big") + path_bytes
    body += bserve.encode_headers(headers or [])
    bserve.write_frame(conn, bserve.FRAME_REQUEST, 0, body)


def read_response(conn):
    ftype, flags, payload = bserve.read_frame(conn)
    status = int.from_bytes(payload[0:2], "big")
    headers, offset = bserve.decode_headers(payload, 3, payload[2])
    body = payload[offset:]
    return ftype, status, dict(headers), body


class BServeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = tempfile.TemporaryDirectory()
        root = os.path.join(cls.tmpdir.name, "root")
        os.makedirs(os.path.join(root, "sub"))
        with open(os.path.join(root, "index.html"), "wb") as f:
            f.write(b"<html>hello</html>")
        with open(os.path.join(root, "sub", "page.txt"), "wb") as f:
            f.write(b"nested file")
        with open(os.path.join(cls.tmpdir.name, "outside.txt"), "wb") as f:
            f.write(b"should never be served")

        cls.proc = subprocess.Popen(
            [sys.executable, os.path.join(HERE, "bserve"), root, str(PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                connect().close()
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError("bserve did not start listening in time")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.tmpdir.cleanup()

    def test_200_serves_file(self):
        conn = connect()
        send_request(conn, "/index.html")
        ftype, status, headers, body = read_response(conn)
        self.assertEqual(ftype, bserve.FRAME_RESPONSE)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"<html>hello</html>")
        self.assertEqual(headers["content-type"], "text/html")
        self.assertEqual(headers["content-length"], str(len(body)))
        conn.close()

    def test_root_path_maps_to_index(self):
        conn = connect()
        send_request(conn, "/")
        _, status, _, body = read_response(conn)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"<html>hello</html>")
        conn.close()

    def test_nested_file(self):
        conn = connect()
        send_request(conn, "/sub/page.txt")
        _, status, headers, body = read_response(conn)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"nested file")
        self.assertEqual(headers["content-type"], "text/plain")
        conn.close()

    def test_404_missing_file(self):
        conn = connect()
        send_request(conn, "/nope.html")
        _, status, _, body = read_response(conn)
        self.assertEqual(status, 404)
        conn.close()

    def test_404_path_traversal_blocked(self):
        conn = connect()
        send_request(conn, "/../outside.txt")
        _, status, _, _ = read_response(conn)
        self.assertEqual(status, 404)
        conn.close()

    def test_404_cross_drive_path_does_not_crash(self):
        conn = connect()
        send_request(conn, "/D:/x")
        _, status, _, _ = read_response(conn)
        self.assertEqual(status, 404)
        send_request(conn, "/index.html")
        _, status2, _, _ = read_response(conn)
        self.assertEqual(status2, 200)
        conn.close()

    def test_400_short_frame(self):
        conn = connect()
        bserve.write_frame(conn, bserve.FRAME_REQUEST, 0, b"\xff\xff")
        _, status, _, _ = read_response(conn)
        self.assertEqual(status, 400)
        conn.close()

    def test_400_bad_method(self):
        conn = connect()
        body = bytes([0x7f]) + (0).to_bytes(2, "big") + bserve.encode_headers([])
        bserve.write_frame(conn, bserve.FRAME_REQUEST, 0, body)
        _, status, _, _ = read_response(conn)
        self.assertEqual(status, 400)
        conn.close()

    def test_400_invalid_utf8_path(self):
        conn = connect()
        body = bytes([0x00]) + (2).to_bytes(2, "big") + b"\xff\xfe" + bytes([0])
        bserve.write_frame(conn, bserve.FRAME_REQUEST, 0, body)
        _, status, _, _ = read_response(conn)
        self.assertEqual(status, 400)
        conn.close()

    def test_400_keeps_connection_open(self):
        conn = connect()
        bserve.write_frame(conn, bserve.FRAME_REQUEST, 0, b"\xff\xff")
        _, status, _, _ = read_response(conn)
        self.assertEqual(status, 400)
        send_request(conn, "/index.html")
        _, status2, _, _ = read_response(conn)
        self.assertEqual(status2, 200)
        conn.close()

    def test_unknown_frame_type_is_skipped(self):
        conn = connect()
        bserve.write_frame(conn, 0x7E, 0, b"hello")
        send_request(conn, "/index.html")
        _, status, _, body = read_response(conn)
        self.assertEqual(status, 200)
        self.assertEqual(body, b"<html>hello</html>")
        conn.close()

    def test_connection_serves_many_requests(self):
        conn = connect()
        for _ in range(10):
            send_request(conn, "/index.html")
            _, status, _, _ = read_response(conn)
            self.assertEqual(status, 200)
        conn.close()

    def test_server_accepts_a_new_connection_after_one_closes(self):
        conn1 = connect()
        send_request(conn1, "/index.html")
        read_response(conn1)
        conn1.close()

        conn2 = connect()
        send_request(conn2, "/index.html")
        _, status, _, _ = read_response(conn2)
        self.assertEqual(status, 200)
        conn2.close()


if __name__ == "__main__":
    unittest.main()

"""Exercise the optional server through real local HTTP and MCP transports."""

import asyncio
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from mcp import Client, StdioServerParameters
import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def write_pdf(path, texts):
    with pymupdf.open() as document:
        for text in texts:
            document.new_page().insert_text((72, 72), text)
        document.save(path)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.process = subprocess.Popen(
            [sys.executable, str(ROOT / "bok_server.py"), "--data-dir", str(self.folder),
             "--port", str(self.port)], cwd=self.folder,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        self.addCleanup(self.stop_server)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.fail(self.process.stderr.read())
            try:
                with urlopen(self.base + "/", timeout=1):
                    break
            except URLError:
                time.sleep(.05)
        else:
            self.fail("local server did not become ready")
        connect = socket.socket.connect

        def local_connect(sock, address):
            if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "localhost", "::1"}:
                raise AssertionError("External network forbidden in server tests")
            return connect(sock, address)

        network = patch.object(socket.socket, "connect", local_connect)
        network.start()
        self.addCleanup(network.stop)

    def stop_server(self):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate(timeout=5)

    def request(self, path, headers=None):
        try:
            response = urlopen(Request(self.base + path, headers=headers or {}), timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read().decode("utf-8"), response.headers

    def search_http(self, **params):
        code, body, _ = self.request("/api/search?" + urlencode(params))
        return code, json.loads(body)

    async def search_mcp(self, query="policy", limit=5, mode="auto"):
        async with Client(self.base + "/mcp", mode=mode) as client:
            tools = await client.list_tools()
            self.assertEqual([tool.name for tool in tools.tools], ["search_pdf"])
            self.assertTrue(tools.tools[0].annotations.read_only_hint)
            return await client.call_tool("search_pdf", {"query": query, "limit": limit})

    def test_cli_http_and_both_mcp_protocols_return_identical_evidence(self):
        write_pdf(self.folder / "policy.pdf", ["unrelated", "Rate policy has changed."])
        cli = subprocess.run([sys.executable, str(ROOT / "bok_cli.py"), "search", "RATE policy",
                              "--limit", "1", "--data-dir", str(self.folder)],
                             capture_output=True, text=True, check=True, timeout=10)
        expected = json.loads(cli.stdout)
        code, actual = self.search_http(query="RATE policy", limit=1)
        self.assertEqual(code, 200)
        self.assertEqual(actual, expected)
        for mode in ("auto", "legacy"):
            with self.subTest(mode=mode):
                mcp = asyncio.run(self.search_mcp("RATE policy", 1, mode))
                self.assertFalse(mcp.is_error)
                self.assertEqual(mcp.structured_content, expected)
        self.assertEqual(actual["results"][0]["page"], 2)
        self.assertEqual(actual["results"][0]["source"], "policy.pdf")
        self.assertIsNone(actual["results"][0]["published_at"])

    def test_empty_corpus_and_no_matches_are_not_tool_errors(self):
        for expected in ("empty_corpus", "no_matches"):
            if expected == "no_matches":
                write_pdf(self.folder / "other.pdf", ["unrelated"])
            with self.subTest(expected=expected):
                code, result = self.search_http(query="policy")
                self.assertEqual(code, 200)
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["results"], [])
                mcp = asyncio.run(self.search_mcp())
                self.assertFalse(mcp.is_error)
                self.assertEqual(mcp.structured_content, result)

    def test_invalid_http_inputs_are_json_errors(self):
        for params in ({}, {"query": " "}, {"query": "x", "limit": "bad"},
                       {"query": "x", "limit": 0}, {"query": "x", "limit": 21},
                       {"query": "x" * 501}, {"query": "x", "data_dir": "/tmp"}):
            with self.subTest(params=params):
                code, result = self.search_http(**params)
                self.assertEqual(code, 400)
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "invalid_input")

    def test_invalid_mcp_inputs_are_tool_errors(self):
        for query, limit in (("", 5), (" ", 5), ("x" * 501, 5), ("x", 0),
                             ("x", 21), ("x", True), ("x", "1")):
            with self.subTest(query=query[:10], limit=limit):
                result = asyncio.run(self.search_mcp(query, limit))
                self.assertTrue(result.is_error)

    def test_broken_pdf_fails_without_partial_evidence(self):
        write_pdf(self.folder / "good.pdf", ["policy"])
        (self.folder / "broken.pdf").write_bytes(b"not a PDF")
        code, result = self.search_http(query="policy")
        self.assertEqual(code, 400)
        self.assertNotIn("results", result)
        self.assertIn("broken.pdf", result["error"]["message"])
        mcp = asyncio.run(self.search_mcp())
        self.assertTrue(mcp.is_error)
        self.assertIsNone(mcp.structured_content)

    def test_host_origin_and_file_access_are_restricted(self):
        for path in ("/", "/api/search?query=policy", "/mcp"):
            for headers in ({"Host": "outside.example"}, {"Origin": "https://outside.example"},
                            {"Origin": "null"}, {"Origin": "http://localhost:1"}):
                with self.subTest(path=path, headers=headers):
                    code, body, _ = self.request(path, headers)
                    self.assertEqual(code, 403)
                    self.assertEqual(json.loads(body)["error"]["code"], "forbidden")
        code, body, headers = self.request("/api/search?query=policy", {"Origin": self.base})
        self.assertEqual(code, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        for path in ("/.env", "/bok_server.py", "/../README.md", "/data/policy.pdf"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)

    def test_stdio_is_clean_even_when_pdf_needs_repair(self):
        path = self.folder / "repaired.pdf"
        write_pdf(path, ["policy evidence"])
        original = path.read_bytes()
        path.write_bytes(original[:original.rfind(b"startxref")] + b"startxref\n0\n%%EOF\n")

        async def run():
            params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "bok_server.py"),
                                           "--transport", "stdio", "--data-dir", str(self.folder)],
                                           cwd=str(self.folder))
            async with Client(params) as client:
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 1)
                return await client.call_tool("search_pdf", {"query": "policy"})

        result = asyncio.run(run())
        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["results"][0]["source"], "repaired.pdf")
        self.assertIn("policy evidence", result.structured_content["results"][0]["text"])


if __name__ == "__main__":
    unittest.main()

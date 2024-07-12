import contextlib
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import cycle

import pytest

import vastdb.errors

log = logging.getLogger(__name__)


def test_hello_world(session):
    with session.transaction() as tx:
        assert tx.txid is not None


def test_bad_credentials(session):
    bad_session = vastdb.connect(access='BAD', secret='BAD', endpoint=session.api.url)
    with pytest.raises(vastdb.errors.Forbidden):
        with bad_session.transaction():
            pass


def test_bad_endpoint(session):
    backoff_config = vastdb.config.BackoffConfig(max_tries=3)
    with pytest.raises(vastdb.errors.ConnectionError):
        vastdb.connect(access='BAD', secret='BAD', endpoint='http://invalid-host-name-for-tests:12345', backoff_config=backoff_config)


def test_version_extraction():
    # A list of version and expected version parsed by API
    TEST_CASES = [
            (None, None),                                   # vast server without version in header
            ("5", None),                                    # major
            ("5.2", None),                                  # major.minor
            ("5.2.0", None),                                # major.minor.patch
            ("5.2.0.10", (5, 2, 0, 10)),                    # major.minor.patch.protocol
            ("5.2.0.10 some other things", None),           # suffix
            ("5.2.0.10.20", None),                          # extra version
    ]

    # Mock OPTIONS handle that cycles through the test cases response
    class MockOptionsHandler(BaseHTTPRequestHandler):
        versions_iterator = cycle(TEST_CASES)

        def __init__(self, *args) -> None:
            super().__init__(*args)

        def do_OPTIONS(self):
            self.send_response(204)
            self.end_headers()

        def version_string(self):
            version = next(self.versions_iterator)[0]
            return f"vast {version}" if version else "vast"

        def log_message(self, format, *args):
            log.debug(format, *args)

    # start the server on localhost on some available port port
    server_address = ('localhost', 0)
    httpd = HTTPServer(server_address, MockOptionsHandler)

    def start_http_server_in_thread():
        log.info(f"Mock HTTP server is running on port {httpd.server_port}")
        httpd.serve_forever()
        log.info("Mock HTTP server killed")

    # start the server in a thread so we have the main thread to operate the API
    server_thread = threading.Thread(target=start_http_server_in_thread)
    server_thread.start()

    try:
        for _, expected in TEST_CASES:
            with (pytest.raises(NotImplementedError) if expected is None else contextlib.nullcontext()):
                s = vastdb.connect(endpoint=f"http://localhost:{httpd.server_port}", access="abc", secret="abc")
                assert s.api.vast_version == expected
    finally:
        # make sure we shut the server down no matter what
        httpd.shutdown()

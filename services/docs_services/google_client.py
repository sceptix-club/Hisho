import socket

import httplib2
from google_auth_httplib2 import AuthorizedHttp
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config import Settings


class IPv4HTTPConnection(httplib2.HTTPConnectionWithTimeout):
    """Force IPv4 so we never get stuck on a blackholed IPv6 route.

    httplib2 resolves Google to an IPv6 address first in this environment and
    the IPv6 path to Google is unreachable, so connections time out. Forcing
    AF_INET uses the working IPv4 route (which curl reaches fine).
    """

    def connect(self):
        sock = None
        err = None
        for res in socket.getaddrinfo(
            self.host, self.port, socket.AF_INET, socket.SOCK_STREAM
        ):
            af, socktype, proto, _canonname, sa = res
            try:
                sock = socket.socket(af, socktype, proto)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                if self.timeout:
                    sock.settimeout(self.timeout)
                sock.connect(sa)
                break
            except socket.error as e:
                err = e
                if sock is not None:
                    sock.close()
                sock = None
        if sock is None:
            raise err
        self.sock = sock


class IPv4HTTPSConnection(httplib2.HTTPSConnectionWithTimeout):
    def connect(self):
        sock = None
        err = None
        for res in socket.getaddrinfo(
            self.host, self.port, socket.AF_INET, socket.SOCK_STREAM
        ):
            af, socktype, proto, _canonname, sa = res
            try:
                sock = socket.socket(af, socktype, proto)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                if self.timeout:
                    sock.settimeout(self.timeout)
                sock.connect(sa)
                break
            except socket.error as e:
                err = e
                if sock is not None:
                    sock.close()
                sock = None
        if sock is None:
            raise err
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class IPv4Http(httplib2.Http):
    """httplib2.Http that uses the IPv4 connection classes above."""

    def request(
        self,
        uri,
        method="GET",
        body=None,
        headers=None,
        redirections=httplib2.DEFAULT_MAX_REDIRECTS,
        connection_type=None,
        *args,
        **kwargs,
    ):
        if connection_type is None:
            scheme = uri.split(":", 1)[0]
            connection_type = (
                IPv4HTTPSConnection if scheme == "https" else IPv4HTTPConnection
            )
        return super().request(
            uri, method, body, headers, redirections, connection_type, *args, **kwargs
        )


class GoogleUserClient:
    def __init__(self, settings: Settings, access_token: str, refresh_token: str):
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.client_id,
            client_secret=settings.client_secret,
        )
        self.creds = creds
        http = IPv4Http(timeout=30)
        authed_http = AuthorizedHttp(creds, http=http)
        self.service = build("docs", "v1", http=authed_http)
        self.drive_service = build("drive", "v3", http=authed_http)

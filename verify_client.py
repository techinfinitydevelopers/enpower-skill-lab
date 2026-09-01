"""
A test client that always speaks HTTPS.

With `SECURE_SSL_REDIRECT` on — which is the case wherever DEBUG is off —
Django answers a plain HTTP request with a 301 before any view runs. A suite
using the stock test client therefore tests the redirect, not the application:
locally, where DEBUG is on, everything passes; on the deployed host the same
suite reports failures that have nothing to do with the code being checked.

Passing `secure=True` to every single call is easy to forget, so the default
lives here instead.
"""

from django.test import Client


class HttpsClient(Client):
    """Stock test client with `secure=True` as the default on every request."""

    def generic(self, method, path, *args, **kwargs):
        kwargs.setdefault('secure', True)
        return super().generic(method, path, *args, **kwargs)

    def get(self, path, *args, **kwargs):
        kwargs.setdefault('secure', True)
        return super().get(path, *args, **kwargs)

    def post(self, path, *args, **kwargs):
        kwargs.setdefault('secure', True)
        return super().post(path, *args, **kwargs)

    def head(self, path, *args, **kwargs):
        kwargs.setdefault('secure', True)
        return super().head(path, *args, **kwargs)

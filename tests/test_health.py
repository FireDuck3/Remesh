def test_healthz_returns_ok(client):
    r = client.get("/healthz/")
    assert r.status_code == 200
    assert r.content == b"ok"


def test_healthz_does_not_validate_the_host(client, settings):
    """The platform probes with an internal Host/IP that is not in ALLOWED_HOSTS."""
    settings.ALLOWED_HOSTS = ["example.com"]
    assert client.get("/healthz/", HTTP_HOST="10.0.0.5").status_code == 200
    assert client.get("/cart/", HTTP_HOST="10.0.0.5").status_code == 400  # every other page still checks it


def test_healthz_answers_plain_http_when_https_is_enforced(client, settings):
    settings.ALLOWED_HOSTS = ["example.com"]
    settings.SECURE_SSL_REDIRECT = True
    settings.SECURE_REDIRECT_EXEMPT = []  # the answer must not depend on the redirect exemption
    r = client.get("/healthz/", HTTP_HOST="10.0.0.5")
    assert r.status_code == 200 and r.content == b"ok"
    assert client.get("/cart/", HTTP_HOST="example.com").status_code == 301  # the redirect itself is still on

from fastapi.testclient import TestClient

from cte import __version__
from cte.api import app


def test_release_version_is_unified():
    client=TestClient(app)
    assert __version__ == "2.6.0-rc1"
    assert app.version == __version__
    assert client.get("/health").json()["version"] == __version__
    assert client.get("/openapi.json").json()["info"]["version"] == __version__
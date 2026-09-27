from fastapi.testclient import TestClient
from cte.api import app


def test_science_lab_ui_is_served():
    client=TestClient(app)
    response=client.get("/science-lab/ui")
    assert response.status_code==200
    assert "Science Lab" in response.text


def test_science_lab_assets_are_served():
    client=TestClient(app)
    response=client.get("/science-lab/assets/app.js")
    assert response.status_code==200
    assert "runScenario" in response.text

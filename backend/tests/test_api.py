"""
End-to-end API test: upload two real GeoTIFFs, run change detection through
the controller, fetch the evidence overlay and download the report.
Needs fastapi, httpx and rasterio (all in requirements.txt). No ML model is
loaded, so it runs quickly.
"""

import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

fastapi_testclient = pytest.importorskip("fastapi.testclient")


def _tif_bytes(data):
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff", height=data.shape[1], width=data.shape[2],
            count=data.shape[0], dtype="uint16", crs="EPSG:4326",
            transform=from_origin(77.0, 28.0, 0.0001, 0.0001),
        ) as dst:
            dst.write(data)

        return memory.read()


@pytest.fixture
def client(tmp_path, monkeypatch):
    # uploads/ is relative to the working directory; keep it out of the repo.
    monkeypatch.chdir(tmp_path)

    from backend.app.main import app

    return fastapi_testclient.TestClient(app)


def _upload(client, name, data):
    response = client.post(
        "/inspect-raster",
        files={"file": (name, _tif_bytes(data), "image/tiff")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_change_detection_end_to_end_with_overlay_and_report(client):
    rng = np.random.default_rng(0)
    before = rng.integers(500, 1500, (3, 64, 64)).astype("uint16")
    after = before.copy()
    after[:, 20:40, 30:50] += 3000

    first = _upload(client, "scene_20230101.tif", before)
    _upload(client, "scene_20240101.tif", after)

    assert first["metadata"]["modality"] == "OPTICAL"
    assert first["metadata"]["acquisition_date"] == "2023-01-01"

    response = client.post(
        "/analyze",
        json={
            "query": "What changed between the two dates?",
            "image_id": "scene_20230101.tif",
            "image_id_2": "scene_20240101.tif",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["task"] == "CHANGE"
    assert "Detected 1 changed region" in body["answer"]
    assert "about" in body["answer"]  # georeferenced, so an area is reported
    assert [item["kind"] for item in body["evidence"]] == ["mask", "bbox"]
    assert body["evidence"][1]["bbox"] == [30, 20, 50, 40]
    assert len(body["analysis_id"]) == 32

    overlay = client.get(f"/preview/{body['overlay']}")
    assert overlay.status_code == 200
    assert overlay.content[:4] == b"\x89PNG"

    report = client.get(f"/report/{body['analysis_id']}")
    assert report.status_code == 200
    assert "attachment" in report.headers["content-disposition"]
    assert "Detected 1 changed region" in report.text
    assert "data:image/png;base64," in report.text
    assert "change-detection" in report.text


def test_blocked_request_still_gets_a_report(client):
    data = np.random.default_rng(1).integers(0, 255, (3, 32, 32)).astype("uint16")
    _upload(client, "only.tif", data)

    body = client.post(
        "/analyze",
        json={"query": "What changed?", "image_id": "only.tif"},
    ).json()

    assert body["answer"].startswith("I can't run CHANGE")
    assert body["evidence"] == [] and body["overlay"] is None
    assert client.get(f"/report/{body['analysis_id']}").status_code == 200


def test_unknown_report_and_compatibility(client):
    assert client.get("/report/" + "0" * 32).status_code == 404
    assert client.get("/report/not-an-id").status_code == 404

    data = np.random.default_rng(2).integers(0, 255, (3, 32, 32)).astype("uint16")
    _upload(client, "a_20230101.tif", data)
    _upload(client, "a_20240101.tif", data)

    pair = client.get(
        "/compatibility",
        params={"image_id": "a_20230101.tif", "image_id_2": "a_20240101.tif"},
    ).json()["pair"]

    assert pair["co_registered"] is True
    assert pair["pair_type"] == "BITEMPORAL"


def _sar_tif_bytes(data):
    with MemoryFile() as memory:
        with memory.open(
            driver="GTiff", height=data.shape[0], width=data.shape[1],
            count=1, dtype="float32", crs="EPSG:32643",
            transform=from_origin(500000.0, 3100000.0, 10.0, 10.0),
        ) as dst:
            dst.write(data.astype("float32"), 1)

        return memory.read()


def test_sar_water_mapping_end_to_end(client):
    rng = np.random.default_rng(0)
    mean = np.full((128, 128), 0.1)
    mean[32:96, 16:80] *= 10 ** (-12 / 10)  # a lake, 12 dB darker than land
    data = mean * rng.gamma(4, 0.25, mean.shape)

    upload = client.post(
        "/inspect-raster",
        files={"file": ("s1_vv_20240101.tif", _sar_tif_bytes(data), "image/tiff")},
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["metadata"]["modality"] == "SAR"

    body = client.post(
        "/analyze",
        json={
            "query": "Where is the water in this SAR image?",
            "image_id": "s1_vv_20240101.tif",
        },
    ).json()

    assert body["task"] == "SAR"
    assert body["answer"].startswith("Low-backscatter (water-like) surfaces cover 25")
    assert "hectares" in body["answer"]  # 4,096 px x 100 sq. m
    assert body["evidence"][0]["kind"] == "mask"
    assert client.get(f"/preview/{body['overlay']}").status_code == 200
    assert "sar-analysis" in client.get(f"/report/{body['analysis_id']}").text

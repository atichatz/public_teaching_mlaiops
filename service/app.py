"""Lab 3 — inference service.

Provider-neutral by construction: the model arrives through the adapter, and the same
container image deploys to SageMaker, Azure ML, or Vertex AI. Route paths differ per
platform; that difference belongs in cloudlayer/, never here.

Run locally:  uvicorn service.app:app --port 8080
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from service.schemas import BatchRequest, BatchResponse, PredictRequest, PredictResponse
from src.data import FEATURES

logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}',
)
log = logging.getLogger("service")

STATE: dict[str, Any] = {"model": None, "version": os.environ.get("MODEL_VERSION", "unknown")}
PREDICTION_DELAY_MS = float(os.environ.get("PREDICTION_DELAY_MS", "0"))
FEATURE_WINDOW_SIZE = 100
FEATURE_WINDOWS = {feature: deque(maxlen=FEATURE_WINDOW_SIZE) for feature in FEATURES}

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the prediction service.",
    ["method", "path", "status_class"],
)
REQUEST_LATENCY = Histogram(
    "request_latency_ms",
    "Prediction service request latency in milliseconds.",
    ["path"],
    buckets=(5, 10, 25, 50, 100, 200, 500, 1000, 2500, 5000),
)
FEATURE_ROLLING_MEAN = Gauge(
    "feature_rolling_mean",
    f"Mean feature value over the most recent {FEATURE_WINDOW_SIZE} prediction rows.",
    ["feature"],
)
MODEL_VERSION_INFO = Gauge(
    "model_version_info",
    "Currently loaded model version.",
    ["version"],
)

def _load_model():
    """Load one registered model version once during application startup."""
    from pathlib import Path

    import joblib

    artifact_uri = os.environ.get("MODEL_ARTIFACT_URI")
    if artifact_uri:
        import tempfile

        from cloudlayer.factory import get_adapter
        from src import config

        cfg = config.load()
        cache_dir = Path(tempfile.mkdtemp(prefix="itcs355-model-"))
        local_model = cache_dir / "model.joblib"
        get_adapter(cfg).download(artifact_uri, str(local_model))
        return joblib.load(local_model)

    name = os.environ.get("MODEL_REGISTRY_NAME")
    version = os.environ.get("MODEL_VERSION")

    if name and version:
        import tempfile

        from cloudlayer.factory import get_adapter
        from src import config

        cfg = config.load()
        adapter = get_adapter(cfg)

        registered = adapter.resolve_registered_model(
            name=name,
            version=version,
        )

        model_uri = (
            registered["artifact_uri"].rstrip("/")
            + "/model.joblib"
        )

        cache_dir = Path(tempfile.mkdtemp(prefix="itcs355-model-"))
        local_model = cache_dir / "model.joblib"

        adapter.download(model_uri, str(local_model))
        return joblib.load(local_model)

    # Local development and automated tests only.
    path = Path(
        os.environ.get(
            "MODEL_PATH",
            "reports/model.joblib",
        )
    )

    if not path.exists():
        raise RuntimeError(
            "No model available. Set MODEL_REGISTRY_NAME and "
            "MODEL_VERSION for cloud deployment, or MODEL_PATH locally."
        )

    return joblib.load(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        STATE["model"] = _load_model()
        MODEL_VERSION_INFO.labels(version=str(STATE["version"])).set(1)
        log.info('"model loaded, version=%s"', STATE["version"])
    except Exception as exc:  # readiness stays false; liveness still passes
        STATE["model"] = None
        log.error('"model load failed: %s"', exc)
    yield
    STATE["model"] = None


app = FastAPI(title="ITCS355 inference", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000
        HTTP_REQUESTS.labels(
            method=request.method,
            path=request.url.path,
            status_class="5xx",
        ).inc()
        REQUEST_LATENCY.labels(path=request.url.path).observe(latency_ms)
        raise

    latency_ms = (time.perf_counter() - started) * 1000
    HTTP_REQUESTS.labels(
        method=request.method,
        path=request.url.path,
        status_class=f"{response.status_code // 100}xx",
    ).inc()
    REQUEST_LATENCY.labels(path=request.url.path).observe(latency_ms)
    response.headers["x-request-id"] = request_id
    response.headers["x-model-version"] = str(STATE["version"])
    log.info(
        '{"request_id":"%s","path":"%s","status":%d,"latency_ms":%.2f,"model_version":"%s"}',
        request_id, request.url.path, response.status_code, latency_ms, STATE["version"],
    )
    return response


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness. The process is up. Says nothing about whether it can serve."""
    return {"status": "alive"}


@app.get("/ready")
def ready():
    """Readiness. The model is loaded and can score.

    These two are genuinely different, and confusing them causes a specific production
    failure: traffic routed to a container whose model has not finished loading. All three
    providers distinguish them, and Quiz 3 asks about it.
    """
    if STATE["model"] is None:
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "model not loaded"})
    return {"status": "ready", "model_version": STATE["version"]}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus scrape endpoint for service and model telemetry."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _record_feature_statistics(rows: list[dict]) -> None:
    """Update rolling feature means from the most recent prediction inputs."""
    for row in rows:
        for feature in FEATURES:
            FEATURE_WINDOWS[feature].append(float(row[feature]))

    for feature, values in FEATURE_WINDOWS.items():
        if values:
            FEATURE_ROLLING_MEAN.labels(feature=feature).set(sum(values) / len(values))


def _score(rows: list[dict]) -> list[float]:
    if STATE["model"] is None:
        raise HTTPException(status_code=503, detail="model not loaded")

    if PREDICTION_DELAY_MS > 0:
        time.sleep(PREDICTION_DELAY_MS / 1000)

    import pandas as pd

    from src.data import FEATURES

    frame = pd.DataFrame(rows)[FEATURES]
    _record_feature_statistics(rows)
    return [float(p) for p in STATE["model"].predict_proba(frame)[:, 1]]


@app.post("/predict", response_model=PredictResponse)
def predict(payload: PredictRequest) -> PredictResponse:
    score = _score([payload.model_dump()])[0]
    return PredictResponse(probability=score, model_version=str(STATE["version"]))


@app.post("/predict/batch", response_model=BatchResponse)
def predict_batch(payload: BatchRequest) -> BatchResponse:
    scores = _score([row.model_dump() for row in payload.rows])
    return BatchResponse(probabilities=scores, model_version=str(STATE["version"]))

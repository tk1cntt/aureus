def test_trades_contract_envelope_and_order_deterministic(client):
    params = {
        "symbol": "XAUUSD",
        "strategy_id": 10,
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-02T00:00:00+00:00",
        "status": "CLOSED",
        "page": 1,
        "page_size": 20,
    }

    response_1 = client.get("/api/v1/performance/trades", params=params)
    response_2 = client.get("/api/v1/performance/trades", params=params)

    assert response_1.status_code == 200
    assert response_2.status_code == 200

    body_1 = response_1.json()
    body_2 = response_2.json()

    assert "data" in body_1 and isinstance(body_1["data"], list)
    assert "meta" in body_1 and isinstance(body_1["meta"], dict)

    meta = body_1["meta"]
    assert set(["total", "page", "page_size", "total_pages", "filters"]).issubset(meta.keys())

    ids_1 = [item["id"] for item in body_1["data"]]
    ids_2 = [item["id"] for item in body_2["data"]]
    assert ids_1 == ids_2


def test_win_rate_numeric_contract(client):
    response = client.get(
        "/api/v1/performance/metrics",
        params={
            "symbol": "XAUUSD",
            "strategy_id": 10,
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-01-02T00:00:00+00:00",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert "metrics" in body
    metrics = body["metrics"]

    assert isinstance(metrics.get("win_rate"), (int, float))


def test_profit_factor_numeric_contract(client):
    response = client.get(
        "/api/v1/performance/metrics",
        params={
            "symbol": "XAUUSD",
            "strategy_id": 10,
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-01-02T00:00:00+00:00",
        },
    )

    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert isinstance(metrics.get("profit_factor"), (int, float))


def test_max_drawdown_numeric_contract(client):
    response = client.get(
        "/api/v1/performance/metrics",
        params={
            "symbol": "XAUUSD",
            "strategy_id": 10,
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-01-02T00:00:00+00:00",
        },
    )

    assert response.status_code == 200
    metrics = response.json()["metrics"]
    assert isinstance(metrics.get("max_drawdown"), (int, float))


def test_avg_rr_nullability_explicit(client):
    response = client.get(
        "/api/v1/performance/metrics",
        params={
            "symbol": "XAUUSD",
            "strategy_id": 10,
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-01-02T00:00:00+00:00",
        },
    )

    assert response.status_code == 200
    avg_rr = response.json().get("metrics", {}).get("avg_rr")
    assert avg_rr is None or isinstance(avg_rr, (int, float))


def test_equity_curve_contract_uses_shared_filters(client):
    common_params = {
        "start": "2026-01-01T00:00:00+00:00",
        "end": "2026-01-03T00:00:00+00:00",
        "symbol": "XAUUSD",
        "timeframe": "M15",
    }

    strategy_10 = client.get(
        "/api/v1/performance/equity-curve",
        params={**common_params, "strategy_id": 10},
    )
    strategy_20 = client.get(
        "/api/v1/performance/equity-curve",
        params={**common_params, "strategy_id": 20},
    )

    assert strategy_10.status_code == 200
    assert strategy_20.status_code == 200

    body_10 = strategy_10.json()
    body_20 = strategy_20.json()

    assert "data" in body_10 and isinstance(body_10["data"], list)
    assert "meta" in body_10 and isinstance(body_10["meta"], dict)
    assert "filters" in body_10["meta"]

    assert body_10["meta"]["filters"]["strategy_id"] == 10
    assert body_20["meta"]["filters"]["strategy_id"] == 20
    assert body_10["data"] != body_20["data"]
    assert len(body_10["data"]) > len(body_20["data"])


def test_filter_validation_returns_structured_4xx(client):
    response = client.get(
        "/api/v1/performance/trades",
        params={
            "status": "INVALID",
            "page_size": 999,
            "start": "not-a-date",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert set(["error", "code", "details"]).issubset(body.keys())

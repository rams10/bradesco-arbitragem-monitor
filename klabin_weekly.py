import datetime as dt
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent
DATA_FILE = ROOT / "docs" / "klabin-data.json"
TZ = ZoneInfo("America/Sao_Paulo")
TICKERS = ("KLBN3", "KLBN4")
API_URL = "https://brapi.dev/api/quote/{}"


def fetch_history(ticker):
    token = os.environ.get("BRAPI_TOKEN")
    if not token:
        raise RuntimeError("O secret BRAPI_TOKEN não está configurado.")
    params = urllib.parse.urlencode({"range": "3mo", "interval": "1d"})
    url = API_URL.format(ticker) + "?" + params
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "KlabinWeeklyMonitor/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("message") or json.loads(body).get("error") or body[:300]
        except Exception:
            detail = body[:300]
        raise RuntimeError(f"Falha na consulta de {ticker}: HTTP {exc.code} · {detail}") from exc
    except Exception as exc:
        raise RuntimeError(f"Falha ao consultar {ticker}: {exc}") from exc

    results = payload.get("results") or []
    if not results:
        raise RuntimeError(f"A brapi não retornou resultados para {ticker}.")
    rows = results[0].get("historicalDataPrice") or []
    cleaned = []
    for row in rows:
        try:
            stamp = int(row["date"])
            close = float(row["close"])
            day = dt.datetime.fromtimestamp(stamp, tz=dt.timezone.utc).astimezone(TZ).date()
            if close > 0:
                cleaned.append((day, close))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if len(cleaned) < 20:
        raise RuntimeError(
            f"Histórico insuficiente para {ticker}: {len(cleaned)} pregões recebidos."
        )
    return cleaned


def weekly_last_close(rows):
    # Usa o último pregão disponível de cada semana ISO; feriados não quebram a coleta.
    weekly = {}
    for day, close in rows:
        iso = day.isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
        old = weekly.get(key)
        if old is None or day.isoformat() > old["date"]:
            weekly[key] = {"week": key, "date": day.isoformat(), "close": close}
    return weekly


def main():
    # Só publica o novo arquivo quando os dois tickers retornarem dados válidos.
    raw3 = fetch_history("KLBN3")
    raw4 = fetch_history("KLBN4")
    w3 = weekly_last_close(raw3)
    w4 = weekly_last_close(raw4)

    common_weeks = sorted(set(w3) & set(w4))
    if len(common_weeks) < 8:
        raise RuntimeError("Menos de oito semanas em comum entre KLBN3 e KLBN4.")

    existing = {"history": []}
    if DATA_FILE.exists():
        try:
            existing = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    merged = {row["week"]: row for row in existing.get("history", []) if row.get("week")}
    for week in common_weeks:
        a, b = w3[week], w4[week]
        spread = (a["close"] / b["close"] - 1.0) * 100.0
        merged[week] = {
            "week": week,
            "date": min(a["date"], b["date"]) if a["date"] == b["date"] else max(a["date"], b["date"]),
            "klbn3": round(a["close"], 4),
            "klbn4": round(b["close"], 4),
            "spread_pct": round(spread, 4),
            "klbn3_date": a["date"],
            "klbn4_date": b["date"],
        }

    history = sorted(merged.values(), key=lambda row: row["week"])
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    output = {
        "source": "brapi.dev",
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "frequency": "weekly",
        "weekly_method": "last available trading close in each ISO week",
        "initial_history_limit": "3 months on the free brapi plan; the stored weekly series accumulates over time",
        "threshold_pct": 5.0,
        "history": history,
        "last_run": {
            "weeks_received": len(common_weeks),
            "total_weeks": len(history),
            "latest_week": history[-1]["week"],
            "latest_date": history[-1]["date"],
        },
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest = history[-1]
    print(
        f"OK: {len(common_weeks)} semanas consultadas; {len(history)} acumuladas; "
        f"última {latest['week']} ({latest['date']}), "
        f"KLBN3 R$ {latest['klbn3']:.2f}, KLBN4 R$ {latest['klbn4']:.2f}, "
        f"diferença {latest['spread_pct']:+.2f}%."
    )


if __name__ == "__main__":
    main()

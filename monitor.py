import os, json, datetime, pathlib
from zoneinfo import ZoneInfo
import httpx

TZ = ZoneInfo("America/Sao_Paulo")
ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "docs" / "data.json"

PAIRS = [
    {
        "history_key": "history",
        "signal_key": "last_signal",
        "prefix": "bbdc",
        "ticker3": "BBDC3",
        "ticker4": "BBDC4",
        "lower": 1.07,
        "upper": 1.13,
    },
    {
        "history_key": "sapr_history",
        "signal_key": "sapr_last_signal",
        "prefix": "sapr",
        "ticker3": "SAPR3",
        "ticker4": "SAPR4",
        # Starting thresholds: approximate 1st/3rd quartiles of annual SAPR4/SAPR3
        # closes for 2017-2026. These are provisional until a daily backtest is run.
        "lower": 0.88,
        "upper": 1.05,
    },
]


def get_quote(client, ticker, now):
    response = client.get(f"https://brapi.dev/api/quote/{ticker}")
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        raise RuntimeError(f"A brapi não retornou {ticker}.")
    item = results[0]
    price = float(item["regularMarketPrice"])
    quote_time = item.get("regularMarketTime")
    if not quote_time:
        raise RuntimeError(f"A brapi não informou o horário de {ticker}.")
    quote_dt = datetime.datetime.fromisoformat(
        quote_time.replace("Z", "+00:00")
    ).astimezone(TZ)
    if abs((now - quote_dt).total_seconds()) > 90 * 60:
        raise RuntimeError(f"Cotação de {ticker} antiga demais; sinal suspenso.")
    return price, quote_time, quote_dt


def collect_pair(client, old, pair, now):
    ticker3, ticker4 = pair["ticker3"], pair["ticker4"]
    p3, t3, d3 = get_quote(client, ticker3, now)
    p4, t4, d4 = get_quote(client, ticker4, now)
    if abs((d3 - d4).total_seconds()) > 30 * 60:
        raise RuntimeError(
            f"Horários das cotações de {ticker3} e {ticker4} muito diferentes."
        )

    ratio = p4 / p3
    history = old.get(pair["history_key"], [])
    previous = history[-1]["ratio"] if history else None
    signal = None
    if previous is not None:
        if previous > pair["lower"] and ratio <= pair["lower"]:
            signal = (
                f"{ticker4} relativamente barata",
                f"A relação {ticker4}/{ticker3} caiu para {ratio:.4f} "
                f"(limite {pair['lower']:.2f}). Avalie {ticker3} → {ticker4}.",
            )
        elif previous < pair["upper"] and ratio >= pair["upper"]:
            signal = (
                f"{ticker3} relativamente barata",
                f"A relação {ticker4}/{ticker3} subiu para {ratio:.4f} "
                f"(limite {pair['upper']:.2f}). Avalie {ticker4} → {ticker3}.",
            )

    record = {
        "captured_at": now.isoformat(),
        f"{pair['prefix']}3": p3,
        f"{pair['prefix']}4": p4,
        "ratio": ratio,
        "quote_time3": t3,
        "quote_time4": t4,
    }
    history.append(record)
    return history[-1000:], signal, record


def main():
    now = datetime.datetime.now(TZ)
    old = {"history": [], "sapr_history": []}
    if DATA.exists():
        try:
            old = json.loads(DATA.read_text())
        except Exception:
            pass

    result = {
        "history": old.get("history", []),
        "sapr_history": old.get("sapr_history", []),
        "last_signal": old.get("last_signal"),
        "sapr_last_signal": old.get("sapr_last_signal"),
        "pair_status": old.get("pair_status", {}),
    }
    alerts, successes, errors = [], [], []
    headers = {"Authorization": f"Bearer {os.environ['BRAPI_TOKEN']}"}

    # Plano Gratuito: um ticker por chamada; quatro chamadas por coleta (dois pares).
    with httpx.Client(timeout=25, headers=headers) as client:
        for pair in PAIRS:
            try:
                history, signal, record = collect_pair(client, old, pair, now)
                result[pair["history_key"]] = history
                if signal:
                    result[pair["signal_key"]] = signal[0]
                    alerts.append((pair, signal, record))
                result["pair_status"][pair["prefix"]] = {
                    "status": "ok",
                    "checked_at": now.isoformat(),
                    "ratio": record["ratio"],
                }
                successes.append(pair["prefix"])
                print(
                    f"OK {pair['ticker3']}={record[pair['prefix']+'3']:.2f} "
                    f"{pair['ticker4']}={record[pair['prefix']+'4']:.2f} "
                    f"relação={record['ratio']:.4f}"
                )
            except Exception as exc:
                errors.append(f"{pair['prefix'].upper()}: {exc}")
                result["pair_status"][pair["prefix"]] = {
                    "status": "error",
                    "checked_at": now.isoformat(),
                    "message": str(exc),
                }
                print(f"FALHA {pair['prefix'].upper()}: {exc}")

    if not successes:
        raise RuntimeError("Nenhum par foi atualizado. " + " | ".join(errors))

    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(result, ensure_ascii=False, indent=2))

    if alerts:
        parts = ["🔔 Monitor de alternância entre classes"]
        for pair, signal, record in alerts:
            p3 = record[f"{pair['prefix']}3"]
            p4 = record[f"{pair['prefix']}4"]
            parts.extend([
                f"\n{pair['ticker3']} / {pair['ticker4']}: {signal[0]}",
                signal[1],
                f"{pair['ticker3']}: R$ {p3:.2f} | {pair['ticker4']}: R$ {p4:.2f}",
            ])
        parts.append(
            f"Coleta: {now.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)"
        )
        parts.append(
            "Sinal relativo; confira preços executáveis, spread, custos, "
            "impostos, liquidez e proventos antes de operar."
        )
        with httpx.Client(timeout=20) as client:
            sent = client.post(
                f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                json={
                    "chat_id": os.environ["TELEGRAM_CHAT_ID"],
                    "text": "\n".join(parts),
                },
            )
            sent.raise_for_status()

    print(json.dumps({
        "successes": successes,
        "errors": errors,
        "alerts": [x[1][0] for x in alerts],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

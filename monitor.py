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
        "ratio_numerator": "4",
        "ratio_label": "BBDC4 / BBDC3",
        "lower": 1.07,
        "upper": 1.13,
    },
    {
        "history_key": "sapr_history",
        "signal_key": "sapr_last_signal",
        "prefix": "sapr",
        "ticker3": "SAPR3",
        "ticker4": "SAPR4",
        "ratio_numerator": "4",
        "ratio_label": "SAPR4 / SAPR3",
        # Starting thresholds: approximate 1st/3rd quartiles of annual SAPR4/SAPR3
        # closes for 2017-2026. Provisional until a daily backtest is run.
        "lower": 0.88,
        "upper": 1.05,
    },
    {
        "history_key": "klbn_history",
        "signal_key": "klbn_last_signal",
        "prefix": "klbn",
        "ticker3": "KLBN3",
        "ticker4": "KLBN4",
        "ratio_numerator": "3",
        "ratio_label": "KLBN3 / KLBN4",
        # The requested ±5% relative-price alert band.
        "lower": 0.95,
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

    if pair["ratio_numerator"] == "4":
        numerator, denominator = p4, p3
        numerator_ticker, denominator_ticker = ticker4, ticker3
    else:
        numerator, denominator = p3, p4
        numerator_ticker, denominator_ticker = ticker3, ticker4
    ratio = numerator / denominator

    history = old.get(pair["history_key"], [])
    previous = history[-1]["ratio"] if history else None
    signal = None
    if previous is not None:
        if previous > pair["lower"] and ratio <= pair["lower"]:
            signal = (
                f"{numerator_ticker} relativamente barata",
                f"A relação {pair['ratio_label']} caiu para {ratio:.4f} "
                f"(limite {pair['lower']:.2f}). Avalie "
                f"{denominator_ticker} → {numerator_ticker}.",
            )
        elif previous < pair["upper"] and ratio >= pair["upper"]:
            signal = (
                f"{denominator_ticker} relativamente barata",
                f"A relação {pair['ratio_label']} subiu para {ratio:.4f} "
                f"(limite {pair['upper']:.2f}). Avalie "
                f"{numerator_ticker} → {denominator_ticker}.",
            )

    record = {
        "captured_at": now.isoformat(),
        f"{pair['prefix']}3": p3,
        f"{pair['prefix']}4": p4,
        "ratio": ratio,
        "ratio_label": pair["ratio_label"],
        "quote_time3": t3,
        "quote_time4": t4,
    }
    history.append(record)
    return history[-2000:], signal, record


def main():
    now = datetime.datetime.now(TZ)
    old = {
        "history": [],
        "sapr_history": [],
        "klbn_history": [],
    }
    if DATA.exists():
        try:
            old = json.loads(DATA.read_text())
        except Exception:
            pass

    result = {
        "history": old.get("history", []),
        "sapr_history": old.get("sapr_history", []),
        "klbn_history": old.get("klbn_history", []),
        "last_signal": old.get("last_signal"),
        "sapr_last_signal": old.get("sapr_last_signal"),
        "klbn_last_signal": old.get("klbn_last_signal"),
        "pair_status": old.get("pair_status", {}),
    }
    alerts, successes, errors = [], [], []
    headers = {"Authorization": f"Bearer {os.environ['BRAPI_TOKEN']}"}

    # Plano gratuito: um ticker por chamada. São seis chamadas por coleta:
    # BBDC3/4, SAPR3/4 e KLBN3/4.
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
                    f"relação {pair['ratio_label']}={record['ratio']:.4f}"
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
        # Fora do pregão, cotações antigas não devem gerar sinais nem falhar
        # o workflow. Mantém os históricos anteriores intactos.
        print(
            "Nenhum par atualizado; históricos preservados. "
            "Isso pode ocorrer com mercado fechado ou cotações antigas. "
            + " | ".join(errors)
        )
        return

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
                f"Relação {pair['ratio_label']}: {record['ratio']:.4f}",
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

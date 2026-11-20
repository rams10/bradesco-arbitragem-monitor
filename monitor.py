import os, json, datetime, pathlib
from zoneinfo import ZoneInfo
import httpx

TZ = ZoneInfo("America/Sao_Paulo")
ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "docs" / "data.json"
LOWER, UPPER = 1.07, 1.13

def main():
    now = datetime.datetime.now(TZ)
    headers = {"Authorization": f"Bearer {os.environ['BRAPI_TOKEN']}"}
    # No plano gratuito, faça uma chamada por ticker.
    with httpx.Client(timeout=25) as client:
        response3 = client.get("https://brapi.dev/api/quote/BBDC3", headers=headers)
        response3.raise_for_status()
        response4 = client.get("https://brapi.dev/api/quote/BBDC4", headers=headers)
        response4.raise_for_status()
        results3 = response3.json().get("results", [])
        results4 = response4.json().get("results", [])

    if not results3 or not results4:
        raise RuntimeError("A brapi não retornou BBDC3 e BBDC4.")
    a, b = results3[0], results4[0]
    p3, p4 = float(a["regularMarketPrice"]), float(b["regularMarketPrice"])
    t3, t4 = a.get("regularMarketTime"), b.get("regularMarketTime")
    if not t3 or not t4:
        raise RuntimeError("A fonte não informou os horários das duas cotações.")

    d3 = datetime.datetime.fromisoformat(t3.replace("Z", "+00:00")).astimezone(TZ)
    d4 = datetime.datetime.fromisoformat(t4.replace("Z", "+00:00")).astimezone(TZ)
    # O plano gratuito tem delay aproximado de 30 min; tolerância maior impede
    # que pequenas diferenças de publicação gerem falso bloqueio, mas não valida tempo real.
    if abs((now - d3).total_seconds()) > 90 * 60 or abs((now - d4).total_seconds()) > 90 * 60:
        raise RuntimeError("Cotação antiga demais: sinal suspenso.")
    if abs((d3 - d4).total_seconds()) > 30 * 60:
        raise RuntimeError("Horários das cotações muito diferentes: sinal suspenso.")

    ratio = p4 / p3
    old = {"history": [], "last_signal": None}
    if DATA.exists():
        try:
            old = json.loads(DATA.read_text())
        except Exception:
            pass
    history = old.get("history", [])
    previous = history[-1]["ratio"] if history else None
    signal = None
    if previous is not None:
        if previous > LOWER and ratio <= LOWER:
            signal = ("BBDC4 relativamente barata",
                      f"A relação caiu para {ratio:.4f} (limite {LOWER:.2f}). Avalie BBDC3 → BBDC4.")
        elif previous < UPPER and ratio >= UPPER:
            signal = ("BBDC3 relativamente barata",
                      f"A relação subiu para {ratio:.4f} (limite {UPPER:.2f}). Avalie BBDC4 → BBDC3.")

    history.append({
        "captured_at": now.isoformat(),
        "bbdc3": p3, "bbdc4": p4, "ratio": ratio,
        "quote_time3": t3, "quote_time4": t4
    })
    history = history[-1000:]
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps({
        "history": history,
        "last_signal": signal[0] if signal else old.get("last_signal")
    }, ensure_ascii=False, indent=2))

    if signal:
        message = (
            "🔔 Bradesco Arbitragem Monitor\n"
            f"{signal[0]}\n{signal[1]}\n"
            f"BBDC3: R$ {p3:.2f} | BBDC4: R$ {p4:.2f}\n"
            f"Coleta: {now.strftime('%d/%m/%Y %H:%M:%S')} (Brasília)\n"
            "Sinal relativo; confira cotações, spread, custos, impostos e proventos antes de operar."
        )
        with httpx.Client(timeout=20) as client:
            sent = client.post(
                f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
                json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": message}
            )
            sent.raise_for_status()

    print(json.dumps({"BBDC3": p3, "BBDC4": p4, "ratio": ratio,
                      "signal": signal[0] if signal else None}))

if __name__ == "__main__":
    main()

"""Read official TAIFEX TXO option daily quotes; fail closed if data is unusable."""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data.json"
TZ = timezone(timedelta(hours=8))
BASE = "https://openapi.taifex.com.tw/v1/"
URL = os.getenv("TAIFEX_OPTION_URL", BASE + "DailyMarketReportOpt").strip()


def normalize(key):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(key).lower())


def value(row, *names):
    fields = {normalize(k): v for k, v in row.items()}
    for name in names:
        x = fields.get(normalize(name))
        if x is not None and str(x).strip() not in ("", "--", "-", "N/A", "－"):
            return x
    return None


def number(x):
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None


def parse_row(row):
    product = str(value(row, "Contract", "商品代號", "商品", "商品名稱", "CommodityID", "ProductID", "商品契約") or "").strip().upper()
    if product != "TXO" and not product.startswith("TXO") and product not in ("臺指選擇權", "台指選擇權"):
        return None
    cp = str(value(row, "CallPut", "Call/Put", "買賣權", "買權賣權", "買權/賣權") or "").strip().upper()
    if cp in ("買權", "C", "CALL"):
        cp = "C"
    elif cp in ("賣權", "P", "PUT"):
        cp = "P"
    else:
        return None
    strike = number(value(row, "StrikePrice", "履約價", "履約價格", "Strike"))
    oi = number(value(row, "OpenInterest", "未沖銷契約量", "未沖銷契約數", "未平倉量", "未平倉口數", "未沖銷契約數量"))
    price = number(value(row, "SettlementPrice", "結算價", "Close", "ClosePrice", "收盤價", "最後成交價"))
    expiry = str(value(row, "ContractMonth(Week)", "到期月份(週別)", "到期月份(週)", "ContractMonth", "到期月份", "契約月份", "Expiry") or "").strip()
    date = str(value(row, "Date", "日期", "交易日期", "TradeDate") or "").strip()
    session = str(value(row, "TradingSession", "交易時段") or "").strip()
    if not expiry or strike is None or strike <= 0 or oi is None or oi < 0 or not date:
        return None
    return {"expiry": expiry, "strike": strike, "cp": cp, "oi": int(oi), "price": price, "date": date, "session": session}


def read_source():
    request = urllib.request.Request(URL, headers={"User-Agent": "TWOptionsExposureResearch/1.1", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"TAIFEX HTTP request failed: {exc}") from exc
    try:
        raw = json.loads(body)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"TAIFEX did not return JSON. Response begins: {body[:160]!r}") from exc
    if isinstance(raw, dict):
        raw = next((part for part in raw.values() if isinstance(part, list)), [])
    if not isinstance(raw, list) or not raw:
        raise RuntimeError("TAIFEX returned an empty or unsupported response")
    rows = [parsed for row in raw if isinstance(row, dict) if (parsed := parse_row(row)) is not None]
    if len(rows) < 20:
        sample = next((list(r.keys()) for r in raw if isinstance(r, dict)), [])
        txo_samples = [r for r in raw if isinstance(r, dict) and "TXO" in str(r.get("Contract", ""))][:2]
        raise RuntimeError(f"Only {len(rows)} valid TXO rows from {len(raw)} records. API fields={sample}; example TXO={txo_samples}")
    return rows


def main():
    rows = read_source()
    # Do not mix trading days and sessions. Sum same-date day/night rows only if
    # the official API represents them independently (normally it supplies day snapshot).
    latest = max(r["date"] for r in rows)
    rows = [r for r in rows if r["date"] == latest]
    if len(rows) < 20:
        raise RuntimeError(f"Only {len(rows)} contracts on latest trading date {latest}")
    # Never overwrite fresh data with a response from an older date.
    if OUT.exists():
        try:
            previous = json.loads(OUT.read_text(encoding="utf-8"))
            if previous.get("status") == "raw_official_data" and str(previous.get("data_date", "")) > latest:
                raise RuntimeError(f"Existing market data date {previous['data_date']} is newer than API {latest}")
        except json.JSONDecodeError:
            pass
    payload = {
        "status": "raw_official_data", "source": URL, "data_date": latest,
        "retrieved_at": datetime.now(TZ).isoformat(), "contract": "TXO",
        "notes": "OI is market-wide, not dealer position. Estimated GEX/VEX depends on assumptions; not a trading signal.",
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUT.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temp.replace(OUT)
    print(f"Updated {OUT}: {len(rows)} official TXO rows; date={latest}; source={URL}")


if __name__ == "__main__":
    main()

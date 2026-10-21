"""TAIFEX public-data importer. Never substitutes synthetic data for market data."""
import csv, json, math, os, re, sys, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'data.json'
TZ=timezone(timedelta(hours=8))
# Official API datasets may vary in naming and availability. Override through env when necessary.
BASE='https://openapi.taifex.com.tw/v1/'
CANDIDATES=['DailyMarketReportOpt','DailyMarketReportOption']

def get_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':'TWOptionsExposureResearch/1.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=35) as response:
        return json.load(response)

def keynorm(s):return re.sub(r'[^a-z0-9\u4e00-\u9fff]','',str(s).lower())
def field(row,*names):
    lookup={keynorm(k):v for k,v in row.items()}
    for n in names:
        v=lookup.get(keynorm(n))
        if v is not None and str(v).strip() not in ('','--','-','N/A'):return v
    return None

def num(v):
    try:return float(str(v).replace(',','').replace('%','').strip())
    except (ValueError,TypeError):return None

def parse_row(r):
    product=str(field(r,'商品代號','商品','商品名稱','CommodityID','ProductID','Contract','商品契約') or '').upper().strip()
    if product not in ('TXO','臺指選擇權','台指選擇權') and not product.startswith('TXO'):return None
    cp=str(field(r,'買賣權','買權賣權','CallPut','Call/Put','買權/賣權') or '').strip().upper()
    if cp in ('買權','C','CALL'):cp='C'
    elif cp in ('賣權','P','PUT'):cp='P'
    else:return None
    strike=num(field(r,'履約價格','履約價','StrikePrice','Strike'))
    oi=num(field(r,'未沖銷契約數','未平倉量','未平倉口數','OpenInterest','Open Interest','未沖銷契約數量'))
    price=num(field(r,'收盤價','最後成交價','Close','ClosePrice','結算價','SettlementPrice'))
    expiry=str(field(r,'到期月份(週別)','到期月份','契約月份','ContractMonth','Expiry','到期月份(週)') or '').strip()
    date=str(field(r,'交易日期','日期','Date','TradeDate') or '').strip()
    if not expiry or strike is None or oi is None or oi < 0:return None
    return {'expiry':expiry,'strike':strike,'cp':cp,'oi':int(oi),'price':price,'date':date}

def read_source():
    url=os.getenv('TAIFEX_OPTION_URL','').strip()
    urls=[url] if url else [BASE+s for s in CANDIDATES]
    errors=[]
    for u in urls:
        try:
            raw=get_json(u)
            if isinstance(raw,dict):raw=next((v for v in raw.values() if isinstance(v,list)),[])
            if not isinstance(raw,list) or not raw:raise ValueError('API returned empty or non-list data')
            rows=[z for r in raw if isinstance(r,dict) if (z:=parse_row(r))]
            if len(rows)<20:raise ValueError(f'Only {len(rows)} valid TXO rows; field schema may have changed')
            return u, rows
        except Exception as e:errors.append(f'{u}: {e}')
    raise RuntimeError('; '.join(errors))

def main():
    source,rows=read_source()
    # Never mix dates; daily feeds may contain multiple dates.
    dates=[r['date'] for r in rows if r['date']]
    latest=max(dates) if dates else datetime.now(TZ).strftime('%Y%m%d')
    if dates:rows=[r for r in rows if not r['date'] or r['date']==latest]
    if len(rows)<20:raise ValueError('Insufficient rows on latest trading date')
    output={'status':'raw_official_data','source':source,'data_date':latest,'retrieved_at':datetime.now(TZ).isoformat(), 'contract':'TXO','notes':'OI is market-wide, NOT dealer position; Greeks and exposure are estimated client-side.', 'rows':rows}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(output,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(f'Updated {OUT}: {len(rows)} rows, date={latest}, source={source}')

if __name__=='__main__':main()

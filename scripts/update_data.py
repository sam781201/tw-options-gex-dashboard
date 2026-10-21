"""TAIFEX TXO official daily feed; never substitutes fabricated quotes."""
import json, os, re, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs'/'data.json'
URL=os.getenv('TAIFEX_OPTION_URL','https://openapi.taifex.com.tw/v1/DailyMarketReportOpt')
TZ=timezone(timedelta(hours=8))
def normalize(x):return re.sub(r'[^a-z0-9\u4e00-\u9fff]','',str(x).lower())
def value(row,*names):
    r={normalize(k):v for k,v in row.items()}
    for n in names:
        v=r.get(normalize(n))
        if v is not None and str(v).strip() not in ('','--','-','N/A'):return v
    return None
def num(v):
    try:return float(str(v).replace(',','').strip())
    except (ValueError,TypeError):return None
def parse(row):
    product=str(value(row,'Contract','商品代號','商品') or '').strip().upper()
    if product!='TXO':return None
    cp=str(value(row,'CallPut','買賣權') or '').upper().strip()
    if cp in ('CALL','買權'):cp='C'
    if cp in ('PUT','賣權'):cp='P'
    if cp not in ('C','P'):return None
    strike=num(value(row,'StrikePrice','履約價','履約價格'))
    oi=num(value(row,'OpenInterest','未平倉量','未沖銷契約量','未沖銷契約數'))
    price=num(value(row,'SettlementPrice','結算價','收盤價'))
    exp=str(value(row,'ContractMonth(Week)','到期月份(週別)','到期月份') or '').strip()
    date=str(value(row,'Date','交易日期','日期') or '').strip()
    session=str(value(row,'TradingSession','交易時段') or '').strip()
    if not exp or not re.fullmatch(r'\d{8}',date) or strike is None or strike<=0 or oi is None or oi<0:return None
    return dict(expiry=exp,strike=strike,cp=cp,oi=int(oi),price=price,date=date,session=session)
def main():
    req=urllib.request.Request(URL,headers={'User-Agent':'TWOptionsResearch/2.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=50) as f: raw=json.load(f)
    if isinstance(raw,dict):raw=next((v for v in raw.values() if isinstance(v,list)),[])
    if not isinstance(raw,list):raise RuntimeError('Unexpected API response')
    rows=[p for x in raw if isinstance(x,dict) if (p:=parse(x))]
    if len(rows)<20:raise RuntimeError(f'Only {len(rows)} valid TXO rows; source schema may have changed. keys={list(raw[0]) if raw else []}')
    latest=max(x['date'] for x in rows)
    rows=[x for x in rows if x['date']==latest]
    old=json.loads(OUT.read_text('utf-8')) if OUT.exists() else {}
    if old.get('data_date','')>latest:raise RuntimeError('Official feed older than stored snapshot')
    if old.get('data_date')==latest and old.get('status')=='raw_official_data':
        print('Same trading day; preserving original snapshot and retrieval time');return
    payload=dict(status='raw_official_data',source=URL,data_date=latest,retrieved_at=datetime.now(TZ).isoformat(),contract='TXO',rows=rows,notes='Official market-wide OI is not dealer inventory. Option parity is only a proxy; no live price supplied.')
    OUT.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print('Official TXO:',latest,len(rows),'rows')
if __name__=='__main__':main()

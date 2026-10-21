"""Strict out-of-sample next-session forecast ledger based on daily put-call-parity proxy.
No hindsight predictions. Existing predictions never overwritten. Model parameters derived only
from prior resolved observations. This is a research signal, NOT verified market direction.
"""
import json, math, statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'docs'; H=D/'history'; H.mkdir(parents=True,exist_ok=True)
TZ=timezone(timedelta(hours=8))
def load(p,default):
    try:return json.loads(p.read_text('utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):return default
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def proxy(rows):
    # Select the nearest monthly expiry; weekly codes cannot be translated safely without official calendar.
    expiries=sorted({str(r['expiry']) for r in rows if str(r['expiry']).isdigit() and len(str(r['expiry']))==6})
    if not expiries:return None
    expiry=expiries[0];pairs={}
    for r in rows:
        if r['expiry']!=expiry or not isinstance(r.get('price'),(float,int)) or r['price']<=0:continue
        pairs.setdefault(r['strike'],{})[r['cp']]=r
    vals=[]
    for k,p in pairs.items():
        if 'C' not in p or 'P' not in p:continue
        c,put=p['C'],p['P']; f=k+c['price']-put['price']
        if f<=0 or c['oi']+put['oi']<10:continue
        vals.append((f,k,min(c['oi'],put['oi'])))
    if len(vals)<7:return None
    middle=statistics.median(x[0] for x in vals)
    near=[x[0] for x in vals if abs(x[1]-middle)<=middle*.035 and abs(x[0]-middle)<=middle*.06]
    if len(near)<5:return None
    return {'price':round(statistics.median(near),2),'source':'TXO 同到期買賣權結算價平價代理（未調整利率與股利）','expiry':expiry,'pairs':len(near)}
def category(ret,neutral,strong):
    if ret>=strong:return '強多'
    if ret>neutral:return '偏多'
    if ret<=-strong:return '強空'
    if ret<-neutral:return '偏空'
    return '盤整'
def predict(series,evals):
    if len(series)<21:return {'regime':'資料不足／等待確認','reason':f'已累積 {len(series)} 個交易日代理價格，需至少 21 個才開始預測','ready':False}
    prices=[x['proxy']['price'] for x in series]
    avg5=statistics.mean(prices[-5:]);avg20=statistics.mean(prices[-20:]);cur=prices[-1]
    r5=cur/prices[-6]-1;r20=cur/prices[-21]-1
    prior_abs=[abs(x['return']) for x in evals[-40:] if isinstance(x.get('return'),(float,int))]
    neutral=max(.002,min(.008,statistics.median(prior_abs)*.5)) if len(prior_abs)>=30 else .003
    strong=max(.009,min(.025,statistics.median(prior_abs)*1.8)) if len(prior_abs)>=30 else .012
    # A conservative trend proxy, not a market forecast probability.
    score=.6*r5+.4*r20
    if cur<avg5 and avg5<avg20:score=min(score,-neutral*.75)
    if cur>avg5 and avg5>avg20:score=max(score,neutral*.75)
    regime=category(score,neutral,strong)
    return {'regime':regime,'ready':True,'model':'proxy-trend-v1','score':round(score,6),'neutral':neutral,'strong':strong,'reason':f'平價代理價格 {cur:,.1f}；5 日變化 {r5:+.2%}；20 日變化 {r20:+.2%}；5 日均值 {avg5:,.1f}、20 日均值 {avg20:,.1f}。這是趨勢代理，並非真實台指報價。','calibrated':len(prior_abs)>=30}
def main():
    data=load(D/'data.json',{})
    if data.get('status')!='raw_official_data' or not data.get('rows'):raise RuntimeError('No verified official option data')
    date=data['data_date']; snap=H/(date+'.json')
    if not snap.exists():
        save(snap,{'date':date,'proxy':proxy(data['rows']),'rows_count':len(data['rows']),'source':data['source']})
    history=sorted((load(p,{}) for p in H.glob('????????.json')),key=lambda x:x.get('date',''))
    series=[x for x in history if x.get('date') and x.get('proxy')]
    forecasts=load(D/'forecasts.json',[])
    bydate={f['date']:f for f in forecasts}
    resolved=[]
    # Outcome measured at NEXT AVAILABLE observed trading day, not calendar next day.
    for i,obs in enumerate(series):
        f=bydate.get(obs['date'])
        if not f or not f.get('ready') or i+1>=len(series):continue
        nxt=series[i+1];actual_ret=nxt['proxy']['price']/obs['proxy']['price']-1
        actual=category(actual_ret,f['neutral'],f['strong'])
        predicted=f['regime'];direction=lambda a:0 if a=='盤整' else 1 if '多' in a else -1
        resolved.append({'prediction_date':obs['date'],'outcome_date':nxt['date'],'predicted':predicted,'actual':actual,'return':round(actual_ret,6),'exact_match':predicted==actual,'direction_hit':direction(predicted)==direction(actual),'model':f['model']})
    if date not in bydate:
        prior=[x for x in series if x['date']<=date]
        f={'date':date,'target':'下一個有資料的交易日','created_at':datetime.now(TZ).isoformat(),**predict(prior,resolved)}
        forecasts.append(f)
    save(D/'forecasts.json',forecasts)
    save(D/'evaluations.json',resolved)
    current=next((f for f in forecasts if f['date']==date),None)
    n=len(resolved)
    summary={'data_date':date,'data_retrieved_at':data['retrieved_at'],'model_updated_at':datetime.now(TZ).isoformat(),'proxy':next((x['proxy'] for x in series if x['date']==date),None),'history_days':len(series),'latest_prediction':current,'evaluated_count':n,'exact_accuracy':round(sum(x['exact_match'] for x in resolved)/n,4) if n else None,'direction_accuracy':round(sum(x['direction_hit'] for x in resolved)/n,4) if n else None,'latest_evaluations':resolved[-30:],'backtest_note':'Only predictions actually saved before the next session are evaluated; no past-date predictions are reconstructed. Adaptive thresholds activate after >=30 resolved predictions, calculated only from earlier outcomes. Signal uses options parity proxy, not observed futures spot.'}
    save(D/'analysis.json',summary)
    print('Analysis',date,'history',len(series),'prediction',current['regime'] if current else 'none','evaluations',n)
if __name__=='__main__':main()

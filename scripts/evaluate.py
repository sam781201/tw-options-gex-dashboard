"""Append-only, strictly forward evaluation of next-trading-session direction.
Educational proxy: matched call/put settlement parity K+C-P, NOT official index/futures close.
No prediction is scored on the same date it was made.
"""
import json, math, statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; DOCS=ROOT/'docs'; HISTORY=DOCS/'history.json'; REPORT=DOCS/'backtest.json'; FORECAST=DOCS/'forecast.json'
LABELS={'strong_bear':'強空','bear':'偏空','flat':'盤整','bull':'偏多','strong_bull':'強多','wait':'等待確認'}

def proxy(rows):
    expiry=sorted({str(r['expiry']) for r in rows})
    for e in expiry:
        pairs={}
        for r in rows:
            if r['expiry']!=e or r.get('price') is None or r['price']<=0: continue
            pairs.setdefault(r['strike'],{})[r['cp']]=r
        parity=[]
        for strike,v in pairs.items():
            if 'C' in v and 'P' in v and min(v['C']['oi'],v['P']['oi'])>0:
                # Prefer strikes where both sides have meaningful OI; avoid wings.
                parity.append((strike+v['C']['price']-v['P']['price'],min(v['C']['oi'],v['P']['oi'])))
        if len(parity)>=5:
            parity.sort(key=lambda x:x[0]); total=sum(w for _,w in parity); run=0
            for x,w in parity:
                run+=w
                if run>=total/2:return round(x,2),e,len(parity)
    return None,None,0

def prediction(history):
    if len(history)<7:return 'wait',None,['歷史交易日不足七筆，不能判斷五種行情。']
    vals=[x['proxy'] for x in history[-7:]]
    if any(not isinstance(x,(float,int)) or x<=0 for x in vals):return 'wait',None,['歷史價格代理不完整。']
    m3=statistics.mean(vals[-3:]);m7=statistics.mean(vals)
    impulse=(vals[-1]/vals[-4]-1)*100
    slow=(m3/m7-1)*100
    score=impulse*.65+slow*.35
    if score>=1.0: label='strong_bull'
    elif score>=.25: label='bull'
    elif score<=-1.0:label='strong_bear'
    elif score<=-.25:label='bear'
    else:label='flat'
    return label,round(score,4),[f'最近四筆價格代理變化 {impulse:+.2f}%','三筆與七筆均值的相對差 '+f'{slow:+.2f}%','這是跨日趨勢規則，不是造市商持倉或未來漲跌的保證。']

def actual(ret):
    # Next-session move thresholds are fixed ex ante and *not* trained on future data.
    if ret>=1:return 'strong_bull'
    if ret>=.25:return 'bull'
    if ret<=-1:return 'strong_bear'
    if ret<=-.25:return 'bear'
    return 'flat'

def run():
    snapshot=json.loads((DOCS/'data.json').read_text(encoding='utf-8'))
    if snapshot.get('status')!='raw_official_data' or not snapshot.get('rows'):raise ValueError('Official data not available')
    dt=str(snapshot['data_date']); spot,expiry,pairs=proxy(snapshot['rows'])
    old=json.loads(HISTORY.read_text(encoding='utf-8')) if HISTORY.exists() else {'records':[]}
    entries=old['records']; prior=next((r for r in entries if r['date']==dt),None)
    if prior is None:
        # Persist one prediction per date, created before next trading date is known.
        label,score,reasons=prediction(entries)
        entries.append({'date':dt,'proxy':spot,'proxy_expiry':expiry,'paired_strikes':pairs,
                        'prediction':label,'score':score,'reasons':reasons,'created_at':snapshot['retrieved_at']})
    else:
        # Never revise a prediction once archived, even on reruns.
        if prior['proxy'] is None and spot is not None:prior['proxy']=spot
    entries.sort(key=lambda r:r['date'])
    evaluated=[]
    for first,second in zip(entries,entries[1:]):
        if first['prediction']=='wait' or not first['proxy'] or not second['proxy']:continue
        change=100*(second['proxy']/first['proxy']-1)
        outcome=actual(change)
        evaluated.append({'forecast_date':first['date'],'outcome_date':second['date'],'forecast':first['prediction'],
                         'actual':outcome,'return_pct':round(change,4),'correct_exact':first['prediction']==outcome,
                         'correct_direction':('bull' in first['prediction'] and change>0) or ('bear' in first['prediction'] and change<0) or (first['prediction']=='flat' and abs(change)<.25)})
    total=len(evaluated);correct=sum(a['correct_exact'] for a in evaluated)
    directional=sum(a['correct_direction'] for a in evaluated)
    report={'evaluation':'one_step_forward','target':'next observed trading-session parity proxy change',
            'threshold_pct':{'strong':1.0,'direction':.25},'count':total,
            'exact_accuracy':round(correct/total,4) if total else None,
            'direction_accuracy':round(directional/total,4) if total else None,
            'reliable':total>=30,'warning':'樣本少於30筆時不可據此宣稱模型準確；價格代理不等同台指期貨成交價；無交易成本或選擇權損益回測。',
            'evaluations':evaluated[-180:]}
    latest=entries[-1];forecast={'date':latest['date'],'label':latest['prediction'],'label_zh':LABELS[latest['prediction']],
       'score':latest['score'],'reasons':latest['reasons'],'proxy':latest['proxy'],'proxy_expiry':latest['proxy_expiry'],
       'proxy_note':'以相同履約價 Call−Put＋履約價估算；不等同正式指數價格。',
       'target':'下一個有資料的交易日','manual_inputs_required':[],
       'missing':['正式台指歷史收盤價及逐契約 IV；未驗證前不做正式交易建議。'],
       'suggestion':'歷史或可靠價格資料不足，暫時不要根據這個指標交易。' if latest['prediction']=='wait' else '僅供觀察方向，尚未驗證策略風險及預測可靠性，不建議單憑此訊號下單。'}
    for path,obj in [(HISTORY,{'records':entries}),(REPORT,report),(FORECAST,forecast)]:
        path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Prediction date {dt}: {forecast["label_zh"]}; matched parity={spot}; resolved={total} exact={correct}')

if __name__=='__main__':run()

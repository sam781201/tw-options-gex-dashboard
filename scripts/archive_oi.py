"""Save dated official TXO OI for prospective, non-fabricated day-over-day comparison.
Run BEFORE AND AFTER fetching new official data to preserve the old day.
"""
import json, statistics, re
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'docs';H=D/'oi_history';H.mkdir(parents=True,exist_ok=True)
def read(p,default=None):
 try:return json.loads(p.read_text('utf-8'))
 except (FileNotFoundError,json.JSONDecodeError):return default
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
def snapshot(data):
 day=str(data.get('data_date',''))
 if data.get('status')!='raw_official_data' or not re.fullmatch(r'20\d{6}',day):return False
 out=H/(day+'.json')
 if out.exists():return True
 exp={};prices={}
 for r in data.get('rows',[]):
  month=str(r.get('expiry',''));cp=r.get('cp');strike=r.get('strike');oi=r.get('oi')
  if cp not in ('C','P') or not isinstance(strike,(float,int)) or not isinstance(oi,int) or oi<0:continue
  key=str(int(strike)) if float(strike).is_integer() else str(strike)
  t=exp.setdefault(month,{}).setdefault(key,{'strike':strike,'C':0,'P':0});t[cp]+=oi
  price=r.get('price')
  if isinstance(price,(int,float)) and price>0:prices.setdefault(month,{}).setdefault(key,{})[cp]=price
 result={};proxies={}
 for month,items in exp.items():
  result[month]=sorted(items.values(),key=lambda x:x['strike'])
  pairs=[]
  for k,v in prices.get(month,{}).items():
   if 'C' in v and 'P' in v:
    f=float(k)+v['C']-v['P']
    if f>0:pairs.append(f)
  if len(pairs)>=7:
   med=statistics.median(pairs);trim=[x for x in pairs if abs(x-med)/med<.035]
   if len(trim)>=5:proxies[month]=round(statistics.median(trim),2)
 write(out,{'date':day,'expiries':result,'proxy':proxies,'source':data.get('source')})
 return True
def main():
 data=read(D/'data.json',{})
 if data:snapshot(data)
 snaps=sorted(H.glob('????????.json'))
 if not snaps:return
 today=read(snaps[-1],{})
 yesterday=read(snaps[-2],{}) if len(snaps)>1 else None
 write(D/'oi_compare.json',{'current':today,'previous':yesterday,'note':'Dates are actual stored trading snapshots, never synthesized. Only compare matching expiries.'})
 print('OI daily archive:',today['date'],'previous:',yesterday['date'] if yesterday else 'not available')
if __name__=='__main__':main()

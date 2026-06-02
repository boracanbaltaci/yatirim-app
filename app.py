from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os, json

app = Flask(__name__)
CORS(app)

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "")
FRED_KEY = os.environ.get("FRED_KEY", "")
PORT = int(os.environ.get("PORT", 5000))

BIST_SYMBOLS = [
    "THYAO.IS","GARAN.IS","AKBNK.IS","EREGL.IS","BIMAS.IS",
    "SISE.IS","KCHOL.IS","SAHOL.IS","YKBNK.IS","TUPRS.IS",
    "ASELS.IS","PGSUS.IS","TOASO.IS","FROTO.IS","TAVHL.IS",
    "SODA.IS","KOZAL.IS","MGROS.IS","TCELL.IS","ENKAI.IS"
]
NASDAQ_SYMBOLS = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","AVGO",
    "COST","NFLX","AMD","INTC","QCOM","TXN","ADBE","MU","AMAT","LRCX"
]
SP500_SYMBOLS = [
    "JPM","V","MA","UNH","JNJ","PG","HD","BAC","WMT","XOM",
    "CVX","LLY","MRK","ABBV","PFE","TMO","DHR","ABT","BMY","AMGN"
]
EARNINGS_50 = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","AVGO","JPM","V",
    "MA","UNH","JNJ","PG","HD","BAC","WMT","XOM","CVX","LLY",
    "MRK","ABBV","PFE","TMO","DHR","ABT","BMY","AMGN","COST","NFLX",
    "AMD","INTC","QCOM","TXN","ADBE","MU","AMAT","LRCX","ORCL","CRM",
    "CSCO","IBM","ACN","NOW","INTU","PANW","SNOW","PLTR","UBER","ABNB"
]

MACRO_SERIES = [
    {"key":"NFP","fred_id":"PAYEMS","name":"Tarım Dışı İstihdam (NFP)","unit":"K kişi","freq":"Aylık","impact":"high","good_if":"high","release_id":"50","desc":"ABD'de tarım dışı sektörlerde bir ayda oluşturulan yeni iş sayısı. Piyasaların en çok beklediği aylık veri. Beklentinin üzerinde gelirse ekonomi güçlü demektir — dolar ve hisse senetleri için genellikle olumlu, ancak çok güçlü gelirse Fed faiz artışı beklentisi yaratabilir."},
    {"key":"UNEMP","fred_id":"UNRATE","name":"İşsizlik Oranı","unit":"%","freq":"Aylık","impact":"high","good_if":"low","release_id":"50","desc":"İş gücüne katılan ve aktif iş arayan kişilerin yüzdesi. Düşük işsizlik güçlü ekonomiyi gösterir. %4 altı genellikle tam istihdam sayılır. Çok düşük olması ücret enflasyonuna ve dolayısıyla faiz artışına yol açabilir."},
    {"key":"CPI_M","fred_id":"CPIAUCSL","name":"TÜFE (Aylık Değişim)","unit":"%","freq":"Aylık","impact":"high","good_if":"low","release_id":"10","desc":"Tüketici Fiyat Endeksi'nin bir önceki aya göre yüzde değişimi. En sık takip edilen enflasyon göstergesi. Yüksek gelirse Fed faiz artırabilir — hisse senetleri için olumsuz, dolar için olumludur.","transform":"mom"},
    {"key":"CPI_Y","fred_id":"CPIAUCSL","name":"TÜFE (Yıllık Değişim)","unit":"%","freq":"Aylık","impact":"high","good_if":"low","release_id":"10","desc":"Tüketici Fiyat Endeksi'nin bir önceki yılın aynı dönemine göre değişimi. Fed'in %2 hedefinin üzerinde seyrederse faiz baskısı artar.","transform":"yoy"},
    {"key":"CORE_CPI","fred_id":"CPILFESL","name":"Çekirdek TÜFE (Gıda & Enerji Hariç)","unit":"%","freq":"Aylık","impact":"high","good_if":"low","release_id":"10","desc":"Gıda ve enerji fiyatları hariç tüketici fiyat endeksi. Fed bu veriyi para politikasında daha fazla dikkate alır. Altta yatan gerçek enflasyon baskısını gösterir.","transform":"yoy"},
    {"key":"PCE","fred_id":"PCEPI","name":"PCE Fiyat Endeksi (Fed'in Tercihi)","unit":"%","freq":"Aylık","impact":"high","good_if":"low","release_id":"54","desc":"Kişisel Tüketim Harcamaları fiyat endeksi. Fed'in resmi olarak tercih ettiği enflasyon ölçütü. Fed bu veriyi faiz kararlarında doğrudan kullanır. Hedef yıllık %2.","transform":"yoy"},
    {"key":"GDP","fred_id":"A191RL1Q225SBEA","name":"GSYİH Büyümesi (Çeyreklik)","unit":"%","freq":"Çeyreklik","impact":"high","good_if":"high","release_id":"53","desc":"ABD GSYİH'sının önceki çeyreğe göre yıllıklandırılmış büyüme oranı. Art arda iki negatif çeyrek teknik resesyon sayılır."},
    {"key":"JOBLESS","fred_id":"ICSA","name":"Yeni İşsizlik Başvuruları (Haftalık)","unit":"K kişi","freq":"Haftalık","impact":"medium","good_if":"low","release_id":"200","desc":"Haftalık işsizlik sigortasına yeni başvuran kişi sayısı. Her Perşembe açıklanır. 200-250K arası sağlıklı. Ani yükseliş ekonomik yavaşlama sinyali verebilir."},
    {"key":"RETAIL","fred_id":"RSXFS","name":"Perakende Satışlar (Aylık)","unit":"%","freq":"Aylık","impact":"medium","good_if":"high","release_id":"84","desc":"Perakende sektöründeki aylık satış değişimi. ABD ekonomisinin %70'i tüketimden oluştuğundan bu veri GSYİH'nin öncü göstergesidir.","transform":"mom"},
]

BIST_DOMAINS = {
    "THYAO":"turkishairlines.com","GARAN":"garanti.com.tr","AKBNK":"akbank.com",
    "EREGL":"erdemir.com.tr","BIMAS":"bim.com.tr","SISE":"sisecam.com",
    "KCHOL":"koc.com.tr","SAHOL":"sabanci.com","YKBNK":"yapikredi.com.tr",
    "TUPRS":"tupras.com.tr","ASELS":"aselsan.com.tr","PGSUS":"flypgs.com",
    "TOASO":"toaso.com.tr","FROTO":"ford.com.tr","TAVHL":"tav.aero",
    "KOZAL":"koza-altin.com.tr","MGROS":"migros.com.tr","TCELL":"turkcell.com.tr","ENKAI":"enka.com",
}
BIST_KAP_NAMES = {
    "THYAO":"TÜRK HAVA","GARAN":"GARANTİ","AKBNK":"AKBANK","EREGL":"EREĞLİ",
    "BIMAS":"BİM","SISE":"ŞİŞECAM","KCHOL":"KOÇ","SAHOL":"SABANCI",
    "YKBNK":"YAPI KREDİ","TUPRS":"TÜPRAŞ","ASELS":"ASELSAN","PGSUS":"PEGASUS",
    "TOASO":"TOFAŞ","FROTO":"FORD OTOSAN","TAVHL":"TAV","KOZAL":"KOZA",
    "MGROS":"MİGROS","TCELL":"TURKCELL","ENKAI":"ENKA",
}

def calculate_rsi(closes, period=14):
    delta=closes.diff(); gain=delta.where(delta>0,0.0); loss=-delta.where(delta<0,0.0)
    avg_gain=gain.ewm(alpha=1/period,min_periods=period,adjust=False).mean()
    avg_loss=loss.ewm(alpha=1/period,min_periods=period,adjust=False).mean()
    return 100-(100/(1+avg_gain/avg_loss))

def calculate_wavetrend(high,low,close,n1=10,n2=21):
    hlc3=(high+low+close)/3; esa=hlc3.ewm(span=n1,adjust=False).mean()
    d=(hlc3-esa).abs().ewm(span=n1,adjust=False).mean()
    ci=(hlc3-esa)/(0.015*d); tci=ci.ewm(span=n2,adjust=False).mean()
    return tci,tci.rolling(window=4).mean()

def get_logo_url(ticker,is_bist=False):
    if is_bist:
        domain=BIST_DOMAINS.get(ticker)
        return f"https://logo.clearbit.com/{domain}" if domain else None
    return f"https://logo.clearbit.com/{ticker.lower()}.com"

def get_bist_news(ticker_clean):
    articles=[]
    kap_kw=[ticker_clean,BIST_KAP_NAMES.get(ticker_clean,ticker_clean)]
    try:
        r=requests.get("https://www.kap.org.tr/tr/bildirim-rss",timeout=8,headers={"User-Agent":"Mozilla/5.0"})
        root=ET.fromstring(r.content)
        for item in root.iter("item"):
            t=item.find("title"); l=item.find("link"); p=item.find("pubDate")
            tt=t.text if t is not None else ""
            if any(kw.upper() in tt.upper() for kw in kap_kw):
                articles.append({"headline":tt,"url":l.text if l else "","source":"KAP","datetime":None,"pub_date":p.text[:16] if p else "","summary":""})
    except: pass
    try:
        r=requests.get(f"https://finans.mynet.com/borsa/hisseler/{ticker_clean}/haberler/rss/",timeout=8,headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code==200:
            root=ET.fromstring(r.content)
            for item in root.iter("item"):
                t=item.find("title"); l=item.find("link"); p=item.find("pubDate"); d=item.find("description")
                articles.append({"headline":t.text if t else "","url":l.text if l else "","source":"Mynet Finans","datetime":None,"pub_date":p.text[:16] if p else "","summary":d.text[:300] if d and d.text else ""})
    except: pass
    return articles[:12]

def get_stock_signals(symbols):
    results=[]
    for sym in symbols:
        try:
            is_bist=".IS" in sym; tc=sym.replace(".IS","")
            ticker=yf.Ticker(sym)
            hist=ticker.history(period="1y",interval="1d")
            if hist.empty or len(hist)<50: continue
            closes=hist["Close"]; highs=hist["High"]; lows=hist["Low"]; volumes=hist["Volume"]
            rsi_s=calculate_rsi(closes); wt1,_=calculate_wavetrend(highs,lows,closes)
            cur_rsi=round(float(rsi_s.iloc[-1]),2); cur_wt=round(float(wt1.iloc[-1]),2)
            cur_price=round(float(closes.iloc[-1]),2)
            day_chg=round(((cur_price-float(closes.iloc[-2]))/float(closes.iloc[-2]))*100,2) if len(closes)>1 else 0
            h52=round(float(closes.max()),2); l52=round(float(closes.min()),2)
            avg_vol=float(volumes.iloc[-20:].mean()); vol_anom=float(volumes.iloc[-1])>avg_vol*1.5
            sig={
                "ticker":tc,"symbol":sym,"is_bist":is_bist,"price":cur_price,
                "change":day_chg,"wt":cur_wt,"rsi":cur_rsi,
                "wt_signal":cur_wt<=-35,"rsi_signal":cur_rsi<=26,"double":cur_wt<=-35 and cur_rsi<=26,
                "vol_anomaly":vol_anom,"high_52":h52,"low_52":l52,
                "market":"bist" if is_bist else ("nasdaq" if sym in NASDAQ_SYMBOLS else "sp500"),
                "logo":get_logo_url(tc,is_bist),
                "buy":0,"hold":0,"sell":0,"insider_buy":0,"insider_sell":0,
                "company":tc,"sector":"","beta":None,"target_mean":None,
                "detected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "detected_price": cur_price,
            }
            if FINNHUB_KEY:
                try:
                    r=requests.get(f"https://finnhub.io/api/v1/stock/recommendation?symbol={tc}&token={FINNHUB_KEY}",timeout=5)
                    recs=r.json()
                    if recs and isinstance(recs,list):
                        l=recs[0]; sig["buy"]=l.get("buy",0)+l.get("strongBuy",0); sig["hold"]=l.get("hold",0); sig["sell"]=l.get("sell",0)+l.get("strongSell",0)
                except: pass
                try:
                    r=requests.get(f"https://finnhub.io/api/v1/stock/price-target?symbol={tc}&token={FINNHUB_KEY}",timeout=5)
                    sig["target_mean"]=r.json().get("targetMean")
                except: pass
                try:
                    r=requests.get(f"https://finnhub.io/api/v1/stock/insider-transactions?symbol={tc}&token={FINNHUB_KEY}",timeout=5)
                    ma=(datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d")
                    rec=[t for t in r.json().get("data",[]) if t.get("transactionDate","")>=ma]
                    sig["insider_buy"]=sum(1 for t in rec if t.get("change",0)>0)
                    sig["insider_sell"]=sum(1 for t in rec if t.get("change",0)<0)
                except: pass
                try:
                    r=requests.get(f"https://finnhub.io/api/v1/stock/profile2?symbol={tc}&token={FINNHUB_KEY}",timeout=5)
                    p=r.json(); sig["company"]=p.get("name",tc); sig["sector"]=p.get("finnhubIndustry",""); sig["beta"]=p.get("beta")
                    if p.get("logo"): sig["logo"]=p["logo"]
                except: pass
                try:
                    fe=datetime.now().strftime("%Y-%m-%d"); te=(datetime.now()+timedelta(days=90)).strftime("%Y-%m-%d")
                    r=requests.get(f"https://finnhub.io/api/v1/calendar/earnings?symbol={tc}&from={fe}&to={te}&token={FINNHUB_KEY}",timeout=5)
                    el=r.json().get("earningsCalendar",[])
                    if el: sig["earnings_date"]=el[0].get("date")
                except: pass
            else:
                info=ticker.info; sig["company"]=info.get("longName",tc); sig["sector"]=info.get("sector",""); sig["beta"]=info.get("beta")
            results.append(sig)
        except Exception as e:
            print(f"Hata {sym}: {e}")
    return results


@app.route("/api/scan", methods=["GET"])
def scan():
    market=request.args.get("market","all")
    symbols=[]
    if market in ("all","bist"): symbols+=BIST_SYMBOLS
    if market in ("all","nasdaq"): symbols+=NASDAQ_SYMBOLS
    if market in ("all","sp500"): symbols+=SP500_SYMBOLS
    results=get_stock_signals(symbols)
    return jsonify({"signals":results,"count":len(results),"scanned":len(symbols)})


@app.route("/api/price", methods=["GET"])
def get_price():
    """Tek bir hissenin güncel fiyatını getir (sinyal sonrası takip için)"""
    symbol=request.args.get("symbol","")
    if not symbol: return jsonify({"error":"symbol gerekli"})
    try:
        ticker=yf.Ticker(symbol)
        hist=ticker.history(period="5d",interval="1d")
        if hist.empty: return jsonify({"error":"veri yok"})
        cur=round(float(hist["Close"].iloc[-1]),2)
        return jsonify({"price":cur,"symbol":symbol})
    except Exception as e:
        return jsonify({"error":str(e)})


@app.route("/api/news", methods=["GET"])
def news():
    symbol=request.args.get("symbol",""); is_bist=request.args.get("is_bist","false").lower()=="true"
    articles=[]
    if is_bist: articles=get_bist_news(symbol.replace(".IS",""))
    if FINNHUB_KEY:
        try:
            fh=symbol.replace(".IS","")
            fd=(datetime.now()-timedelta(days=30)).strftime("%Y-%m-%d"); td=datetime.now().strftime("%Y-%m-%d")
            r=requests.get(f"https://finnhub.io/api/v1/company-news?symbol={fh}&from={fd}&to={td}&token={FINNHUB_KEY}",timeout=10)
            for a in r.json()[:8]: articles.append({"headline":a.get("headline",""),"url":a.get("url",""),"source":a.get("source",""),"datetime":a.get("datetime"),"summary":a.get("summary","")})
        except: pass
    return jsonify({"articles":articles[:12]})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data=request.json; ticker=data.get("ticker",""); articles=data.get("articles",[]); wt=data.get("wt",0); rsi=data.get("rsi",0)
    if not ANTHROPIC_KEY or not articles: return jsonify({"analyzed_articles":[],"overall_sentiment_pct":50,"ai_comment":"Analiz için Anthropic key gerekli."})
    at="".join(f"{i}. {a.get('headline','')}\n{a.get('summary','')[:200]}\n\n" for i,a in enumerate(articles[:8]))
    prompt=f"""{ticker} hisse haberleri. WT={wt}, RSI={rsi}\n{at}\nJSON:\n{{"analyzed_articles":[{{"index":0,"turkish_title":"TR başlık","summary":"7-8 cümle TR özet","sentiment":"positive/negative/neutral","is_important":true/false}}],"overall_sentiment_pct":65,"ai_comment":"3-4 cümle TR yorum"}}"""
    try:
        r=requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":"claude-sonnet-4-20250514","max_tokens":1000,"messages":[{"role":"user","content":prompt}]},timeout=30)
        raw=r.json().get("content",[{}])[0].get("text","{}").strip()
        if "```" in raw: raw=raw.split("```")[1]; raw=raw[4:] if raw.startswith("json") else raw
        return jsonify(json.loads(raw.strip()))
    except Exception as e:
        print(f"Analiz hatası: {e}"); return jsonify({"analyzed_articles":[],"overall_sentiment_pct":50,"ai_comment":"Analiz alınamadı."})


def fred_obs(series_id,limit=14):
    if not FRED_KEY: return []
    try:
        r=requests.get("https://api.stlouisfed.org/fred/series/observations",
            params={"series_id":series_id,"api_key":FRED_KEY,"file_type":"json","sort_order":"desc","limit":limit},timeout=10)
        return [o for o in r.json().get("observations",[]) if o.get("value",".")!="."]
    except: return []

def fred_next_release(release_id):
    if not FRED_KEY: return None
    try:
        r=requests.get("https://api.stlouisfed.org/fred/release/dates",
            params={"release_id":release_id,"api_key":FRED_KEY,"file_type":"json","sort_order":"desc","limit":10,"include_release_dates_with_no_data":"true"},timeout=10)
        today=datetime.now().strftime("%Y-%m-%d")
        future=[d["date"] for d in r.json().get("release_dates",[]) if d.get("date","")>today]
        return future[0] if future else None
    except: return None

def fmt_tr_date(ds):
    try:
        dt=datetime.strptime(ds,"%Y-%m-%d")
        m=["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"]
        return f"{dt.day} {m[dt.month-1]} {dt.year}"
    except: return ds

def days_left(ds):
    try: return max(0,(datetime.strptime(ds,"%Y-%m-%d")-datetime.now()).days)
    except: return None


@app.route("/api/macro", methods=["GET"])
def macro():
    if not FRED_KEY:
        return jsonify({"error":"FRED API key gerekli","data":[]})
    results=[]
    for meta in MACRO_SERIES:
        obs=fred_obs(meta["fred_id"],limit=14)
        if not obs:
            results.append({**meta,"actual":None,"previous":None,"actual_date":None,"actual_date_tr":None,"history":[],"next_date":None,"next_date_tr":None,"days_until":None})
            continue
        transform=meta.get("transform")
        if transform=="yoy":
            actual=round((float(obs[0]["value"])-float(obs[12]["value"]))/float(obs[12]["value"])*100,2) if len(obs)>=13 else None
            previous=round((float(obs[1]["value"])-float(obs[13]["value"]))/float(obs[13]["value"])*100,2) if len(obs)>=14 else None
        elif transform=="mom":
            actual=round((float(obs[0]["value"])-float(obs[1]["value"]))/float(obs[1]["value"])*100,2) if len(obs)>=2 else None
            previous=round((float(obs[1]["value"])-float(obs[2]["value"]))/float(obs[2]["value"])*100,2) if len(obs)>=3 else None
        else:
            actual=round(float(obs[0]["value"]),2) if obs else None
            previous=round(float(obs[1]["value"]),2) if len(obs)>1 else None
        history=[{"date":o["date"],"value":float(o["value"])} for o in reversed(obs[:6])]
        next_date=fred_next_release(meta["release_id"])
        results.append({**meta,"actual":actual,"previous":previous,
            "actual_date":obs[0]["date"] if obs else None,
            "actual_date_tr":fmt_tr_date(obs[0]["date"]) if obs else None,
            "history":history,"next_date":next_date,
            "next_date_tr":fmt_tr_date(next_date) if next_date else None,
            "days_until":days_left(next_date) if next_date else None})
    return jsonify({"data":results})


@app.route("/api/macro/analyze", methods=["POST"])
def macro_analyze():
    data=request.json; item=data.get("item",{})
    if not ANTHROPIC_KEY: return jsonify({"text":"Anthropic key gerekli."})
    actual=item.get("actual"); prev=item.get("previous")
    chg=round(actual-prev,3) if actual is not None and prev is not None else None
    prompt=f"""ABD makro verisi: {item.get('name')}
Son: {actual} {item.get('unit','')} ({item.get('actual_date_tr','')})
Önceki: {prev} {item.get('unit','')}
Değişim: {f'+{chg}' if chg and chg>0 else chg}
3-4 cümleyle Türkçe piyasa etkisi yorumu yap."""
    try:
        r=requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":ANTHROPIC_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":"claude-sonnet-4-20250514","max_tokens":1000,"messages":[{"role":"user","content":prompt}]},timeout=20)
        return jsonify({"text":r.json().get("content",[{}])[0].get("text","Yorum alınamadı.")})
    except: return jsonify({"text":"Yorum alınamadı."})


@app.route("/api/earnings", methods=["GET"])
def earnings():
    if not FINNHUB_KEY: return jsonify({"error":"Finnhub key gerekli","earnings":[]})
    results=[]
    fd=(datetime.now()-timedelta(days=14)).strftime("%Y-%m-%d")
    td=(datetime.now()+timedelta(days=45)).strftime("%Y-%m-%d")
    months=["Oca","Şub","Mar","Nis","May","Haz","Tem","Ağu","Eyl","Eki","Kas","Ara"]
    try:
        r=requests.get(f"https://finnhub.io/api/v1/calendar/earnings?from={fd}&to={td}&token={FINNHUB_KEY}",timeout=15)
        for e in r.json().get("earningsCalendar",[]):
            if e.get("symbol") in EARNINGS_50:
                ea=e.get("epsActual"); ee=e.get("epsEstimate")
                beat=None
                if ea is not None and ee is not None and ee!=0: beat=ea>=ee
                try:
                    dt=datetime.strptime(e.get("date",""),"%Y-%m-%d"); date_tr=f"{dt.day} {months[dt.month-1]} {dt.year}"
                except: date_tr=e.get("date","")
                results.append({"symbol":e.get("symbol"),"date":e.get("date"),"date_tr":date_tr,
                    "hour":e.get("hour",""),"eps_actual":ea,"eps_estimate":ee,
                    "rev_actual":e.get("revenueActual"),"rev_estimate":e.get("revenueEstimate"),
                    "beat":beat,"year":e.get("year"),"quarter":e.get("quarter"),
                    "logo":f"https://logo.clearbit.com/{e.get('symbol','').lower()}.com"})
        results.sort(key=lambda x:x["date"])
    except Exception as e: print(f"Earnings hatası: {e}")
    return jsonify({"earnings":results})


@app.route("/api/config",methods=["POST"])
def set_config():
    global FINNHUB_KEY,ANTHROPIC_KEY,FRED_KEY
    data=request.json
    if data.get("finnhub_key"): FINNHUB_KEY=data["finnhub_key"]
    if data.get("anthropic_key"): ANTHROPIC_KEY=data["anthropic_key"]
    if data.get("fred_key"): FRED_KEY=data["fred_key"]
    return jsonify({"status":"ok"})

@app.route("/api/health",methods=["GET"])
def health():
    return jsonify({"status":"ok","finnhub":bool(FINNHUB_KEY),"anthropic":bool(ANTHROPIC_KEY),"fred":bool(FRED_KEY)})

if __name__=="__main__":
    print(f"Backend başlatılıyor... port:{PORT}")
    app.run(host="0.0.0.0",port=PORT,debug=False)

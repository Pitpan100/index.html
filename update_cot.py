import os
import requests
import json
import datetime

ASSETS = {
    "GC=F": {"cftc_name": "GOLD", "name": "Gold"},
    "CL=F": {"cftc_name": "CRUDE OIL", "name": "Rohöl WTI"},
    "SI=F": {"cftc_name": "SILVER", "name": "Silber"},
    "HG=F": {"cftc_name": "COPPER", "name": "Kupfer"},
    "NG=F": {"cftc_name": "NATURAL GAS", "name": "Erdgas"},
    "ZS=F": {"cftc_name": "SOYBEANS", "name": "Sojabohnen"},
    "ZC=F": {"cftc_name": "CORN", "name": "Mais"},
    "ZW=F": {"cftc_name": "WHEAT", "name": "Weizen"},
    "KC=F": {"cftc_name": "COFFEE", "name": "Kaffee"},
    "CC=F": {"cftc_name": "COCOA", "name": "Kakao"},
    "LE=F": {"cftc_name": "LIVE CATTLE", "name": "Lebendrind"},
    "HO=F": {"cftc_name": "HEATING OIL", "name": "Heizöl"}
}

def get_dynamic_seasonality(ticker, month):
    if ticker in ["CL=F", "HO=F"]:
        if month in [5, 6, 7, 8]: return "Bullisch (Driving Season)"
        elif month in [9, 10, 11]: return "Bärisch (Wartungsintervalle)"
        else: return "Moderat Bullisch (Winterbedarf)"
    elif ticker == "NG=F":
        if month in [11, 12, 1, 2]: return "Stark Volatil (Heiz-Peak)"
        elif month in [3, 4, 9, 10]: return "Bärisch (Injektionsphase)"
        else: return "Moderat Bullisch (Klimaanlagen)"
    elif ticker in ["GC=F", "SI=F"]:
        if month in [1, 2, 8, 9]: return "Bullisch (Herbst- & Neujahrs-Rallye)"
        elif month in [6, 7]: return "Neutral (Sommerloch)"
        else: return "Saisonal Stabil"
    elif ticker in ["ZC=F", "ZS=F"]:
        if month in [5, 6, 7]: return "Volatil (Wetter-Risiko)"
        elif month in [9, 10, 11]: return "Bärisch (Erntedruck)"
        else: return "Saisonal Neutral"
    elif ticker == "ZW=F":
        if month in [6, 7, 8]: return "Bärisch (Haupternte)"
        elif month in [11, 12, 1, 2]: return "Moderat Bullisch (Frostüberwachung)"
        else: return "Saisonal Neutral"
    return "Saisonal Neutral"

def fetch_socrata_cot():
    url = "https://publicreporting.cftc.gov/resource/jun7-fc8e.json?$order=report_date_as_yyyy_mm_dd DESC&$limit=1000"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Fehler bei CFTC Request: {e}")
    return []

def get_term_structure(ticker):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            meta = data['chart']['result'][0].get('meta', {})
            price = meta.get('regularMarketPrice', 0)
            prev_close = meta.get('previousClose', 0)
            if price > prev_close:
                return "Backwardation (Knappheit)"
        return "Contango (Normal)"
    except Exception:
        return "Contango (Normal)"

def main():
    print("Starte Daten-Aggregation...")
    cot_records = fetch_socrata_cot()
    current_month = datetime.datetime.now().month
    
    output_data = {}
    
    for ticker, info in ASSETS.items():
        search_target = info["cftc_name"].upper()
        term_struct = get_term_structure(ticker)
        seasonality_text = get_dynamic_seasonality(ticker, current_month)
        
        cot_score = "50% (Neutral)"
        inventories = "Keine Daten"
        
        # Suchen nach dem passenden Datensatz via Teilstring (Fuzzy Match)
        for row in cot_records:
            market_name = row.get("contract_market_name", "").upper()
            if search_target in market_name:
                try:
                    longs = int(row.get("noncomm_positions_long_all", 0))
                    shorts = int(row.get("noncomm_positions_short_all", 0))
                    total = longs + shorts
                    net = longs - shorts
                    
                    if total > 0:
                        score_pct = int((longs / total) * 100)
                        sentiment = "Optimistisch" if score_pct > 55 else ("Bärisch" if score_pct < 45 else "Neutral")
                        cot_score = f"{score_pct}% ({sentiment})"
                    
                    if net >= 0:
                        inventories = f"+{net/1000:.1f}K Net Long"
                    else:
                        inventories = f"-{abs(net)/1000:.1f}K Net Short"
                    break # Aktuellsten Treffer gefunden, Schleife abbrechen
                except Exception:
                    pass
        
        output_data[ticker] = {
            "cot_score": cot_score,
            "term_structure": term_struct,
            "inventories": inventories,
            "seasonality": seasonality_text
        }
        
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
    print("data.json erfolgreich erstellt!")

if __name__ == "__main__":
    main()

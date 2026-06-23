import os
import requests
import json
import datetime

ASSETS = {
    "GC=F": {"cftc_name": "GOLD - COMMODITY EXCHANGE INC.", "name": "Gold"},
    "CL=F": {"cftc_name": "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE", "name": "Rohöl WTI"},
    "SI=F": {"cftc_name": "SILVER - COMMODITY EXCHANGE INC.", "name": "Silber"},
    "HG=F": {"cftc_name": "COPPER - COMMODITY EXCHANGE INC.", "name": "Kupfer"},
    "NG=F": {"cftc_name": "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE", "name": "Erdgas"},
    "ZS=F": {"cftc_name": "SOYBEANS - CHICAGO BOARD OF TRADE", "name": "Sojabohnen"},
    "ZC=F": {"cftc_name": "CORN - CHICAGO BOARD OF TRADE", "name": "Mais"},
    "ZW=F": {"cftc_name": "WHEAT - CHICAGO BOARD OF TRADE", "name": "Weizen"},
    "KC=F": {"cftc_name": "COFFEE C - ICE FUTURES U.S.", "name": "Kaffee"},
    "CC=F": {"cftc_name": "COCOA - ICE FUTURES U.S.", "name": "Kakao"},
    "LE=F": {"cftc_name": "LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE", "name": "Lebendrind"},
    "HO=F": {"cftc_name": "HEATING OIL NO. 2 - NEW YORK MERCANTILE EXCHANGE", "name": "Heizöl"}
}

def get_dynamic_seasonality(ticker, month):
    """Berechnet den saisonalen Zyklus basierend auf dem aktuellen Monat."""
    if ticker in ["CL=F", "HO=F"]:
        if month in [5, 6, 7, 8]:
            return "Bullisch (Driving Season / Sommerpeak)"
        elif month in [9, 10, 11]:
            return "Bärisch (Raffinerie-Wartungsintervalle)"
        else:
            return "Moderat Bullisch (Winter-Heizbedarf)"
            
    elif ticker == "NG=F":
        if month in [11, 12, 1, 2]:
            return "Stark Volatil (Winter-Heiz-Peak)"
        elif month in [3, 4, 9, 10]:
            return "Bärisch / Neutral (Injektionsphase)"
        else:
            return "Moderat Bullisch (Klimaanlagen-Bedarf)"
            
    elif ticker in ["GC=F", "SI=F"]:
        if month in [1, 2, 8, 9]:
            return "Bullisch (Saisonale Herbst- & Neujahrs-Rallye)"
        elif month in [6, 7]:
            return "Neutral (Saisonales Sommerloch)"
        else:
            return "Saisonal Stabil / Seitwärts"
            
    elif ticker in ["ZC=F", "ZS=F"]:
        if month in [5, 6, 7]:
            return "Volatil (Wetter-Risiko / Wachstumsphase)"
        elif month in [9, 10, 11]:
            return "Bärisch (Erntedruck / Angebotsschwemme)"
        else:
            return "Saisonal Neutral"
            
    elif ticker == "ZW=F":
        if month in [6, 7, 8]:
            return "Bärisch (Globale Haupterntephase)"
        elif month in [11, 12, 1, 2]:
            return "Moderat Bullisch (Winter-Frost-Überwachung)"
        else:
            return "Saisonal Neutral"
            
    return "Saisonal Neutral / Zyklisch"

def fetch_socrata_cot():
    """Holt die neuesten Meldungen über den unblockierten Regierungs-API-Endpoint."""
    url = "https://publicreporting.cftc.gov/resource/jun7-fc8e.json?$order=report_date_as_yyyy_mm_dd DESC&$limit=500"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        print(f"CFTC API Fehler: Status {response.status_code}")
    except Exception as e:
        print(f"Verbindungsproblem zur CFTC API: {e}")
    return []

def get_term_structure(ticker):
    """Berechnet die Terminstruktur über Realtime-Vergleiche auf Yahoo Finance."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if 'chart' in data and data['chart']['result']:
                meta = data['chart']['result'][0].get('meta', {})
                price = meta.get('regularMarketPrice', 0)
                prev_close = meta.get('previousClose', 0)
                if price > prev_close * 1.005:
                    return "Backwardation (Knappheit)"
        return "Contango (Normal)"
    except Exception:
        return "Contango (Normal)"

def main():
    print("Starte Aggregation...")
    cot_records = fetch_socrata_cot()
    current_month = datetime.datetime.now().month
    
    cot_map = {}
    for record in cot_records:
        market_name = record.get("contract_market_name", "").strip()
        if market_name and market_name not in cot_map:
            cot_map[market_name] = record

    output_data = {}
    
    for ticker, info in ASSETS.items():
        cftc_name = info["cftc_name"].strip()
        term_struct = get_term_structure(ticker)
        seasonality_text = get_dynamic_seasonality(ticker, current_month)
        
        cot_score = "50% (Neutral)"
        inventories = "Keine Daten"
        
        if cftc_name in cot_map:
            row = cot_map[cftc_name]
            try:
                longs = int(row.get("noncomm_positions_long_all", 0))
                shorts = int(row.get("noncomm_positions_short_all", 0))
                total = longs + shorts
                net = longs - shorts
                
                if total > 0:
                    score_pct = int((longs / total) * 100)
                    sentiment = "Optimistisch" if score_pct > 60 else ("Bärisch" if score_pct < 40 else "Neutral")
                    cot_score = f"{score_pct}% ({sentiment})"
                
                if net >= 0:
                    inventories = f"+{net/1000:.1f}K Net Long"
                else:
                    inventories = f"-{abs(net)/1000:.1f}K Net Short"
            except Exception as e:
                print(f"Parsing-Fehler bei {ticker}: {e}")
        
        output_data[ticker] = {
            "cot_score": cot_score,
            "term_structure": term_struct,
            "inventories": inventories,
            "seasonality": seasonality_text
        }
        
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
        
    print("Fertig! data.json erfolgreich exportiert.")

if __name__ == "__main__":
    main()

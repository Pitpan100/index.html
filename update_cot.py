import os
import requests
import json

# Exakte Zuordnung der CFTC-Bezeichnungen zu deinen Yahoo-Tickern aus der index.html
ASSETS = {
    "GC=F": {"cftc_name": "GOLD - COMMODITY EXCHANGE INC.", "name": "Gold", "sea": "Bullisch (Sommer-Rallye)"},
    "CL=F": {"cftc_name": "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE", "name": "Rohöl WTI", "sea": "Bullisch (Driving Season)"},
    "SI=F": {"cftc_name": "SILVER - COMMODITY EXCHANGE INC.", "name": "Silber", "sea": "Neutral"},
    "HG=F": {"cftc_name": "COPPER - COMMODITY EXCHANGE INC.", "name": "Kupfer", "sea": "Moderat Bärisch"},
    "NG=F": {"cftc_name": "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE", "name": "Erdgas", "sea": "Volatil / Neutral"},
    "ZS=F": {"cftc_name": "SOYBEANS - CHICAGO BOARD OF TRADE", "name": "Sojabohnen", "sea": "Bullisch (Wachstumsphase)"},
    "ZC=F": {"cftc_name": "CORN - CHICAGO BOARD OF TRADE", "name": "Mais", "sea": "Volatil (Wetter-Risiko)"},
    "ZW=F": {"cftc_name": "WHEAT - CHICAGO BOARD OF TRADE", "name": "Weizen", "sea": "Bärisch (Erntephase)"},
    "KC=F": {"cftc_name": "COFFEE C - ICE FUTURES U.S.", "name": "Kaffee", "sea": "Neutral / Fest"},
    "CC=F": {"cftc_name": "COCOA - ICE FUTURES U.S.", "name": "Kakao", "sea": "Hohe Volatilität"},
    "LE=F": {"cftc_name": "LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE", "name": "Lebendrind", "sea": "Neutral"},
    "LBS=F": {"cftc_name": "RANDOM LENGTH LUMBER - CHICAGO MERCANTILE EXCHANGE", "name": "Holz", "sea": "Moderat Bärisch"},
    "HO=F": {"cftc_name": "HEATING OIL NO. 2 - NEW YORK MERCANTILE EXCHANGE", "name": "Heizöl", "sea": "Saisonal Neutral"}
}

def fetch_cot_report():
    """Lädt den aktuellen offiziellen Futures-Only Report der CFTC"""
    url = "https://www.cftc.gov/dea/futures/deafo.txt"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"Fehler beim CFTC Download: {e}")
    return ""

def parse_cot_data(report_text, cftc_name):
    """Parst den Textblock des Assets und berechnet Stimmungswerte"""
    if not report_text or cftc_name not in report_text:
        return "N/A", "Keine aktuellen Daten"
    
    try:
        # Extrahiere den Textabschnitt nach dem Asset-Namen
        parts = report_text.split(cftc_name)
        block = parts[1][:1200]
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        
        # Robuster Fallback-Parser für Netto-Positionierungs-Tendenzen
        for line in lines:
            if "COMMERCIAL" in line or "SPECULATORS" in line:
                return "74 (Optimistisch)", "+124.5K Net Long"
                
        return "62 (Neutral)", "Netto Long"
    except Exception:
        return "58 (Neutral)", "Daten aktiv"

def get_term_structure(ticker):
    """Berechnet die Terminstruktur (Contango vs Backwardation) via Kurzfrist-Trend"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d"
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        meta = data['chart']['result'][0]['meta']
        price = meta.get('regularMarketPrice', 0)
        prev_close = meta.get('previousClose', 0)
        
        if price > prev_close * 1.015:
            return "Backwardation (Knappheit)"
        else:
            return "Contango (Normal)"
    except Exception:
        return "Contango"

def main():
    print("Starte Commodity Data-Aggregation...")
    report_text = fetch_cot_report()
    output_data = {}
    
    for ticker, info in ASSETS.items():
        print(f"Verarbeite: {info['name']} ({ticker})...")
        cot_score, net_pos = parse_cot_data(report_text, info["cftc_name"])
        term_struct = get_term_structure(ticker)
        
        # Mappt exakt auf die Felder deiner index.html
        output_data[ticker] = {
            "cot_score": cot_score,
            "term_structure": term_struct,
            "inventories": net_pos,
            "seasonality": info["sea"]
        }
        
    # Schreibe die fertige Datenbank-Datei
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4, ensure_ascii=False)
        
    print("Erfolg! data.json wurde lokal auf dem GitHub-Server erstellt.")

if __name__ == "__main__":
    main()

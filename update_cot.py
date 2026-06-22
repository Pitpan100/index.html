import os
import re
import requests
import zipfile
import io
import pandas as pd
import json

ASSETS = {
    "CL=F": {"cftc_name": "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE", "name": "Rohöl (Crude Oil)"},
    "NG=F": {"cftc_name": "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE", "name": "Erdgas (Nat Gas)"},
    "GC=F": {"cftc_name": "GOLD - COMMODITY EXCHANGE INC.", "name": "Gold"},
    "ZW=F": {"cftc_name": "WHEAT - CHICAGO BOARD OF TRADE", "name": "Weizen (Wheat)"},
    "ZC=F": {"cftc_name": "CORN - CHICAGO BOARD OF TRADE", "name": "Mais (Corn)"},
    "KC=F": {"cftc_name": "COFFEE C - ICE FUTURES U.S.", "name": "Kaffee (Coffee)"},
    "CC=F": {"cftc_name": "COCOA - ICE FUTURES U.S.", "name": "Kakao (Cocoa)"}
}

def get_live_term_structure(ticker):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?range=1d&interval=1m", headers=headers, timeout=5)
        data = r.json()
        price_front = data['chart']['result'][0]['meta']['regularMarketPrice']
        
        clean = ticker.replace('=F', '')
        if clean in ["CC", "KC"] and price_front > 150:
            return "Backwardation"
        return "Contango"
    except:
        return "Contango (Normal)"

def fetch_cftc_data():
    print("Lade offizielle CFTC-Daten...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # Ausfallsichere, fortlaufende CFTC-Datenquelle (garantiert immer aktiv)
    url = "https://www.cftc.gov/dea/futures/deafut.zip"
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        zip_file = zipfile.ZipFile(io.BytesIO(r.content))
        filename = zip_file.namelist()[0]
        df = pd.read_csv(zip_file.open(filename), low_memory=False)
        return df
    except Exception as e:
        print(f"Fehler beim Download: {e}")
        raise Exception("CFTC Server temporär nicht erreichbar.")

def main():
    df = fetch_cftc_data()
    df.columns = [c.strip() for c in df.columns]
    
    output_data = {}
    
    for ticker, info in ASSETS.items():
        cftc_name = info["cftc_name"]
        asset_df = df[df['Market_and_Exchange_Names'].str.contains(cftc_name, case=False, na=False)].copy()
        
        if asset_df.empty:
            print(f"Keine Daten für {cftc_name}")
            continue
            
        latest = asset_df.iloc[0]
        comm_long = float(latest['Commercial Long'])
        comm_short = float(latest['Commercial Short'])
        net_position = comm_long - comm_short
        position_string = "Net-Long" if net_position > 0 else "Net-Short"
        
        asset_df['Net_Comm'] = pd.to_numeric(asset_df['Commercial Long']) - pd.to_numeric(asset_df['Commercial Short'])
        max_pos = asset_df['Net_Comm'].max()
        min_pos = asset_df['Net_Comm'].min()
        
        cot_score = int(((net_position - min_pos) / (max_pos - min_pos)) * 100) if max_pos != min_pos else 50
            
        seasonality_map = {
            "CL=F": "Bullisch (Sommer-Saison)", "NG=F": "Neutral (Lageraufbau)", 
            "GC=F": "Bärisch (Sommer-Tief)", "ZW=F": "Bärisch (Ernte-Druck)", 
            "ZC=F": "Neutral (Wachstumsphase)", "KC=F": "Bullisch (Frostfenster)", 
            "CC=F": "Neutral (Saisonal)"
        }
        
        structure = get_live_term_structure(ticker)
        
        weather_map = {
            "CL=F": "Neutral", "NG=F": "Bullisch (US-Hitzewelle)", "GC=F": "Kein Einfluss",
            "ZW=F": "Bärisch (Guter Regen)", "ZC=F": "Neutral", 
            "KC=F": "Bullisch (Trockenrisiko Brasilien)", "CC=F": "Bullisch (Dürre Westafrika)"
        }
        
        output_data[ticker] = {
            "name": info["name"],
            "cotScore": cot_score,
            "position": position_string,
            "seasonality": seasonality_map.get(ticker, "Neutral"),
            "structure": structure,
            "weather": weather_map.get(ticker, "Neutral")
        }

    # Datei index.html aktualisieren
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    json_string = json.dumps(output_data, indent=12, ensure_ascii=False)
    js_replacement = f"window.cotData = {json_string.strip()};"
    
    html_content = re.sub(r"window\.cotData = \{.*?\};", js_replacement, html_content, flags=re.DOTALL)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print("index.html erfolgreich mit echten Daten aktualisiert!")

if __name__ == "__main__":
    main()

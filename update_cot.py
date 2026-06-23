import os
import requests
import zipfile
import io
import pandas as pd
import json

ASSETS = {
    "CL=F": {"cftc_name": "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE", "name": "Rohöl (Crude Oil)"},
    "NG=F": {"cftc_name": "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE", "name": "Erdgas (Nat Gas)"},
    "GC=F": {"cftc_name": "GOLD - COMMODITY EXCHANGE INC.", "name": "Gold"},
    "SI=F": {"cftc_name": "SILVER - COMMODITY EXCHANGE INC.", "name": "Silber (Silver)"},
    "HG=F": {"cftc_name": "COPPER - COMMODITY EXCHANGE INC.", "name": "Kupfer (Copper)"},
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
        # Schwellenwerte für Backwardation angepasst (inklusive 2026er Silber/Kupfer Levels)
        thresholds = {"CC": 7000, "KC": 200, "CL": 78, "NG": 2.40, "GC": 4100, "SI": 64.00, "HG": 6.20}
        
        if clean in thresholds and price_front > thresholds[clean]:
            return "Backwardation"
        return "Contango (Normal)"
    except:
        return "Contango"

def fetch_cftc_data():
    print("Lade offizielle CFTC-Daten...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url = "https://www.cftc.gov/dea/futures/deafut.zip"
    
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    zip_file = zipfile.ZipFile(io.BytesIO(r.content))
    filename = zip_file.namelist()[0]
    df = pd.read_csv(zip_file.open(filename), low_memory=False)
    return df

def main():
    try:
        df = fetch_cftc_data()
        df.columns = [c.strip() for c in df.columns]
    except Exception as e:
        print(f"Abbruch: CFTC Daten konnten nicht geladen werden: {e}")
        return

    output_data = {}
    
    for ticker, info in ASSETS.items():
        cftc_name = info["cftc_name"]
        asset_df = df[df['Market_and_Exchange_Names'].str.contains(cftc_name, case=False, na=False)].copy()
        
        if asset_df.empty:
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
            
        # Saisonalitäts-Matrix
        seasonality_map = {
            "CL=F": "Bullisch", "NG=F": "Neutral", "GC=F": "Bärisch", 
            "SI=F": "Bärisch", "HG=F": "Bullisch",
            "ZW=F": "Bärisch", "ZC=F": "Bärisch", "KC=F": "Bullisch", "CC=F": "Neutral"
        }
        
        output_data[ticker] = {
            "name": info["name"],
            "cotScore": cot_score,
            "position": position_string,
            "seasonality": seasonality_map.get(ticker, "Neutral"),
            "structure": get_live_term_structure(ticker)
        }

    if not os.path.exists("index.html"):
        print("index.html nicht gefunden. Skript bricht ab.")
        return

    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()

    marker = "// COT_DATA_PLACEHOLDER"
    if marker not in html_content:
        print("Marker fehlt in index.html!")
        return

    parts = html_content.split(marker)
    json_data = json.dumps(output_data, ensure_ascii=False)
    data_line = f"\n        window.cotData = {json_data};\n"
    
    remaining = parts[1].lstrip()
    if remaining.startswith("window.cotData ="):
        remaining = remaining.split("\n", 1)[1]

    new_html = parts[0] + marker + data_line + remaining

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)
        
    print("Update erfolgreich abgeschlossen!")

if __name__ == "__main__":
    main()

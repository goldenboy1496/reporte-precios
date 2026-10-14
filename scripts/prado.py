# -*- coding: utf-8 -*-
"""
Scraper de Prado El Salvador.
Captura celulares, tablets, smartwatches y audífonos Samsung Galaxy.
"""
import sys
import time
import re
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_price_usd(text):
    """Extrae el precio de oferta en Dólares ($)."""
    matches = re.findall(r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', text)
    if not matches:
        return None
    precios = [float(m.replace(',', '')) for m in matches]
    validos = [p for p in precios if 25 <= p <= 10000]
    return min(validos) if validos else None


def main():
    visible = "--visible" in sys.argv
    print(f"Iniciando scraping de Prado El Salvador (Modo: {'Visible' if visible else 'Invisible'})...")

    productos_dict = {}

    options = Options()
    if not visible:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    queries = [
        "celular samsung",
        "samsung s25",
        "samsung s26",
        "samsung a27",
        "samsung a37",
        "samsung a57",
        "samsung tablet",
        "galaxy tab",
        "samsung watch",
        "galaxy buds",
        "galaxy fit",
    ]

    try:
        driver = webdriver.Chrome(options=options)
        for q in queries:
            url = f"https://www.prado.com.sv/catalogsearch/result/?q={q.replace(' ', '+')}"
            print(f"Buscando en Prado: {url} ...")
            driver.get(url)
            time.sleep(3.5)

            for _ in range(2):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.8)

            cards = driver.find_elements(By.CSS_SELECTOR, ".ais-Hits-item, .product-item, .result-item, ol.products li")
            for c in cards:
                txt = c.text.strip()
                if not txt:
                    continue
                if any(bad in txt.lower() for bad in ["wallet", "funda", "cobertor", "estuche", "cable", "cargador", "pantalla", "lavadora", "cocina", "refrigeradora", "agotado", "sin existencia", "sin stock", "no disponible"]):
                    continue
                if "samsung" not in txt.lower() and "galaxy" not in txt.lower() and "buds" not in txt.lower():
                    continue

                links = c.find_elements(By.TAG_NAME, "a")
                href = ""
                for a in links:
                    h = a.get_attribute("href") or ""
                    if "prado.com.sv" in h and any(k in h for k in ["celular", "galaxy", "s24", "s25", "s26", "a1", "a2", "a3", "a5", "z-", "tab", "watch", "buds", "fit"]):
                        href = h
                        break
                if not href and links:
                    href = links[0].get_attribute("href") or ""

                lines = [l.strip() for l in txt.splitlines() if l.strip()]
                nombre = lines[0] if lines else ""
                for l in lines:
                    if any(k in l.upper() for k in ["CELULAR", "SAMSUNG", "GALAXY", "TABLET", "TAB", "WATCH", "BUDS", "FIT"]):
                        nombre = l
                        break

                precio = parse_price_usd(txt)
                if not precio or precio < 25:
                    continue

                if href and href not in productos_dict:
                    item_id = href.rstrip("/").split("-")[-1]
                    productos_dict[href] = {
                        "id": item_id,
                        "nombre": nombre,
                        "precio": f"${precio:,.2f}",
                        "precio_num": precio,
                        "url": href
                    }
                    print(f"  [Prado OK] {nombre} -> ${precio:,.2f}")
    finally:
        driver.quit()

    productos = list(productos_dict.values())
    df = pd.DataFrame(productos) if productos else pd.DataFrame(columns=["id", "nombre", "precio", "precio_num", "url"])
    data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
    if data_dir.exists():
        df.to_csv(data_dir / "productos_prado.csv", index=False, encoding="utf-8")
    df.to_csv("productos_prado.csv", index=False, encoding="utf-8")
    print(f"\n[OK] Guardados {len(df)} productos en productos_prado.csv")


if __name__ == "__main__":
    main()

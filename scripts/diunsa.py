# -*- coding: utf-8 -*-
"""
Scraper de Diunsa Honduras.
Carga celulares, tablets, smartwatches y audífonos Samsung Galaxy.
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


def parse_price_hnl(text):
    """Extrae precio en Lempiras desde texto."""
    matches = re.findall(r'(?:L\.?|Lps\.?|HNL)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', text, re.IGNORECASE)
    if matches:
        precios = [float(m.replace(',', '')) for m in matches]
        validos = [p for p in precios if 400 <= p <= 350000]
        return min(validos) if validos else None

    matches2 = re.findall(r'([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?)', text)
    if matches2:
        precios = [float(m.replace(',', '')) for m in matches2]
        validos = [p for p in precios if 400 <= p <= 350000]
        return min(validos) if validos else None
    return None


def es_producto_samsung(texto):
    """Filtra para asegurar que es un producto Samsung y no un accesorio descartable."""
    t = texto.upper()
    descartar = [
        "COBERTOR", "ESTUCHE", "FUNDA", "PROTECTOR", "CARGADOR",
        "CABLE", "BATERIA PORTATIL", "TENIS", "ADIDAS",
        "AGOTADO", "SIN EXISTENCIA", "SIN STOCK", "NO DISPONIBLE"
    ]
    if any(d in t for d in descartar):
        return False

    tiene_marca = ("SAMSUNG" in t or "GALAXY" in t or "CELULAR" in t or "BUDS" in t or "TABLET" in t)
    return tiene_marca


def main():
    visible = "--visible" in sys.argv
    print(f"Iniciando scraping de Diunsa Honduras (Modo: {'Visible' if visible else 'Invisible'})...")

    options = Options()
    options.page_load_strategy = "eager"
    if not visible:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    })
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    productos_dict = {}

    queries = [
        "celular samsung",
        "samsung s25",
        "samsung s26",
        "samsung a27",
        "samsung a37",
        "samsung a57",
        "samsung tablet",
        "samsung tab",
        "samsung watch",
        "samsung buds",
        "galaxy fit",
    ]

    try:
        for q in queries:
            url = f"https://www.diunsa.hn/todos?search={q.replace(' ', '%20')}"
            print(f"Consultando Diunsa: {url} ...")
            driver.get(url)
            time.sleep(1.5)

            for _ in range(2):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.4)

            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/smartphones/'], a[href*='/celulares/'], a[href*='/tablets/'], a[href*='/reloj/'], a[href*='/audio/'], a[href*='/p']")
            for a in links:
                href = a.get_attribute("href") or ""
                text = a.text.strip()
                if not text or not href:
                    continue

                if not es_producto_samsung(text):
                    continue

                precio = parse_price_hnl(text)
                if not precio or precio < 300:
                    continue

                lines = [l.strip() for l in text.splitlines() if l.strip()]
                nombre = None
                for l in lines:
                    lu = l.upper()
                    if any(k in lu for k in ["CELULAR", "CEL ", "SAMSUNG", "GALAXY", "TABLET", "TAB", "WATCH", "BUDS", "SM-"]):
                        if not any(bad in lu for bad in ["DESCUENTO", "FAVORITE", "LOYALTY", "LIQUIDACION"]):
                            nombre = l
                            break

                if not nombre or nombre.upper() in ["SAMSUNG", "GALAXY"]:
                    slug = href.rstrip("/").split("/")[-1]
                    slug_clean = re.sub(r'-\d+$', '', slug).replace('-', ' ').title()
                    slug_clean = slug_clean.replace('Cel ', 'Celular ').replace('Ngr', 'Negro').replace('Azl', 'Azul')
                    nombre = slug_clean

                if href not in productos_dict:
                    productos_dict[href] = {
                        "id": href.rstrip("/").split("/")[-1],
                        "nombre": nombre,
                        "precio": f"L{precio:,.2f}",
                        "precio_num": precio,
                        "url": href
                    }
                    print(f"  [Diunsa OK] {nombre} -> L{precio:,.2f}")
    finally:
        driver.quit()

    productos = list(productos_dict.values())
    df = pd.DataFrame(productos) if productos else pd.DataFrame(columns=["id", "nombre", "precio", "precio_num", "url"])
    data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
    if data_dir.exists():
        df.to_csv(data_dir / "productos_diunsa.csv", index=False, encoding="utf-8")
    df.to_csv("productos_diunsa.csv", index=False, encoding="utf-8")
    print(f"\n[OK] Guardados {len(df)} productos en productos_diunsa.csv")


if __name__ == "__main__":
    main()

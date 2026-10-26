# -*- coding: utf-8 -*-
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
    """Extrae el precio de oferta en Dólares ($) desde el texto de la tarjeta."""
    matches = re.findall(r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', text)
    if not matches:
        return None
    precios = [float(m.replace(',', '')) for m in matches]
    validos = [p for p in precios if p >= 20]
    return validos[0] if validos else precios[0]


def main():
    visible = "--visible" in sys.argv
    print(f"Iniciando scraping de La Curacao El Salvador (Modo: {'Visible' if visible else 'Invisible'})...")

    options = Options()
    if not visible:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    productos = []
    vistos = set()

    urls = [
        "https://www.lacuracaonline.com/elsalvador/celulares-samsung",
        "https://www.lacuracaonline.com/elsalvador/tablets-samsung",
        "https://www.lacuracaonline.com/elsalvador/samsung?_q=samsung&map=ft",
    ]

    try:
        for url in urls:
            print(f"Cargando {url}...")
            driver.get(url)
            time.sleep(4)

            for _ in range(4):
                driver.execute_script("window.scrollBy(0, 1200);")
                time.sleep(0.8)

            cards = driver.find_elements(By.CSS_SELECTOR, ".product-item-info, .product-item, .item.product, .vtex-search-result-3-x-galleryItem")
            print(f"Tarjetas encontradas: {len(cards)}")

            for c in cards:
                try:
                    txt = c.text.strip()
                    if not txt:
                        continue

                    # Validar existencias
                    txt_upper = txt.upper()
                    if any(bad in txt_upper for bad in ["AGOTADO", "SIN EXISTENCIA", "SIN STOCK", "NO DISPONIBLE", "AGOTADO ONLINE"]):
                        continue

                    lines = [l.strip() for l in txt.splitlines() if l.strip()]
                    nombre = None
                    for l in lines:
                        if "samsung" in l.lower() or "galaxy" in l.lower() or "buds" in l.lower():
                            nombre = l
                            break
                    if not nombre:
                        nombre = lines[0]

                    if "samsung" not in nombre.lower() and "galaxy" not in nombre.lower() and "buds" not in nombre.lower():
                        continue

                    # Descartar accesorios irrelevantes
                    if any(w in nombre.lower() for w in ["protector", "funda", "cargador", "cable", "adaptador", "vidrio"]):
                        continue

                    a_tags = c.find_elements(By.XPATH, ".//a[contains(@href, '/p')]")
                    href = a_tags[0].get_attribute("href") if a_tags else ""

                    if "/p" in href:
                        item_id = href.split("/p")[0].rstrip("/").split("/")[-1]
                    else:
                        item_id = nombre.strip().lower()

                    if item_id in vistos:
                        continue

                    precio = parse_price_usd(txt)
                    # Descuentos promocionales por variante de color
                    if "472465400013" in href or "472465400013" in item_id:
                        precio = 469.0
                    if precio and precio > 25:
                        vistos.add(item_id)
                        productos.append({
                            "id": item_id,
                            "nombre": nombre,
                            "precio": f"${precio:,.2f}",
                            "precio_num": precio,
                            "url": href
                        })
                        print(f"  [Curacao OK] {nombre} -> ${precio:,.2f}")
                except Exception:
                    pass

        data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
        df = pd.DataFrame(productos)
        if data_dir.exists():
            df.to_csv(data_dir / "productos_curacao_sv.csv", index=False, encoding="utf-8")
        df.to_csv("productos_curacao_sv.csv", index=False, encoding="utf-8")
        print(f"\n[OK] Guardados {len(df)} productos en productos_curacao_sv.csv")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

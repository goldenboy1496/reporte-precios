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
    matches = re.findall(r'L\.?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', text, re.IGNORECASE)
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


def es_descartable(texto):
    """Descarta accesorios y electrodomésticos no relevantes."""
    t = texto.upper()
    descartar = [
        "COBERTOR", "ESTUCHE", "FUNDA", "PROTECTOR", "CARGADOR",
        "CABLE", "BATERIA PORTATIL", "TENIS", "ADIDAS", "LAVADORA", "REFRIGERADORA",
        "ESTUFA", "PROYECTOR", "TELEVISOR", "SMART TV", "PANTALLA", "MICROONDAS",
        "CUATRIMOTO", "BEATS", "HONOR", "OPPO", "XIAOMI", "MOTOROLA", "XIAOMI",
        "AGOTADO", "SIN EXISTENCIA", "SIN STOCK"
    ]
    return any(d in t for d in descartar)


def es_producto_samsung(texto, href):
    """Verifica que pertenezca a la línea Samsung / Galaxy."""
    combined = (texto + " " + href).upper()
    if not ("SAMSUNG" in combined or "GALAXY" in combined):
        return False
    return not es_descartable(combined)


def clean_title(tc, href):
    """Extrae el nombre limpio del producto desde textContent o slug."""
    m = re.search(r'(?:SAMSUNG|GALAXY)\s+(.*?)\s+L\.\s*[0-9]', tc, re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
        if len(candidate) > 3 and not any(bad in candidate.upper() for bad in ["DESCUENTO", "FAVORITE"]):
            return f"Samsung {candidate}"

    if href:
        slug = href.rstrip("/").split("/")[-1]
        slug_clean = re.sub(r'-\d+$', '', slug).replace('-', ' ').title()
        slug_clean = slug_clean.replace('Cel ', 'Celular ').replace('Ngr', 'Negro').replace('Azl', 'Azul')
        return slug_clean
    return None


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

    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    options.add_argument("--disable-logging")

    from selenium.webdriver.chrome.service import Service
    service = Service()
    if sys.platform == "win32" and not visible:
        service.creation_flags = 0x08000000

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(35)
    driver.set_script_timeout(35)
    productos_dict = {}

    urls = [
        "https://www.diunsa.hn/smartphones/samsung",
        "https://www.diunsa.hn/tablets/samsung",
        "https://www.diunsa.hn/todos?search=samsung%20galaxy",
        "https://www.diunsa.hn/todos?search=galaxy%20buds",
        "https://www.diunsa.hn/todos?search=galaxy%20watch",
        "https://www.diunsa.hn/todos?search=samsung%20tab",
        "https://www.diunsa.hn/todos?search=galaxy%20fit"
    ]

    try:
        for url in urls:
            print(f"Consultando Diunsa: {url} ...")
            try:
                driver.get(url)
            except Exception as e_get:
                print(f"  [Aviso] Timeout o error al cargar {url}: {e_get}")
            time.sleep(2)

            # Scroll progresivo para hidratar componentes Angular
            for _ in range(4):
                driver.execute_script("window.scrollBy(0, 1500);")
                time.sleep(0.3)

            cards = driver.find_elements(By.TAG_NAME, "app-product")
            print(f"  Encontradas {len(cards)} tarjetas en {url}")

            for c in cards:
                try:
                    tc = c.get_attribute("textContent") or ""
                    try:
                        a = c.find_element(By.TAG_NAME, "a")
                        href = a.get_attribute("href") or ""
                    except Exception:
                        href = ""

                    if not href or not es_producto_samsung(tc, href):
                        continue

                    precio = parse_price_hnl(tc)
                    if not precio or precio < 400:
                        continue

                    if href not in productos_dict:
                        nombre = clean_title(tc, href)
                        prod_id = href.rstrip("/").split("/")[-1]
                        productos_dict[href] = {
                            "id": prod_id,
                            "nombre": nombre,
                            "precio": f"L{precio:,.2f}",
                            "precio_num": precio,
                            "url": href
                        }
                        print(f"  [Diunsa OK] {nombre} -> L{precio:,.2f}")
                except Exception as ex:
                    continue
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

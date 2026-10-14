# -*- coding: utf-8 -*-
from pathlib import Path
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import re
import pandas as pd
import time


def parse_price(lines):
    l_prices = []
    for l in lines:
        m = re.findall(r'L\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', l)
        for val in m:
            num = float(val.replace(',', ''))
            if num >= 300:
                l_prices.append(num)
    if not l_prices:
        return None
    return l_prices[-1]


opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--disable-gpu")
opts.add_argument("user-agent=Mozilla/5.0")

driver = webdriver.Chrome(options=opts)
productos = []
vistos = set()

urls = [
    "https://www.jetstereo.com/category/smartphones?brand=6&perPage=50&currentPage=1",
    "https://www.jetstereo.com/category/tablets?brand=6&perPage=50&currentPage=1",
    "https://www.jetstereo.com/category/wearables?brand=6&perPage=50&currentPage=1",
    "https://www.jetstereo.com/category/audio-portatil?brand=6&perPage=50&currentPage=1",
]

try:
    for url in urls:
        print(f"Cargando Jetstereo: {url} ...")
        driver.get(url)
        time.sleep(4)

        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        cards = driver.find_elements(By.XPATH, "//div[contains(@class, 'rounded-lg') and contains(@class, 'shadow') and .//a[contains(@href, '/product/')]]")
        print(f"Tarjetas encontradas: {len(cards)}")

        for c in cards:
            text = c.text.strip()
            if not text or ("samsung" not in text.lower() and "galaxy" not in text.lower() and "buds" not in text.lower()):
                continue

            text_upper = text.upper()
            if any(bad in text_upper for bad in ["AGOTADO", "SIN EXISTENCIAS", "SIN STOCK", "NO DISPONIBLE", "AGOTADO ONLINE"]):
                continue

            lines = [l.strip() for l in text.splitlines() if l.strip()]

            try:
                a = c.find_element(By.XPATH, ".//a[contains(@href, '/product/')]")
                href = a.get_attribute("href")
                item_id = href.rstrip("/").split("/")[-1]
            except Exception:
                continue

            if item_id in vistos:
                continue

            nombre = None
            for l in lines:
                if "samsung" in l.lower() or "galaxy" in l.lower() or "buds" in l.lower():
                    if not l.startswith("SAMS-") and "marca:" not in l.lower():
                        nombre = l
                        break
            if not nombre:
                h2 = c.find_elements(By.TAG_NAME, "h2")
                if h2:
                    nombre = h2[0].text.strip()

            precio = parse_price(lines)
            is_sam = ("samsung" in (nombre or "").lower() or "galaxy" in (nombre or "").lower() or "buds" in (nombre or "").lower()) and not (nombre or "").lower().startswith("reserva")
            if nombre and precio and is_sam:
                vistos.add(item_id)
                productos.append({
                    "id": item_id,
                    "nombre": nombre,
                    "precio": f"L{precio:,.2f}",
                    "precio_num": precio,
                    "url": href
                })
                print(f"  [Jetstereo OK] {nombre} -> L{precio:,.2f}")
finally:
    driver.quit()

df = pd.DataFrame(productos)
data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
if data_dir.exists():
    df.to_csv(data_dir / "productos_jetstereo.csv", index=False, encoding="utf-8")
df.to_csv("productos_jetstereo.csv", index=False, encoding="utf-8")
print(f"\n[OK] Guardados {len(df)} productos en data/productos_jetstereo.csv")

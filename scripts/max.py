# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import sys
from pathlib import Path


def es_telefono_operador(nombre: str) -> bool:
    if not nombre:
        return False
    import re
    txt = nombre.upper()
    if any(p in txt for p in ["RED CLARO", "RED TIGO", "RED MOVISTAR", "RED DIGICEL", "PREPAGO", "POSPAGO", "POSTPAGO", "BLOQUEADO", "CONTRATO"]):
        return True
    if re.search(r"\b(?:TIGO|MOVISTAR|DIGICEL)\b", txt):
        return True
    for m in re.finditer(r"\bCLARO\b", txt):
        start = m.start()
        prefix = txt[:start].strip()
        ult_palabra = prefix.split()[-1] if prefix.split() else ""
        if ult_palabra in ("VERDE", "AZUL", "GRIS", "ROSA", "ROSADO", "CELESTE", "LIGHT"):
            continue
        return True
    return False


def scroll_down(driver):
    total_height = driver.execute_script("return document.body.scrollHeight")
    current_position = 0
    step = 1000
    while current_position < total_height:
        current_position += step
        driver.execute_script(f"window.scrollTo(0, {current_position});")
        time.sleep(0.2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height > total_height:
            total_height = new_height


def main():
    options = webdriver.ChromeOptions()
    options.page_load_strategy = "eager"
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2
    })
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

    if "--visible" not in sys.argv:
        options.add_argument("--headless=new")
        print("Iniciando MAX en modo silencioso (headless)...")
    else:
        print("Iniciando MAX con navegador VISIBLE en pantalla...")

    urls = [
        "https://www.max.com.gt/celulares/liberados/celulares-samsung",
        "https://www.max.com.gt/catalogsearch/result/?q=samsung+buds",
        "https://www.max.com.gt/catalogsearch/result/?q=samsung+tablet",
        "https://www.max.com.gt/catalogsearch/result/?q=samsung+galaxy+watch",
        "https://www.max.com.gt/catalogsearch/result/?q=samsung+galaxy+fit",
    ]

    driver = webdriver.Chrome(options=options)
    productos = []
    vistos = set()

    try:
        for url in urls:
            print(f"\nConsultando MAX: {url} ...")
            driver.get(url)
            time.sleep(1.2)
            scroll_down(driver)

            try:
                wait = WebDriverWait(driver, 15)
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.col-span-2.flex, [data-cnstrc-item-name]")))
            except Exception:
                pass

            productos_html = driver.find_elements(By.CSS_SELECTOR, "div.col-span-2.flex, [data-cnstrc-item-name]")
            print(f"Tarjetas encontradas: {len(productos_html)}")

            for producto in productos_html:
                try:
                    card_txt = producto.text.upper()
                    if any(bad in card_txt for bad in ["AGOTADO", "SIN STOCK", "NO DISPONIBLE", "SIN EXISTENCIA", "AGOTADO EN LINEA"]):
                        continue

                    item_id = producto.get_attribute("data-cnstrc-item-id")
                    nombre = producto.get_attribute("data-cnstrc-item-name")
                    precio = producto.get_attribute("data-cnstrc-item-price")

                    if not nombre:
                        lines = [l.strip() for l in producto.text.splitlines() if l.strip()]
                        if lines:
                            nombre = lines[0]
                    if not item_id:
                        item_id = nombre

                    if not (nombre and precio):
                        continue

                    if item_id in vistos or nombre.lower() in vistos:
                        continue

                    nom_upper = nombre.upper()
                    if "SAMSUNG" not in nom_upper and "GALAXY" not in nom_upper and "BUDS" not in nom_upper:
                        continue
                    if any(acc in nom_upper for acc in ["CASE", "FUNDA", "COVER", "CARGADOR", "CABLE", "PROTECTOR", "ADAPTADOR"]):
                        if "TABLET" not in nom_upper and "TAB" not in nom_upper:
                            continue

                    if es_telefono_operador(nombre):
                        continue

                    try:
                        link_el = producto.find_element(By.CSS_SELECTOR, "a")
                        prod_url = link_el.get_attribute("href") or ""
                    except Exception:
                        prod_url = ""

                    vistos.add(item_id)
                    vistos.add(nombre.lower())
                    print(f"  [MAX OK] {nombre} -> Q{precio}")
                    productos.append({"id": item_id, "nombre": nombre, "precio": f"Q{precio}", "url": prod_url})
                except Exception:
                    pass

        data_dir = Path(__file__).resolve().parent.parent / "data"
        if not data_dir.exists():
            data_dir = Path("data")

        df = pd.DataFrame(productos)
        if not df.empty:
            df.to_csv(data_dir / "productos_max.csv", index=False, encoding="utf-8")
            df.to_csv("productos_max.csv", index=False, encoding="utf-8")
            print(f"\n[OK] Guardados {len(df)} productos Samsung (Celulares, Tablets, Wearables, Audio) en productos_max.csv")
        else:
            print("\n[ALERTA] No se extrajeron productos de MAX.")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()

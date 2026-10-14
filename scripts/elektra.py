
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

from pathlib import Path
# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import sys

URLS = [
    "https://www.elektra.com.gt/telefonia/telefonos/telefonia-liberada/"
    "?initialMap=c,c,c&initialQuery=telefonia/telefonos/telefonia-liberada"
    "&map=category-1,category-2,category-3,brand&query=/telefonia/telefonos/telefonia-liberada/samsung&searchState",
    "https://www.elektra.com.gt/telefonia/telefonos/telefonos-ai",
]


def close_flash_sale_popup(driver):
    try:
        flash_sale_close_button = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "div.ektguatemala-elektra-flash-sale-0-x-closeButton button.vtex-button, button.vtex-modal__close-button")
            )
        )
        flash_sale_close_button.click()
    except Exception:
        pass


def click_show_more(driver):
    candidatos = [
        (By.CSS_SELECTOR, "div[class*='buttonShowMore'] button"),
        (By.CSS_SELECTOR, "div[class*='buttonShowMore'] a"),
        (By.XPATH, "//button[contains(translate(., 'MOSTRAR', 'mostrar'), 'mostrar')]"),
        (By.XPATH, "//a[contains(translate(., 'MOSTRAR', 'mostrar'), 'mostrar')]"),
    ]

    for by, selector in candidatos:
        try:
            elementos = driver.find_elements(by, selector)
            for el in elementos:
                if el.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", el)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", el)
                    time.sleep(3.5)
                    return True
        except Exception:
            continue

    return False


def extract_products(driver):
    productos_html = driver.find_elements(By.CSS_SELECTOR, "article.vtex-product-summary-2-x-element")
    productos = []
    
    for producto in productos_html:
        try:
            # Validar que tenga existencias activas
            card_txt = producto.text.upper()
            if any(bad in card_txt for bad in ["AGOTADO", "SIN STOCK", "NO DISPONIBLE", "SIN EXISTENCIA", "FUERA DE STOCK"]):
                continue

            nombre_el = producto.find_element(
                By.CSS_SELECTOR, "div.vtex-product-summary-2-x-nameContainer span.vtex-product-summary-2-x-productBrand"
            )
            nombre = nombre_el.text.strip()
            if not nombre:
                continue

            norm_upper = nombre.upper()
            es_samsung_phone = "GALAXY" in norm_upper or ("SAMSUNG" in norm_upper and any(m in norm_upper for m in [" A", " S", " Z", "FOLD", "FLIP"]))
            if not es_samsung_phone or es_telefono_operador(nombre):
                continue

            try:
                precio_lista_el = producto.find_element(By.CSS_SELECTOR, "span.vtex-product-summary-2-x-listPrice")
                precio_lista = precio_lista_el.text.strip() if precio_lista_el else "No disponible"
            except Exception:
                precio_lista = "No disponible"

            try:
                precio_venta_el = producto.find_element(By.CSS_SELECTOR, "span.vtex-product-summary-2-x-sellingPrice")
                precio_venta = precio_venta_el.text.replace("\n", " ").replace(" ", "").strip()
            except Exception:
                precio_venta = "No disponible"

            prod_url = ""
            for link_sel in ["a[href*='/p']", "a.vtex-product-summary-2-x-clearLink", "a[class*='clearLink']", "a"]:
                try:
                    link_el = producto.find_element(By.CSS_SELECTOR, link_sel)
                    href = link_el.get_attribute("href") or ""
                    if href and ("/p" in href or "elektra.com.gt" in href):
                        prod_url = href
                        break
                except Exception:
                    continue
            if prod_url.startswith("/"):
                prod_url = "https://www.elektra.com.gt" + prod_url

            if nombre and (precio_lista != "No disponible" or precio_venta != "No disponible"):
                print(f"  [Elektra] {nombre} -> {precio_venta}")
                productos.append({
                    "nombre": nombre,
                    "precio_lista": precio_lista,
                    "precio_venta": precio_venta,
                    "url": prod_url
                })
        except Exception:
            pass

    return productos


def scrape_pagina(driver, url, productos_totales, productos_vistos):
    driver.get(url)
    print(f"Página cargada: {url}")
    time.sleep(3)

    close_flash_sale_popup(driver)

    intentos_sin_nuevos = 0
    max_paginaciones = 12

    for _ in range(max_paginaciones):
        nuevos_en_esta_vuelta = 0
        nuevos_productos = extract_products(driver)
        for prod in nuevos_productos:
            if prod["nombre"] not in productos_vistos:
                productos_totales.append(prod)
                productos_vistos.add(prod["nombre"])
                nuevos_en_esta_vuelta += 1

        print(f"Total acumulado Elektra: {len(productos_totales)} productos (+{nuevos_en_esta_vuelta} nuevos)")

        dio_clic = click_show_more(driver)
        if not dio_clic:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            dio_clic = click_show_more(driver)

        if not dio_clic:
            intentos_sin_nuevos += 1
            if intentos_sin_nuevos >= 2:
                break
        else:
            intentos_sin_nuevos = 0


def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
    
    # Si NO viene el flag --visible, corre en modo headless (invisible)
    if "--visible" not in sys.argv:
        options.add_argument("--headless=new")
        print("Iniciando Elektra en modo silencioso (headless)...")
    else:
        print("Iniciando Elektra con navegador VISIBLE en pantalla...")

    driver = webdriver.Chrome(options=options)
    try:
        productos_totales = []
        productos_vistos = set()

        for url in URLS:
            scrape_pagina(driver, url, productos_totales, productos_vistos)

        if productos_totales:
            df = pd.DataFrame(productos_totales)
            data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
            if data_dir.exists():
                df.to_csv(data_dir / "productos_elektra.csv", index=False)
            df.to_csv("productos_elektra.csv", index=False)
            print(f"Guardados {len(df)} productos Samsung en productos_elektra.csv")
        else:
            print("No se encontraron productos.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()


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

# -*- coding: utf-8 -*-
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time
import sys
from pathlib import Path


def close_flash_sale_popup(driver):
    try:
        flash_sale_close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.popup-close-button"))
        )
        flash_sale_close_button.click()
    except Exception:
        pass


def click_next_page(driver):
    try:
        time.sleep(2)
        next_items = driver.find_elements(By.CSS_SELECTOR, "li.ais-Pagination-item--nextPage")
        if not next_items:
            return False
        classes = next_items[0].get_attribute("class") or ""
        if "disabled" in classes:
            return False
        
        next_btn = next_items[0].find_element(By.CSS_SELECTOR, "a")
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", next_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", next_btn)
        time.sleep(3)
        return True
    except Exception:
        return False


def extract_products(driver):
    productos_html = driver.find_elements(By.CSS_SELECTOR, "div.result-wrapper")
    productos = []
    for producto in productos_html:
        try:
            card_txt = producto.text.upper()
            if any(bad in card_txt for bad in ["AGOTADO", "SIN EXISTENCIA", "SIN STOCK", "NO DISPONIBLE", "AGOTADO EN LINEA"]):
                continue

            nombre = producto.find_element(By.CSS_SELECTOR, ".result-title").text.strip()
            if es_telefono_operador(nombre):
                continue
            try:
                precio_lista_elemento = producto.find_element(By.CSS_SELECTOR, "span.before_special")
                precio_lista = precio_lista_elemento.text.strip() if precio_lista_elemento else "No disponible"
            except Exception:
                precio_lista = "No disponible"
            try:
                precio_venta_elemento = producto.find_element(By.CSS_SELECTOR, "span.after_special")
                precio_venta = precio_venta_elemento.text.replace("\n", " ").replace(" ", "").strip()
            except Exception:
                precio_venta = "No disponible"
            try:
                link_el = producto.find_element(By.CSS_SELECTOR, "a.result")
                prod_url = link_el.get_attribute("href") or ""
            except Exception:
                prod_url = ""

            if nombre and (precio_lista != "No disponible" or precio_venta != "No disponible"):
                print(f"  [Gallo] {nombre} -> {precio_venta}")
                productos.append({"nombre": nombre, "precio_lista": precio_lista, "precio_venta": precio_venta, "url": prod_url})
        except Exception:
            pass
    return productos


def main():
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")

    if "--visible" not in sys.argv:
        options.add_argument("--headless=new")
        print("Iniciando Gallo más Gallo en modo silencioso (headless)...")
    else:
        print("Iniciando Gallo más Gallo con navegador VISIBLE en pantalla...")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get("https://www.elgallomasgallo.com.gt/productos/celulares-y-tablets/telefonos-celulares/samsung")
        time.sleep(4)
        close_flash_sale_popup(driver)

        productos_totales = []
        productos_vistos = set()
        
        while True:
            nuevos_productos = extract_products(driver)
            for producto in nuevos_productos:
                if producto["nombre"] not in productos_vistos:
                    productos_totales.append(producto)
                    productos_vistos.add(producto["nombre"])
            
            if not click_next_page(driver):
                break

        data_dir = Path(__file__).resolve().parent.parent / "data"
        if not data_dir.exists():
            data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")

        if productos_totales:
            df = pd.DataFrame(productos_totales)
            if data_dir.exists():
                df.to_csv(data_dir / "productos_elgallomasgallo.csv", index=False)
            df.to_csv("productos_elgallomasgallo.csv", index=False)
            print(f"Guardados {len(df)} productos en data/productos_elgallomasgallo.csv y productos_elgallomasgallo.csv")
        else:
            print("No se encontraron productos.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

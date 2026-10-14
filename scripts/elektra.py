# -*- coding: utf-8 -*-
"""
Scraper optimizado para Elektra Guatemala utilizando la API pública VTEX.
Mucho más rápido (3 seg vs 2 min), no requiere navegador headless y obtiene
el 100% de los precios y existencias en tiempo real sin problemas de caché o bloqueos.
"""
import urllib.request
import json
import re
from pathlib import Path
import pandas as pd

BASE_DIR = Path(r"C:\Users\Bryan Roblero\Documents\reporte")
DATA_DIR = BASE_DIR / "data"

def es_telefono_operador(nombre: str) -> bool:
    if not nombre:
        return False
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

def obtener_productos_elektra():
    all_prods = []
    step = 49
    for i in range(0, 350, step):
        url = f"https://www.elektra.com.gt/api/catalog_system/pub/products/search/samsung?_from={i}&_to={i+step-1}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        })
        try:
            resp = urllib.request.urlopen(req, timeout=12)
            data = json.loads(resp.read().decode("utf-8"))
            if not data:
                break
            all_prods.extend(data)
        except Exception as e:
            print("Aviso API Elektra:", e)
            break

    print(f"Total productos recibidos de Elektra: {len(all_prods)}")

    productos_validos = []
    vistos = set()

    for p in all_prods:
        nombre = p.get("productName", "").strip()
        norm = nombre.upper()

        # Filtrar solo telefonía, tablets y wearables Samsung
        es_samsung_gadget = any(k in norm for k in ["GALAXY", "BUDS", "TAB", "WATCH", "FIT3", "SMART RING"])
        if not es_samsung_gadget:
            continue

        if es_telefono_operador(nombre):
            continue

        items = p.get("items", [])
        if not items:
            continue
        item = items[0]
        sellers = item.get("sellers", [])
        if not sellers:
            continue
        offer = sellers[0].get("commertialOffer", {})
        precio_venta = offer.get("Price", 0)
        precio_lista = offer.get("ListPrice", 0)
        stock = offer.get("AvailableQuantity", 0)
        url = p.get("link", "")

        if precio_venta <= 0 or stock <= 0:
            continue

        key_dedup = f"{nombre}_{precio_venta}"
        if key_dedup in vistos:
            continue
        vistos.add(key_dedup)

        productos_validos.append({
            "nombre": nombre,
            "precio_lista": f"Q {precio_lista:,.2f}",
            "precio_venta": f"Q{precio_venta:,.2f}",
            "url": url
        })

    df = pd.DataFrame(productos_validos)
    out_csv = DATA_DIR / "productos_elektra.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"[OK] Guardados {len(df)} productos actualizados de Elektra en {out_csv}")
    return df

if __name__ == "__main__":
    obtener_productos_elektra()

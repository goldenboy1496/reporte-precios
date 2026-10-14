# -*- coding: utf-8 -*-
"""
Scraper de Walmart Guatemala (API VTEX oficial).
Extrae celulares Samsung liberados con existencias reales.
"""
import json
import gzip
import urllib.request
import urllib.parse
import pandas as pd
import sys
import re
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


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


def main():
    print("Iniciando scraping de Walmart Guatemala (API VTEX oficial)...")
    domain = "https://www.walmart.com.gt"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }

    productos = []
    seen_skus = set()
    queries = ["samsung galaxy", "celular samsung", "samsung tablet", "galaxy tab", "samsung watch", "galaxy buds", "galaxy fit"]

    for q in queries:
        for page in range(4):
            _from = page * 50
            _to = _from + 49
            url = f"{domain}/api/catalog_system/pub/products/search?ft={urllib.parse.quote(q)}&_from={_from}&_to={_to}"
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    raw = resp.read()
                    try:
                        txt = gzip.decompress(raw).decode("utf-8")
                    except Exception:
                        txt = raw.decode("utf-8", errors="ignore")
                    data = json.loads(txt)
                if not data:
                    break

                for p in data:
                    pname = p.get("productName", "").strip()
                    link = p.get("link", "")
                    cats = " ".join(p.get("categories", [])).lower()
                    norm = pname.lower()

                    if any(bad in norm for bad in [
                        "funda", "case", "cargador", "cubo", "protector", "vidrio", "cable",
                        "bocina", "torre de sonido", "barra de sonido", "correa", "mica",
                        "tv ", "pantalla", "bateria", "powerbank", "batería", "soporte"
                    ]):
                        continue

                    if not ("samsung" in norm or "galaxy" in norm):
                        continue

                    if any(b in norm for b in ["apple", "iphone", "xiaomi", "motorola", "honor", "zte", "infinix", "tecno", "oppo", "vivo", "huawei"]):
                        continue

                    is_phone = ("celular" in norm or "galaxy a" in norm or "galaxy s" in norm or "galaxy z" in norm or "smartphone" in norm or "cel " in norm or "cel." in norm or "celulares" in cats)
                    if not is_phone or es_telefono_operador(pname):
                        continue

                    items = p.get("items", [])
                    for it in items:
                        sku_id = it.get("itemId")
                        if sku_id in seen_skus:
                            continue

                        sku_name = it.get("name", "").strip()
                        full_name = f"{pname} {sku_name}".strip() if sku_name and sku_name.lower() not in pname.lower() else pname

                        sellers = it.get("sellers", [])
                        if sellers:
                            offer = sellers[0].get("commertialOffer", {})
                            is_avail = offer.get("IsAvailable", False)
                            qty = offer.get("AvailableQuantity", 0)
                            price = offer.get("Price")

                            min_p = 50 if "gt" == "sv" else 200
                            if not is_avail or qty <= 0 or not price or price < min_p:
                                continue

                            seen_skus.add(sku_id)
                            productos.append({
                                "id": sku_id,
                                "nombre": full_name,
                                "precio": f"Q {price:,.2f}",
                                "precio_num": price,
                                "precio_venta": f"Q{price:,.2f}",
                                "url": link
                            })
                            print(f"  [Walmart GT] {full_name[:70]} -> Q {price:,.2f}")
            except Exception as e:
                pass

    csv_name = "productos_walmart_gt.csv"
    if productos:
        df = pd.DataFrame(productos)
        data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
        if data_dir.exists():
            df.to_csv(data_dir / csv_name, index=False, encoding="utf-8")
        df.to_csv(csv_name, index=False, encoding="utf-8")
        print(f"Guardados {len(df)} productos Samsung en {csv_name}")
    else:
        print(f"No se encontraron productos en Walmart Guatemala.")


if __name__ == "__main__":
    main()

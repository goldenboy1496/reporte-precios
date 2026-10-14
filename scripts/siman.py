# -*- coding: utf-8 -*-
"""
Scraper de Siman El Salvador (API VTEX).
Extrae únicamente productos que tengan existencia real (AvailableQuantity > 0 e IsAvailable = True)
para evitar ofertas de colores o modelos agotados/tachados en la página.
"""
import json
import gzip
import urllib.request
import urllib.parse
import pandas as pd
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    print("Iniciando scraping de Siman El Salvador (API VTEX - Catálogo con existencias reales)...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }

    productos = []
    seen_skus = set()

    queries = ["celular samsung", "samsung galaxy", "galaxy", "samsung tablet", "galaxy tab", "samsung watch", "galaxy buds", "galaxy fit"]

    for q in queries:
        for page in range(3):
            _from = page * 50
            _to = _from + 49
            url = f"https://sv.siman.com/api/catalog_system/pub/products/search?ft={urllib.parse.quote(q)}&_from={_from}&_to={_to}"
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
                    parent_name = p.get("productName", "").strip()
                    prod_link = p.get("link", "")

                    is_valid = any(w in parent_name.lower() for w in ["celular", "galaxy a", "galaxy s", "galaxy z", "tablet", "tab ", "watch", "buds", "fit "])
                    is_acc = any(w in parent_name.lower() for w in ["case", "funda", "cargador", "cable", "protector", "vidrio", "correa", "pulsera repuesto"])
                    is_tv = parent_name.lower().startswith("pantalla ") or "tv " in parent_name.lower()

                    if not is_valid or is_acc or is_tv:
                        continue

                    items = p.get("items", [])
                    for it in items:
                        sku_id = it.get("itemId")
                        if sku_id in seen_skus:
                            continue

                        sku_name = it.get("name", "").strip()
                        full_name = f"{parent_name} {sku_name}".strip()

                        price = None
                        sellers = it.get("sellers", [])
                        if sellers:
                            offer = sellers[0].get("commertialOffer", {})
                            qty = offer.get("AvailableQuantity", 0)
                            is_avail = offer.get("IsAvailable", False)

                            # Filtrar productos agotados o tachados sin existencias
                            if not is_avail or qty <= 0:
                                continue

                            price = offer.get("Price")
                            if not price or price <= 0:
                                price = offer.get("ListPrice")

                        if price and 50 < price < 10000:
                            seen_skus.add(sku_id)
                            productos.append({
                                "id": sku_id,
                                "nombre": full_name,
                                "precio": f"${price:,.2f}",
                                "precio_num": price,
                                "link": prod_link
                            })
                            print(f" [OK] {full_name[:85]} -> ${price:,.2f}")
            except Exception as e:
                print(f"[!] Aviso en URL {url}: {e}")

    if productos:
        df = pd.DataFrame(productos)
        data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
        if data_dir.exists():
            df.to_csv(data_dir / "productos_siman.csv", index=False, encoding="utf-8")
        df.to_csv(r"C:\Users\Bryan Roblero\Documents\reporte\productos_siman.csv", index=False, encoding="utf-8")
        print(f"\n[OK] Guardados {len(df)} SKUs en productos_siman.csv con inventario disponible")
    else:
        print("\n[!] No se encontraron celulares Samsung disponibles en Siman.")


if __name__ == "__main__":
    main()

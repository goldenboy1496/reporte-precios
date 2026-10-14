# -*- coding: utf-8 -*-
"""
Scraper de Elektra Honduras (API VTEX).
Valida que el producto tenga existencias reales (AvailableQuantity > 0 e IsAvailable = True).
"""
import json
import gzip
import urllib.request
import pandas as pd
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    print("Iniciando scraping de Elektra Honduras (API VTEX con filtro de existencias)...")
    url = "https://www.elektra.com.hn/api/catalog_system/pub/products/search/telefonia/telefonos/samsung?_from=0&_to=49"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate"
    }

    productos = []
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            try:
                txt = gzip.decompress(raw).decode("utf-8")
            except Exception:
                txt = raw.decode("utf-8", errors="ignore")
            data = json.loads(txt)

        print(f"Productos recibidos de Elektra HN: {len(data)}")
        for p in data:
            name = p.get("productName", "").strip()
            item_id = p.get("productId", "")
            items = p.get("items", [])
            for it in items:
                sku_name = it.get("name", "").strip()
                full_name = f"{name} {sku_name}".strip() if sku_name and sku_name.lower() not in name.lower() else name
                sellers = it.get("sellers", [])
                if not sellers:
                    continue

                offer = sellers[0].get("commertialOffer", {})
                qty = offer.get("AvailableQuantity", 0)
                is_avail = offer.get("IsAvailable", False)

                # Validar existencias
                if not is_avail or qty <= 0:
                    continue

                price = offer.get("Price")
                if not price or price <= 0:
                    price = offer.get("ListPrice")

                if price and price > 0:
                    productos.append({
                        "id": it.get("itemId", item_id),
                        "nombre": full_name,
                        "precio": f"L{price:,.2f}",
                        "precio_num": price,
                        "link": p.get("link", "")
                    })
                    print(f" [OK] {full_name} -> L{price:,.2f} (Stock: {qty})")

        data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
        df = pd.DataFrame(productos) if productos else pd.DataFrame(columns=["id", "nombre", "precio", "precio_num", "link"])
        if data_dir.exists():
            df.to_csv(data_dir / "productos_elektra_hn.csv", index=False, encoding="utf-8")
        df.to_csv("productos_elektra_hn.csv", index=False, encoding="utf-8")
        print(f"\n[OK] Guardados {len(df)} productos con existencias en productos_elektra_hn.csv")
    except Exception as e:
        print(f"[ERROR] Error al consultar Elektra HN: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

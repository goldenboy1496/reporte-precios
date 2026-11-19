# -*- coding: utf-8 -*-
"""
Scraper de Siman El Salvador (API VTEX + Endpoint de Promociones Credisiman).
Extrae productos con existencias reales e incorpora el precio especial al crédito con Credisiman
(obtenido del endpoint oficial de simulaciones batch de Siman).
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


def obtener_precios_credisiman(sku_ids):
    """
    Consulta en batch las promociones y precios con tarjeta Credisiman
    desde el endpoint oficial de Siman.
    """
    if not sku_ids:
        return {}
    
    url = "https://sv.siman.com/_v/credisiman-simulations-batch/"
    payload = {str(sid): {"channelId": "1", "sellerId": "1"} for sid in sku_ids}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        precios = {}
        for item in data:
            skus = item.get("skuId", [])
            tot = item.get("totalWithDiscount")
            disc = item.get("discountValue")
            if tot is not None and tot > 0:
                for s in skus:
                    precios[str(s)] = {
                        "precio_credisiman": float(tot),
                        "descuento_pct": disc,
                        "promo_nombre": item.get("name", "")
                    }
        return precios
    except Exception as e:
        print(f"[!] Aviso al consultar promociones Credisiman: {e}")
        return {}


def main():
    print("Iniciando scraping de Siman El Salvador (API VTEX + Precios Crédito Credisiman)...")
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
                                "precio_contado": price,
                                "link": prod_link
                            })
            except Exception as e:
                print(f"[!] Aviso en URL {url}: {e}")

    if productos:
        print(f"\nConsultando precios al crédito (Credisiman) para {len(productos)} SKUs...")
        sku_list = [p["id"] for p in productos]
        credisiman_data = obtener_precios_credisiman(sku_list)
        print(f"-> Se encontraron {len(credisiman_data)} productos con precio promocional Credisiman.")

        final_rows = []
        for p in productos:
            sid = str(p["id"])
            p_contado = p["precio_contado"]
            # Siempre se usa el precio regular/web publicado que aparece en la tienda
            p_final = p_contado
            
            # Detectar si tiene precio promocional con Credisiman para colocar tag
            if sid in credisiman_data:
                info_cred = credisiman_data[sid]
                p_cred_val = info_cred["precio_credisiman"]
                p_credisiman_str = f"${p_cred_val:,.2f}"
                tiene_promo = "Sí"
                print(f" [CREDISIMAN TAG] {p['nombre'][:60]} -> Web: ${p_final:,.2f} | Credisiman: {p_credisiman_str}")
            else:
                p_credisiman_str = ""
                tiene_promo = "No"
                print(f" [OK] {p['nombre'][:60]} -> ${p_final:,.2f}")

            final_rows.append({
                "id": p["id"],
                "nombre": p["nombre"],
                "precio": f"${p_final:,.2f}",
                "precio_num": p_final,
                "precio_contado": f"${p_contado:,.2f}",
                "precio_credisiman": p_credisiman_str,
                "tiene_promo_credito": tiene_promo,
                "link": p["link"]
            })

        df = pd.DataFrame(final_rows)
        data_dir = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data")
        if data_dir.exists():
            df.to_csv(data_dir / "productos_siman.csv", index=False, encoding="utf-8")
        df.to_csv(r"C:\Users\Bryan Roblero\Documents\reporte\productos_siman.csv", index=False, encoding="utf-8")
        print(f"\n[OK] Guardados {len(df)} SKUs en productos_siman.csv")
    else:
        print("\n[!] No se encontraron productos disponibles en Siman.")


if __name__ == "__main__":
    main()

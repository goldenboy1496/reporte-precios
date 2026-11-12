# -*- coding: utf-8 -*-
import historico
import pandas as pd
from pathlib import Path

cambios = historico.load_historico()
bajas = [c for c in cambios if c.get('fecha', '').startswith('2026-11') and c.get('tipo') == 'baja']
df = pd.DataFrame(bajas)

# Exportar un CSV específico para el usuario con solo las bajas del mes agrupadas
out_csv = Path(r"C:\Users\Bryan Roblero\Documents\reporte\data\bajas_precios_noviembre_2026.csv")
cols_export = ["fecha", "pais", "retailer", "categoria", "mobile", "memoria", "moneda", "precio_anterior", "precio_nuevo", "diferencia", "pct_cambio"]
df_export = df[cols_export].sort_values(by=["pais", "retailer", "fecha"], ascending=[True, True, False])
df_export.to_csv(out_csv, index=False, encoding="utf-8-sig")
print(f"[OK] Archivo exportado a: {out_csv} ({len(df_export)} registros)")

# Imprimir resumen consolidado
print("\n" + "="*80)
print(f"RESUMEN DE BAJAS DE PRECIOS - NOVIEMBRE 2026 (Total: {len(df)} bajas)")
print("="*80)

resumen_tiendas = df.groupby(["pais", "retailer"]).size().reset_index(name="cantidad_bajas")
print(resumen_tiendas.to_string(index=False))
print("\n" + "="*80)

for (pais, ret), grp in df.groupby(["pais", "retailer"]):
    print(f"\n🏬 SHOP: {ret} ({pais}) - {len(grp)} bajadas de precio en el mes")
    print("-" * 75)
    grp_sorted = grp.sort_values(by="fecha", ascending=False)
    for _, row in grp_sorted.iterrows():
        f = row["fecha"]
        mob = row["mobile"]
        mem = row["memoria"]
        mon = row["moneda"]
        p_ant = row["precio_anterior"]
        p_nue = row["precio_nuevo"]
        dif = abs(row["diferencia"])
        pct = abs(row["pct_cambio"])
        print(f"  • {f[:10]} | {mob} ({mem}): {mon}{p_ant:,.2f} ➔ {mon}{p_nue:,.2f} (Bajó {mon}{dif:,.2f} / -{pct}%)")


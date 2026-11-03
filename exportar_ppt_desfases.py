# -*- coding: utf-8 -*-
import sys
from datetime import datetime
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

BASE_DIR = Path(r"C:\Users\Bryan Roblero\Documents\reporte")
DATA_DIR = BASE_DIR / "data"
sys.path.insert(0, str(BASE_DIR))

from matching import build_report, PAISES_CONFIG

# Paleta Corporativa Samsung
C_BG = RGBColor(11, 15, 25)         # #0B0F19
C_CARD = RGBColor(26, 34, 52)       # #1A2234
C_BORDER = RGBColor(46, 58, 89)     # #2E3A59
C_TEXT = RGBColor(248, 250, 252)    # Blanco
C_MUTED = RGBColor(148, 163, 184)   # Gris secundario
C_BLUE = RGBColor(3, 78, 162)       # Samsung Blue #034EA2
C_CYAN = RGBColor(56, 189, 248)     # Cyan #38BDF8
C_RED = RGBColor(239, 68, 68)       # Rojo alerta #EF4444
C_GREEN = RGBColor(16, 185, 129)    # Verde ok #10B981

def aplicar_fondo_oscuro(slide, prs):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = C_BG
    bg.line.fill.background()
    return bg

def formato_precio(p, moneda):
    if p is None: return "—"
    return f"{moneda} {p:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")

def crear_presentacion_desfases(pais="gt", output_path=None, solo_celulares=True):
    cfg = PAISES_CONFIG.get(pais.lower(), PAISES_CONFIG["gt"])
    moneda = cfg["moneda"]
    pais_nombre = cfg["nombre"]
    bandera = cfg["bandera"]

    reporte = build_report(DATA_DIR, pais=pais)
    filas_todas = reporte.get("filas", [])
    retailers = reporte.get("retailers", {})
    ret_keys = list(retailers.keys())

    # FILTRO POR CATEGORÍA ACTIVA (Por defecto: Solo Celulares)
    if solo_celulares:
        filas = [f for f in filas_todas if f.get("categoria", "Smartphones") == "Smartphones"]
        cat_tag = " (Solo Celulares)"
    else:
        filas = filas_todas
        cat_tag = " (Catálogo Completo)"

    # Recalcular métricas exactas basadas en las filas activas
    total_evaluados = 0
    total_alineados = 0
    alertas = []

    for f in filas:
        eval_fila = False
        fila_ok = False
        base = f.get("mi_precio") or f.get("msrp")

        for k in ret_keys:
            st = f.get(f"{k}_estado")
            diff = f.get(f"{k}_diff_pct")
            p_ret = f.get(k)

            if st in ("ok", "menor", "alerta"):
                eval_fila = True
            if st == "ok":
                fila_ok = True
            elif st in ("menor", "alerta") and p_ret is not None and base is not None:
                alertas.append({
                    "retailer": retailers.get(k, k),
                    "retailer_key": k,
                    "mobile": f["mobile"],
                    "memoria": f["memoria"],
                    "precio_retailer": p_ret,
                    "base": base,
                    "diff_pct": diff if diff is not None else 0.0,
                    "categoria": f.get("categoria", "Smartphones")
                })

        if eval_fila:
            total_evaluados += 1
        if fila_ok:
            total_alineados += 1

    alertas.sort(key=lambda a: a["diff_pct"])
    total_alertas = len(alertas)
    pct_ok = round((total_alineados / total_evaluados) * 100) if total_evaluados else 0

    # Agrupar alertas por retailer
    alertas_por_ret = {}
    for a in alertas:
        ret = a["retailer"]
        if ret not in alertas_por_ret:
            alertas_por_ret[ret] = []
        alertas_por_ret[ret].append(a)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    layout_blank = prs.slide_layouts[6]
    fecha_str = datetime.now().strftime("%d/%m/%Y")

    # ==========================================================
    # SLIDE 1: PORTADA & RESUMEN EJECUTIVO
    # ==========================================================
    s1 = prs.slides.add_slide(layout_blank)
    aplicar_fondo_oscuro(s1, prs)

    # Header de la diapositiva
    tb_header = s1.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.2))
    tf = tb_header.text_frame
    tf.word_wrap = True
    p1 = tf.paragraphs[0]
    p1.text = f"SAMSUNG RETAIL · REPORTE EJECUTIVO DE DESFASES {bandera}"
    p1.font.size = Pt(13)
    p1.font.bold = True
    p1.font.color.rgb = C_CYAN

    p2 = tf.add_paragraph()
    p2.text = f"Monitoreo de Precios en Retailers — {pais_nombre}{cat_tag}"
    p2.font.size = Pt(24)
    p2.font.bold = True
    p2.font.color.rgb = C_TEXT

    p3 = tf.add_paragraph()
    p3.text = f"Fecha de emisión: {fecha_str} | Base de comparación: Samsung Shop & MSRP Oficial"
    p3.font.size = Pt(11)
    p3.font.color.rgb = C_MUTED

    # 3 Tarjetas de KPIs principales
    kpi_data = [
        {"val": f"{total_evaluados}", "label": "MODELOS MONITOREADOS", "sub": f"Catálogo activo: {len(filas)} modelos", "color": C_TEXT},
        {"val": f"{pct_ok}%", "label": "CUMPLIMIENTO EN REGLA", "sub": f"{total_alineados} modelos alineados", "color": C_GREEN if pct_ok >= 75 else C_RED},
        {"val": f"{total_alertas}", "label": "DESFASES DETECTADOS", "sub": f"Precios por debajo de MSRP/Shop", "color": C_RED}
    ]

    card_w = Inches(3.64)
    card_h = Inches(1.5)
    card_y = Inches(2.0)

    for idx, k in enumerate(kpi_data):
        cx = Inches(0.8 + idx * 4.0)
        shape = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, card_y, card_w, card_h)
        shape.fill.solid()
        shape.fill.fore_color.rgb = C_CARD
        shape.line.color.rgb = C_BORDER
        shape.line.width = Pt(1)

        ktb = s1.shapes.add_textbox(cx, card_y + Inches(0.15), card_w, card_h - Inches(0.3))
        ktf = ktb.text_frame
        kp1 = ktf.paragraphs[0]
        kp1.text = k["val"]
        kp1.font.size = Pt(28)
        kp1.font.bold = True
        kp1.font.color.rgb = k["color"]
        kp1.alignment = PP_ALIGN.CENTER

        kp2 = ktf.add_paragraph()
        kp2.text = k["label"]
        kp2.font.size = Pt(10)
        kp2.font.bold = True
        kp2.font.color.rgb = C_MUTED
        kp2.alignment = PP_ALIGN.CENTER

        kp3 = ktf.add_paragraph()
        kp3.text = k["sub"]
        kp3.font.size = Pt(9.5)
        kp3.font.color.rgb = C_MUTED
        kp3.alignment = PP_ALIGN.CENTER

    # Subtítulo tabla de retailers
    sub_title = s1.shapes.add_textbox(Inches(0.8), Inches(3.8), Inches(11.7), Inches(0.5))
    st_p = sub_title.text_frame.paragraphs[0]
    st_p.text = f"Desglose de Desfases por Cadena Comercial{cat_tag}"
    st_p.font.size = Pt(14)
    st_p.font.bold = True
    st_p.font.color.rgb = C_CYAN

    ret_rows = len(retailers) + 1
    t_shape = s1.shapes.add_table(ret_rows, 5, Inches(0.8), Inches(4.3), Inches(11.7), Inches(2.4))
    tbl = t_shape.table
    tbl.columns[0].width = Inches(3.2)
    tbl.columns[1].width = Inches(2.1)
    tbl.columns[2].width = Inches(2.1)
    tbl.columns[3].width = Inches(2.5)
    tbl.columns[4].width = Inches(1.8)

    headers = ["RETAILER / CADENA", "DESFASES", "MAYOR DESCUENTO", "MODELO MÁS AGRESIVO", "ESTADO"]
    for col_idx, h in enumerate(headers):
        cell = tbl.cell(0, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_BLUE
        cell.text_frame.paragraphs[0].text = h
        cell.text_frame.paragraphs[0].font.size = Pt(10)
        cell.text_frame.paragraphs[0].font.bold = True
        cell.text_frame.paragraphs[0].font.color.rgb = C_TEXT

    for row_idx, (r_key, r_name) in enumerate(retailers.items(), start=1):
        r_alertas = alertas_por_ret.get(r_name, [])
        num_al = len(r_alertas)
        max_diff = r_alertas[0]["diff_pct"] if num_al > 0 else 0.0
        peor_item = r_alertas[0] if num_al > 0 else None
        
        datos_fila = [
            r_name,
            f"{num_al} productos",
            f"{max_diff:.1f}%" if num_al > 0 else "0%",
            f"{peor_item['mobile']} ({formato_precio(peor_item['precio_retailer'], moneda)})" if peor_item else "Alineado",
            "🔴 Alerta Comercial" if num_al > 0 else "🟢 Alineado"
        ]

        for col_idx, val in enumerate(datos_fila):
            cell = tbl.cell(row_idx, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_CARD if row_idx % 2 == 1 else RGBColor(19, 26, 42)
            cp = cell.text_frame.paragraphs[0]
            cp.text = val
            cp.font.size = Pt(10)
            if col_idx == 1 and num_al > 0:
                cp.font.bold = True
                cp.font.color.rgb = C_RED
            elif col_idx == 2 and num_al > 0:
                cp.font.bold = True
                cp.font.color.rgb = C_RED
            elif col_idx == 4:
                cp.font.bold = True
                cp.font.color.rgb = C_RED if num_al > 0 else C_GREEN
            else:
                cp.font.color.rgb = C_TEXT

    # ==========================================================
    # SLIDE 2: TOP MODELOS CON MAYOR DESFASE
    # ==========================================================
    s2 = prs.slides.add_slide(layout_blank)
    aplicar_fondo_oscuro(s2, prs)

    tb2 = s2.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.1))
    tf2 = tb2.text_frame
    p2_1 = tf2.paragraphs[0]
    p2_1.text = f"SAMSUNG RETAIL · AUDITORÍA DE PRECIOS {bandera}"
    p2_1.font.size = Pt(12)
    p2_1.font.bold = True
    p2_1.font.color.rgb = C_CYAN

    p2_2 = tf2.add_paragraph()
    p2_2.text = f"Modelos con Mayor Desfase{cat_tag} (Precios por debajo de MSRP / Shop)"
    p2_2.font.size = Pt(22)
    p2_2.font.bold = True
    p2_2.font.color.rgb = C_TEXT

    p2_3 = tf2.add_paragraph()
    p2_3.text = f"Alertas prioritarias ordenadas por mayor impacto de descuento ({len(alertas)} alertas en total)"
    p2_3.font.size = Pt(11)
    p2_3.font.color.rgb = C_MUTED

    top_alertas = alertas[:12]
    num_filas = max(len(top_alertas) + 1, 2)
    t2_height = Inches(min(5.0, 0.45 * num_filas))
    t2_shape = s2.shapes.add_table(num_filas, 7, Inches(0.8), Inches(1.8), Inches(11.7), t2_height)
    tbl2 = t2_shape.table

    col_widths = [Inches(2.7), Inches(1.2), Inches(2.1), Inches(1.5), Inches(1.6), Inches(1.3), Inches(1.3)]
    for ci, w in enumerate(col_widths):
        tbl2.columns[ci].width = w

    h2 = ["MODELO", "MEMORIA", "RETAILER", "PRECIO TIENDA", "PRECIO BASE / MSRP", "DIFERENCIA", "DESFASE %"]
    for ci, h in enumerate(h2):
        cell = tbl2.cell(0, ci)
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_BLUE
        cp = cell.text_frame.paragraphs[0]
        cp.text = h
        cp.font.size = Pt(9.5)
        cp.font.bold = True
        cp.font.color.rgb = C_TEXT

    if top_alertas:
        for r_idx, al in enumerate(top_alertas, start=1):
            dif_moneda = (al["base"] - al["precio_retailer"]) if (al["base"] and al["precio_retailer"]) else 0
            row_vals = [
                al["mobile"],
                str(al["memoria"]),
                al["retailer"],
                formato_precio(al["precio_retailer"], moneda),
                formato_precio(al["base"], moneda),
                f"-{formato_precio(dif_moneda, moneda)}",
                f"{al['diff_pct']:.1f}%"
            ]
            for ci, val in enumerate(row_vals):
                cell = tbl2.cell(r_idx, ci)
                cell.fill.solid()
                cell.fill.fore_color.rgb = C_CARD if r_idx % 2 == 1 else RGBColor(19, 26, 42)
                cp = cell.text_frame.paragraphs[0]
                cp.text = val
                cp.font.size = Pt(9.5)
                if ci in (5, 6):
                    cp.font.bold = True
                    cp.font.color.rgb = C_RED
                elif ci == 3:
                    cp.font.bold = True
                    cp.font.color.rgb = C_TEXT
                else:
                    cp.font.color.rgb = C_MUTED if ci in (1, 4) else C_TEXT
    else:
        # Si no hay alertas
        for ci in range(7):
            cell = tbl2.cell(1, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_CARD
            cp = cell.text_frame.paragraphs[0]
            cp.text = "Todos los precios alineados en regla" if ci == 0 else "—"
            cp.font.size = Pt(10)
            cp.font.color.rgb = C_GREEN if ci == 0 else C_MUTED

    if not output_path:
        tag_f = "Celulares" if solo_celulares else "Todo"
        output_path = BASE_DIR / f"Reporte_Desfases_{pais.upper()}_{datetime.now().strftime('%Y%m%d')}.pptx"

    prs.save(str(output_path))
    print(f"Presentación generada exitosamente en: {output_path}")
    return output_path

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "gt"
    crear_presentacion_desfases(pais=p, solo_celulares=True)

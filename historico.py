# -*- coding: utf-8 -*-
"""
Módulo de Gestión de Histórico de Variación de Precios.
Permite rastrear:
  - Cambios de precio con fecha y hora exacta.
  - Regla de 24 horas (cambios ocurridos en las últimas 24h).
  - Frecuencia mensual de cambios por tienda y producto.
"""

import json
import re
from datetime import datetime
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
HISTORICO_JSON = DATA_DIR / "historico_cambios.json"
HISTORICO_CSV = DATA_DIR / "historico_cambios.csv"
ULTIMOS_PRECIOS_JSON = DATA_DIR / "ultimos_precios.json"

DATA_DIR.mkdir(exist_ok=True)


def load_historico():
    """Carga la lista completa de eventos de cambios de precio."""
    if not HISTORICO_JSON.exists():
        return []
    try:
        return json.loads(HISTORICO_JSON.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_historico(cambios):
    """Guarda la lista de cambios en JSON y CSV."""
    HISTORICO_JSON.write_text(json.dumps(cambios, ensure_ascii=False, indent=2), encoding="utf-8")
    if cambios:
        df = pd.DataFrame(cambios)
        df.to_csv(HISTORICO_CSV, index=False, encoding="utf-8")


def load_ultimos_precios():
    """Carga el mapa de los últimos precios conocidos."""
    if not ULTIMOS_PRECIOS_JSON.exists():
        return {}
    try:
        return json.loads(ULTIMOS_PRECIOS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_ultimos_precios(precios):
    """Guarda el mapa de los últimos precios conocidos."""
    ULTIMOS_PRECIOS_JSON.write_text(json.dumps(precios, ensure_ascii=False, indent=2), encoding="utf-8")


def registrar_cambios_desde_reporte(reporte: dict, fecha_hora_str: str = None):
    """
    Compara las filas de un reporte contra los últimos precios guardados.
    Si detecta un precio diferente, registra el evento de cambio.
    """
    if not reporte or "filas" not in reporte:
        return 0

    if not fecha_hora_str:
        fecha_hora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    pais = (reporte.get("pais") or "gt").upper()
    moneda = reporte.get("moneda") or "Q"
    ret_dict = reporte.get("retailers", {})
    filas = reporte.get("filas", [])

    cambios = load_historico()
    ultimos = load_ultimos_precios()
    nuevos_cambios = 0

    for f in filas:
        mob = f.get("mobile", "").strip()
        mem = str(f.get("memoria", "")).strip()
        cat = f.get("categoria", "Smartphones")

        for r_key, r_nombre in ret_dict.items():
            p_actual = f.get(r_key)
            if p_actual is not None and isinstance(p_actual, (int, float)) and p_actual > 0:
                key = f"{pais}|{r_key}|{mob}|{mem}"
                p_anterior = ultimos.get(key)

                if p_anterior is not None and p_anterior != p_actual:
                    diff = round(p_actual - p_anterior, 2)
                    pct = round((diff / p_anterior) * 100, 2)
                    evento = {
                        "id": f"{int(datetime.now().timestamp())}_{key.replace('|', '_')}",
                        "fecha": fecha_hora_str,
                        "pais": pais,
                        "moneda": moneda,
                        "retailer": r_nombre,
                        "retailer_key": r_key,
                        "mobile": mob,
                        "memoria": mem,
                        "categoria": cat,
                        "precio_anterior": p_anterior,
                        "precio_nuevo": p_actual,
                        "diferencia": diff,
                        "pct_cambio": pct,
                        "tipo": "subida" if diff > 0 else "baja"
                    }
                    cambios.append(evento)
                    nuevos_cambios += 1

                # Actualizar último precio conocido
                ultimos[key] = p_actual

    if nuevos_cambios > 0:
        save_historico(cambios)

    save_ultimos_precios(ultimos)
    return nuevos_cambios


def calcular_metricas_historico(cambios: list = None, ref_datetime: datetime = None):
    """
    Calcula KPIs:
      - Cambios en las últimas 24 horas (Regla 24h).
      - Cambios en el mes actual.
      - Frecuencia mensual por tienda y por producto.
      - Enriquecimiento de la lista con horas_atras y es_24h.
    """
    if cambios is None:
        cambios = load_historico()

    if not ref_datetime:
        ref_datetime = datetime.now()

    mes_actual_str = ref_datetime.strftime("%Y-%m")

    total_24h = 0
    total_mes = 0
    por_retailer_mes = {}
    por_pais_mes = {}
    frecuencia_producto_mes = {}  # key: (pais, retailer_key, mobile, memoria) -> count
    bajas_mes = 0
    subidas_mes = 0

    lista_enriquecida = []

    for c in cambios:
        item = dict(c)
        fecha_str = c.get("fecha", "")
        dt_cambio = None
        horas_atras = 9999.0
        es_24h = False
        es_mes_actual = False

        if fecha_str:
            try:
                dt_cambio = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
                diff_seg = (ref_datetime - dt_cambio).total_seconds()
                horas_atras = round(max(0.0, diff_seg / 3600.0), 1)
                es_24h = (0 <= horas_atras <= 24.0)
                es_mes_actual = (dt_cambio.strftime("%Y-%m") == mes_actual_str)
            except Exception:
                pass

        item["horas_atras"] = horas_atras
        item["es_24h"] = es_24h

        if es_24h:
            total_24h += 1

        if es_mes_actual:
            total_mes += 1
            ret = c.get("retailer", "Desconocido")
            pais = c.get("pais", "GT")
            por_retailer_mes[ret] = por_retailer_mes.get(ret, 0) + 1
            por_pais_mes[pais] = por_pais_mes.get(pais, 0) + 1

            p_key = f"{pais}|{c.get('retailer_key')}|{c.get('mobile')}|{c.get('memoria')}"
            frecuencia_producto_mes[p_key] = frecuencia_producto_mes.get(p_key, 0) + 1

            if c.get("tipo") == "baja":
                bajas_mes += 1
            else:
                subidas_mes += 1

        lista_enriquecida.append(item)

    # Asignar a cada item cuántas veces ha cambiado ese producto en el mes
    for item in lista_enriquecida:
        p_key = f"{item.get('pais')}|{item.get('retailer_key')}|{item.get('mobile')}|{item.get('memoria')}"
        item["cambios_mes_producto"] = frecuencia_producto_mes.get(p_key, 1)

    # Ordenar del más reciente al más antiguo
    lista_enriquecida.sort(key=lambda x: x.get("fecha", ""), reverse=True)

    # Tienda más activa en el mes
    tienda_top = "N/A"
    tienda_top_count = 0
    if por_retailer_mes:
        tienda_top, tienda_top_count = max(por_retailer_mes.items(), key=lambda x: x[1])

    return {
        "total_cambios_mes": total_mes,
        "total_cambios_24h": total_24h,
        "mes_nombre": ref_datetime.strftime("%B %Y"),
        "tienda_top": tienda_top,
        "tienda_top_count": tienda_top_count,
        "bajas_mes": bajas_mes,
        "subidas_mes": subidas_mes,
        "por_retailer_mes": por_retailer_mes,
        "por_pais_mes": por_pais_mes,
        "cambios": lista_enriquecida
    }

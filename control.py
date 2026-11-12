# -*- coding: utf-8 -*-
"""
Centro de Control de Precios: vista nueva en /control y su API (/api/v2/...).
No modifica las rutas existentes del dashboard.
"""
import json
import time
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request

import precios_db

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UMBRAL_REVISAR = 25.0   # brecha (en %) a partir de la cual se sospecha del emparejamiento
PAISES = ["gt", "sv", "hn"]

bp = Blueprint("control", __name__)


def _status():
    try:
        return json.loads((DATA_DIR / "status.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _familia(mobile, categoria):
    if categoria != "Smartphones":
        return categoria or "Otros"
    m = mobile.replace("Galaxy-", "Galaxy ")
    if m.startswith("Galaxy Z"):
        return "Serie Z"
    if m.startswith("Galaxy S"):
        return "Serie S"
    return "Serie A"


def _dias_en_desfase(pais, tol, actuales):
    """Para cada precio hoy fuera de regla, dias desde que cruzo el limite (segun la serie guardada)."""
    series = {}
    for o in precios_db.observaciones_pais(pais):
        series.setdefault((o["retailer"], o["mobile"], o["memoria"]), []).append((o["fecha"], o["precio"]))
    out = {}
    ahora = datetime.now()
    lim = precios_db.limites(pais) or {}
    for k, (precio, base) in actuales.items():
        limite = base * (1 - tol / 100.0)
        if precio >= limite:
            continue
        pts = series.get(k) or []
        inicio = None
        for f, p in reversed(pts):
            if p < limite:
                inicio = f
            else:
                break
        if inicio:
            try:
                al_inicio = inicio == pts[0][0]
                # si ya estaba fuera de regla cuando empezo el registro, se cuenta desde el primer dato del pais
                if al_inicio and lim.get("siembra") and inicio <= lim["siembra"] and lim.get("primera"):
                    inicio = lim["primera"]
                out[k] = {"dias": (ahora - datetime.strptime(inicio, precios_db.FMT)).days, "desde_inicio_registro": al_inicio}
            except Exception:
                pass
    return out


def tablero(pais, tol=None):
    import matching
    rep = matching.build_report(DATA_DIR, tolerancia_pct=tol, pais=pais)
    tol = (rep.get("resumen") or {}).get("tolerancia_pct", 5.0)
    rks = list((rep.get("retailers") or {}).keys())
    st = _status()
    actuales = {}
    filas = []
    for f in rep.get("filas", []):
        base = f.get("mi_precio")
        celdas = {}
        for rk in rks:
            p = f.get(rk)
            if p is None:
                celdas[rk] = None
                continue
            gap = (p - base) / base * 100 if base else None
            celdas[rk] = {"p": p, "gap": gap, "revisar": bool(gap is not None and abs(gap) >= UMBRAL_REVISAR),
                          "color": f.get(rk + "_color"), "nombre": f.get(rk + "_nombre"), "url": f.get(rk + "_url")}
            if base and gap is not None and abs(gap) < UMBRAL_REVISAR:
                actuales[(rk, f["mobile"], str(f.get("memoria", "")))] = (p, base)
        filas.append({"m": f["mobile"], "g": str(f.get("memoria", "")), "cat": f.get("categoria"),
                      "fam": _familia(f["mobile"], f.get("categoria")), "base": base, "msrp": f.get("msrp"), "c": celdas})
    try:
        dias = _dias_en_desfase(pais, tol, actuales)
    except Exception:
        dias = {}
    for fila in filas:
        for rk, cel in fila["c"].items():
            d = dias.get((rk, fila["m"], fila["g"]))
            if cel and d:
                cel["dias"] = d["dias"]
                cel["dias_min"] = d["desde_inicio_registro"]
    estado_tiendas = {}
    for rk in rks:
        cands = [st.get(rk), st.get(rk + "_gt")]
        cands = [c for c in cands if isinstance(c, dict)]
        mejor = max(cands, key=lambda c: c.get("ultima_actualizacion", 0)) if cands else {}
        estado_tiendas[rk] = {"estado": mejor.get("estado"), "ts": mejor.get("ultima_actualizacion")}
    return {"pais": pais, "pais_nombre": rep.get("pais_nombre"), "moneda": rep.get("moneda"), "tolerancia": tol,
            "retailers": rep.get("retailers") or {}, "filas": filas, "estado_tiendas": estado_tiendas,
            "sin_coincidencia": rep.get("sin_coincidencia") or {}, "umbral_revisar": UMBRAL_REVISAR,
            "generado": time.time()}


@bp.route("/control")
def vista_control():
    return render_template("control.html")


@bp.route("/api/v2/tablero")
def api_tablero():
    pais = request.args.get("pais", "gt").lower()
    if pais not in PAISES:
        pais = "gt"
    t = request.args.get("tolerancia")
    try:
        tol = float(t) if t else None
    except ValueError:
        tol = None
    data = tablero(pais, tol)
    try:
        data["eventos"] = precios_db.eventos(pais, dias=35)
    except Exception as e:
        data["eventos"] = []
        data["error_db"] = str(e)
    return jsonify(data)


@bp.route("/api/v2/regional")
def api_regional():
    return jsonify({"paises": [tablero(p) for p in PAISES]})


@bp.route("/api/v2/serie")
def api_serie():
    pais = request.args.get("pais", "gt").lower()
    try:
        dias = max(1, min(int(request.args.get("dias", 90)), 730))
    except ValueError:
        dias = 90
    return jsonify({"puntos": precios_db.serie(pais, request.args.get("mobile", ""), request.args.get("memoria", ""), dias)})


@bp.route("/api/v2/eventos")
def api_eventos():
    try:
        dias = max(1, min(int(request.args.get("dias", 35)), 730))
    except ValueError:
        dias = 35
    pais = request.args.get("pais")
    return jsonify({"eventos": precios_db.eventos(pais if pais in PAISES else None, dias)})


@bp.route("/api/v2/salud")
def api_salud():
    import planificador
    s = precios_db.salud()
    s["planificador"] = planificador.estado()
    return jsonify(s)


@bp.route("/api/v2/actualizar", methods=["POST"])
def api_actualizar():
    import planificador
    ok = planificador.lanzar("manual desde Centro de Control")
    return jsonify({"ok": ok, "mensaje": "Corrida iniciada" if ok else "Ya hay una corrida en curso"}), (200 if ok else 409)

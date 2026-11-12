# -*- coding: utf-8 -*-
"""
Base de precios en SQLite (data/precios.db).

Guarda la serie completa de precios por modelo y tienda, y los eventos
derivados (baja, subida, nuevo, agotado, reaparece). Convive con
historico.py: no reemplaza ni modifica sus archivos.

  observaciones  una fila por modelo/tienda cada vez que se registra una corrida
  eventos        cambios detectados, con marca de confirmado o rebote
  estado         ultimo precio conocido por modelo/tienda
  salud          cuantos precios entrego cada tienda en cada corrida
"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "precios.db"
FMT = "%Y-%m-%d %H:%M:%S"
MIN_ENTRE_OBS = 30          # minutos: evita duplicar observaciones de una misma corrida
MIN_PARA_CONFIRMAR = 60     # minutos: un cambio se confirma en una corrida posterior

SCHEMA = """
CREATE TABLE IF NOT EXISTS corridas(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, pais TEXT NOT NULL, origen TEXT DEFAULT 'scraping');
CREATE TABLE IF NOT EXISTS observaciones(
  id INTEGER PRIMARY KEY AUTOINCREMENT, corrida_id INTEGER, fecha TEXT NOT NULL,
  pais TEXT NOT NULL, retailer TEXT NOT NULL, mobile TEXT NOT NULL, memoria TEXT NOT NULL,
  categoria TEXT, precio REAL NOT NULL, base REAL, nombre TEXT, url TEXT, color TEXT, origen TEXT DEFAULT 'scraping');
CREATE INDEX IF NOT EXISTS ix_obs_sku ON observaciones(pais, mobile, memoria, retailer, fecha);
CREATE INDEX IF NOT EXISTS ix_obs_fecha ON observaciones(fecha);
CREATE TABLE IF NOT EXISTS eventos(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL,
  pais TEXT NOT NULL, retailer TEXT NOT NULL, retailer_nombre TEXT, mobile TEXT NOT NULL, memoria TEXT NOT NULL,
  categoria TEXT, tipo TEXT NOT NULL, precio_anterior REAL, precio_nuevo REAL, pct REAL,
  mismo_producto INTEGER DEFAULT 1, confirmado INTEGER DEFAULT 0, origen TEXT DEFAULT 'scraping');
CREATE INDEX IF NOT EXISTS ix_ev_fecha ON eventos(fecha);
CREATE INDEX IF NOT EXISTS ix_ev_sku ON eventos(pais, retailer, mobile, memoria);
CREATE TABLE IF NOT EXISTS estado(
  pais TEXT NOT NULL, retailer TEXT NOT NULL, mobile TEXT NOT NULL, memoria TEXT NOT NULL,
  precio REAL, url TEXT, disponible INTEGER DEFAULT 1, visto TEXT, ult_obs TEXT,
  PRIMARY KEY(pais, retailer, mobile, memoria));
CREATE TABLE IF NOT EXISTS salud(
  corrida_id INTEGER, fecha TEXT, pais TEXT, retailer TEXT, n_precios INTEGER, fallo INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_salud ON salud(pais, retailer, fecha);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
"""

_listo = False


def con():
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    return c


def init():
    """Crea las tablas y, la primera vez, importa el historico anterior."""
    global _listo
    if _listo and DB_PATH.exists():
        return
    c = con()
    try:
        c.executescript(SCHEMA)
        c.commit()
        hecho = c.execute("SELECT v FROM meta WHERE k='legacy_migrado'").fetchone()
        if not hecho:
            _migrar_legacy(c)
            c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('legacy_migrado', ?)", (datetime.now().strftime(FMT),))
            c.commit()
    finally:
        c.close()
    _listo = True


def _migrar_legacy(c):
    """Importa data/historico_cambios.json como eventos y puntos de serie."""
    p = DATA_DIR / "historico_cambios.json"
    if not p.exists():
        return 0
    try:
        cambios = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return 0
    grupos = {}
    for ev in cambios:
        try:
            k = (str(ev["pais"]).lower(), ev["retailer_key"], ev["mobile"], str(ev.get("memoria", "")))
            grupos.setdefault(k, []).append(ev)
        except Exception:
            continue
    n = 0
    for (pais, rk, mob, mem), lst in grupos.items():
        lst.sort(key=lambda e: e.get("fecha", ""))
        for i, ev in enumerate(lst):
            ant, nue = ev.get("precio_anterior"), ev.get("precio_nuevo")
            if ant is None or nue is None:
                continue
            sig = lst[i + 1] if i + 1 < len(lst) else None
            rebote = bool(sig and sig.get("precio_nuevo") == ant)
            if i == 0:
                try:
                    f0 = (datetime.strptime(ev["fecha"], FMT) - timedelta(minutes=1)).strftime(FMT)
                except Exception:
                    f0 = ev["fecha"]
                c.execute("INSERT INTO observaciones(fecha,pais,retailer,mobile,memoria,categoria,precio,origen) VALUES(?,?,?,?,?,?,?,'legacy')",
                          (f0, pais, rk, mob, mem, ev.get("categoria"), ant))
            c.execute("INSERT INTO observaciones(fecha,pais,retailer,mobile,memoria,categoria,precio,origen) VALUES(?,?,?,?,?,?,?,'legacy')",
                      (ev["fecha"], pais, rk, mob, mem, ev.get("categoria"), nue))
            c.execute("""INSERT INTO eventos(fecha,pais,retailer,retailer_nombre,mobile,memoria,categoria,tipo,precio_anterior,precio_nuevo,pct,mismo_producto,confirmado,origen)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,'legacy')""",
                      (ev["fecha"], pais, rk, ev.get("retailer"), mob, mem, ev.get("categoria"), ev.get("tipo") or ("subida" if nue > ant else "baja"),
                       ant, nue, ev.get("pct_cambio"), -1 if rebote else 1))
            n += 1
    return n


def _es_precio(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def registrar(reporte, fecha=None):
    """
    Registra una corrida a partir del reporte de matching.build_report().
    Devuelve {'observaciones': n, 'eventos': n}. Nunca lanza excepcion hacia afuera.
    """
    try:
        return _registrar(reporte, fecha)
    except Exception as e:  # la base nunca debe tumbar el scraping
        print("[precios_db] Error registrando corrida:", e)
        return {"observaciones": 0, "eventos": 0, "error": str(e)}


def _registrar(reporte, fecha=None):
    if not reporte or not reporte.get("filas"):
        return {"observaciones": 0, "eventos": 0}
    init()
    ahora = datetime.strptime(fecha, FMT) if fecha else datetime.now()
    fecha = ahora.strftime(FMT)
    pais = (reporte.get("pais") or "gt").lower()
    retailers = reporte.get("retailers") or {}
    filas = reporte["filas"]
    n_obs = n_ev = 0
    c = con()
    try:
        c.execute("BEGIN IMMEDIATE")
        sembrado = c.execute("SELECT 1 FROM estado WHERE pais=? LIMIT 1", (pais,)).fetchone() is not None
        cur = c.execute("INSERT INTO corridas(fecha,pais) VALUES(?,?)", (fecha, pais))
        corrida = cur.lastrowid
        est = {(r["retailer"], r["mobile"], r["memoria"]): r for r in c.execute("SELECT * FROM estado WHERE pais=?", (pais,))}
        for rk, rnombre in retailers.items():
            ahora_n = sum(1 for f in filas if _es_precio(f.get(rk)))
            antes_n = sum(1 for (r, _, _), s in est.items() if r == rk and s["disponible"])
            fallo = ahora_n == 0 and antes_n >= 3
            c.execute("INSERT INTO salud(corrida_id,fecha,pais,retailer,n_precios,fallo) VALUES(?,?,?,?,?,?)",
                      (corrida, fecha, pais, rk, ahora_n, 1 if fallo else 0))
            for f in filas:
                mob = str(f.get("mobile", "")).strip()
                mem = str(f.get("memoria", "")).strip()
                if not mob:
                    continue
                cat = f.get("categoria")
                p = f.get(rk)
                s = est.get((rk, mob, mem))

                def evento(tipo, ant, nue, mismo=1):
                    pct = round((nue - ant) / ant * 100, 2) if (ant and nue) else None
                    c.execute("""INSERT INTO eventos(fecha,pais,retailer,retailer_nombre,mobile,memoria,categoria,tipo,precio_anterior,precio_nuevo,pct,mismo_producto,confirmado)
                                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)""",
                              (fecha, pais, rk, rnombre, mob, mem, cat, tipo, ant, nue, pct, mismo))

                if _es_precio(p):
                    url = f.get(rk + "_url") or ""
                    # confirmar o descartar cambios pendientes de corridas anteriores
                    limite = (ahora - timedelta(minutes=MIN_PARA_CONFIRMAR)).strftime(FMT)
                    for ev in c.execute("""SELECT id, precio_anterior, precio_nuevo FROM eventos WHERE pais=? AND retailer=? AND mobile=? AND memoria=?
                                            AND confirmado=0 AND tipo IN ('baja','subida','reaparece','nuevo') AND fecha<=?""",
                                        (pais, rk, mob, mem, limite)).fetchall():
                        conf = -1 if (ev["precio_anterior"] is not None and p == ev["precio_anterior"] and p != ev["precio_nuevo"]) else 1
                        c.execute("UPDATE eventos SET confirmado=? WHERE id=?", (conf, ev["id"]))
                    insertar = True
                    if s is None:
                        if sembrado:
                            evento("nuevo", None, p); n_ev += 1
                    elif not s["disponible"]:
                        evento("reaparece", s["precio"], p); n_ev += 1
                    elif s["precio"] != p:
                        mismo = 1 if (not url or not s["url"] or url == s["url"]) else 0
                        evento("subida" if p > s["precio"] else "baja", s["precio"], p, mismo); n_ev += 1
                    else:
                        if s["ult_obs"] and (s["url"] or "") == url:
                            try:
                                if ahora - datetime.strptime(s["ult_obs"], FMT) < timedelta(minutes=MIN_ENTRE_OBS):
                                    insertar = False
                            except Exception:
                                pass
                    if insertar:
                        c.execute("""INSERT INTO observaciones(corrida_id,fecha,pais,retailer,mobile,memoria,categoria,precio,base,nombre,url,color)
                                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                                  (corrida, fecha, pais, rk, mob, mem, cat, p, f.get("mi_precio"), f.get(rk + "_nombre"), url, f.get(rk + "_color")))
                        n_obs += 1
                    c.execute("""INSERT INTO estado(pais,retailer,mobile,memoria,precio,url,disponible,visto,ult_obs) VALUES(?,?,?,?,?,?,1,?,?)
                                 ON CONFLICT(pais,retailer,mobile,memoria) DO UPDATE SET precio=excluded.precio, url=excluded.url, disponible=1, visto=excluded.visto,
                                 ult_obs=CASE WHEN ? THEN excluded.ult_obs ELSE estado.ult_obs END""",
                              (pais, rk, mob, mem, p, url, fecha, fecha, 1 if insertar else 0))
                elif s is not None and s["disponible"] and not fallo:
                    c.execute("""INSERT INTO eventos(fecha,pais,retailer,retailer_nombre,mobile,memoria,categoria,tipo,precio_anterior,precio_nuevo,pct,mismo_producto,confirmado)
                                 VALUES(?,?,?,?,?,?,?,'agotado',?,NULL,NULL,1,0)""", (fecha, pais, rk, rnombre, mob, mem, cat, s["precio"]))
                    c.execute("UPDATE estado SET disponible=0 WHERE pais=? AND retailer=? AND mobile=? AND memoria=?", (pais, rk, mob, mem))
                    n_ev += 1
        c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", ("ultima_corrida_" + pais, fecha))
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
    return {"observaciones": n_obs, "eventos": n_ev}


# ---------------------------------------------------------------- consultas
def _filas(sql, args=()):
    init()
    c = con()
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def eventos(pais=None, dias=35):
    desde = (datetime.now() - timedelta(days=dias)).strftime(FMT)
    if pais:
        return _filas("SELECT * FROM eventos WHERE pais=? AND fecha>=? ORDER BY fecha DESC, id DESC", (pais.lower(), desde))
    return _filas("SELECT * FROM eventos WHERE fecha>=? ORDER BY fecha DESC, id DESC", (desde,))


def serie(pais, mobile, memoria, dias=90):
    desde = (datetime.now() - timedelta(days=dias)).strftime(FMT)
    return _filas("""SELECT fecha, retailer, precio, nombre, url, color, origen FROM observaciones
                     WHERE pais=? AND mobile=? AND memoria=? AND fecha>=? ORDER BY fecha, id""", (pais.lower(), mobile, memoria, desde))


def observaciones_pais(pais, dias=120):
    desde = (datetime.now() - timedelta(days=dias)).strftime(FMT)
    return _filas("""SELECT fecha, retailer, mobile, memoria, precio FROM observaciones
                     WHERE pais=? AND fecha>=? ORDER BY fecha, id""", (pais.lower(), desde))


def limites(pais):
    """Primera fecha con datos del pais y primera fecha registrada por scraping (la siembra)."""
    r = _filas("""SELECT MIN(fecha) primera, MIN(CASE WHEN origen='scraping' THEN fecha END) siembra
                  FROM observaciones WHERE pais=?""", (pais.lower(),))
    return r[0] if r else {"primera": None, "siembra": None}


def salud():
    filas = _filas("""SELECT s.* FROM salud s JOIN (SELECT pais, retailer, MAX(fecha) f FROM salud GROUP BY pais, retailer) u
                      ON u.pais=s.pais AND u.retailer=s.retailer AND u.f=s.fecha""")
    meta = {r["k"]: r["v"] for r in _filas("SELECT k, v FROM meta")}
    tot = _filas("SELECT (SELECT COUNT(*) FROM observaciones) obs, (SELECT COUNT(*) FROM eventos) ev, (SELECT MIN(fecha) FROM observaciones) desde")[0]
    return {"tiendas": filas, "meta": meta, "totales": tot}


if __name__ == "__main__":
    init()
    print(json.dumps(salud()["totales"], ensure_ascii=False))

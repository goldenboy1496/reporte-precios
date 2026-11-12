# -*- coding: utf-8 -*-
"""
Planificador dentro del servidor.

Complementa la tarea programada de Windows: si a una hora programada no hubo
corrida (PC apagada o dormida), la lanza en cuanto el servidor esta arriba.
No duplica: solo corre si la ultima actualizacion tiene mas de HORAS_MAX horas
y no hay otra corrida en curso.
"""
import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATUS_FILE = DATA_DIR / "status.json"
LOG_FILE = DATA_DIR / "planificador.log"

HORA_INICIO = 7       # no lanza corridas antes de esta hora
HORA_FIN = 21         # ni despues de esta
HORAS_MAX = 4.5       # antiguedad maxima de los datos antes de lanzar una corrida
REVISAR_CADA = 300    # segundos entre revisiones

_hilo = None
_lock = threading.Lock()
_corriendo = {"activo": False, "inicio": None}


def _log(msg):
    linea = "[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass


def _status():
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def horas_desde_ultima():
    """Horas desde la actualizacion mas reciente de cualquier tienda (None si no hay)."""
    ts = [s.get("ultima_actualizacion", 0) for s in _status().values() if isinstance(s, dict)]
    ts = [t for t in ts if t]
    return (time.time() - max(ts)) / 3600.0 if ts else None


def hay_corrida_en_curso():
    if _corriendo["activo"]:
        return True
    for s in _status().values():
        if isinstance(s, dict) and s.get("estado") == "corriendo" and time.time() - s.get("inicio", 0) < 900:
            return True
    return False


def lanzar(motivo="manual"):
    """Lanza una corrida completa en segundo plano. Devuelve False si ya hay una."""
    with _lock:
        if hay_corrida_en_curso():
            return False
        _corriendo["activo"] = True
        _corriendo["inicio"] = time.time()

    def _run():
        try:
            _log("Iniciando corrida (%s)" % motivo)
            flags = 0x08000000 if sys.platform == "win32" else 0
            r = subprocess.run([sys.executable, str(BASE_DIR / "actualizar_precios.py")], cwd=str(BASE_DIR),
                               capture_output=True, text=True, timeout=3600, creationflags=flags)
            _log("Corrida terminada (codigo %s)" % r.returncode)
        except Exception as e:
            _log("Error en corrida: %s" % e)
        finally:
            _corriendo["activo"] = False

    threading.Thread(target=_run, daemon=True).start()
    return True


def estado():
    h = horas_desde_ultima()
    return {"horas_desde_ultima": round(h, 2) if h is not None else None, "en_curso": hay_corrida_en_curso(),
            "atrasado": bool(h is None or h > 6), "ventana": [HORA_INICIO, HORA_FIN], "horas_max": HORAS_MAX}


def _bucle():
    time.sleep(90)  # deja que el servidor y la red terminen de levantar
    while True:
        try:
            ahora = datetime.now()
            h = horas_desde_ultima()
            if HORA_INICIO <= ahora.hour < HORA_FIN and (h is None or h >= HORAS_MAX) and not hay_corrida_en_curso():
                lanzar("recuperacion: datos con %s h" % ("?" if h is None else round(h, 1)))
        except Exception as e:
            _log("Error en planificador: %s" % e)
        time.sleep(REVISAR_CADA)


def iniciar():
    global _hilo
    if _hilo and _hilo.is_alive():
        return
    _hilo = threading.Thread(target=_bucle, daemon=True, name="planificador")
    _hilo.start()
    _log("Planificador iniciado")

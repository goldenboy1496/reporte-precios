# -*- coding: utf-8 -*-
"""
Script orquestador de scraping para Reporte de Precios Multi-País.
Soporta:
  python actualizar_precios.py                 # Corre todos los países
  python actualizar_precios.py --pais=gt       # Solo Guatemala
  python actualizar_precios.py --pais=sv       # Solo El Salvador
  python actualizar_precios.py --pais=hn       # Solo Honduras
  python actualizar_precios.py --visible       # Muestra navegador si aplica
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Windows terminal UTF-8 safe
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"
STATUS_FILE = DATA_DIR / "status.json"
LOG_FILE = DATA_DIR / "scraping_automatico.log"

DATA_DIR.mkdir(exist_ok=True)

RETAILERS = [
    # Guatemala
    {
        "id": "elektra",
        "nombre": "Elektra (GT)",
        "pais": "gt",
        "script": SCRIPTS_DIR / "elektra.py",
        "csv": DATA_DIR / "productos_elektra.csv",
    },
    {
        "id": "max",
        "nombre": "MAX (GT)",
        "pais": "gt",
        "script": SCRIPTS_DIR / "max.py",
        "csv": DATA_DIR / "productos_max.csv",
    },
    {
        "id": "gallo",
        "nombre": "Gallo más Gallo (GT)",
        "pais": "gt",
        "script": SCRIPTS_DIR / "gallo.py",
        "csv": DATA_DIR / "productos_elgallomasgallo.csv",
    },
    {
        "id": "walmart_gt",
        "nombre": "Walmart (GT)",
        "pais": "gt",
        "script": SCRIPTS_DIR / "walmart_gt.py",
        "csv": DATA_DIR / "productos_walmart_gt.csv",
    },

    # El Salvador
    {
        "id": "siman",
        "nombre": "Siman (SV)",
        "pais": "sv",
        "script": SCRIPTS_DIR / "siman.py",
        "csv": DATA_DIR / "productos_siman.csv",
    },
    {
        "id": "curacao_sv",
        "nombre": "La Curacao (SV)",
        "pais": "sv",
        "script": SCRIPTS_DIR / "curacao_sv.py",
        "csv": DATA_DIR / "productos_curacao_sv.csv",
    },
    {
        "id": "prado",
        "nombre": "Prado (SV)",
        "pais": "sv",
        "script": SCRIPTS_DIR / "prado.py",
        "csv": DATA_DIR / "productos_prado.csv",
    },
    {
        "id": "walmart_sv",
        "nombre": "Walmart (SV)",
        "pais": "sv",
        "script": SCRIPTS_DIR / "walmart_sv.py",
        "csv": DATA_DIR / "productos_walmart_sv.csv",
    },

    # Honduras
    {
        "id": "jetstereo",
        "nombre": "Jetstereo (HN)",
        "pais": "hn",
        "script": SCRIPTS_DIR / "jetstereo.py",
        "csv": DATA_DIR / "productos_jetstereo.csv",
    },
    {
        "id": "elektra_hn",
        "nombre": "Elektra (HN)",
        "pais": "hn",
        "script": SCRIPTS_DIR / "elektra_hn.py",
        "csv": DATA_DIR / "productos_elektra_hn.csv",
    },
    {
        "id": "diunsa",
        "nombre": "Diunsa (HN)",
        "pais": "hn",
        "script": SCRIPTS_DIR / "diunsa.py",
        "csv": DATA_DIR / "productos_diunsa.csv",
    },
    {
        "id": "walmart_hn",
        "nombre": "Walmart (HN)",
        "pais": "hn",
        "script": SCRIPTS_DIR / "walmart_hn.py",
        "csv": DATA_DIR / "productos_walmart_hn.csv",
    },

]


def log_mensaje(texto):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{ahora}] {texto}"
    print(linea)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass


def cargar_status():
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def guardar_status(status):
    try:
        STATUS_FILE.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log_mensaje(f"Error guardando status.json: {e}")


def ejecutar_scraper(retailer_info, modo_visible=False):
    r_id = retailer_info["id"]
    r_nombre = retailer_info["nombre"]
    script_path = retailer_info["script"]
    csv_path = retailer_info["csv"]

    if not script_path.exists():
        log_mensaje(f"✗ Script no encontrado para {r_nombre}: {script_path.name}")
        return False

    status = cargar_status()
    status[r_id] = {"estado": "corriendo", "inicio": time.time()}
    guardar_status(status)

    modo_str = "VISIBLE en pantalla" if modo_visible else "SILENCIOSO en segundo plano"
    log_mensaje(f"⏳ Iniciando scraping de {r_nombre} ({modo_str})...")
    t_inicio = time.time()

    cmd = [sys.executable, str(script_path)]
    if modo_visible:
        cmd.append("--visible")

    try:
        resultado = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=not modo_visible,
            text=True,
            timeout=900,
        )
        duracion = round(time.time() - t_inicio, 1)
        ok = resultado.returncode == 0 and csv_path.exists()

        status = cargar_status()
        if ok:
            status[r_id] = {
                "estado": "ok",
                "ultima_actualizacion": time.time(),
                "duracion_segundos": duracion,
            }
            log_mensaje(f"✓ {r_nombre} completado con éxito ({duracion}s)")
        else:
            log_err = ""
            if resultado.stdout or resultado.stderr:
                log_err = ((resultado.stdout or "")[-1500:] + "\n" + (resultado.stderr or "")[-1500:]).strip()
            status[r_id] = {
                "estado": "error",
                "ultima_actualizacion": time.time(),
                "duracion_segundos": duracion,
                "log": log_err,
            }
            log_mensaje(f"✗ Error en {r_nombre} (código {resultado.returncode})")

        guardar_status(status)
        return ok

    except subprocess.TimeoutExpired:
        log_mensaje(f"⚠ Timeout en {r_nombre}")
        status = cargar_status()
        status[r_id] = {"estado": "error", "ultima_actualizacion": time.time(), "log": "Timeout"}
        guardar_status(status)
        return False
    except Exception as e:
        log_mensaje(f"✗ Excepción en {r_nombre}: {e}")
        status = cargar_status()
        status[r_id] = {"estado": "error", "ultima_actualizacion": time.time(), "log": str(e)}
        guardar_status(status)
        return False



def publicar_a_github():
    try:
        from datetime import datetime
        log_mensaje("🚀 Publicando actualización automáticamente a GitHub Pages...")
        export_script = BASE_DIR / "exportar_reporte_estatico.py"
        if export_script.exists():
            res_exp = subprocess.run([sys.executable, str(export_script)], cwd=str(BASE_DIR), capture_output=True, text=True)
            if res_exp.returncode != 0:
                log_mensaje(f"⚠️ Error al compilar reporte estático: {res_exp.stderr}")
                return
        
        repo_dir = BASE_DIR.parent / "reporte_web"
        if repo_dir.exists():
            subprocess.run(["git", "add", "-A"], cwd=str(repo_dir), check=True)
            fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
            subprocess.run(["git", "commit", "-m", f"Auto-actualizacion de precios: {fecha_str}"], cwd=str(repo_dir))
            res_push = subprocess.run(["git", "push", "origin", "main"], cwd=str(repo_dir), capture_output=True, text=True)
            if res_push.returncode == 0:
                log_mensaje("✅ Reporte publicado en GitHub Pages con éxito: https://goldenboy1496.github.io/reporte-precios/")
            else:
                log_mensaje(f"⚠️ Aviso al empujar a GitHub: {res_push.stderr}")
    except Exception as e:
        log_mensaje(f"⚠️ No se pudo publicar a GitHub Pages: {e}")

def main():
    modo_visible = "--visible" in sys.argv
    filtro_pais = None
    for arg in sys.argv:
        if arg.startswith("--pais="):
            filtro_pais = arg.split("=")[1].strip().lower()

    lista_retailers = RETAILERS
    if filtro_pais:
        lista_retailers = [r for r in RETAILERS if r.get("pais") == filtro_pais]

    log_mensaje("=" * 60)
    tipo = "MANUAL (VENTANA VISIBLE)" if modo_visible else "AUTOMÁTICO (SILENCIOSO)"
    pais_desc = f"PAÍS: {filtro_pais.upper()}" if filtro_pais else "TODOS LOS PAÍSES"
    log_mensaje(f"Iniciando jornada de actualización de precios [{tipo}] [{pais_desc}]")
    t_total_inicio = time.time()

    exitosos = 0
    for r in lista_retailers:
        ok = ejecutar_scraper(r, modo_visible=modo_visible)
        if ok:
            exitosos += 1
        time.sleep(1)

    t_total = round(time.time() - t_total_inicio, 1)
    log_mensaje(f"Resumen: {exitosos}/{len(lista_retailers)} tiendas actualizadas en {t_total}s.")
    log_mensaje("=" * 60)

    if exitosos > 0:
        publicar_a_github()


if __name__ == "__main__":
    main()

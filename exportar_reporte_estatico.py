# -*- coding: utf-8 -*-
import json
import shutil
from datetime import datetime
from pathlib import Path
import sys

BASE_DIR = Path(r"C:\Users\Bryan Roblero\Documents\reporte")
DATA_DIR = BASE_DIR / "data"
TEMPLATE_FILE = BASE_DIR / "templates" / "index.html"
OUTPUT_WEB_DIR = Path(r"C:\Users\Bryan Roblero\Documents\reporte_web")
OUTPUT_WEB_FILE = OUTPUT_WEB_DIR / "index.html"
OUTPUT_LOCAL_FILE = BASE_DIR / "reporte_publico.html"

sys.path.insert(0, str(BASE_DIR))
from matching import build_report

def main():
    print("Compilando reportes para GT, SV, HN...")
    datos_offline = {}
    import historico
    for pais in ["gt", "sv", "hn"]:
        rep = build_report(DATA_DIR, pais=pais)
        datos_offline[pais] = rep
        try:
            historico.registrar_cambios_desde_reporte(rep)
        except Exception as e:
            print(f"  Aviso registrando historico {pais}:", e)
        print(f"  {pais.upper()}: {len(rep.get('filas', []))} productos procesados.")

    # Cargar metricas del historico para embeber en el HTML estatico
    try:
        metricas_historico = historico.calcular_metricas_historico()
        historico_json = json.dumps(metricas_historico, ensure_ascii=False)
    except Exception as e:
        print("Aviso calculando metricas historico:", e)
        historico_json = "{}"

    # Cargar template
    html = TEMPLATE_FILE.read_text(encoding="utf-8")

    # Inyectar script con window.DATOS_OFFLINE
    datos_json = json.dumps(datos_offline, ensure_ascii=False)
    
    # Cargar configuracion de usuarios y hashes
    users_file = DATA_DIR / "usuarios.json"
    auth_config_json = "{}"
    if users_file.exists():
        try:
            import hashlib
            udata = json.loads(users_file.read_text(encoding="utf-8"))
            usalt = udata.get("salt", "samsung_retail_2026_ca")
            uhashed = []
            for u in udata.get("usuarios", []):
                h = hashlib.sha256(f"{u['usuario'].lower().strip()}:{u['password'].strip()}:{usalt}".encode("utf-8")).hexdigest()
                uhashed.append({"usuario": u["usuario"], "nombre": u.get("nombre", u["usuario"]), "hash": h})
            auth_config_json = json.dumps({"salt": usalt, "users": uhashed}, ensure_ascii=False)
        except Exception as e:
            print("Aviso cargando usuarios:", e)

    offline_script = f"""
    <!-- DATOS Y SEGURIDAD EMBEBIDOS PARA GITHUB PAGES -->
    <script>
      window.AUTH_CONFIG = {auth_config_json};
      window.DATOS_OFFLINE = {datos_json};
      window.HISTORICO_METRICAS = {historico_json};
      console.log("Modo Autónomo y Protegido: Datos y autenticación activos");
    </script>
"""

    # Insertar antes de </head>
    if "</head>" in html:
        html = html.replace("</head>", f"{offline_script}\n</head>", 1)

    # Actualizar cargarDatos en el HTML para consumir DATOS_OFFLINE primero
    cargar_datos_original = """async function cargarDatos(silencioso = false) {
        try {
          const resp = await fetch("/api/data?pais=" + paisActual + "&tolerancia=" + toleranciaDescuentoActual);
          const reporte = await resp.json();
          aplicarReporte(reporte);
          if (!silencioso) showToast("Datos de " + (reporte.pais_nombre || paisActual.toUpperCase()) + " sincronizados", "success", 1800);
        } catch (err) {
          if (!silencioso) showToast("Error de conexión con el servidor", "error");
        }
      }"""

    cargar_datos_nuevo = """async function cargarDatos(silencioso = false) {
        // Soporte GitHub Pages / Modo Offline
        if (window.DATOS_OFFLINE && window.DATOS_OFFLINE[paisActual]) {
          aplicarReporte(window.DATOS_OFFLINE[paisActual]);
          // Intentar actualizar silenciosamente si hay servidor en segundo plano
          try {
            const resp = await fetch("/api/data?pais=" + paisActual + "&tolerancia=" + toleranciaDescuentoActual);
            if (resp.ok) {
              const reporte = await resp.json();
              aplicarReporte(reporte);
            }
          } catch(e) {}
          return;
        }

        try {
          const resp = await fetch("/api/data?pais=" + paisActual + "&tolerancia=" + toleranciaDescuentoActual);
          const reporte = await resp.json();
          aplicarReporte(reporte);
          if (!silencioso) showToast("Datos de " + (reporte.pais_nombre || paisActual.toUpperCase()) + " sincronizados", "success", 1800);
        } catch (err) {
          if (!silencioso) showToast("Error de conexión con el servidor", "error");
        }
      }"""

    if cargar_datos_original in html:
        html = html.replace(cargar_datos_original, cargar_datos_nuevo)
        print("  cargarDatos reemplazado con soporte offline directo.")
    else:
        # Fallback con reemplazo flexible si había diferencias de encoding
        idx = html.find("async function cargarDatos")
        if idx != -1:
            end_idx = html.find("let fastPollTimer", idx)
            if end_idx != -1:
                html = html[:idx] + cargar_datos_nuevo + "\n\n      " + html[end_idx:]
                print("  cargarDatos reemplazado mediante búsqueda posicional.")

    # Actualizar badge de última actualización inicial si está presente
    fecha_hoy = datetime.now().strftime("%d/%m/%Y %I:%M %p")
    html = html.replace('badge-ultima-actualizacion">--</span>', f'badge-ultima-actualizacion">{fecha_hoy}</span>')
    html = html.replace('badge-ultima-actualizacion" style="background:rgba(16,185,129,0.12); color:var(--emerald); border:1px solid rgba(16,185,129,0.3); font-weight:700; letter-spacing:0.2px; display:inline-flex; align-items:center; gap:5px;">🕒 Última actualización: --</span>', f'badge-ultima-actualizacion" style="background:rgba(16,185,129,0.12); color:var(--emerald); border:1px solid rgba(16,185,129,0.3); font-weight:700; letter-spacing:0.2px; display:inline-flex; align-items:center; gap:5px;">🕒 Última actualización: {fecha_hoy}</span>')

    # Guardar en reporte_web/index.html
    OUTPUT_WEB_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_WEB_FILE.write_text(html, encoding="utf-8")
    print(f"Generado {OUTPUT_WEB_FILE} ({len(html)} bytes)")

    # Guardar en reporte/reporte_publico.html
    OUTPUT_LOCAL_FILE.write_text(html, encoding="utf-8")
    print(f"Generado {OUTPUT_LOCAL_FILE} ({len(html)} bytes)")

    # Guardar en la raíz de reporte/index.html (para repositorio único y GitHub Pages)
    INDEX_ROOT = BASE_DIR / "index.html"
    INDEX_ROOT.write_text(html, encoding="utf-8")
    print(f"Generado {INDEX_ROOT} ({len(html)} bytes)")

    # Copiar carpeta static
    static_src = BASE_DIR / "static"
    static_dst = OUTPUT_WEB_DIR / "static"
    if static_src.exists():
        if static_dst.exists():
            shutil.rmtree(static_dst)
        shutil.copytree(static_src, static_dst)
        print("Copiada carpeta static a reporte_web.")

if __name__ == "__main__":
    main()
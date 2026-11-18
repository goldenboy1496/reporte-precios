"""Herramienta GUI para cargar forecast desde Excel hacia las matrices de Tesser (mytesser.com).

Permite:
1. Abrir o conectarse a una sesión de Google Chrome con depuración remota (puerto 9222).
2. Leer el archivo Excel de forecast (hoja 'SKU Unidades' por defecto), detectar países y meses.
3. Seleccionar país (GT, SV, HN), matrices (Tablets, Serie A, Serie S, Serie Z, etc.) y meses.
4. Ejecutar en modo simulación (Dry Run) o cargar en vivo a Tesser haciendo coincidir
   estrictamente por código exacto de SKU en la fila AJUSTE, con verificación posterior.
"""

from __future__ import annotations

import os
import queue
import re
import socket
import subprocess
import threading
import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk
import openpyxl
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_EXCEL_PATH = r"c:\Users\Bryan Roblero\Downloads\Forecast_Ventas_SKU_Pais_2027.xlsx"
DEFAULT_DEBUG_PORT = 9222
CHROME_PROFILE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "TesserForecastChrome",
)

MONTH_MAP = {
    "ene": "1",
    "feb": "2",
    "mar": "3",
    "abr": "4",
    "may": "5",
    "jun": "6",
    "jul": "7",
    "ago": "8",
    "sep": "9",
    "oct": "10",
    "nov": "11",
    "dic": "12",
}

MATRICES: dict[str, dict[str, str]] = {
    "TABLETS": {
        "label": "Tablets",
        "familia": "TABLETS",
        "subfamilia": "",
        "url": "https://mytesser.com/matrix/open/695ae50ec3a50cef19062dc5",
    },
    "SERIE A": {
        "label": "Celulares - Serie A",
        "familia": "CELULARES",
        "subfamilia": "SERIE A",
        "url": "https://mytesser.com/matrix/open/690272c7aa17a045ec00815c",
    },
    "SERIE S": {
        "label": "Celulares - Serie S",
        "familia": "CELULARES",
        "subfamilia": "SERIE S",
        "url": "https://mytesser.com/matrix/open/6907b87baa17a045ec00a7d0",
    },
    "SERIE Z": {
        "label": "Celulares - Serie Z",
        "familia": "CELULARES",
        "subfamilia": "SERIE Z",
        "url": "https://mytesser.com/matrix/open/6907c19aaa17a045ec00a83e",
    },
    "AUDIFONOS": {
        "label": "Audífonos",
        "familia": "AUDIFONOS",
        "subfamilia": "",
        "url": "https://mytesser.com/matrix/open/695c08a4c3a50cef1906357b",
    },
    "RELOJES": {
        "label": "Relojes",
        "familia": "RELOJES",
        "subfamilia": "",
        "url": "https://mytesser.com/matrix/open/695bf3acc3a50cef19063468",
    },
    "ACCESORIOS": {
        "label": "Telefonía Accesorios",
        "familia": "ACCESORIOS",
        "subfamilia": "",
        "url": "https://mytesser.com/matrix/open/69b21857d2d70091a800eb79",
    },
}


@dataclass
class MonthCol:
    """Representa una columna de mes en el Excel y su equivalente (año, mes) en Tesser."""

    col_idx: int
    header: str
    year: str
    month: str


def parse_month_header(header: Any) -> tuple[str, str] | None:
    """Convierte encabezados tipo 'nov-26' o 'ene-27' en ('2026', '11')."""
    if header is None:
        return None
    text = str(header).strip().lower()
    match = re.fullmatch(r"([a-záéíóú]{3})-(\d{2,4})", text)
    if not match:
        return None
    mon_abbr, yr_str = match.groups()
    if mon_abbr not in MONTH_MAP:
        return None
    year = f"20{yr_str}" if len(yr_str) == 2 else yr_str
    return year, MONTH_MAP[mon_abbr]


def find_chrome_executable() -> str | None:
    """Busca el ejecutable de Google Chrome en rutas estándar de Windows."""
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Verifica si un puerto TCP local está escuchando."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def load_excel_forecast(
    excel_path: str, sheet_name: str = "SKU Unidades"
) -> tuple[list[str], list[MonthCol], dict[tuple[str, str], dict[str, dict[tuple[str, str], int]]]]:
    """Lee el Excel de forecast y devuelve (paises, meses, datos).

    datos[(pais, matrix_key)][sku_code][(year, month)] = int_value
    """
    wb = openpyxl.load_workbook(excel_path, data_only=True, read_only=True)
    if sheet_name not in wb.sheetnames:
        raise ValueError(f"La hoja '{sheet_name}' no existe en {os.path.basename(excel_path)}.")

    ws = wb[sheet_name]
    header_row_idx = None
    headers: list[Any] = []
    for idx, row in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True), start=1):
        row_strs = [str(c).strip().upper() if c is not None else "" for c in row]
        if "SKU" in row_strs and "PAÍS" in row_strs or ("SKU" in row_strs and "PAIS" in row_strs):
            header_row_idx = idx
            headers = list(row)
            break

    if header_row_idx is None:
        raise ValueError("No se encontró la fila de encabezados (con 'País' y 'SKU') en las primeras 15 filas.")

    col_map: dict[str, int] = {}
    month_cols: list[MonthCol] = []
    for c_idx, val in enumerate(headers):
        label = str(val).strip() if val is not None else ""
        upper = label.upper()
        if upper in ("PAÍS", "PAIS"):
            col_map["pais"] = c_idx
        elif upper == "FAMILIA":
            col_map["familia"] = c_idx
        elif upper == "SUBFAMILIA":
            col_map["subfamilia"] = c_idx
        elif upper == "SKU":
            col_map["sku"] = c_idx
        else:
            parsed = parse_month_header(label)
            if parsed:
                month_cols.append(MonthCol(c_idx, label, parsed[0], parsed[1]))

    required = {"pais", "familia", "subfamilia", "sku"}
    if not required.issubset(col_map):
        raise ValueError(f"Faltan columnas requeridas en encabezados: {required - set(col_map)}")

    paises_set: set[str] = set()
    datos: dict[tuple[str, str], dict[str, dict[tuple[str, str], int]]] = {}

    for row in ws.iter_rows(min_row=header_row_idx + 1, values_only=True):
        pais = str(row[col_map["pais"]] or "").strip().upper()
        familia = str(row[col_map["familia"]] or "").strip().upper()
        subfamilia = str(row[col_map["subfamilia"]] or "").strip().upper()
        sku = str(row[col_map["sku"]] or "").strip().upper()
        if not pais or not sku:
            continue

        matrix_key = None
        if familia == "CELULARES" and subfamilia in ("SERIE A", "SERIE S", "SERIE Z"):
            matrix_key = subfamilia
        elif familia in ("TABLETS", "AUDIFONOS", "RELOJES", "ACCESORIOS"):
            matrix_key = familia

        if not matrix_key:
            continue

        paises_set.add(pais)
        sku_months: dict[tuple[str, str], int] = {}
        for mc in month_cols:
            raw_val = row[mc.col_idx] if mc.col_idx < len(row) else None
            num_val = round(float(raw_val)) if raw_val is not None and raw_val != "" else 0
            sku_months[(mc.year, mc.month)] = num_val

        datos.setdefault((pais, matrix_key), {})[sku] = sku_months

    wb.close()
    return sorted(paises_set), month_cols, datos


class TesserAutomator:
    """Controla Tesser en Chrome vía Selenium conectado por puerto de depuración."""

    JS_GET_HOT = """
    const el = document.querySelector('.handsontable');
    if (!el) return null;
    if (el.hot) return el.hot;
    for (const k of Object.keys(el)) {
        if (el[k] && typeof el[k].getData === 'function') return el[k];
    }
    if (window.hot && typeof window.hot.getData === 'function') return window.hot;
    if (window.Handsontable && el.dataset && el.dataset.hotId) {
        return window.Handsontable.getInstance?.(el) || null;
    }
    return null;
    """

    JS_INSPECT_GRID = """
    const hot = (() => {
        const el = document.querySelector('.handsontable');
        if (!el) return null;
        if (el.hot) return el.hot;
        for (const k of Object.keys(el)) {
            if (el[k] && typeof el[k].getData === 'function') return el[k];
        }
        return window.hot || null;
    })();
    if (!hot) return { error: 'No se encontró la instancia de Handsontable en la página.' };

    const colHeaders = [];
    const colCount = hot.countCols();
    const headerRows = hot.getColHeader();
    // Construir mapa de columnas usando las filas de encabezado del DOM (.ht_clone_top thead tr)
    const theadRows = Array.from(document.querySelectorAll('.ht_clone_top thead tr'));
    const matrix = theadRows.map(tr => {
        const cells = [];
        Array.from(tr.children).forEach(th => {
            const span = parseInt(th.getAttribute('colspan') || '1', 10);
            const txt = (th.innerText || '').trim();
            for (let i = 0; i < span; i++) cells.push(txt);
        });
        return cells;
    });

    // Determinar año y mes por cada índice de columna de datos
    const rowHeaderCount = document.querySelectorAll('.ht_clone_top_left_corner thead tr:last-child th').length;
    const colsInfo = [];
    for (let c = 0; c < colCount; c++) {
        const domIdx = c + rowHeaderCount;
        let year = '';
        let month = '';
        if (matrix.length >= 2) {
            year = (matrix[0][domIdx] || '').trim();
            month = (matrix[1][domIdx] || '').trim();
        } else if (matrix.length === 1) {
            month = (matrix[0][domIdx] || '').trim();
        }
        colsInfo.push({ col: c, year, month });
    }

    // Leer filas: buscar SKU-DESC y DATOS SLC == AJUSTE
    const rowCount = hot.countRows();
    const rowsInfo = [];
    const cornerRows = Array.from(document.querySelectorAll('.ht_clone_left tbody tr'));
    // Usamos getSourceData / getDataAtRowProp o headers de fila vía hot
    const rowHeaders = [];
    for (let r = 0; r < rowCount; r++) {
        let texts = [];
        if (typeof hot.getRowHeader === 'function') {
            const rh = hot.getRowHeader(r);
            texts = Array.isArray(rh) ? rh.map(x => String(x || '').trim()) : [String(rh || '').trim()];
        }
        rowHeaders.push(texts);
    }

    // También leemos el DOM de .ht_clone_left si getRowHeader no trae todas las columnas jerárquicas
    const leftTrs = Array.from(document.querySelectorAll('.ht_master .htCore tbody tr'));
    let currentSku = '';
    for (let r = 0; r < rowCount; r++) {
        let skuText = '';
        let metricText = '';
        if (leftTrs[r]) {
            const ths = Array.from(leftTrs[r].querySelectorAll('th'));
            const texts = ths.map(th => (th.innerText || '').trim());
            for (const t of texts) {
                if (t.includes('_') && /^SM-/i.test(t)) skuText = t;
                if (['AJUSTE', 'FORECAST FINAL', 'FORECAST PRO', 'COSTO FCST', 'INVENTARIO'].includes(t.toUpperCase())) {
                    metricText = t.toUpperCase();
                }
            }
        }
        if (skuText) currentSku = skuText;
        if (metricText === 'AJUSTE' && currentSku) {
            const skuCode = currentSku.split('_')[0].trim().toUpperCase();
            rowsInfo.push({ row: r, sku: skuCode, fullSku: currentSku });
        }
    }

    return {
        colCount,
        rowCount,
        colsInfo,
        ajusteRows: rowsInfo,
    };
    """

    def __init__(self, port: int = DEFAULT_DEBUG_PORT) -> None:
        self.port = port
        self.driver: webdriver.Chrome | None = None

    def connect(self) -> None:
        """Conecta Selenium al Chrome abierto en el puerto de depuración."""
        if not is_port_open(self.port):
            raise ConnectionError(
                f"No hay ningún Chrome escuchando en el puerto {self.port}. "
                "Usa el botón 'Abrir Chrome para Tesser' primero."
            )
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.port}")
        self.driver = webdriver.Chrome(options=options)

    def ensure_logged_in(self) -> None:
        """Verifica que la sesión en mytesser.com esté iniciada."""
        assert self.driver is not None
        url = self.driver.current_url
        if "mytesser.com" not in url:
            self.driver.get("https://mytesser.com/")
            time.sleep(2.5)
        if "/login" in self.driver.current_url or "/auth" in self.driver.current_url:
            raise PermissionError(
                "No has iniciado sesión en Tesser. Inicia sesión en la ventana de Chrome y vuelve a intentar."
            )

    def open_matrix(self, url: str) -> None:
        """Abre una matriz de Tesser y espera a que cargue Handsontable."""
        assert self.driver is not None
        self.driver.get(url)
        WebDriverWait(self.driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".handsontable .htCore"))
        )
        time.sleep(1.5)

    def get_current_pais(self) -> str | None:
        """Lee el país actualmente seleccionado en la barra superior de filtros."""
        assert self.driver is not None
        js = """
        const pills = Array.from(document.querySelectorAll('button, .ant-select, .filter-pill, [class*="filter"]'));
        for (const el of pills) {
            const txt = (el.innerText || '').trim();
            const m = txt.match(/PAIS\\s*[:\\n]?\\s*(GT|SV|HN)/i);
            if (m) return m[1].toUpperCase();
        }
        return null;
        """
        return self.driver.execute_script(js)

    def select_pais(self, target_pais: str) -> bool:
        """Cambia el filtro PAIS en Tesser al país indicado si es necesario."""
        assert self.driver is not None
        current = self.get_current_pais()
        if current == target_pais:
            return True

        # Intentar abrir el selector de PAIS en la barra superior
        clicked = self.driver.execute_script(
            """
            const candidates = Array.from(document.querySelectorAll('button, div, span'));
            for (const el of candidates) {
                const txt = (el.innerText || '').trim();
                if (/^PAIS\\b/i.test(txt) && txt.length < 25 && el.offsetParent !== null) {
                    el.click();
                    return true;
                }
            }
            return false;
            """
        )
        if not clicked:
            return False
        time.sleep(0.8)

        selected = self.driver.execute_script(
            """
            const target = arguments[0].toUpperCase();
            const items = Array.from(document.querySelectorAll('li, option, div[role="option"], label, span, a'));
            for (const el of items) {
                if (el.offsetParent === null) continue;
                const txt = (el.innerText || '').trim().toUpperCase();
                if (txt === target) {
                    el.click();
                    return true;
                }
            }
            return false;
            """,
            target_pais,
        )
        if selected:
            time.sleep(2.0)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".handsontable .htCore"))
            )
        return bool(selected)

    def inspect_grid(self) -> dict[str, Any]:
        """Inspecciona la grilla Handsontable actual y devuelve columnas y filas AJUSTE."""
        assert self.driver is not None
        return self.driver.execute_script(self.JS_INSPECT_GRID)

    def apply_updates(
        self,
        updates: list[tuple[int, int, int]],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Aplica una lista de (row, col, value) en Handsontable y verifica leyendo de nuevo."""
        assert self.driver is not None
        if dry_run or not updates:
            return {"updated": 0, "mismatches": []}

        js_apply = """
        const updates = arguments[0];
        const el = document.querySelector('.handsontable');
        let hot = el && el.hot;
        if (!hot && el) {
            for (const k of Object.keys(el)) {
                if (el[k] && typeof el[k].setDataAtCell === 'function') { hot = el[k]; break; }
            }
        }
        if (!hot) hot = window.hot;
        if (!hot) return { error: 'Handsontable no disponible' };

        const batch = updates.map(([r, c, v]) => [r, c, v]);
        hot.setDataAtCell(batch, 'tesser_loader');
        return { sent: batch.length };
        """
        res = self.driver.execute_script(js_apply, updates)
        if isinstance(res, dict) and res.get("error"):
            raise RuntimeError(res["error"])

        # Esperar a que Tesser procese los save_value
        time.sleep(max(1.5, min(6.0, len(updates) * 0.04)))

        js_verify = """
        const updates = arguments[0];
        const el = document.querySelector('.handsontable');
        let hot = el && el.hot;
        if (!hot && el) {
            for (const k of Object.keys(el)) {
                if (el[k] && typeof el[k].getDataAtCell === 'function') { hot = el[k]; break; }
            }
        }
        if (!hot) hot = window.hot;
        const mismatches = [];
        for (const [r, c, expected] of updates) {
            const actual = hot.getDataAtCell(r, c);
            const actualNum = actual === null || actual === '' ? null : Number(String(actual).replace(/,/g, ''));
            if (actualNum !== expected) {
                mismatches.push({ row: r, col: c, expected, actual });
            }
        }
        return { mismatches };
        """
        ver = self.driver.execute_script(js_verify, updates)
        return {"updated": len(updates), "mismatches": ver.get("mismatches", [])}


class ForecastLoaderApp(ctk.CTk):
    """Interfaz gráfica principal para cargar el forecast a Tesser."""

    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Cargador de Forecast -> Tesser")
        self.geometry("920x720")
        self.minsize(820, 640)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.excel_data: dict[tuple[str, str], dict[str, dict[tuple[str, str], int]]] = {}
        self.excel_paises: list[str] = []
        self.excel_months: list[MonthCol] = []
        self.matrix_vars: dict[str, tk.BooleanVar] = {}
        self.month_vars: dict[tuple[str, str], tk.BooleanVar] = {}
        self.is_running = False

        self._build_ui()
        self.after(150, self._poll_logs)

        if os.path.isfile(DEFAULT_EXCEL_PATH):
            self.excel_path_var.set(DEFAULT_EXCEL_PATH)
            self._load_excel()

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 6}

        # 1. Archivo Excel
        file_frame = ctk.CTkFrame(self)
        file_frame.pack(fill="x", **pad)

        ctk.CTkLabel(file_frame, text="Archivo Excel:", font=("Segoe UI", 13, "bold")).pack(
            side="left", padx=(10, 8), pady=10
        )
        self.excel_path_var = tk.StringVar()
        ctk.CTkEntry(file_frame, textvariable=self.excel_path_var, width=480).pack(
            side="left", fill="x", expand=True, padx=4, pady=10
        )
        ctk.CTkButton(file_frame, text="Buscar...", width=90, command=self._browse_excel).pack(
            side="left", padx=4, pady=10
        )
        ctk.CTkButton(file_frame, text="Leer Excel", width=100, command=self._load_excel).pack(
            side="left", padx=(4, 10), pady=10
        )

        # 2. Chrome & País
        conn_frame = ctk.CTkFrame(self)
        conn_frame.pack(fill="x", **pad)

        ctk.CTkLabel(conn_frame, text="País:", font=("Segoe UI", 13, "bold")).pack(
            side="left", padx=(10, 6), pady=10
        )
        self.pais_var = tk.StringVar(value="GT")
        self.pais_menu = ctk.CTkOptionMenu(conn_frame, variable=self.pais_var, values=["GT", "SV", "HN"], width=90)
        self.pais_menu.pack(side="left", padx=4, pady=10)

        ctk.CTkLabel(conn_frame, text="Puerto Chrome:", font=("Segoe UI", 12)).pack(
            side="left", padx=(16, 6), pady=10
        )
        self.port_var = tk.StringVar(value=str(DEFAULT_DEBUG_PORT))
        ctk.CTkEntry(conn_frame, textvariable=self.port_var, width=70).pack(side="left", padx=4, pady=10)

        ctk.CTkButton(
            conn_frame,
            text="Abrir Chrome para Tesser",
            fg_color="#1f6aa5",
            command=self._launch_chrome,
        ).pack(side="left", padx=(16, 6), pady=10)

        self.dry_run_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            conn_frame,
            text="Modo Simulación (no guarda cambios)",
            variable=self.dry_run_var,
        ).pack(side="right", padx=12, pady=10)

        # 3. Selección de Matrices y Meses
        sel_frame = ctk.CTkFrame(self)
        sel_frame.pack(fill="x", **pad)

        mat_col = ctk.CTkFrame(sel_frame, fg_color="transparent")
        mat_col.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        ctk.CTkLabel(mat_col, text="Matrices a cargar:", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 4))

        mat_grid = ctk.CTkFrame(mat_col, fg_color="transparent")
        mat_grid.pack(fill="x")
        for idx, (key, info) in enumerate(MATRICES.items()):
            default_on = key in ("TABLETS", "SERIE A", "SERIE S", "SERIE Z")
            var = tk.BooleanVar(value=default_on)
            self.matrix_vars[key] = var
            cb = ctk.CTkCheckBox(mat_grid, text=info["label"], variable=var)
            cb.grid(row=idx // 2, column=idx % 2, sticky="w", padx=8, pady=3)

        mon_col = ctk.CTkFrame(sel_frame, fg_color="transparent")
        mon_col.pack(side="right", fill="both", expand=True, padx=10, pady=8)
        ctk.CTkLabel(mon_col, text="Meses a cargar:", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 4))
        self.months_grid = ctk.CTkFrame(mon_col, fg_color="transparent")
        self.months_grid.pack(fill="x")

        # 4. Botón Ejecutar
        act_frame = ctk.CTkFrame(self, fg_color="transparent")
        act_frame.pack(fill="x", padx=12, pady=4)
        self.run_btn = ctk.CTkButton(
            act_frame,
            text="Ejecutar Carga en Tesser",
            height=40,
            font=("Segoe UI", 14, "bold"),
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self._start_run,
        )
        self.run_btn.pack(fill="x")

        # 5. Log
        self.log_box = ctk.CTkTextbox(self, font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def log(self, msg: str) -> None:
        self.log_queue.put(msg)

    def _poll_logs(self) -> None:
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()
            self.log_box.insert("end", line + "\n")
            self.log_box.see("end")
        self.after(150, self._poll_logs)

    def _browse_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="Seleccionar archivo Excel de Forecast",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if path:
            self.excel_path_var.set(path)
            self._load_excel()

    def _load_excel(self) -> None:
        path = self.excel_path_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Error", "Selecciona un archivo Excel válido.")
            return
        try:
            paises, months, data = load_excel_forecast(path)
        except Exception as exc:
            messagebox.showerror("Error al leer Excel", str(exc))
            return

        self.excel_paises = paises
        self.excel_months = months
        self.excel_data = data

        if paises:
            self.pais_menu.configure(values=paises)
            if self.pais_var.get() not in paises:
                self.pais_var.set(paises[0])

        for w in self.months_grid.winfo_children():
            w.destroy()
        self.month_vars.clear()

        default_targets = {("2026", "11"), ("2026", "12"), ("2027", "1"), ("2027", "2"), ("2027", "3")}
        for idx, mc in enumerate(months):
            key = (mc.year, mc.month)
            var = tk.BooleanVar(value=key in default_targets)
            self.month_vars[key] = var
            cb = ctk.CTkCheckBox(self.months_grid, text=mc.header, variable=var, width=90)
            cb.grid(row=idx // 4, column=idx % 4, sticky="w", padx=4, pady=2)

        self.log(f"[Excel] Cargado: {os.path.basename(path)} | Países: {paises} | Meses: {len(months)}")

    def _launch_chrome(self) -> None:
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Puerto inválido", "Ingresa un número de puerto válido (ej. 9222).")
            return

        if is_port_open(port):
            self.log(f"[Chrome] Ya hay un Chrome escuchando en el puerto {port}.")
            return

        chrome_exe = find_chrome_executable()
        if not chrome_exe:
            messagebox.showerror("Chrome no encontrado", "No se encontró chrome.exe en las rutas estándar.")
            return

        os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
        subprocess.Popen(
            [
                chrome_exe,
                f"--remote-debugging-port={port}",
                f"--user-data-dir={CHROME_PROFILE_DIR}",
                "https://mytesser.com/",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.log(
            f"[Chrome] Abriendo Chrome en puerto {port}. Inicia sesión en mytesser.com y luego presiona 'Ejecutar Carga'."
        )

    def _start_run(self) -> None:
        if self.is_running:
            return
        if not self.excel_data:
            messagebox.showwarning("Sin datos", "Primero carga el archivo Excel.")
            return

        selected_matrices = [k for k, v in self.matrix_vars.items() if v.get()]
        selected_months = [k for k, v in self.month_vars.items() if v.get()]
        if not selected_matrices or not selected_months:
            messagebox.showwarning("Selección vacía", "Selecciona al menos una matriz y un mes.")
            return

        self.is_running = True
        self.run_btn.configure(state="disabled", text="Ejecutando...")
        threading.Thread(
            target=self._run_worker,
            args=(self.pais_var.get(), selected_matrices, selected_months, self.dry_run_var.get()),
            daemon=True,
        ).start()

    def _run_worker(
        self,
        pais: str,
        selected_matrices: list[str],
        selected_months: list[tuple[str, str]],
        dry_run: bool,
    ) -> None:
        try:
            port = int(self.port_var.get().strip())
            bot = TesserAutomator(port=port)
            self.log(f"\n=== Iniciando {'SIMULACIÓN' if dry_run else 'CARGA REAL'} para PAÍS={pais} ===")
            bot.connect()
            bot.ensure_logged_in()

            for m_key in selected_matrices:
                info = MATRICES[m_key]
                sku_map = self.excel_data.get((pais, m_key), {})
                if not sku_map:
                    self.log(f"[{info['label']}] Sin SKUs en Excel para {pais}/{m_key}. Saltando.")
                    continue

                self.log(f"\n[{info['label']}] Abriendo matriz...")
                bot.open_matrix(info["url"])

                if not bot.select_pais(pais):
                    self.log(f"[{info['label']}] ADVERTENCIA: No se pudo seleccionar PAIS={pais} (actual: {bot.get_current_pais()}).")
                    continue

                grid = bot.inspect_grid()
                if grid.get("error"):
                    self.log(f"[{info['label']}] ERROR: {grid['error']}")
                    continue

                col_lookup: dict[tuple[str, str], int] = {}
                for c in grid["colsInfo"]:
                    if c["year"] and c["month"]:
                        col_lookup[(c["year"], c["month"])] = c["col"]

                missing_cols = [ym for ym in selected_months if ym not in col_lookup]
                if missing_cols:
                    self.log(
                        f"[{info['label']}] ADVERTENCIA: Faltan columnas en la grilla (¿año 2027 oculto?): {missing_cols}"
                    )

                ajuste_rows = grid["ajusteRows"]
                updates: list[tuple[int, int, int]] = []
                matched_skus = 0
                for row_info in ajuste_rows:
                    sku = row_info["sku"]
                    if sku not in sku_map:
                        continue
                    matched_skus += 1
                    for ym in selected_months:
                        if ym in col_lookup and ym in sku_map[sku]:
                            updates.append((row_info["row"], col_lookup[ym], sku_map[sku][ym]))

                unmatched_excel = len(sku_map) - matched_skus
                self.log(
                    f"[{info['label']}] SKUs Excel: {len(sku_map)} | Coincidencias exactas visibles: {matched_skus} "
                    f"| No encontrados en grilla visible: {unmatched_excel} | Celdas a escribir: {len(updates)}"
                )

                res = bot.apply_updates(updates, dry_run=dry_run)
                if dry_run:
                    self.log(f"[{info['label']}] Simulación OK (0 celdas modificadas).")
                else:
                    mismatches = res.get("mismatches", [])
                    self.log(
                        f"[{info['label']}] Escritas: {res['updated']} celdas | Discrepancias: {len(mismatches)}"
                    )
                    if mismatches:
                        self.log(f"  Detalle discrepancias: {mismatches[:5]}")

            self.log("\n=== Proceso finalizado ===")
        except Exception as exc:
            self.log(f"[ERROR] {exc}")
        finally:
            self.is_running = False
            self.after(0, lambda: self.run_btn.configure(state="normal", text="Ejecutar Carga en Tesser"))


if __name__ == "__main__":
    app = ForecastLoaderApp()
    app.mainloop()

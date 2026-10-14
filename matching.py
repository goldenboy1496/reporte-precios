# -*- coding: utf-8 -*-
"""
Lógica de emparejamiento (matching) inteligente entre:
  - El catálogo de referencia (data/precios_mercado.csv -> columnas MOBILE, Memoria, RRP, MSRP)
  - Los precios propios editables (data/mis_precios.csv)
  - Los productos scrapeados de cada retailer (data/productos_*.csv)
  - Configuración de tolerancia de descuento dinámica (data/config.json)
"""

import json
import re
import unicodedata
from pathlib import Path
import pandas as pd

CONFIG_DEFAULT_TOLERANCIA_PCT = 5.0

# Reglas de modelos ordenadas por especificidad estricta

COLOR_RULES = [
    ("Celeste",     r"\b(?:AZUL|AZUL)\s*CIELO\b|\bSKY\s*BLUE\b|\bAWESOME\s*ICE\s*BLUE\b|\bICE\s*BLUE\b|\bICEBLUE\b|\bCELESTE\b"),
    ("Azul",        r"\b(?:AZUL|BLUE|AWESOME\s*NAVY|DARK\s*BLUE|NAVY|AZL)\b"),
    ("Verde",       r"\b(?:VERDE|GREEN|MINT|MENTA|LIME|OLIVE|VERDE\s*CLARO)\b"),
    ("Violeta",     r"\b(?:VIOLETA|VIOLET|LAVANDA|LAVENDER|PURPURA|PURPLE|LILAC|LILA|MORADO|TECHO\s*VIOLET|COBALT\s*VIOLET|LIGHT\s*VIOLET|T\s*V|TITANIUM\s*VIOLET)\b"),
    ("Rosado",      r"\b(?:ROSADO|ROSA|PINK|LIGHT\s*PINK|ROSE|LIGHT\s*ROSE)\b"),
    ("Negro",       r"\b(?:NEGRO|BLACK|PHANTOM\s*BLACK|GRAPHITE|GRAFITO|ONYX|AWESOME\s*BLACK|DARK\s*NIGHT|BK|BLK|JETBLAK|NGR|T\s*BLACK)\b"),
    ("Blanco",      r"\b(?:BLANCO|WHITE|CREAM|CREMA|MARFIL|AWESOME\s*WHITE|WH)\b"),
    ("Plata",       r"\b(?:PLATA|SILVER|TITANIUM\s*SILVER|T\s*SILVER)\b"),
    ("Gris",        r"\b(?:GRIS|GREY|GRAY|TITANIUM\s*GR[AE]Y|TITANIO|T\s*GR[AE]Y|GY|GRAPH|GPH)\b"),
    ("Amarillo",    r"\b(?:AMARILLO|YELLOW|GOLD|DORADO|AWESOME\s*LEMON)\b"),
    ("Naranja",     r"\b(?:NARANJA|ORANGE)\b"),
    ("Rojo",        r"\b(?:ROJO|RED)\b"),
]


def extract_color(text):
    if not text:
        return None
    norm = normalize_text(text)
    for color_name, pattern in COLOR_RULES:
        if re.search(pattern, norm):
            return color_name
    return None

MODEL_RULES = [
    # Tablets
    ("Tab S12 Ultra", r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*12\s*(?:ULTRA|ULTR)\b"),
    ("Tab S12+",      r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*12\s*(?:\+|\bPLUS\b)"),
    ("Tab S11 Ultra", r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*11\s*(?:ULTRA|ULTR)\b"),
    ("Tab S11",       r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*11\b"),
    ("Tab S10 Ultra", r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*10\s*(?:ULTRA|ULTR)\b"),
    ("Tab S10 FE+",   r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*10\s*FE\s*(?:\+|\bPLUS\b)"),
    ("Tab S10 FE",    r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*10\s*FE\b"),
    ("Tab S10+",      r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*10\s*(?:\+|\bPLUS\b)"),
    ("Tab S10 Lite",  r"\b(?:TABLET|G?LAXY\s*TAB|TAB)?\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*10\s*LITE\b"),
    ("Tab S10",       r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?S\s*10\b"),
    ("Tab A11+",      r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?A\s*11\s*(?:\+|\bPLUS\b)"),
    ("Tab A11",       r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?A\s*11\b"),
    ("Tab A9+",       r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?A\s*9\s*(?:\+|\bPLUS\b)"),
    ("Tab A9",        r"\b(?:TABLET|G?LAXY\s*TAB|TAB)\s*(?:SAMSUNG\s*)?(?:GALAXY\s*)?A\s*9\b"),

    # Wearables - Watches
    ("Watch Ultra 2",   r"\b(?:WATCH\s*ULTRA\s*2|WATCH\s*ULTRA2|SM[- ]?L715\w*)\b"),
    ("Watch Ultra",     r"\b(?:WATCH\s*ULTRA|SM[- ]?L705\w*)\b"),
    ("Watch 9",         r"\b(?:WATCH\s*9|SM[- ]?L350\w*|SM[- ]?L340\w*)\b"),
    ("Watch 8 Classic", r"\b(?:WATCH\s*8\s*CLASSIC|SM[- ]?L500\w*)\b"),
    ("Watch 8",         r"\b(?:WATCH\s*8|SM[- ]?L330\w*|SM[- ]?L320\w*)\b"),
    ("Watch 7",         r"\b(?:WATCH\s*7|SM[- ]?L310\w*|SM[- ]?L300\w*)\b"),
    ("Watch FE",        r"\b(?:WATCH\s*FE|SM[- ]?R861\w*)\b"),

    # Wearables - Buds & Fit
    ("Buds 4 Pro",      r"\b(?:BUDS\s*4\s*PRO|SM[- ]?R640\w*)\b"),
    ("Buds 3 Pro",      r"\b(?:BUDS\s*3\s*PRO|SM[- ]?R630\w*)\b"),
    ("Buds 4",          r"\b(?:BUDS\s*4|SM[- ]?R540\w*)\b"),
    ("Buds 3 FE",       r"\b(?:BUDS\s*3\s*FE|SM[- ]?R420\w*)\b"),
    ("Buds 3",          r"\b(?:BUDS\s*3|SM[- ]?R530\w*)\b"),
    ("Buds FE",         r"\b(?:BUDS\s*FE|SM[- ]?R400\w*)\b"),
    ("Buds Core",       r"\b(?:BUDS\s*CORE|SM[- ]?R410\w*)\b"),
    ("Fit 3",           r"\b(?:FIT\s*3|GALAXY\s*FIT\s*3|SM[- ]?R390\w*)\b"),

    # Z Fold & Flip
    ("Z Fold 8 Ultra", r"\bZ\s*FOLD\s*(?:8\s*(?:ULTRA|ULTR)|ULTRA\s*8?)\b"),
    ("Z Fold 8",       r"\bZ\s*FOLD\s*8\b"),
    ("Z Fold 7",       r"\bZ\s*FOLD\s*7\b"),
    ("Z Flip 8",       r"\bZ\s*FLIP\s*8\b"),
    ("Z Flip 7 FE",    r"\bZ\s*FLIP\s*7\s*FE\b"),
    ("Z Flip 7",       r"\bZ\s*FLIP\s*7\b"),
    
    # S Series
    ("S26 Ultra",      r"\bS\s*26\s*(?:ULTRA|ULTR)\b"),
    ("S26+",           r"\bS\s*26\s*(?:\+|\bPLUS\b)"),
    ("S26 FE",         r"\bS\s*26\s*FE\b"),
    ("S26",            r"\bS\s*26\b"),
    
    ("S25 Ultra",      r"\bS\s*25\s*(?:ULTRA|ULTR)\b"),
    ("S25+",           r"\bS\s*25\s*(?:\+|\bPLUS\b)"),
    ("S25 FE",         r"\bS\s*25\s*FE\b"),
    ("S25",            r"\bS\s*25\b"),
    
    ("S24 FE",         r"\bS\s*24\s*FE\b"),
    ("S24 Ultra",      r"\bS\s*24\s*(?:ULTRA|ULTR)\b"),
    ("S24+",           r"\bS\s*24\s*(?:\+|\bPLUS\b)"),
    ("S24",            r"\bS\s*24\b"),
    
    # A Series
    ("A57",            r"\bA\s*57\b"),
    ("A56",            r"\bA\s*56\b"),
    ("A37",            r"\bA\s*37\b"),
    ("A36",            r"\bA\s*36\b"),
    ("A27",            r"\bA\s*27\b"),
    ("A26",            r"\bA\s*26\b"),
    ("A18",            r"\bA\s*18\b"),
    ("A17",            r"\b(?:A\s*17|SM[- ]?A?17)\b"),
    ("A16",            r"\bA\s*16\b"),
    ("A08",            r"\bA\s*08\b"),
    ("A07s",           r"\b(?:A\s*07\s*S|07\s*S)\b"),
    ("A07",            r"\bA\s*07\b"),
    ("A06",            r"\bA\s*06\b"),
]


def get_categoria(modelo: str, text: str = "") -> str:
    m = (modelo or "").strip()
    t = (text or "").lower()
    if m.startswith("Tab ") or "tab" in t or "s10lite" in t or "s10 lite" in t:
        return "Tablets"
    if m.startswith("Watch ") or m.startswith("Buds ") or m.startswith("Fit ") or any(w in t for w in ["watch", "buds", "fit", "ring"]):
        return "Wearables"
    return "Smartphones"


def extract_connectivity(text: str) -> str:
    if not text:
        return None
    txt = normalize_text(text)
    if re.search(r"\b(?:5G)\b", txt):
        return "5G"
    if re.search(r"\b(?:LTE|4G)\b", txt):
        return "LTE"
    if re.search(r"\b(?:WIFI|WI\s*FI)\b", txt):
        return "WIFI"
    return None


def extract_size_mm(text: str) -> str:
    if not text:
        return None
    m = re.search(r"\b(40|41|42|43|44|45|46|47)\s*MM\b", normalize_text(text))
    return (m.group(1) + "mm") if m else None


def extract_sm_code(text: str) -> str:
    if not text:
        return None
    norm = normalize_text(text)
    m = re.search(r"\b(SM[- ][A-Z0-9]{4,6}|[LR]\d{3}[A-Z]?)\b", norm)
    if m:
        c = m.group(1).replace(" ", "-")
        if not c.startswith("SM-") and len(c) >= 4:
            c = "SM-" + c
        return c
    return None

def load_config(data_dir: Path):
    """Carga la tolerancia de descuento desde data/config.json."""
    cfg_path = data_dir / "config.json"
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            val = data.get("tolerancia_descuento_pct", data.get("tolerancia_pct", CONFIG_DEFAULT_TOLERANCIA_PCT))
            return float(val)
        except Exception:
            pass
    return CONFIG_DEFAULT_TOLERANCIA_PCT


def save_config(data_dir: Path, tolerancia_pct: float):
    """Guarda la tolerancia de descuento en data/config.json."""
    cfg_path = data_dir / "config.json"
    try:
        data = {"tolerancia_descuento_pct": round(float(tolerancia_pct), 2)}
        cfg_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        print(f"Error guardando config.json: {e}")
        return False


def strip_accents(text):
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize_text(text):
    text = strip_accents(str(text)).upper()
    text = text.replace("PLUS", "+")
    text = re.sub(r"[-_]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


SM_MODEL_MAP = {
    "SM-L300": "Watch 7",
    "SM-L310": "Watch 7",
    "SM-L320": "Watch 8",
    "SM-L330": "Watch 8",
    "SM-L340": "Watch 9",
    "SM-L350": "Watch 9",
    "SM-L500": "Watch 8 Classic",
    "SM-L705": "Watch Ultra",
    "SM-L715": "Watch Ultra 2",
    "SM-R861": "Watch FE",
    "SM-R390": "Fit 3",
    "SM-R410": "Buds Core",
    "SM-R400": "Buds FE",
    "SM-R420": "Buds 3 FE",
    "SM-R530": "Buds 3",
    "SM-R540": "Buds 4",
    "SM-R630": "Buds 3 Pro",
    "SM-R640": "Buds 4 Pro",
}

def extract_model(text):
    norm = normalize_text(text)
    for model_name, pattern in MODEL_RULES:
        if re.search(pattern, norm):
            return model_name
    sm = extract_sm_code(text)
    if sm:
        key = sm[:7]
        if key in SM_MODEL_MAP:
            return SM_MODEL_MAP[key]
    return None


def extract_memory(text):
    norm = normalize_text(text)
    # Corregir posibles errores tipograficos y variantes de tiendas
    norm = re.sub(r'\b(32|64|128|256|512|1024)\s*B\b', r'\g<1>GB', norm)
    norm = re.sub(r'\b(32|64|128|256|512|1024)\s*G\b', r'\g<1>GB', norm)
    norm = re.sub(r'\b(32|64|128|256|512|1024)\s*(?:ALMACENAMIENTO|INTERNO|STORAGE)\b', r'\g<1>GB', norm)

    # 1. RAM + almacenamiento en TB
    m = re.search(r'\b(\d{1,2})\s*(?:GB)?\s*[/+]\s*(\d{1,2})\s*TB\b', norm)
    if m:
        return (int(m.group(1)), int(m.group(2)) * 1024)

    # 2. Solo TB
    m = re.search(r'\b(\d{1,2})\s*TB\b', norm)
    if m:
        return (None, int(m.group(1)) * 1024)

    # 3. RAM y ROM explicitos
    ram_m = re.search(r'\b(\d{1,2})\s*GB\s*RAM\b', norm)
    rom_m = re.search(r'\b(\d{2,4})\s*GB\s*ROM\b', norm)
    if ram_m and rom_m:
        return (int(ram_m.group(1)), int(rom_m.group(1)))

    # 4. Multiples numeros con GB (ej: 12GB + 256GB, 12GB RAM 256GB)
    numeros_gb = [int(x) for x in re.findall(r'\b(\d{1,4})\s*GB\b', norm)]
    if len(numeros_gb) >= 2:
        posibles_ram = [n for n in numeros_gb if n <= 16]
        posibles_almacenamiento = [n for n in numeros_gb if n >= 32]
        ram = posibles_ram[0] if posibles_ram else min(numeros_gb)
        almacenamiento = max(posibles_almacenamiento) if posibles_almacenamiento else max(numeros_gb)
        return (ram, almacenamiento)

    # 5. RAM + almacenamiento con separador explicito / o + (ej: 8+256, 8/256GB, 12+512GB)
    m = re.search(r'\b(\d{1,2})\s*(?:GB)?\s*[/+]\s*(\d{2,4})\s*(?:GB)?\b', norm)
    if m:
        val1, val2 = int(m.group(1)), int(m.group(2))
        if val1 > val2 and val2 <= 16:
            return (val2, val1)
        return (val1, val2)

    # 5b. RAM + almacenamiento separados por espacio (ej: 8 256gb, 6 128gb)
    m = re.search(r'\b([468]|12|16)\s*(?:GB)?\s+(32|64|128|256|512|1024)\s*GB\b', norm)
    if m:
        return (int(m.group(1)), int(m.group(2)))

    # 6. Un solo numero con GB
    if len(numeros_gb) == 1:
        val = numeros_gb[0]
        if val >= 32:
            return (None, val)
        return (val, None)

    m = re.fullmatch(r'(\d{2,4})', norm)
    if m:
        return (None, int(m.group(1)))

    return (None, None)


def parse_price(value):
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in ("", "NA", "N/A", "NO DISPONIBLE", "LIBERADO", "NAN", "NULL"):
        return None
    # Eliminar identificadores de moneda (Q, $, L, L., LPS, HNL, USD, GTQ)
    text = re.sub(r'\b(?:USD|HNL|GTQ|LPS)\b', '', text)
    for sym in ['L.', '$', 'Q', 'L']:
        text = text.replace(sym, '')
    text = text.replace(',', '').strip()
    try:
        num = float(text)
    except ValueError:
        m = re.search(r'(\d+(?:\.\d+)?)', text)
        if m:
            try:
                num = float(m.group(1))
            except ValueError:
                return None
        else:
            return None
    if num <= 0:
        return None
    return round(num, 2)


def load_catalogo(data_dir: Path, pais: str = "gt"):
    path = data_dir / "precios_mercado.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path, dtype=str).fillna("")
    catalogo = []
    
    cfg = PAISES_CONFIG.get(pais, PAISES_CONFIG["gt"])
    rrp_col = cfg["rrp_col"]
    msrp_col = cfg["msrp_col"]

    for _, row in df.iterrows():
        mob = row.get("MOBILE", "").strip()
        mem = row.get("Memoria", "").strip()
        if not mob:
            continue
            
        rrp_val = row.get(rrp_col, "").strip() or row.get("RRP", "").strip()
        msrp_val = row.get(msrp_col, "").strip() or row.get("MSRP", "").strip()
        
        rrp = parse_price(rrp_val)
        msrp = parse_price(msrp_val)
        
        mod = extract_model(mob)
        cat_tipo = get_categoria(mod, mob + " " + mem)
        catalogo.append({
            "mobile": mob,
            "memoria": mem,
            "rrp": rrp,
            "rrp_raw": rrp_val,
            "msrp": msrp,
            "msrp_raw": msrp_val,
            "modelo": mod,
            "mem": extract_memory(mem if cat_tipo != "Wearables" else mob + " " + mem),
            "categoria": cat_tipo,
            "conectividad": extract_connectivity(mob + " " + mem),
            "size_mm": extract_size_mm(mob + " " + mem),
            "sm_code": extract_sm_code(mob + " " + mem),
        })
    return catalogo


def load_mis_precios(data_dir: Path, pais: str = "gt"):
    cfg = PAISES_CONFIG.get(pais, PAISES_CONFIG["gt"])
    path = data_dir / cfg["mis_precios_file"]
    if not path.exists() and pais == "gt":
        path = data_dir / "mis_precios.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    precios = {}
    for _, row in df.iterrows():
        mob = row.get("mobile", "").strip()
        mem = row.get("memoria", "").strip()
        p = parse_price(row.get("mi_precio", ""))
        if mob and mem and p is not None:
            precios[(mob, mem)] = p
    return precios


def es_telefono_operador(nombre: str) -> bool:
    if not nombre:
        return False
    txt = nombre.upper()
    if any(p in txt for p in ["RED CLARO", "RED TIGO", "RED MOVISTAR", "RED DIGICEL", "PREPAGO", "POSPAGO", "POSTPAGO", "BLOQUEADO", "CONTRATO"]):
        return True
    if re.search(r"\b(?:TIGO|MOVISTAR|DIGICEL)\b", txt):
        return True
    for m in re.finditer(r"\bCLARO\b", txt):
        start = m.start()
        prefix = txt[:start].strip()
        ult_palabra = prefix.split()[-1] if prefix.split() else ""
        if ult_palabra in ("VERDE", "AZUL", "GRIS", "ROSA", "ROSADO", "CELESTE", "LIGHT"):
            continue
        return True
    return False


def es_otra_marca(nombre: str) -> bool:
    if not nombre:
        return False
    txt = nombre.upper()
    otras = ['MOTOROLA', 'MOTO ', 'OPPO', 'XIAOMI', 'REDMI', 'POCO', 'IPHONE', 'APPLE', 'HONOR', 'HUAWEI', 'INFINIX', 'TECNO', 'ZTE', 'REALME']
    return any(m in txt for m in otras)


def es_accesorio(nombre: str, cat_tipo: str) -> bool:
    if not nombre:
        return False
    t = normalize_text(nombre)

    # Cobertores y accesorios generales
    if any(bad in t for bad in [
        "CLIP CASE", "CASE P ", "CASE PARA", "ESTUCHE PARA", "FUNDA PARA", "COBERTOR PARA",
        "PROTECTOR PARA", "VIDRIO TEMPLADO", "KIT 2 EN 1", "SPORT BAND", "CORREA SPORT",
        "CORREA PARA", "STRAP PARA", "BAND PARA"
    ]):
        return True

    # Si empieza directamente por una palabra de accesorio
    if any(t.startswith(prefix) for prefix in [
        "CASE ", "CLIP ", "ESTUCHE ", "FUNDA ", "COBERTOR ", "PROTECTOR ", "CORREA ", "STRAP ", "VIDRIO "
    ]):
        return True

    if cat_tipo == "Wearables":
        # Para audífonos / buds: un estuche, clip case o cover no son los audífonos
        if any(w in t for w in ["CASE", "COVER", "ESTUCHE", "FUNDA", "SILICON"]) and not any(w in t for w in ["AUDIFONO", "AUDFONO", "AURICULAR", "HEADPHONE", "TWS", "IN EAR"]):
            return True
        if any(w in t for w in ["CORREA", "STRAP PARA", "SPORT BAND", "BAND PARA"]):
            return True

    if cat_tipo == "Tablets":
        if any(w in t for w in ["SMART BOOK COVER PARA", "BOOK COVER PARA", "FRAME COVER PARA", "TECLADO PRO PARA", "TECLADO PARA"]):
            return True
        if re.search(r"\b(?:COVER|ESTUCHE|FUNDA|TECLADO)\s+PARA\b", t):
            return True

    if cat_tipo == "Smartphones":
        if any(w in t for w in ["COBERTOR", "ESTUCHE", "FUNDA", "SILICN", "SILICON", "CLEAR CASE", "FLIPWALLET", "RING MAGNET"]):
            return True

    return False

def load_retailer_csv(path: Path, nombre_col, precio_cols):
    if not path.exists():
        return []
    df = pd.read_csv(path, dtype=str).fillna("")
    items = []
    for _, row in df.iterrows():
        nombre = row.get(nombre_col, "").strip()
        if not nombre:
            continue
        if es_telefono_operador(nombre) or es_otra_marca(nombre):
            continue
        precio = None
        for col in precio_cols:
            precio = parse_price(row.get(col, ""))
            if precio is not None:
                break
        url = row.get("url", "").strip() if "url" in row else ""
        mod = extract_model(nombre)
        cat_tipo = get_categoria(mod, nombre)
        if es_accesorio(nombre, cat_tipo):
            continue
        items.append({
            "nombre": nombre,
            "modelo": mod,
            "mem": extract_memory(nombre),
            "color": extract_color(nombre),
            "precio": precio,
            "url": url,
            "categoria": cat_tipo,
            "conectividad": extract_connectivity(nombre),
            "size_mm": extract_size_mm(nombre),
            "sm_code": extract_sm_code(nombre),
        })
    return items


def mem_match_score(cat, it):
    cat_tipo = cat.get("categoria", "Smartphones")
    it_tipo = it.get("categoria", "Smartphones")
    
    # Si las categorías son estrictamente diferentes, no deben emparejarse
    if cat_tipo != it_tipo:
        return 0

    if cat_tipo == "Wearables":
        sm_c = cat.get("sm_code")
        sm_it = it.get("sm_code")
        if sm_c and sm_it:
            if sm_c == sm_it:
                return 150
            return 0
        
        size_c = cat.get("size_mm")
        size_it = it.get("size_mm")
        if size_c and size_it:
            if size_c == size_it:
                return 120
            return 0
        return 80

    if cat_tipo == "Tablets":
        conn_c = cat.get("conectividad")
        conn_it = it.get("conectividad")
        if conn_c and conn_it and conn_c != conn_it:
            return 0
        
        mem_cat = cat.get("mem", (None, None))
        mem_it = it.get("mem", (None, None))
        rom_cat = mem_cat[1] if mem_cat else None
        rom_it = mem_it[1] if mem_it else None
        
        if rom_cat and rom_it:
            if rom_cat != rom_it:
                return 0
            if conn_c and conn_it and conn_c == conn_it:
                return 100
            return 85
        return 70

    # Smartphones:
    mem_cat = cat.get("mem", (None, None))
    mem_it = it.get("mem", (None, None))
    ram_cat, rom_cat = mem_cat
    ram_it, rom_it = mem_it

    if rom_cat is not None and rom_it is not None and rom_cat != rom_it:
        return 0

    if ram_cat is not None and ram_it is not None and rom_cat is not None and rom_it is not None:
        if ram_cat == ram_it and rom_cat == rom_it:
            return 100
        elif rom_cat == rom_it:
            return 50

    if rom_cat is not None and rom_it is not None and rom_cat == rom_it:
        return 80

    return 0

    if ram_cat is not None and ram_it is not None and rom_cat is not None and rom_it is not None:
        if ram_cat == ram_it and rom_cat == rom_it:
            return 100
        elif rom_cat == rom_it:
            return 50

    if rom_cat is not None and rom_it is not None and rom_cat == rom_it:
        return 80

    return 0


def match_retailer_items(catalogo, items):
    resultados = {}
    items_emparejados_ids = set()

    for idx, cat in enumerate(catalogo):
        if not cat["modelo"]:
            continue

        candidatos = [
            it for it in items
            if it["modelo"] == cat["modelo"] and it["precio"] is not None
        ]
        if not candidatos:
            continue

        candidatos_con_score = []
        for it in candidatos:
            score = mem_match_score(cat, it)
            if score > 0:
                candidatos_con_score.append((score, it))

        if not candidatos_con_score:
            modelos_iguales_en_cat = sum(1 for c in catalogo if c["modelo"] == cat["modelo"])
            if modelos_iguales_en_cat == 1 and cat["mem"][1] is None:
                candidatos_con_score = [(10, it) for it in candidatos]

        if not candidatos_con_score:
            continue

        candidatos_con_score.sort(key=lambda x: (-x[0], x[1]["precio"]))

        mejor_score, mejor_item = candidatos_con_score[0]
        resultados[idx] = mejor_item
        items_emparejados_ids.add(id(mejor_item))

        for sc, it in candidatos_con_score:
            if sc == mejor_score:
                items_emparejados_ids.add(id(it))

    return resultados, items_emparejados_ids


def evaluar_precio(precio_retailer, base, tolerancia_pct=CONFIG_DEFAULT_TOLERANCIA_PCT):
    """
    Compara el precio del retailer contra la base de referencia (Mi Precio o MSRP).
    - tolerancia_pct: Porcentaje máximo de descuento permitido sobre la base (ej. 5.0%).
    - Si diff_pct < -tolerancia_pct (ej. -5.1% o -10%), el descuento supera la regla -> 'menor' (Alerta / Desfasado).
    - Si diff_pct >= -tolerancia_pct (ej. -3.0% o 0% o mayor), está dentro de la regla -> 'ok'.
    """
    if precio_retailer is None:
        return "sin_dato", None
    if base is None:
        return "sin_base", None
        
    diff_pct = (precio_retailer - base) / base * 100
    tol = abs(float(tolerancia_pct))
    
    if diff_pct < -tol:
        return "menor", diff_pct
    return "ok", diff_pct


PAISES_CONFIG = {
    "gt": {
        "nombre": "Guatemala",
        "moneda": "Q",
        "moneda_codigo": "GTQ",
        "bandera": "🇬🇹",
        "rrp_col": "RRP_GT",
        "msrp_col": "MSRP_GT",
        "mis_precios_file": "mis_precios.csv",
        "retailers": {
            "elektra": {"nombre": "Elektra", "csv": "productos_elektra.csv", "name_col": "nombre", "price_cols": ["precio_venta", "precio_lista", "precio", "precio_num"]},
            "max": {"nombre": "MAX", "csv": "productos_max.csv", "name_col": "nombre", "price_cols": ["precio", "precio_num"]},
            "gallo": {"nombre": "El Gallo más Gallo", "csv": "productos_elgallomasgallo.csv", "name_col": "nombre", "price_cols": ["precio_venta", "precio_lista", "precio", "precio_num"]},
            "walmart": {"nombre": "Walmart", "csv": "productos_walmart_gt.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio", "precio_venta"]},
        }
    },
    "sv": {
        "nombre": "El Salvador",
        "moneda": "$",
        "moneda_codigo": "USD",
        "bandera": "🇸🇻",
        "rrp_col": "RRP_SV",
        "msrp_col": "MSRP_SV",
        "mis_precios_file": "mis_precios_sv.csv",
        "retailers": {
            "siman": {"nombre": "Siman", "csv": "productos_siman.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio"]},
            "curacao_sv": {"nombre": "La Curacao", "csv": "productos_curacao_sv.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio"]},
            "prado": {"nombre": "Prado", "csv": "productos_prado.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio"]},
            "walmart_sv": {"nombre": "Walmart", "csv": "productos_walmart_sv.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio", "precio_venta"]},
        }
    },
    "hn": {
        "nombre": "Honduras",
        "moneda": "L",
        "moneda_codigo": "HNL",
        "bandera": "🇭🇳",
        "rrp_col": "RRP_HN",
        "msrp_col": "MSRP_HN",
        "mis_precios_file": "mis_precios_hn.csv",
        "retailers": {
            "jetstereo": {"nombre": "Jetstereo", "csv": "productos_jetstereo.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio"]},
            "elektra_hn": {"nombre": "Elektra HN", "csv": "productos_elektra_hn.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio"]},
            "diunsa": {"nombre": "Diunsa", "csv": "productos_diunsa.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio"]},
            "walmart_hn": {"nombre": "Walmart", "csv": "productos_walmart_hn.csv", "name_col": "nombre", "price_cols": ["precio_num", "precio", "precio_venta"]},
        }
    }
}


def build_report(data_dir: Path, tolerancia_pct: float = None, pais: str = "gt"):
    if tolerancia_pct is None:
        tolerancia_pct = load_config(data_dir)
    tolerancia_pct = round(float(tolerancia_pct), 2)
    
    cfg = PAISES_CONFIG.get(pais, PAISES_CONFIG["gt"])
    catalogo = load_catalogo(data_dir, pais=pais)
    mis_precios = load_mis_precios(data_dir, pais=pais)

    if not catalogo:
        return {
            "filas": [], "resumen": {}, "sin_coincidencia": {},
            "catalogo_vacio": True, "pais": pais, "moneda": cfg["moneda"]
        }

    retailers_dict = cfg["retailers"]
    ret_items = {}
    ret_matches = {}
    ret_usados = {}

    for r_key, r_info in retailers_dict.items():
        csv_file = data_dir / r_info["csv"]
        items = load_retailer_csv(csv_file, r_info["name_col"], r_info["price_cols"])
        matches, usados = match_retailer_items(catalogo, items)
        ret_items[r_key] = items
        ret_matches[r_key] = matches
        ret_usados[r_key] = usados

    filas = []
    alertas = []
    alertas_vistas = set()
    total_evaluado = 0
    total_alineado = 0

    for idx, cat in enumerate(catalogo):
        key = (cat["mobile"], cat["memoria"])
        mi_precio_editado = mis_precios.get(key)
        mi_precio_base = mi_precio_editado if mi_precio_editado is not None else cat["msrp"]

        fila = {
            "mobile": cat["mobile"],
            "memoria": cat["memoria"],
            "categoria": cat.get("categoria", "Smartphones"),
            "rrp": cat["rrp"],
            "rrp_raw": cat["rrp_raw"],
            "msrp": cat["msrp"],
            "msrp_raw": cat["msrp_raw"],
            "mi_precio": mi_precio_base,
            "mi_precio_personalizado": mi_precio_editado is not None,
        }

        for r_key, r_info in retailers_dict.items():
            matched = ret_matches[r_key].get(idx, {})
            precio = matched.get("precio")
            nombre_ret = matched.get("nombre")
            color_ret = matched.get("color")

            estado, diff_pct = evaluar_precio(precio, mi_precio_base, tolerancia_pct=tolerancia_pct)
            fila[r_key] = precio
            fila[f"{r_key}_estado"] = estado
            fila[f"{r_key}_diff_pct"] = diff_pct
            fila[f"{r_key}_nombre"] = nombre_ret
            fila[f"{r_key}_color"] = color_ret
            fila[f"{r_key}_url"] = matched.get("url", "")

            if estado in ("ok", "menor"):
                total_evaluado += 1
                if estado == "ok":
                    total_alineado += 1
                else:
                    alert_key = (r_key, cat["mobile"].strip().upper(), str(cat["memoria"]).strip().upper())
                    if alert_key not in alertas_vistas:
                        alertas_vistas.add(alert_key)
                        alertas.append({
                            "retailer": r_info["nombre"],
                            "retailer_key": r_key,
                            "mobile": cat["mobile"],
                            "memoria": cat["memoria"],
                            "precio_retailer": precio,
                            "base": mi_precio_base,
                            "diff_pct": diff_pct,
                            "color": color_ret,
                        })

        filas.append(fila)

    alertas.sort(key=lambda a: abs(a["diff_pct"]), reverse=True)

    faltantes = []
    for idx, cat in enumerate(catalogo):
        for r_key, r_info in retailers_dict.items():
            if idx not in ret_matches[r_key]:
                faltantes.append({
                    "retailer": r_info["nombre"],
                    "retailer_key": r_key,
                    "mobile": cat["mobile"],
                    "memoria": cat["memoria"],
                })

    pct_ok = round((total_alineado / total_evaluado) * 100) if total_evaluado else None

    resumen = {
        "pct_ok": pct_ok,
        "total_evaluado": total_evaluado,
        "total_ok": total_alineado,
        "alertas": alertas,
        "faltantes": faltantes,
        "tolerancia_pct": tolerancia_pct,
    }

    sin_coincidencia = {}
    for r_key in retailers_dict:
        sin_coincidencia[r_key] = [
            it["nombre"] for it in ret_items[r_key]
            if id(it) not in ret_usados[r_key]
        ]

    return {
        "filas": filas,
        "resumen": resumen,
        "sin_coincidencia": sin_coincidencia,
        "catalogo_vacio": len(catalogo) == 0,
        "pais": pais,
        "pais_nombre": cfg["nombre"],
        "bandera": cfg["bandera"],
        "moneda": cfg["moneda"],
        "moneda_codigo": cfg["moneda_codigo"],
        "retailers": {k: v["nombre"] for k, v in retailers_dict.items()},
        "paises_disponibles": {k: {"nombre": v["nombre"], "bandera": v["bandera"], "moneda": v["moneda"]} for k, v in PAISES_CONFIG.items()}
    }

# Reporte de Precios — Samsung Galaxy

Reporte local en HTML que compara, para cada modelo Samsung Galaxy:

- **Precio de mercado (MSRP)** — de `data/precios_mercado.csv`
- **Mi precio** — editable directamente en el reporte
- **Elektra, MAX y Gallo más Gallo** — obtenidos corriendo tus scripts de Selenium con un clic

Corre 100% en tu computadora (no en la nube), porque los scripts de Elektra/MAX/Gallo necesitan abrir Chrome de verdad.

## 1. Instalación (una sola vez)

Necesitas Python 3.9+ y Google Chrome instalado.

```bash
cd reporte-precios
python -m venv venv
venv\Scripts\activate        # en Windows
# source venv/bin/activate   # en Mac/Linux

pip install -r requirements.txt
```

Selenium 4.6+ descarga el driver de Chrome automáticamente, no necesitas instalar ChromeDriver a mano.

## 2. Correr el reporte

```bash
python app.py
```

Abre en tu navegador: **http://localhost:5000**

Deja esa ventana de la terminal abierta mientras usas el reporte (ahí corre el servidor).

## 3. Cómo usarlo

- **Botón "Actualizar" por retailer** (Elektra / MAX / Gallo más Gallo): corre el script real de Selenium para ese sitio. Abrirá una ventana de Chrome, navegará, scrapeará los productos y guardará el CSV en `data/`. Puede tardar 1-3 minutos por sitio, dependiendo del sitio. No cierres la ventana de Chrome que se abre.
- **Botón "Actualizar todos"**: corre los tres, uno por uno.
- **Columna "Mi Precio"**: escríbela directamente en la tabla y presiona **"Guardar mis precios"**. Se guarda en `data/mis_precios.csv` y no se pierde al cerrar el navegador.
- **Colores**: si el precio de un retailer es **menor** que tu precio, la celda se marca en rojo (alerta, te están vendiendo más barato). Si es **mayor**, se marca en verde.
- **"Productos que no se pudieron emparejar"**: al final del reporte hay una sección desplegable que lista los productos que cada script encontró pero que no se pudieron relacionar automáticamente con ningún modelo del catálogo (por ejemplo si cambia el nombre en la web, o es un modelo que no está en `precios_mercado.csv`).

## 4. Archivos importantes

```
reporte-precios/
├── app.py                     servidor local (Flask)
├── matching.py                lógica que empareja productos por modelo/memoria
├── requirements.txt
├── templates/index.html       el reporte (interfaz)
├── scripts/
│   ├── elektra.py
│   ├── max.py
│   └── gallo.py
└── data/
    ├── precios_mercado.csv    catálogo de referencia (MOBILE, Memoria, RRP, MSRP)
    ├── mis_precios.csv        tus precios (se edita desde el reporte)
    ├── productos_elektra.csv  se genera al presionar "Actualizar" (Elektra)
    ├── productos_max.csv      se genera al presionar "Actualizar" (MAX)
    └── productos_elgallomasgallo.csv  se genera al presionar "Actualizar" (Gallo más Gallo)
```

## 5. Agregar o quitar modelos del catálogo

Edita `data/precios_mercado.csv` con Excel o cualquier editor de texto (columnas `MOBILE`, `Memoria`, `RRP`, `MSRP`). Al reiniciar `python app.py` (o recargar la página), el reporte y `mis_precios.csv` se ajustan solos a los modelos que tenga ese archivo.

## 6. Cómo funciona el emparejamiento automático

Los nombres de producto vienen distintos en cada tienda (ej. "Samsung Galaxy A16 128GB Negro" en Elektra vs "Galaxy A16 4/128GB" en MAX). `matching.py` extrae de cada nombre el modelo (A16, S25 Ultra, Z Fold8, etc.) y la memoria (RAM+almacenamiento) con expresiones regulares, y los compara contra tu catálogo. Si un producto no se puede identificar con confianza, no se le asigna precio y aparece en la sección "sin emparejar" para que lo revises a mano.

## 7. Notas

- Los sitios web pueden cambiar su diseño (HTML/CSS) en cualquier momento, lo que puede romper los selectores de los scripts. Si un script deja de encontrar productos, hay que revisar los `By.CSS_SELECTOR` dentro de `scripts/<retailer>.py` y ajustarlos a como esté la página en ese momento.
- El servidor (`app.py`) corre en modo desarrollo (`debug=True`), pensado para uso local. No lo expongas a internet tal cual.

## 8. Scraping Automático Programado (Sin abrir el navegador)

Se ha configurado un sistema para que los precios se actualicen solos en segundo plano mediante el Programador de Tareas de Windows:

- **`actualizar_precios.py`**: Orquestador en Python que ejecuta secuencialmente Elektra, MAX y Gallo más Gallo, actualiza `data/status.json` y guarda un registro en `data/scraping_automatico.log`.
- **`ejecutar_scraping_oculto.vbs`**: Ejecuta el proceso de forma invisible con `pythonw` para no mostrar ventanas negras de consola.
- **`crear_tarea_programada.bat`**: Registra la tarea en Windows para ejecutarse todos los días a las **08:00 AM**.
- **`eliminar_tarea_programada.bat`**: Elimina la tarea si ya no deseas que se ejecute sola.

Para probar la tarea inmediatamente desde la consola puedes ejecutar:
```cmd
schtasks /run /tn "ReportePrecios_AutoScraping"
```

# Sistema de Ganancias ML

## Instalación (una sola vez)

1. Tener Python instalado (https://www.python.org/downloads/)
2. Abrir terminal y ejecutar:

```
pip install streamlit pandas openpyxl
```

## Cómo usar cada semana

1. Abrir terminal en esta carpeta
2. Ejecutar:

```
streamlit run app.py
```

3. Se abre en el navegador automáticamente

## Archivos que necesitás subir

**Reporte ML:** El xlsx que descargás de Mercado Libre > Ventas > Reportes

**costos.xlsx:** Vos lo mantenés. Dos columnas obligatorias:
- Columna A: ID de publicación (ej: MLA1785923271)
- Columna C: Tu costo en ARS (ej: 8000)
- Columna C: Nombre del producto (solo referencia, no lo usa el sistema)

Ver costos_template.xlsx como ejemplo.

## Flujo semanal

1. Subís los 2 archivos
2. Revisás las devoluciones — si alguna fue por tu culpa, ingresás el costo del envío de vuelta
3. Verificás el resultado neto
4. Hacés clic en "Guardar semana" para acumularlo al mes

## Cómo encontrar el ID de publicación en ML

Entrá a tu publicación en ML > la URL dice algo como mercadolibre.com.ar/MLA-1785923271-...
El ID es MLA1785923271 (sin guión)

## Actualizar precios de zonas Flex

Si ML cambia los precios, avisale a Claude y actualiza las 4 líneas de ZONAS_FLEX en app.py

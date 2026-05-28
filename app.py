import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="Ganancias ML", page_icon="📦", layout="wide")

# Zona -> (costo_logistica, bonif_menos_30k, bonif_mas_30k)
ZONAS = {
    "vicente lopez":         (4670, 6490, 649),
    "vicente lópez":         (4670, 6490, 649),
    "tres de febrero":       (4670, 6490, 649),
    "tigre":                 (5860, 8490, 849),
    "san miguel":            (5860, 8490, 849),
    "san martin":            (4670, 6490, 649),
    "san martín":            (4670, 6490, 649),
    "san isidro":            (4670, 6490, 649),
    "san fernando":          (4670, 6490, 649),
    "quilmes":               (5860, 8490, 849),
    "moron":                 (4670, 6490, 649),
    "morón":                 (4670, 6490, 649),
    "moreno":                (5860, 8490, 849),
    "merlo":                 (5860, 8490, 849),
    "malvinas argentinas":   (5860, 8490, 849),
    "lomas de zamora":       (4670, 6490, 649),
    "lanus":                 (4670, 6490, 649),
    "lanús":                 (4670, 6490, 649),
    "la matanza sur":        (5860, 8490, 849),
    "la matanza norte":      (4670, 6490, 649),
    "la matanza":            (4670, 6490, 649),
    "jose c paz":            (5860, 8490, 849),
    "josé c paz":            (5860, 8490, 849),
    "ituzaingo":             (4670, 6490, 649),
    "ituzaingó":             (4670, 6490, 649),
    "hurlingham":            (4670, 6490, 649),
    "florencio varela":      (5860, 8490, 849),
    "ezeiza":                (5860, 8490, 849),
    "esteban echeverria":    (5860, 8490, 849),
    "esteban echeverría":    (5860, 8490, 849),
    "berazategui":           (5860, 8490, 849),
    "avellaneda":            (4670, 6490, 649),
    "almirante brown":       (5860, 8490, 849),
}

LOCALIDAD_A_PARTIDO = {
    "general san martin": "san martin", "general san martín": "san martin",
    "caseros": "tres de febrero", "loma hermosa": "tres de febrero",
    "villa adelina": "san isidro", "boulogne": "san isidro",
    "san andres": "san isidro", "san andrés": "san isidro",
    "olivos": "vicente lopez", "florida": "vicente lopez",
    "florida oeste": "vicente lopez", "munro": "vicente lopez",
    "carapachay": "vicente lopez",
    "villa ballester": "san martin", "billinghurst": "san martin",
    "los polvorines": "malvinas argentinas",
    "temperley": "lomas de zamora", "remedios de escalada": "lomas de zamora",
    "monte chingolo": "lomas de zamora",
    "lanus oeste": "lanus", "lanús oeste": "lanus",
    "lanus este": "lanus", "lanús este": "lanus",
    "valentin alsina": "lanus",
    "bernal oeste": "quilmes", "bosques": "quilmes",
    "wilde": "avellaneda", "dock sud": "avellaneda",
    "sarandi": "avellaneda", "sarandí": "avellaneda",
    "benavidez": "tigre", "benavídez": "tigre",
    "rincon de milberg": "tigre", "rincón de milberg": "tigre",
    "virreyes": "san fernando",
    "bella vista": "san miguel", "bella vista": "san miguel",
    "castelar": "moron", "ramos mejia": "la matanza",
    "lomas del mirador": "la matanza", "lomas del mirador": "la matanza",
    "gregorio de laferrere": "la matanza", "gonzález catán": "la matanza",
    "gonzalez catan": "la matanza", "san justo": "la matanza",
    "villa luzuriaga": "la matanza",
}

# Estados que SÍ implican pérdida real (ya despachaste)
ESTADOS_PERDIDA = [
    "devolución finalizada",
    "devolución finalizada con reembolso",
    "cancelada. tu transportista",
    "reclamo cerrado con reembolso",
]

# Estados que NO implican pérdida (nunca salió)
ESTADOS_SIN_PERDIDA = [
    "cancelada por el comprador",
    "paquete cancelado por mercado libre",
]

ACUMULADO_FILE = "acumulado.json"
UMBRAL_ENVIO_GRATIS = 29999

def normalizar(texto):
    if not texto:
        return ""
    return str(texto).strip().lower()

def get_zona(ciudad, provincia):
    prov = normalizar(provincia)
    ciudad_n = normalizar(ciudad)
    if "capital federal" in prov or "caba" in prov:
        return "CABA", (3100, 4490, 449)
    if ciudad_n in ZONAS:
        return ciudad_n.title(), ZONAS[ciudad_n]
    if ciudad_n in LOCALIDAD_A_PARTIDO:
        partido = LOCALIDAD_A_PARTIDO[ciudad_n]
        if partido in ZONAS:
            return f"{ciudad} ({partido.title()})", ZONAS[partido]
    for zona_key, vals in ZONAS.items():
        if zona_key in ciudad_n or ciudad_n in zona_key:
            return f"{ciudad} ({zona_key.title()})", vals
    return None, None

def cargar_acumulado():
    if os.path.exists(ACUMULADO_FILE):
        with open(ACUMULADO_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_acumulado(data):
    with open(ACUMULADO_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def safe_float(val, default=0.0):
    try:
        v = float(val)
        return v if not pd.isna(v) else default
    except:
        return default

def procesar_reporte(df_ml, df_costos):
    costos_dict = {}
    for _, row in df_costos.iterrows():
        id_pub = str(row.iloc[0]).strip()
        costo  = safe_float(row.iloc[1])
        costos_dict[id_pub] = costo

    ventas = []
    devoluciones = []
    sin_costo = []

    for _, row in df_ml.iterrows():
        estado   = normalizar(str(row.get("Estado", "")))
        if not estado or estado == "nan":
            continue

        id_pub    = str(row.get("# de publicación", "")).strip()
        titulo    = str(row.get("Título de la publicación", "")).strip()
        forma     = str(row.get("Forma de entrega", "")).strip()
        ciudad    = str(row.get("Ciudad", "")).strip()
        provincia = str(row.get("Estado.1", "")).strip()
        total_ml  = safe_float(row.get("Total (ARS)"))
        anulacion = safe_float(row.get("Anulaciones y reembolsos (ARS)"))
        ingresos  = safe_float(row.get("Ingresos por productos (ARS)"))
        descuentos= safe_float(row.get("Descuentos y bonificaciones"))
        unidades  = max(1, int(safe_float(row.get("Unidades"), 1)))
        fecha     = str(row.get("Fecha de venta", "")).strip()

        es_flex    = "flex"    in normalizar(forma)
        es_acuerdo = "acuerdo" in normalizar(forma)

        # Clasificar estado
        es_sin_perdida = any(c in estado for c in ESTADOS_SIN_PERDIDA)
        es_con_perdida = any(c in estado for c in ESTADOS_PERDIDA)
        es_cancelada   = es_sin_perdida or es_con_perdida

        # Paquete sin ID
        es_paquete = (id_pub == "" or id_pub == "nan")

        costo_producto = costos_dict.get(id_pub) if not es_paquete else None
        if costo_producto is None and not es_cancelada:
            label = "(paquete sin ID)" if es_paquete else id_pub
            sin_costo.append({"ID publicación": label, "Título": titulo[:60], "Unidades": unidades})

        costo_logistica = 0
        bonif_esperada  = 0
        zona_nombre     = "-"
        zona_sin_precio = False

        if es_flex and not es_cancelada:
            zona_nombre, zona_vals = get_zona(ciudad, provincia)
            if zona_vals is None:
                zona_sin_precio = True
                zona_nombre = f"{ciudad} / {provincia}"
            else:
                costo_logistica = zona_vals[0]
                bonif_esperada  = zona_vals[2] if ingresos > UMBRAL_ENVIO_GRATIS else zona_vals[1]

        if es_acuerdo and total_ml == 0:
            total_ml = ingresos

        if es_cancelada:
            # Solo mostrar/contar pérdida si realmente despachaste
            perdida = anulacion if es_con_perdida else 0.0
            devoluciones.append({
                "fecha": fecha, "id_pub": id_pub, "titulo": titulo[:50],
                "estado": str(row.get("Estado", "")),
                "es_con_perdida": es_con_perdida,
                "total_original": ingresos, "anulacion": anulacion,
                "costo_envio_vuelta": 0.0, "perdida_total": perdida,
                "es_flex": es_flex, "zona": zona_nombre,
            })
        else:
            # Multiplicar costo producto por unidades
            costo_prod_total = (costo_producto or 0) * unidades
            ganancia_neta    = total_ml - costo_logistica - costo_prod_total
            ventas.append({
                "fecha": fecha, "id_pub": id_pub, "titulo": titulo[:50],
                "estado": str(row.get("Estado", "")),
                "forma_entrega": forma, "ciudad": ciudad,
                "zona_nombre": zona_nombre, "zona_sin_precio": zona_sin_precio,
                "unidades": unidades,
                "ingresos_ml": ingresos, "bonif_ml": descuentos,
                "bonif_esperada": bonif_esperada,
                "total_ml": total_ml,
                "costo_producto_unit": costo_producto or 0,
                "costo_producto": costo_prod_total,
                "costo_logistica": costo_logistica,
                "ganancia_neta": ganancia_neta,
                "sin_costo": costo_producto is None,
                "es_flex": es_flex, "es_acuerdo": es_acuerdo,
                "es_paquete": es_paquete,
            })

    return ventas, devoluciones, sin_costo

def fmt(valor):
    if valor is None: return "-"
    try:
        if pd.isna(valor): return "-"
    except: pass
    signo = "-" if valor < 0 else ""
    return f"{signo}${abs(valor):,.0f}".replace(",", ".")

# ─── UI ───────────────────────────────────────────────────────────────────────
st.title("📦 Ganancias Mercado Libre")
tab1, tab2, tab3 = st.tabs(["📂 Procesar semana", "📅 Acumulado mensual", "⚙️ Zonas Flex"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        archivo_ml = st.file_uploader("Reporte ML (.xlsx)", type=["xlsx"], key="ml")
    with col2:
        archivo_costos = st.file_uploader("Costos de productos (.xlsx)", type=["xlsx"], key="costos")
        st.caption("Columna A: ID publicación | Columna B: Tu costo unitario")

    if archivo_ml and archivo_costos:
        with st.spinner("Procesando..."):
            df_ml     = pd.read_excel(archivo_ml, sheet_name="Ventas AR", header=5)
            df_costos = pd.read_excel(archivo_costos, header=0)
            ventas, devoluciones, sin_costo = procesar_reporte(df_ml, df_costos)

        if sin_costo:
            sc_unicos = list({v["ID publicación"]: v for v in sin_costo}.values())
            st.warning(f"⚠️ {len(sc_unicos)} producto(s) sin costo — esas ventas no se incluyen en el total")
            with st.expander("Ver productos sin costo"):
                st.dataframe(pd.DataFrame(sc_unicos), use_container_width=True, hide_index=True)

        zonas_faltantes = list(set(v["zona_nombre"] for v in ventas if v.get("zona_sin_precio")))
        if zonas_faltantes:
            st.warning(f"⚠️ Zonas Flex sin precio: {', '.join(zonas_faltantes)}")

        # ── Cancelaciones / Devoluciones ──────────────────────────────────────
        dev_con_perdida  = [d for d in devoluciones if d["es_con_perdida"]]
        dev_sin_perdida  = [d for d in devoluciones if not d["es_con_perdida"]]

        if dev_sin_perdida:
            st.info(f"ℹ️ {len(dev_sin_perdida)} cancelación(es) sin pérdida — el producto nunca salió")
            with st.expander("Ver cancelaciones sin pérdida"):
                st.dataframe(pd.DataFrame([{
                    "Título": d["titulo"], "Estado": d["estado"], "Fecha": d["fecha"][:20]
                } for d in dev_sin_perdida]), use_container_width=True, hide_index=True)

        st.subheader("Devoluciones con pérdida")
        if dev_con_perdida:
            st.caption("El producto ya había salido. Si fue por tu culpa, ingresá el costo del envío de vuelta.")
            for i, d in enumerate(devoluciones):
                if not d["es_con_perdida"]:
                    continue
                with st.expander(f"🔴 {d['titulo']} — {d['estado']}", expanded=False):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.write(f"**Fecha:** {d['fecha'][:20]}")
                    c2.write(f"**Anulación ML:** {fmt(d['anulacion'])}")
                    c3.write(f"**Zona:** {d['zona']}")
                    envio_vuelta = c4.number_input(
                        "Envío de vuelta", min_value=0.0, value=0.0,
                        step=100.0, key=f"dev_{i}"
                    )
                    perdida = d["anulacion"] - envio_vuelta
                    st.write(f"**Pérdida total: {fmt(perdida)}**")
                    devoluciones[i]["costo_envio_vuelta"] = envio_vuelta
                    devoluciones[i]["perdida_total"]      = perdida
        else:
            st.success("Sin devoluciones con pérdida esta semana ✅")

        total_perdido_dev = sum(d["perdida_total"] for d in devoluciones)

        # ── Ventas ────────────────────────────────────────────────────────────
        st.subheader("Ventas de la semana")
        ventas_ok = [v for v in ventas if not v["sin_costo"]]
        ventas_sc = [v for v in ventas if v["sin_costo"]]

        if ventas_ok:
            df_show = pd.DataFrame([{
                "Título":           v["titulo"],
                "Uds":              v["unidades"],
                "Envío":            "Flex" if v["es_flex"] else ("Acuerdo" if v["es_acuerdo"] else "Correo"),
                "Zona":             v["zona_nombre"],
                "Total ML":         fmt(v["total_ml"]),
                "Costo producto":   fmt(v["costo_producto"]),
                "Costo logística":  fmt(v["costo_logistica"]),
                "Ganancia neta":    fmt(v["ganancia_neta"]),
            } for v in ventas_ok])
            st.dataframe(df_show, use_container_width=True, hide_index=True)

        if ventas_sc:
            with st.expander(f"⚠️ {len(ventas_sc)} ventas sin costo (no incluidas)"):
                st.dataframe(pd.DataFrame([{
                    "Título": v["titulo"], "ID": v["id_pub"],
                    "Uds": v["unidades"], "Total ML": fmt(v["total_ml"])
                } for v in ventas_sc]), use_container_width=True, hide_index=True)

        # ── Resumen ───────────────────────────────────────────────────────────
        ganancia_semana  = sum(v["ganancia_neta"] for v in ventas_ok)
        resultado_semana = ganancia_semana + total_perdido_dev

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ventas procesadas",     len(ventas_ok))
        c2.metric("Ingresos ML totales",   fmt(sum(v["total_ml"]        for v in ventas_ok)))
        c3.metric("Costo logística total", fmt(sum(v["costo_logistica"] for v in ventas_ok)))
        c4.metric("Costo productos total", fmt(sum(v["costo_producto"]  for v in ventas_ok)))

        st.metric("🟢 Ganancia neta de la semana", fmt(resultado_semana),
                  delta=f"Devoluciones con pérdida: {fmt(total_perdido_dev)}" if dev_con_perdida else None,
                  delta_color="normal" if resultado_semana >= 0 else "inverse")

        # ── Guardar ───────────────────────────────────────────────────────────
        st.divider()
        mes_label    = datetime.now().strftime("%Y-%m")
        semana_label = f"Semana del {datetime.now().strftime('%d/%m/%Y')}"

        if st.button("💾 Guardar semana en acumulado mensual", type="primary"):
            acumulado = cargar_acumulado()
            if mes_label not in acumulado:
                acumulado[mes_label] = {"semanas": [], "total_ganancia": 0, "total_devoluciones": 0}
            acumulado[mes_label]["semanas"].append({
                "label": semana_label, "ganancia_neta": ganancia_semana,
                "perdida_devoluciones": total_perdido_dev,
                "resultado": resultado_semana, "ventas": len(ventas_ok),
            })
            acumulado[mes_label]["total_ganancia"]     = sum(s["ganancia_neta"]        for s in acumulado[mes_label]["semanas"])
            acumulado[mes_label]["total_devoluciones"] = sum(s["perdida_devoluciones"] for s in acumulado[mes_label]["semanas"])
            guardar_acumulado(acumulado)
            st.success(f"✅ Guardado. Acumulado de {mes_label} actualizado.")

with tab2:
    acumulado = cargar_acumulado()
    if not acumulado:
        st.info("Todavía no hay semanas guardadas. Procesá tu primer reporte y hacé clic en 'Guardar semana'.")
    else:
        meses   = sorted(acumulado.keys(), reverse=True)
        mes_sel = st.selectbox("Mes", meses)
        data    = acumulado[mes_sel]

        st.subheader(f"Resumen de {mes_sel}")
        c1, c2, c3 = st.columns(3)
        resultado_mes = data["total_ganancia"] + data["total_devoluciones"]
        c1.metric("Ganancia neta acumulada",  fmt(data["total_ganancia"]))
        c2.metric("Pérdida por devoluciones", fmt(data["total_devoluciones"]))
        c3.metric("Resultado neto del mes",   fmt(resultado_mes))

        st.subheader("Semanas")
        st.dataframe(pd.DataFrame([{
            "Semana":        s["label"],
            "Ventas":        s["ventas"],
            "Ganancia neta": fmt(s["ganancia_neta"]),
            "Devoluciones":  fmt(s["perdida_devoluciones"]),
            "Resultado":     fmt(s["resultado"]),
        } for s in data["semanas"]]), use_container_width=True, hide_index=True)

        if st.button("🗑️ Borrar mes", type="secondary"):
            del acumulado[mes_sel]
            guardar_acumulado(acumulado)
            st.rerun()

with tab3:
    st.subheader("Costos logísticos por zona")
    st.caption("Tu costo al transportista + bonificación de ML según precio del producto.")
    vistos = set()
    rows_zonas = []
    for k, v in sorted(ZONAS.items(), key=lambda x: x[1][0]):
        if v not in vistos:
            vistos.add(v)
            rows_zonas.append({
                "Costo logístico":    fmt(v[0]),
                "Bonif ML (<$30k)":   fmt(v[1]),
                "Bonif ML (>$30k)":   fmt(v[2]),
            })
    st.dataframe(pd.DataFrame(rows_zonas), use_container_width=True, hide_index=True)

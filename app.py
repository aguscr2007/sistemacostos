import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="Ganancias ML", page_icon="📦", layout="wide")

ZONAS = {
    "vicente lopez": (4670, 6490, 649), "vicente lópez": (4670, 6490, 649),
    "tres de febrero": (4670, 6490, 649), "tigre": (5860, 8490, 849),
    "san miguel": (5860, 8490, 849), "san martin": (4670, 6490, 649),
    "san martín": (4670, 6490, 649), "san isidro": (4670, 6490, 649),
    "san fernando": (4670, 6490, 649), "quilmes": (5860, 8490, 849),
    "moron": (4670, 6490, 649), "morón": (4670, 6490, 649),
    "moreno": (5860, 8490, 849), "merlo": (5860, 8490, 849),
    "malvinas argentinas": (5860, 8490, 849), "lomas de zamora": (4670, 6490, 649),
    "lanus": (4670, 6490, 649), "lanús": (4670, 6490, 649),
    "la matanza sur": (5860, 8490, 849), "la matanza norte": (4670, 6490, 649),
    "la matanza": (4670, 6490, 649), "jose c paz": (5860, 8490, 849),
    "josé c paz": (5860, 8490, 849), "ituzaingo": (4670, 6490, 649),
    "ituzaingó": (4670, 6490, 649), "hurlingham": (4670, 6490, 649),
    "florencio varela": (5860, 8490, 849), "ezeiza": (5860, 8490, 849),
    "esteban echeverria": (5860, 8490, 849), "esteban echeverría": (5860, 8490, 849),
    "berazategui": (5860, 8490, 849), "avellaneda": (4670, 6490, 649),
    "almirante brown": (5860, 8490, 849),
}

LOCALIDAD_A_PARTIDO = {
    "general san martin": "san martin", "general san martín": "san martin",
    "caseros": "tres de febrero", "loma hermosa": "tres de febrero",
    "villa adelina": "san isidro", "boulogne": "san isidro",
    "san andres": "san isidro", "san andrés": "san isidro",
    "olivos": "vicente lopez", "florida": "vicente lopez",
    "florida oeste": "vicente lopez", "munro": "vicente lopez",
    "carapachay": "vicente lopez", "villa ballester": "san martin",
    "billinghurst": "san martin", "los polvorines": "malvinas argentinas",
    "temperley": "lomas de zamora", "remedios de escalada": "lomas de zamora",
    "monte chingolo": "lomas de zamora", "lanus oeste": "lanus",
    "lanús oeste": "lanus", "lanus este": "lanus", "lanús este": "lanus",
    "valentin alsina": "lanus", "bernal oeste": "quilmes", "bosques": "quilmes",
    "wilde": "avellaneda", "dock sud": "avellaneda",
    "sarandi": "avellaneda", "sarandí": "avellaneda",
    "benavidez": "tigre", "benavídez": "tigre",
    "rincon de milberg": "tigre", "rincón de milberg": "tigre",
    "virreyes": "san fernando", "bella vista": "san miguel",
    "castelar": "moron", "ramos mejia": "la matanza",
    "lomas del mirador": "la matanza", "gregorio de laferrere": "la matanza",
    "gonzález catán": "la matanza", "gonzalez catan": "la matanza",
    "san justo": "la matanza", "villa luzuriaga": "la matanza",
}

ESTADOS_PERDIDA   = ["devolución finalizada", "cancelada. tu transportista", "reclamo cerrado con reembolso"]
ESTADOS_SIN_PERD  = ["cancelada por el comprador", "paquete cancelado por mercado libre"]
UMBRAL_ENVIO      = 29999
ACUMULADO_FILE    = "acumulado.json"

def norm(t):
    return str(t).strip().lower() if t else ""

def get_zona(ciudad, provincia):
    if "capital federal" in norm(provincia) or "caba" in norm(provincia):
        return "CABA", (3100, 4490, 449)
    cn = norm(ciudad)
    if cn in ZONAS: return ciudad.title(), ZONAS[cn]
    if cn in LOCALIDAD_A_PARTIDO:
        p = LOCALIDAD_A_PARTIDO[cn]
        if p in ZONAS: return f"{ciudad} ({p.title()})", ZONAS[p]
    for k, v in ZONAS.items():
        if k in cn or cn in k: return f"{ciudad} ({k.title()})", v
    return None, None

def safe_float(val, default=0.0):
    try:
        v = float(val)
        return v if not pd.isna(v) else default
    except: return default

def cargar_acumulado():
    if os.path.exists(ACUMULADO_FILE):
        with open(ACUMULADO_FILE) as f: return json.load(f)
    return {}

def guardar_acumulado(data):
    with open(ACUMULADO_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def fmt(v):
    if v is None: return "-"
    try:
        if pd.isna(v): return "-"
    except: pass
    s = "-" if v < 0 else ""
    return f"{s}${abs(v):,.0f}".replace(",", ".")

def procesar_reporte(df_ml, df_costos):
    costos_dict = {}
    for _, row in df_costos.iterrows():
        costos_dict[str(row.iloc[0]).strip()] = safe_float(row.iloc[1])

    # ── Pre-procesar: agrupar paquetes ────────────────────────────────────────
    # Identificar filas padre (Paquete de N productos) y sus hijos (Total NaN sin forma de entrega)
    filas = df_ml.reset_index(drop=True)
    paquete_hijos = set()  # índices de filas hijo ya procesadas

    ventas = []
    devoluciones = []
    sin_costo = []

    i = 0
    while i < len(filas):
        row = filas.iloc[i]
        estado   = norm(str(row.get("Estado", "")))
        id_pub   = str(row.get("# de publicación", "")).strip()
        titulo   = str(row.get("Título de la publicación", "")).strip()
        forma    = str(row.get("Forma de entrega", "")).strip()
        ciudad   = str(row.get("Ciudad", "")).strip()
        provincia= str(row.get("Estado.1", "")).strip()
        total_ml = safe_float(row.get("Total (ARS)"))
        ingresos = safe_float(row.get("Ingresos por productos (ARS)"))
        descuentos=safe_float(row.get("Descuentos y bonificaciones"))
        unidades = max(1, int(safe_float(row.get("Unidades"), 1)))
        fecha    = str(row.get("Fecha de venta", "")).strip()

        if not estado or estado == "nan":
            i += 1; continue

        # ── PAQUETE: fila padre ───────────────────────────────────────────────
        if "paquete de" in estado:
            # Recolectar filas hijas que siguen (Total NaN, sin forma de entrega)
            hijos = []
            j = i + 1
            while j < len(filas):
                fh = filas.iloc[j]
                total_h  = fh.get("Total (ARS)")
                forma_h  = str(fh.get("Forma de entrega", "")).strip()
                estado_h = norm(str(fh.get("Estado", "")))
                id_h     = str(fh.get("# de publicación", "")).strip()
                # Es hijo si: total NaN, sin forma de entrega, con ID
                if pd.isna(total_h) and not forma_h and id_h and id_h != "nan":
                    hijos.append(fh)
                    paquete_hijos.add(j)
                    j += 1
                else:
                    break

            # Calcular costo total del paquete sumando costos de cada hijo
            costo_pack = 0
            sin_costo_pack = False
            titulos_pack = []
            for fh in hijos:
                id_h   = str(fh.get("# de publicación", "")).strip()
                uds_h  = max(1, int(safe_float(fh.get("Unidades"), 1)))
                tit_h  = str(fh.get("Título de la publicación", "")).strip()[:40]
                titulos_pack.append(tit_h)
                c = costos_dict.get(id_h)
                if c is None:
                    sin_costo_pack = True
                    sin_costo.append({"ID publicación": id_h, "Título": tit_h, "Unidades": uds_h})
                else:
                    costo_pack += c * uds_h

            titulo_pack = " + ".join(titulos_pack) if titulos_pack else "Paquete"

            es_flex    = "flex"    in norm(forma)
            es_acuerdo = "acuerdo" in norm(forma)

            costo_log = 0; zona_nombre = "-"; zona_sin_precio = False
            if es_flex:
                zona_nombre, zona_vals = get_zona(ciudad, provincia)
                if zona_vals is None:
                    zona_sin_precio = True
                    zona_nombre = f"{ciudad} / {provincia}"
                else:
                    costo_log = zona_vals[0]

            if not sin_costo_pack:
                ganancia = total_ml - costo_log - costo_pack
                ventas.append({
                    "fecha": fecha, "id_pub": "(paquete)", "titulo": titulo_pack[:60],
                    "forma_entrega": forma, "zona_nombre": zona_nombre,
                    "zona_sin_precio": zona_sin_precio, "unidades": unidades,
                    "ingresos_ml": ingresos, "bonif_ml": descuentos,
                    "total_ml": total_ml, "costo_producto": costo_pack,
                    "costo_logistica": costo_log, "ganancia_neta": ganancia,
                    "sin_costo": False, "es_flex": es_flex, "es_acuerdo": es_acuerdo,
                })
            i = j
            continue

        # ── Saltar filas hijo ya procesadas ──────────────────────────────────
        if i in paquete_hijos:
            i += 1; continue

        # ── Saltar filas sin importe (pendientes de acreditación) ─────────────
        if total_ml == 0 and ingresos == 0 and not any(c in estado for c in ESTADOS_PERDIDA + ESTADOS_SIN_PERD):
            i += 1; continue

        es_flex    = "flex"    in norm(forma)
        es_acuerdo = "acuerdo" in norm(forma)
        es_sin_perd= any(c in estado for c in ESTADOS_SIN_PERD)
        es_con_perd= any(c in estado for c in ESTADOS_PERDIDA)
        es_cancel  = es_sin_perd or es_con_perd

        costo_prod = costos_dict.get(id_pub)
        if costo_prod is None and not es_cancel:
            sin_costo.append({"ID publicación": id_pub or "(sin ID)", "Título": titulo[:60], "Unidades": unidades})

        costo_log = 0; zona_nombre = "-"; zona_sin_precio = False
        if es_flex and not es_cancel:
            zona_nombre, zona_vals = get_zona(ciudad, provincia)
            if zona_vals is None:
                zona_sin_precio = True; zona_nombre = f"{ciudad} / {provincia}"
            else:
                costo_log = zona_vals[0]

        if es_acuerdo and total_ml == 0:
            total_ml = ingresos

        if es_cancel:
            perdida = safe_float(row.get("Anulaciones y reembolsos (ARS)")) if es_con_perd else 0.0
            devoluciones.append({
                "fecha": fecha, "id_pub": id_pub, "titulo": titulo[:50],
                "estado": str(row.get("Estado", "")), "es_con_perdida": es_con_perd,
                "anulacion": perdida, "costo_envio_vuelta": 0.0, "perdida_total": perdida,
                "es_flex": es_flex, "zona": zona_nombre,
            })
        else:
            cp = (costo_prod or 0) * unidades
            ganancia = total_ml - costo_log - cp
            ventas.append({
                "fecha": fecha, "id_pub": id_pub, "titulo": titulo[:50],
                "forma_entrega": forma, "zona_nombre": zona_nombre,
                "zona_sin_precio": zona_sin_precio, "unidades": unidades,
                "ingresos_ml": ingresos, "bonif_ml": descuentos,
                "total_ml": total_ml, "costo_producto": cp,
                "costo_logistica": costo_log, "ganancia_neta": ganancia,
                "sin_costo": costo_prod is None,
                "es_flex": es_flex, "es_acuerdo": es_acuerdo,
            })
        i += 1

    return ventas, devoluciones, sin_costo

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
            sc_u = list({v["ID publicación"]: v for v in sin_costo}.values())
            st.warning(f"⚠️ {len(sc_u)} producto(s) sin costo — esas ventas no se incluyen en el total")
            with st.expander("Ver productos sin costo"):
                st.dataframe(pd.DataFrame(sc_u), use_container_width=True, hide_index=True)

        zonas_f = list(set(v["zona_nombre"] for v in ventas if v.get("zona_sin_precio")))
        if zonas_f:
            st.warning(f"⚠️ Zonas Flex sin precio: {', '.join(zonas_f)}")

        dev_sin = [d for d in devoluciones if not d["es_con_perdida"]]
        dev_con = [d for d in devoluciones if d["es_con_perdida"]]

        if dev_sin:
            st.info(f"ℹ️ {len(dev_sin)} cancelación(es) sin pérdida — el producto nunca salió")
            with st.expander("Ver cancelaciones sin pérdida"):
                st.dataframe(pd.DataFrame([{"Título": d["titulo"], "Estado": d["estado"],
                    "Fecha": d["fecha"][:20]} for d in dev_sin]),
                    use_container_width=True, hide_index=True)

        st.subheader("Devoluciones con pérdida")
        if dev_con:
            st.caption("Si fue por tu culpa, ingresá el costo del envío de vuelta.")
            for i, d in enumerate(devoluciones):
                if not d["es_con_perdida"]: continue
                with st.expander(f"🔴 {d['titulo']} — {d['estado']}", expanded=False):
                    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
                    c1.write(f"**Fecha:** {d['fecha'][:20]}")
                    c2.write(f"**Anulación ML:** {fmt(d['anulacion'])}")
                    c3.write(f"**Zona:** {d['zona']}")
                    ev = c4.number_input("Envío de vuelta", min_value=0.0, value=0.0, step=100.0, key=f"dev_{i}")
                    devoluciones[i]["perdida_total"] = d["anulacion"] - ev
                    st.write(f"**Pérdida total: {fmt(devoluciones[i]['perdida_total'])}**")
        else:
            st.success("Sin devoluciones con pérdida esta semana ✅")

        total_dev = sum(d["perdida_total"] for d in devoluciones)

        st.subheader("Ventas de la semana")
        ventas_ok = [v for v in ventas if not v["sin_costo"]]
        ventas_sc = [v for v in ventas if v["sin_costo"]]

        if ventas_ok:
            st.dataframe(pd.DataFrame([{
                "Título": v["titulo"], "Uds": v["unidades"],
                "Envío": "Flex" if v["es_flex"] else ("Acuerdo" if v["es_acuerdo"] else "Correo"),
                "Zona": v["zona_nombre"], "Total ML": fmt(v["total_ml"]),
                "Costo producto": fmt(v["costo_producto"]),
                "Costo logística": fmt(v["costo_logistica"]),
                "Ganancia neta": fmt(v["ganancia_neta"]),
            } for v in ventas_ok]), use_container_width=True, hide_index=True)

        if ventas_sc:
            with st.expander(f"⚠️ {len(ventas_sc)} ventas sin costo (no incluidas)"):
                st.dataframe(pd.DataFrame([{"Título": v["titulo"], "ID": v["id_pub"],
                    "Uds": v["unidades"], "Total ML": fmt(v["total_ml"])}
                    for v in ventas_sc]), use_container_width=True, hide_index=True)

        ganancia = sum(v["ganancia_neta"] for v in ventas_ok)
        resultado = ganancia + total_dev

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ventas procesadas",     len(ventas_ok))
        c2.metric("Ingresos ML totales",   fmt(sum(v["total_ml"]        for v in ventas_ok)))
        c3.metric("Costo logística total", fmt(sum(v["costo_logistica"] for v in ventas_ok)))
        c4.metric("Costo productos total", fmt(sum(v["costo_producto"]  for v in ventas_ok)))
        st.metric("🟢 Ganancia neta de la semana", fmt(resultado),
                  delta=f"Devoluciones: {fmt(total_dev)}" if dev_con else None,
                  delta_color="normal" if resultado >= 0 else "inverse")

        st.divider()
        mes_label = datetime.now().strftime("%Y-%m")
        semana_label = f"Semana del {datetime.now().strftime('%d/%m/%Y')}"
        if st.button("💾 Guardar semana en acumulado mensual", type="primary"):
            ac = cargar_acumulado()
            if mes_label not in ac:
                ac[mes_label] = {"semanas": [], "total_ganancia": 0, "total_devoluciones": 0}
            ac[mes_label]["semanas"].append({
                "label": semana_label, "ganancia_neta": ganancia,
                "perdida_devoluciones": total_dev, "resultado": resultado, "ventas": len(ventas_ok),
            })
            ac[mes_label]["total_ganancia"]     = sum(s["ganancia_neta"]        for s in ac[mes_label]["semanas"])
            ac[mes_label]["total_devoluciones"] = sum(s["perdida_devoluciones"] for s in ac[mes_label]["semanas"])
            guardar_acumulado(ac)
            st.success(f"✅ Guardado. Acumulado de {mes_label} actualizado.")

with tab2:
    ac = cargar_acumulado()
    if not ac:
        st.info("Todavía no hay semanas guardadas.")
    else:
        mes_sel = st.selectbox("Mes", sorted(ac.keys(), reverse=True))
        data = ac[mes_sel]
        st.subheader(f"Resumen de {mes_sel}")
        c1, c2, c3 = st.columns(3)
        res_mes = data["total_ganancia"] + data["total_devoluciones"]
        c1.metric("Ganancia neta acumulada",  fmt(data["total_ganancia"]))
        c2.metric("Pérdida por devoluciones", fmt(data["total_devoluciones"]))
        c3.metric("Resultado neto del mes",   fmt(res_mes))
        st.dataframe(pd.DataFrame([{
            "Semana": s["label"], "Ventas": s["ventas"],
            "Ganancia neta": fmt(s["ganancia_neta"]),
            "Devoluciones":  fmt(s["perdida_devoluciones"]),
            "Resultado":     fmt(s["resultado"]),
        } for s in data["semanas"]]), use_container_width=True, hide_index=True)
        if st.button("🗑️ Borrar mes", type="secondary"):
            del ac[mes_sel]; guardar_acumulado(ac); st.rerun()

with tab3:
    st.subheader("Costos logísticos por zona")
    vistos = set(); rows = []
    for k, v in sorted(ZONAS.items(), key=lambda x: x[1][0]):
        if v not in vistos:
            vistos.add(v)
            rows.append({"Costo logístico": fmt(v[0]), "Bonif ML (<$30k)": fmt(v[1]), "Bonif ML (>$30k)": fmt(v[2])})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="Ganancias ML", page_icon="📦", layout="wide")

ZONAS_FLEX = {
    "capital federal": 4490, "caba": 4490,
    "avellaneda": 6490, "hurlingham": 6490, "ituzaingó": 6490, "ituzaingo": 6490,
    "la matanza norte": 6490, "lanús": 6490, "lanus": 6490,
    "lomas de zamora": 6490, "san fernando": 6490, "san isidro": 6490,
    "san martín": 6490, "san martin": 6490, "tres de febrero": 6490,
    "vicente lópez": 6490, "vicente lopez": 6490,
    "almirante brown": 8490, "berazategui": 8490, "esteban echeverría": 8490,
    "esteban echeverria": 8490, "ezeiza": 8490, "florencio varela": 8490,
    "jose c paz": 8490, "josé c paz": 8490, "jose c. paz": 8490,
    "la matanza sur": 8490, "malvinas argentinas": 8490, "merlo": 8490,
    "moreno": 8490, "quilmes": 8490, "san miguel": 8490, "tigre": 8490,
}

ACUMULADO_FILE = "acumulado.json"

def normalizar(texto):
    if not texto:
        return ""
    return str(texto).strip().lower()

def get_costo_flex(ciudad, partido):
    for lugar in [ciudad, partido]:
        key = normalizar(lugar)
        if key in ZONAS_FLEX:
            return ZONAS_FLEX[key]
    for lugar in [ciudad, partido]:
        key = normalizar(lugar)
        for zona_key, costo in ZONAS_FLEX.items():
            if zona_key in key or key in zona_key:
                return costo
    return None

def cargar_acumulado():
    if os.path.exists(ACUMULADO_FILE):
        with open(ACUMULADO_FILE, "r") as f:
            return json.load(f)
    return {}

def guardar_acumulado(data):
    with open(ACUMULADO_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def procesar_reporte(df_ml, df_costos):
    costos_dict = {}
    for _, row in df_costos.iterrows():
        id_pub = str(row.iloc[0]).strip()
        costo = float(row.iloc[1])
        costos_dict[id_pub] = costo

    estados_cancelados = [
        "cancelada por el comprador",
        "paquete cancelado por mercado libre",
        "reclamo cerrado con reembolso al comprador",
        "te devolveremos el paquete antes del",
    ]

    ventas = []
    devoluciones = []
    sin_costo = []

    for _, row in df_ml.iterrows():
        estado = normalizar(str(row.get("Estado", "")))
        if not estado or estado == "nan":
            continue

        id_pub = str(row.get("# de publicación", "")).strip()
        titulo = str(row.get("Título de la publicación", "")).strip()
        forma_entrega = str(row.get("Forma de entrega", "")).strip()
        ciudad = str(row.get("Ciudad", "")).strip()
        provincia = str(row.get("Estado.1", "")).strip()
        total_ml = float(row.get("Total (ARS)", 0) or 0)
        anulacion = float(row.get("Anulaciones y reembolsos (ARS)", 0) or 0)
        descuentos = float(row.get("Descuentos y bonificaciones", 0) or 0)
        ingresos = float(row.get("Ingresos por productos (ARS)", 0) or 0)
        unidades = int(float(row.get("Unidades", 1) or 1))
        fecha = str(row.get("Fecha de venta", "")).strip()

        es_cancelada = any(c in estado for c in estados_cancelados)

        costo_producto = costos_dict.get(id_pub)
        if costo_producto is None and not es_cancelada:
            sin_costo.append({"ID publicación": id_pub, "Título": titulo[:60]})

        es_flex = "flex" in normalizar(forma_entrega)
        costo_logistica = 0
        zona_detectada = None
        zona_sin_precio = False

        if es_flex and not es_cancelada:
            costo_logistica = get_costo_flex(ciudad, provincia)
            if costo_logistica is None:
                zona_sin_precio = True
                zona_detectada = f"{ciudad} / {provincia}"
                costo_logistica = 0
            else:
                zona_detectada = f"{ciudad} (${ costo_logistica:,.0f})"

        if es_cancelada:
            perdida = anulacion
            devoluciones.append({
                "fecha": fecha,
                "id_pub": id_pub,
                "titulo": titulo[:50],
                "estado": str(row.get("Estado", "")),
                "total_original": ingresos,
                "anulacion": anulacion,
                "costo_envio_vuelta": 0.0,
                "perdida_total": perdida,
                "es_flex": es_flex,
                "zona": zona_detectada or f"{ciudad} / {provincia}",
            })
        else:
            ganancia_neta = total_ml - (costo_producto or 0) - costo_logistica
            ventas.append({
                "fecha": fecha,
                "id_pub": id_pub,
                "titulo": titulo[:50],
                "estado": str(row.get("Estado", "")),
                "forma_entrega": forma_entrega,
                "ciudad": ciudad,
                "provincia": provincia,
                "zona_flex": zona_detectada,
                "zona_sin_precio": zona_sin_precio,
                "unidades": unidades,
                "ingresos_ml": ingresos,
                "total_ml": total_ml,
                "costo_producto": costo_producto or 0,
                "costo_logistica": costo_logistica,
                "ganancia_neta": ganancia_neta,
                "sin_costo": costo_producto is None,
            })

    return ventas, devoluciones, sin_costo

def fmt_ars(valor):
    if valor is None:
        return "-"
    signo = "-" if valor < 0 else ""
    return f"{signo}${abs(valor):,.0f}".replace(",", ".")

st.title("📦 Ganancias Mercado Libre")

tab1, tab2, tab3 = st.tabs(["📂 Procesar semana", "📅 Acumulado mensual", "⚙️ Zonas Flex"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        archivo_ml = st.file_uploader("Reporte ML (.xlsx)", type=["xlsx"], key="ml")
    with col2:
        archivo_costos = st.file_uploader("Costos de productos (.xlsx)", type=["xlsx"], key="costos")
        st.caption("Dos columnas: ID publicación | Costo")

    if archivo_ml and archivo_costos:
        with st.spinner("Procesando..."):
            df_ml = pd.read_excel(archivo_ml, sheet_name="Ventas AR", header=5)
            df_costos = pd.read_excel(archivo_costos, header=0)
            ventas, devoluciones, sin_costo = procesar_reporte(df_ml, df_costos)

        if sin_costo:
            st.warning(f"⚠️ {len(sin_costo)} producto(s) sin costo cargado — la ganancia de esas ventas está incompleta")
            with st.expander("Ver productos sin costo"):
                st.dataframe(pd.DataFrame(sin_costo), use_container_width=True, hide_index=True)

        ventas_sin_precio_zona = [v for v in ventas if v.get("zona_sin_precio")]
        if ventas_sin_precio_zona:
            zonas = list(set(v["zona"] for v in ventas_sin_precio_zona))
            st.warning(f"⚠️ Zonas Flex sin precio configurado: {', '.join(zonas)}")

        st.subheader("Devoluciones / Cancelaciones")
        if devoluciones:
            st.caption("Revisá cada devolución. Si fue por tu culpa, ingresá el costo del envío de vuelta.")
            dev_editables = []
            for i, d in enumerate(devoluciones):
                with st.expander(f"🔴 {d['titulo']} — {d['estado']}", expanded=False):
                    cols = st.columns([2, 1, 1, 1])
                    cols[0].write(f"**Fecha:** {d['fecha'][:20]}")
                    cols[1].write(f"**Anulación ML:** {fmt_ars(d['anulacion'])}")
                    cols[2].write(f"**Zona:** {d['zona']}")
                    envio_vuelta = cols[3].number_input(
                        "Envío de vuelta (tu costo)",
                        min_value=0.0, value=0.0, step=100.0,
                        key=f"dev_{i}", label_visibility="visible"
                    )
                    perdida_total = d["anulacion"] - envio_vuelta
                    st.write(f"**Pérdida total: {fmt_ars(perdida_total)}**")
                    devoluciones[i]["costo_envio_vuelta"] = envio_vuelta
                    devoluciones[i]["perdida_total"] = perdida_total
                    dev_editables.append(devoluciones[i])
        else:
            st.success("Sin devoluciones esta semana")

        total_perdido_dev = sum(d["perdida_total"] for d in devoluciones)

        st.subheader("Ventas de la semana")
        ventas_validas = [v for v in ventas if not v["sin_costo"]]
        ventas_sin_costo_lista = [v for v in ventas if v["sin_costo"]]

        if ventas_validas:
            df_ventas = pd.DataFrame([{
                "Título": v["titulo"],
                "Forma envío": v["forma_entrega"],
                "Zona Flex": v["zona_flex"] or "-",
                "Ingresos ML": fmt_ars(v["total_ml"]),
                "Costo producto": fmt_ars(v["costo_producto"]),
                "Costo logística": fmt_ars(v["costo_logistica"]),
                "Ganancia neta": fmt_ars(v["ganancia_neta"]),
            } for v in ventas_validas])
            st.dataframe(df_ventas, use_container_width=True, hide_index=True)

        if ventas_sin_costo_lista:
            with st.expander(f"⚠️ {len(ventas_sin_costo_lista)} ventas sin costo (no incluidas en el total)"):
                df_sc = pd.DataFrame([{"Título": v["titulo"], "ID": v["id_pub"], "Total ML": fmt_ars(v["total_ml"])} for v in ventas_sin_costo_lista])
                st.dataframe(df_sc, use_container_width=True, hide_index=True)

        ganancia_semana = sum(v["ganancia_neta"] for v in ventas_validas)
        ganancia_semana_bruta = sum(v["total_ml"] for v in ventas_validas)
        resultado_semana = ganancia_semana + total_perdido_dev

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ventas procesadas", len(ventas_validas))
        c2.metric("Ganancia bruta (sin costos producto)", fmt_ars(ganancia_semana_bruta))
        c3.metric("Ganancia neta semanal", fmt_ars(ganancia_semana))
        c4.metric("Pérdida por devoluciones", fmt_ars(total_perdido_dev))

        st.metric("🟢 Resultado neto de la semana", fmt_ars(resultado_semana),
                  delta=None if resultado_semana >= 0 else "Semana negativa")

        st.divider()
        mes_actual = datetime.now().strftime("%Y-%m")
        semana_label = f"Semana del {datetime.now().strftime('%d/%m/%Y')}"

        if st.button("💾 Guardar semana en acumulado mensual", type="primary"):
            acumulado = cargar_acumulado()
            if mes_actual not in acumulado:
                acumulado[mes_actual] = {"semanas": [], "total_ganancia": 0, "total_devoluciones": 0}
            acumulado[mes_actual]["semanas"].append({
                "label": semana_label,
                "ganancia_neta": ganancia_semana,
                "perdida_devoluciones": total_perdido_dev,
                "resultado": resultado_semana,
                "ventas": len(ventas_validas),
            })
            acumulado[mes_actual]["total_ganancia"] = sum(s["ganancia_neta"] for s in acumulado[mes_actual]["semanas"])
            acumulado[mes_actual]["total_devoluciones"] = sum(s["perdida_devoluciones"] for s in acumulado[mes_actual]["semanas"])
            guardar_acumulado(acumulado)
            st.success(f"✅ Semana guardada. Acumulado de {mes_actual} actualizado.")

with tab2:
    acumulado = cargar_acumulado()
    if not acumulado:
        st.info("Aún no hay semanas guardadas. Procesá tu primer reporte y hacé clic en 'Guardar semana'.")
    else:
        meses = sorted(acumulado.keys(), reverse=True)
        mes_sel = st.selectbox("Mes", meses)
        data_mes = acumulado[mes_sel]

        st.subheader(f"Resumen de {mes_sel}")
        c1, c2, c3 = st.columns(3)
        total_resultado = data_mes["total_ganancia"] + data_mes["total_devoluciones"]
        c1.metric("Ganancia neta acumulada", fmt_ars(data_mes["total_ganancia"]))
        c2.metric("Pérdida por devoluciones", fmt_ars(data_mes["total_devoluciones"]))
        c3.metric("Resultado neto del mes", fmt_ars(total_resultado))

        st.subheader("Semanas del mes")
        df_semanas = pd.DataFrame([{
            "Semana": s["label"],
            "Ventas": s["ventas"],
            "Ganancia neta": fmt_ars(s["ganancia_neta"]),
            "Devoluciones": fmt_ars(s["perdida_devoluciones"]),
            "Resultado": fmt_ars(s["resultado"]),
        } for s in data_mes["semanas"]])
        st.dataframe(df_semanas, use_container_width=True, hide_index=True)

        if st.button("🗑️ Borrar mes seleccionado", type="secondary"):
            del acumulado[mes_sel]
            guardar_acumulado(acumulado)
            st.rerun()

with tab3:
    st.subheader("Tus zonas Flex activas")
    st.caption("Estas son las zonas configuradas en el sistema. Si cambian tus precios, avisame y las actualizamos.")
    zonas_df = pd.DataFrame([
        {"Zona / Partido": k.title(), "Costo logístico": fmt_ars(v)}
        for k, v in sorted(ZONAS_FLEX.items(), key=lambda x: x[1])
    ])
    st.dataframe(zonas_df, use_container_width=True, hide_index=True)

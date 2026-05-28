import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="Ganancias ML", page_icon="📦", layout="wide")

ESTADOS_PERDIDA  = ["devolución finalizada", "cancelada. tu transportista", "reclamo cerrado con reembolso"]
ESTADOS_SIN_PERD = ["cancelada por el comprador", "paquete cancelado por mercado libre"]
ACUMULADO_FILE   = "acumulado.json"

def norm(t):
    return str(t).strip().lower() if t else ""

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

    paquete_hijos = set()
    ventas = []
    devoluciones = []
    sin_costo = []

    filas = df_ml.reset_index(drop=True)
    i = 0
    while i < len(filas):
        row    = filas.iloc[i]
        estado = norm(str(row.get("Estado", "")))
        if not estado or estado == "nan":
            i += 1; continue

        id_pub   = str(row.get("# de publicación", "")).strip()
        titulo   = str(row.get("Título de la publicación", "")).strip()
        forma    = str(row.get("Forma de entrega", "")).strip()
        ciudad   = str(row.get("Ciudad", "")).strip()
        total_ml = safe_float(row.get("Total (ARS)"))
        ingresos = safe_float(row.get("Ingresos por productos (ARS)"))
        descuentos = safe_float(row.get("Descuentos y bonificaciones"))
        unidades = max(1, int(safe_float(row.get("Unidades"), 1)))
        fecha    = str(row.get("Fecha de venta", "")).strip()

        es_flex    = "flex"    in norm(forma)
        es_acuerdo = "acuerdo" in norm(forma)
        es_sin_perd= any(c in estado for c in ESTADOS_SIN_PERD)
        es_con_perd= any(c in estado for c in ESTADOS_PERDIDA)
        es_cancel  = es_sin_perd or es_con_perd

        # ── PAQUETE ───────────────────────────────────────────────────────────
        if "paquete de" in estado:
            hijos = []
            j = i + 1
            while j < len(filas):
                fh      = filas.iloc[j]
                total_h = fh.get("Total (ARS)")
                forma_h = str(fh.get("Forma de entrega", "")).strip()
                id_h    = str(fh.get("# de publicación", "")).strip()
                if pd.isna(total_h) and not forma_h and id_h and id_h != "nan":
                    hijos.append(fh)
                    paquete_hijos.add(j)
                    j += 1
                else:
                    break

            costo_pack = 0
            sin_costo_pack = False
            titulos_pack = []
            for fh in hijos:
                id_h  = str(fh.get("# de publicación", "")).strip()
                uds_h = max(1, int(safe_float(fh.get("Unidades"), 1)))
                tit_h = str(fh.get("Título de la publicación", "")).strip()[:40]
                titulos_pack.append(tit_h)
                c = costos_dict.get(id_h)
                if c is None:
                    sin_costo_pack = True
                    sin_costo.append({"ID publicación": id_h, "Título": tit_h, "Unidades": uds_h})
                else:
                    costo_pack += c * uds_h

            if not sin_costo_pack:
                ventas.append({
                    "fecha": fecha,
                    "titulo": (" + ".join(titulos_pack) or "Paquete")[:60],
                    "forma_entrega": forma, "ciudad": ciudad,
                    "unidades": unidades, "ingresos_ml": ingresos,
                    "bonif_ml": descuentos, "total_ml": total_ml,
                    "costo_producto": costo_pack, "ganancia_bruta": total_ml - costo_pack,
                    "sin_costo": False, "es_flex": es_flex, "es_acuerdo": es_acuerdo,
                })
            i = j; continue

        if i in paquete_hijos:
            i += 1; continue

        # Saltar filas sin importe (pendientes de acreditación)
        if total_ml == 0 and ingresos == 0 and not es_cancel:
            i += 1; continue

        costo_prod = costos_dict.get(id_pub)
        if costo_prod is None and not es_cancel:
            sin_costo.append({"ID publicación": id_pub or "(sin ID)", "Título": titulo[:60], "Unidades": unidades})

        if es_acuerdo and total_ml == 0:
            total_ml = ingresos

        if es_cancel:
            perdida = safe_float(row.get("Anulaciones y reembolsos (ARS)")) if es_con_perd else 0.0
            devoluciones.append({
                "fecha": fecha, "id_pub": id_pub, "titulo": titulo[:50],
                "estado": str(row.get("Estado", "")), "es_con_perdida": es_con_perd,
                "anulacion": perdida, "perdida_total": perdida,
                "es_flex": es_flex, "ciudad": ciudad,
            })
        else:
            cp = (costo_prod or 0) * unidades
            ventas.append({
                "fecha": fecha, "id_pub": id_pub, "titulo": titulo[:50],
                "forma_entrega": forma, "ciudad": ciudad,
                "unidades": unidades, "ingresos_ml": ingresos,
                "bonif_ml": descuentos, "total_ml": total_ml,
                "costo_producto": cp, "ganancia_bruta": total_ml - cp,
                "sin_costo": costo_prod is None,
                "es_flex": es_flex, "es_acuerdo": es_acuerdo,
            })
        i += 1

    return ventas, devoluciones, sin_costo

# ─── UI ───────────────────────────────────────────────────────────────────────
st.title("📦 Ganancias Mercado Libre")
tab1, tab2 = st.tabs(["📂 Procesar semana", "📅 Acumulado mensual"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        archivo_ml = st.file_uploader("Reporte ML (.xlsx)", type=["xlsx"], key="ml")
    with col2:
        archivo_costos = st.file_uploader("Costos de productos (.xlsx)", type=["xlsx"], key="costos")
        st.caption("Columna A: ID publicación | Columna B: Tu costo unitario")

    st.divider()
    st.subheader("💰 Costo logístico de la semana")
    st.caption("Ingresá el total de la factura de tu transportista Flex de esta semana.")
    costo_flex_semana = st.number_input(
        "Factura transportista Flex ($)", min_value=0.0, value=0.0,
        step=1000.0, format="%.0f"
    )

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

        # ── Cancelaciones sin pérdida ─────────────────────────────────────────
        dev_sin = [d for d in devoluciones if not d["es_con_perdida"]]
        dev_con = [d for d in devoluciones if d["es_con_perdida"]]

        if dev_sin:
            st.info(f"ℹ️ {len(dev_sin)} cancelación(es) sin pérdida — el producto nunca salió")
            with st.expander("Ver cancelaciones sin pérdida"):
                st.dataframe(pd.DataFrame([{
                    "Título": d["titulo"], "Estado": d["estado"], "Fecha": d["fecha"][:20]
                } for d in dev_sin]), use_container_width=True, hide_index=True)

        # ── Devoluciones con pérdida ──────────────────────────────────────────
        st.subheader("Devoluciones con pérdida")
        if dev_con:
            st.caption("Si fue por tu culpa, ingresá el costo del envío de vuelta.")
            for i, d in enumerate(devoluciones):
                if not d["es_con_perdida"]: continue
                with st.expander(f"🔴 {d['titulo']} — {d['estado']}", expanded=False):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.write(f"**Fecha:** {d['fecha'][:20]}")
                    c2.write(f"**Anulación ML:** {fmt(d['anulacion'])}")
                    ev = c3.number_input("Envío de vuelta", min_value=0.0, value=0.0,
                        step=100.0, key=f"dev_{i}")
                    devoluciones[i]["perdida_total"] = d["anulacion"] - ev
                    st.write(f"**Pérdida total: {fmt(devoluciones[i]['perdida_total'])}**")
        else:
            st.success("Sin devoluciones con pérdida esta semana ✅")

        total_dev = sum(d["perdida_total"] for d in devoluciones)

        # ── Tabla de ventas ───────────────────────────────────────────────────
        st.subheader("Ventas de la semana")
        ventas_ok = [v for v in ventas if not v["sin_costo"]]
        ventas_sc = [v for v in ventas if v["sin_costo"]]

        if ventas_ok:
            st.dataframe(pd.DataFrame([{
                "Título":          v["titulo"],
                "Uds":             v["unidades"],
                "Envío":           "Flex" if v["es_flex"] else ("Acuerdo" if v["es_acuerdo"] else "Correo"),
                "Total ML":        fmt(v["total_ml"]),
                "Costo producto":  fmt(v["costo_producto"]),
                "Ganancia bruta":  fmt(v["ganancia_bruta"]),
            } for v in ventas_ok]), use_container_width=True, hide_index=True)

        if ventas_sc:
            with st.expander(f"⚠️ {len(ventas_sc)} ventas sin costo (no incluidas)"):
                st.dataframe(pd.DataFrame([{
                    "Título": v["titulo"], "ID": v["id_pub"],
                    "Uds": v["unidades"], "Total ML": fmt(v["total_ml"])
                } for v in ventas_sc]), use_container_width=True, hide_index=True)

        # ── Resumen ───────────────────────────────────────────────────────────
        total_ml_semana       = sum(v["total_ml"]        for v in ventas_ok)
        total_costo_productos = sum(v["costo_producto"]  for v in ventas_ok)
        ganancia_bruta        = sum(v["ganancia_bruta"]  for v in ventas_ok)
        ganancia_neta         = ganancia_bruta - costo_flex_semana + total_dev

        ventas_flex   = [v for v in ventas_ok if v["es_flex"]]
        ventas_correo = [v for v in ventas_ok if not v["es_flex"] and not v["es_acuerdo"]]
        ventas_acuerdo= [v for v in ventas_ok if v["es_acuerdo"]]

        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ventas procesadas",       len(ventas_ok))
        c2.metric("Ingresos ML totales",     fmt(total_ml_semana))
        c3.metric("Costo productos total",   fmt(total_costo_productos))
        c4.metric("Factura transportista",   fmt(costo_flex_semana))

        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Ventas Flex",    f"{len(ventas_flex)} ventas",
                  delta=fmt(sum(v['ganancia_bruta'] for v in ventas_flex)) + " bruto")
        c2.metric("Ventas Correo",  f"{len(ventas_correo)} ventas",
                  delta=fmt(sum(v['ganancia_bruta'] for v in ventas_correo)) + " bruto")
        c3.metric("Acuerdo",        f"{len(ventas_acuerdo)} ventas",
                  delta=fmt(sum(v['ganancia_bruta'] for v in ventas_acuerdo)) + " bruto")

        st.divider()
        st.metric(
            "🟢 Ganancia neta de la semana",
            fmt(ganancia_neta),
            delta=f"Devoluciones: {fmt(total_dev)}" if dev_con else None,
            delta_color="normal" if ganancia_neta >= 0 else "inverse"
        )
        st.caption(f"Ingresos ML ${total_ml_semana:,.0f} − Productos ${total_costo_productos:,.0f} − Flex ${costo_flex_semana:,.0f} + Devoluciones ${total_dev:,.0f}".replace(",","."))

        # ── Guardar ───────────────────────────────────────────────────────────
        st.divider()
        mes_label    = datetime.now().strftime("%Y-%m")
        semana_label = f"Semana del {datetime.now().strftime('%d/%m/%Y')}"

        if st.button("💾 Guardar semana en acumulado mensual", type="primary"):
            if costo_flex_semana == 0:
                st.warning("⚠️ Ingresaste $0 de factura Flex. ¿Estás seguro? Si no tenés ventas Flex podés ignorar esto.")
            ac = cargar_acumulado()
            if mes_label not in ac:
                ac[mes_label] = {"semanas": [], "total_ganancia": 0, "total_devoluciones": 0}
            ac[mes_label]["semanas"].append({
                "label":                semana_label,
                "ganancia_neta":        ganancia_neta,
                "perdida_devoluciones": total_dev,
                "resultado":            ganancia_neta,
                "ventas":               len(ventas_ok),
                "costo_flex":           costo_flex_semana,
                "costo_productos":      total_costo_productos,
                "ingresos_ml":          total_ml_semana,
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
        c1.metric("Ganancia neta acumulada",  fmt(data["total_ganancia"]))
        c2.metric("Pérdida por devoluciones", fmt(data["total_devoluciones"]))
        c3.metric("Resultado neto del mes",   fmt(data["total_ganancia"] + data["total_devoluciones"]))

        st.subheader("Semanas")
        st.dataframe(pd.DataFrame([{
            "Semana":           s["label"],
            "Ventas":           s["ventas"],
            "Ingresos ML":      fmt(s.get("ingresos_ml", 0)),
            "Costo productos":  fmt(s.get("costo_productos", 0)),
            "Costo Flex":       fmt(s.get("costo_flex", 0)),
            "Devoluciones":     fmt(s["perdida_devoluciones"]),
            "Ganancia neta":    fmt(s["ganancia_neta"]),
        } for s in data["semanas"]]), use_container_width=True, hide_index=True)

        if st.button("🗑️ Borrar mes", type="secondary"):
            del ac[mes_sel]; guardar_acumulado(ac); st.rerun()

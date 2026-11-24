"""
Dashboard Olist (Project B).
Ejecutar desde la carpeta del proyecto:   streamlit run app/app.py

Reglas que cumple:
  * Cada gráfico sale de una consulta SQL (app/queries.py). Python NO agrega,
    une ni reorganiza resultados: solo pasa las filas al gráfico.
  * Todos los filtros viajan a PostgreSQL como PARÁMETROS (%(nombre)s).
  * El usuario nunca escribe SQL; los controles limitan los valores posibles y
    las entradas inválidas se detectan antes de lanzar la consulta.
"""
from datetime import date

import plotly.graph_objects as go
import psycopg2
import streamlit as st
from plotly.subplots import make_subplots

import queries as Q
from db import run_query

st.set_page_config(page_title="Olist - Project B", layout="wide")


# --------------------------------------------------------------------------
# Acceso a datos (con caché y sin que un error tire la app)
# --------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def _cached(sql, params):
    return run_query(sql, params)


def fetch(sql, params=None):
    """Devuelve (columnas, filas) o None si hubo un problema (ya mostrado al usuario)."""
    try:
        return _cached(sql, params or {})
    except psycopg2.OperationalError:
        st.error("No se pudo conectar con la base de datos. Comprueba que PostgreSQL "
                 "está encendido y que el archivo .env es correcto.")
    except psycopg2.errors.QueryCanceled:
        st.error("La consulta tardó demasiado y se canceló. Prueba con un rango de fechas menor.")
    except psycopg2.Error as e:
        st.error(f"Error de base de datos: {(e.pgerror or str(e)).splitlines()[0]}")
    except Exception as e:                                   # nunca dejamos caer la app
        st.error(f"Error inesperado: {type(e).__name__}")
    return None


def col(rows, i):
    """Selecciona la columna i de las filas (Decimal -> float solo para poder dibujar)."""
    return [float(r[i]) if hasattr(r[i], "as_tuple") else r[i] for r in rows]


def show_sql(sql, params, cols, rows):
    with st.expander("Ver SQL, parámetros y datos"):
        st.code(sql.strip(), language="sql")
        st.json({k: (str(v) if isinstance(v, date) else v) for k, v in params.items()})
        st.dataframe([dict(zip(cols, r)) for r in rows])


def need_data(res):
    if res is None:
        return False
    if not res[1]:
        st.info("No hay datos con estos filtros. Prueba a ampliar el rango de fechas.")
        return False
    return True


# --------------------------------------------------------------------------
# Filtros globales (barra lateral)
# --------------------------------------------------------------------------
st.title("Olist Brazilian E-Commerce")
st.caption("Project B · Beñat Ilzarbe Daza y Nora Cepas Zapico · todos los datos salen de consultas SQL en PostgreSQL")

bounds = fetch(Q.BOUNDS)
if bounds is None or not bounds[1]:
    st.stop()
dmin, dmax = bounds[1][0]

st.sidebar.header("Filtros")
default_from = max(date(2017, 1, 1), dmin)
default_to = min(date(2018, 8, 31), dmax)
picked = st.sidebar.date_input("Rango de fechas de compra", value=(default_from, default_to),
                               min_value=dmin, max_value=dmax)
if not (isinstance(picked, (tuple, list)) and len(picked) == 2):
    st.sidebar.warning("Selecciona la fecha de inicio y la de fin.")
    st.info("Selecciona un rango de fechas completo en la barra lateral.")
    st.stop()
d_from, d_to = picked
if d_from > d_to:
    st.sidebar.error("La fecha de inicio no puede ser posterior a la de fin.")
    st.stop()

states_res = fetch(Q.CUSTOMER_STATES)
state_options = ["Todos"] + ([r[0] for r in states_res[1]] if states_res else [])
state_pick = st.sidebar.selectbox("Estado del cliente", state_options)
state = None if state_pick == "Todos" else state_pick

base = {"d_from": d_from, "d_to": d_to, "state": state}

tabs = st.tabs(["Ingresos por categoría", "Evolución mensual", "Entregas", "Satisfacción",
                "Pagos", "Clientes fieles", "Vendedores", "Distancia y envío"])

# --------------------------------------------------------------------------
# Q1 - Ingresos por categoría
# --------------------------------------------------------------------------
with tabs[0]:
    st.subheader("¿Qué categorías generan más ingresos?  (Q1)")
    status_res = fetch(Q.ORDER_STATUSES)
    status_all = [r[0] for r in status_res[1]] if status_res else []
    c1, c2 = st.columns([1, 2])
    top_n = c1.slider("Número de categorías", 5, 30, 15)
    statuses = c2.multiselect("Estado del pedido", status_all,
                              default=["delivered"] if "delivered" in status_all else [])
    if not statuses:
        st.warning("Elige al menos un estado de pedido.")
    else:
        params = {**base, "statuses": statuses, "top_n": top_n}
        res = fetch(Q.Q1_REVENUE_BY_CATEGORY, params)
        if need_data(res):
            cols, rows = res
            fig = go.Figure(go.Bar(x=col(rows, 2), y=col(rows, 0), orientation="h",
                                   customdata=col(rows, 1),
                                   hovertemplate="%{y}<br>Ingresos: %{x:,.2f}<br>Pedidos: %{customdata}<extra></extra>"))
            fig.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="Ingresos (R$)", height=550)
            st.plotly_chart(fig)
            show_sql(Q.Q1_REVENUE_BY_CATEGORY, params, cols, rows)

# --------------------------------------------------------------------------
# Q5 - Evolución mensual
# --------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Facturación mensual y crecimiento respecto al mes anterior  (Q5)")
    res = fetch(Q.Q5_MONTHLY_REVENUE, base)
    if need_data(res):
        cols, rows = res
        months = [r[0].strftime("%Y-%m") for r in rows]
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_bar(x=months, y=col(rows, 1), name="Ingresos (R$)", secondary_y=False)
        fig.add_scatter(x=months, y=col(rows, 3), name="Crecimiento mensual (%)",
                        mode="lines+markers", secondary_y=True)
        fig.update_yaxes(title_text="Ingresos (R$)", secondary_y=False)
        fig.update_yaxes(title_text="Crecimiento (%)", secondary_y=True)
        fig.update_layout(height=500)
        st.plotly_chart(fig)
        st.caption("Los meses de los extremos del rango pueden estar incompletos.")
        show_sql(Q.Q5_MONTHLY_REVENUE, base, cols, rows)

# --------------------------------------------------------------------------
# Q6 - Entregas por estado
# --------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Tiempo de entrega por estado  (Q6)")
    min_orders = st.slider("Mínimo de pedidos por estado", 1, 1000, 100, step=10)
    params = {"d_from": d_from, "d_to": d_to, "min_orders": min_orders}
    res = fetch(Q.Q6_DELIVERY_BY_STATE, params)
    if need_data(res):
        cols, rows = res
        fig = go.Figure()
        fig.add_bar(x=col(rows, 0), y=col(rows, 2), name="Días hasta la entrega")
        fig.add_bar(x=col(rows, 0), y=col(rows, 3), name="Días de adelanto sobre lo prometido")
        fig.update_layout(barmode="group", yaxis_title="Días", height=500)
        st.plotly_chart(fig)
        show_sql(Q.Q6_DELIVERY_BY_STATE, params, cols, rows)

# --------------------------------------------------------------------------
# Q9 - Satisfacción vs retraso
# --------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Puntuación de las reseñas según el retraso de la entrega  (Q9)")
    res = fetch(Q.Q9_SCORE_VS_DELAY, base)
    if need_data(res):
        cols, rows = res
        fig = go.Figure(go.Bar(x=col(rows, 0), y=col(rows, 2), customdata=col(rows, 1),
                               hovertemplate="%{x}<br>Nota media: %{y}<br>Reseñas: %{customdata}<extra></extra>"))
        fig.update_layout(yaxis=dict(title="Nota media (1-5)", range=[0, 5]), height=450)
        st.plotly_chart(fig)
        show_sql(Q.Q9_SCORE_VS_DELAY, base, cols, rows)

# --------------------------------------------------------------------------
# Q8 - Métodos de pago
# --------------------------------------------------------------------------
with tabs[4]:
    st.subheader("Peso de cada método de pago  (Q8)")
    res = fetch(Q.Q8_PAYMENT_METHODS, base)
    if need_data(res):
        cols, rows = res
        fig = go.Figure(go.Pie(labels=col(rows, 0), values=col(rows, 2), hole=0.4,
                               customdata=col(rows, 3),
                               hovertemplate="%{label}<br>Importe: %{value:,.2f}<br>Cuotas medias: %{customdata}<extra></extra>"))
        fig.update_layout(height=450)
        st.plotly_chart(fig)
        show_sql(Q.Q8_PAYMENT_METHODS, base, cols, rows)

# --------------------------------------------------------------------------
# Q7 - Clientes fieles
# --------------------------------------------------------------------------
with tabs[5]:
    st.subheader("¿Cuántas veces compra cada cliente?  (Q7)")
    res = fetch(Q.Q7_REPEAT_CUSTOMERS, base)
    if need_data(res):
        cols, rows = res
        fig = go.Figure(go.Bar(x=col(rows, 0), y=col(rows, 1), customdata=col(rows, 2),
                               hovertemplate="%{x} pedido(s)<br>Clientes: %{y:,}<br>%{customdata}%<extra></extra>"))
        fig.update_layout(xaxis_title="Pedidos por cliente", yaxis_title="Clientes (escala log)",
                          yaxis_type="log", height=450)
        st.plotly_chart(fig)
        show_sql(Q.Q7_REPEAT_CUSTOMERS, base, cols, rows)

# --------------------------------------------------------------------------
# Q4 - Top vendedores por estado
# --------------------------------------------------------------------------
with tabs[6]:
    st.subheader("Vendedores que más facturan en un estado  (Q4)")
    sres = fetch(Q.SELLER_STATES)
    seller_states = [r[0] for r in sres[1]] if sres else []
    if seller_states:
        c1, c2 = st.columns(2)
        default_idx = seller_states.index("SP") if "SP" in seller_states else 0
        seller_state = c1.selectbox("Estado del vendedor", seller_states, index=default_idx)
        top_k = c2.slider("Top vendedores", 1, 10, 5)
        params = {"d_from": d_from, "d_to": d_to, "seller_state": seller_state, "top_k": top_k}
        res = fetch(Q.Q4_TOP_SELLERS_BY_STATE, params)
        if need_data(res):
            cols, rows = res
            fig = go.Figure(go.Bar(x=[f"#{r[1]} · {r[2][:8]}…" for r in rows], y=col(rows, 3)))
            fig.update_layout(yaxis_title="Ingresos (R$)", height=450)
            st.plotly_chart(fig)
            show_sql(Q.Q4_TOP_SELLERS_BY_STATE, params, cols, rows)

# --------------------------------------------------------------------------
# Q10 - Distancia vs envío
# --------------------------------------------------------------------------
with tabs[7]:
    st.subheader("Distancia vendedor-cliente y coste de envío por estado  (Q10)")
    st.caption("Consulta pesada: la primera vez puede tardar unos segundos; después queda en caché.")
    min_items = st.slider("Mínimo de artículos por estado", 1, 2000, 200, step=50)
    params = {"d_from": d_from, "d_to": d_to, "min_items": min_items}
    res = fetch(Q.Q10_DISTANCE_VS_FREIGHT, params)
    if need_data(res):
        cols, rows = res
        fig = go.Figure(go.Scatter(x=col(rows, 2), y=col(rows, 3), mode="markers+text",
                                   text=col(rows, 0), textposition="top center",
                                   marker=dict(size=14), customdata=col(rows, 1),
                                   hovertemplate="%{text}<br>%{x} km · envío medio %{y}<br>Artículos: %{customdata}<extra></extra>"))
        fig.update_layout(xaxis_title="Distancia media (km)", yaxis_title="Envío medio (R$)", height=500)
        st.plotly_chart(fig)
        show_sql(Q.Q10_DISTANCE_VS_FREIGHT, params, cols, rows)

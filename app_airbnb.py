import streamlit as st
from pymongo import MongoClient
import pandas as pd

# ─── Configuración de página ───
st.set_page_config(page_title="Airbnb Listings", page_icon="🏠", layout="wide")

st.title("🏠 Airbnb Listings — Sample Airbnb")
st.caption("Consulta alojamientos Airbnb vía MongoDB Atlas")

# ─── Conexión a MongoDB Atlas vía secrets ───
try:
    mongo_uri = st.secrets["mongo"]["uri"]
except KeyError:
    st.error(
        "❌ No se encontró el secreto `mongo.uri`. "
        "Crea el archivo `.streamlit/secrets.toml` con:\n\n"
        "```\n[mongo]\nuri = \"mongodb+srv://usuario:password@cluster.xxxxx.mongodb.net/\"\n```"
    )
    st.stop()

with st.sidebar:
    st.header("🔌 MongoDB Atlas")
    st.markdown(
        "**Conexión:** vía `st.secrets`\n\n"
        "**Requisitos:**\n"
        "- Dataset `sample_airbnb` cargado\n"
        "- Colección: `listingsAndReviews`"
    )

# ─── Conectar ───
@st.cache_resource
def get_client(uri):
    return MongoClient(uri)

try:
    client = get_client(mongo_uri)
    db = client["sample_airbnb"]
    col = db["listingsAndReviews"]
    client.admin.command("ping")
    st.sidebar.success("✅ Conectado a MongoDB Atlas")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.stop()

# ─── Filtros ───
st.markdown("---")
col1, col2, col3 = st.columns([3, 2, 1])

with col1:
    nombre_busqueda = st.text_input(
        "🔍 Buscar por nombre del alojamiento",
        placeholder="Ej: Duplex, Cozy, Beach, Studio"
    )

with col2:
    tipo_propiedad = st.selectbox(
        "🏘️ Tipo de propiedad",
        options=["Todos", "Apartment", "House", "Condominium", "Villa", "Loft", "Townhouse", "Other"]
    )

with col3:
    limite = st.selectbox("Resultados máx.", [5, 10, 20, 50], index=1)

if not nombre_busqueda:
    st.info("Escribe un nombre (o parte del nombre) de un alojamiento para buscar.")
    st.stop()

# ─── Construir query ───
query = {"name": {"$regex": nombre_busqueda, "$options": "i"}}
if tipo_propiedad != "Todos":
    query["property_type"] = tipo_propiedad

listings = list(col.find(query).limit(limite))

if not listings:
    st.warning(f"No se encontraron alojamientos con el nombre **'{nombre_busqueda}'**.")
    st.stop()

st.success(f"Se encontraron **{len(listings)}** alojamiento(s)")

# ─── Helper: extraer precio como float ───
def parse_price(val):
    if val is None:
        return None
    try:
        return float(str(val))
    except Exception:
        return None

# ─── Construir tabla de resultados ───
resultados = []
for r in listings:
    address = r.get("address", {})
    location = address.get("location", {})
    coords = location.get("coordinates", [])

    precio = parse_price(r.get("price"))
    cleaning_fee = parse_price(r.get("cleaning_fee"))

    reviews_scores = r.get("review_scores", {})
    score = reviews_scores.get("review_scores_rating", "N/A")

    host = r.get("host", {})

    resultados.append({
        "Nombre": r.get("name", "—"),
        "Tipo Propiedad": r.get("property_type", "—"),
        "Tipo Habitación": r.get("room_type", "—"),
        "País": address.get("country", "—"),
        "Mercado": address.get("market", "—"),
        "Barrio": address.get("suburb", address.get("government_area", "—")),
        "Precio/noche (USD)": precio,
        "Tarifa limpieza (USD)": cleaning_fee,
        "Huéspedes": r.get("accommodates", "—"),
        "Habitaciones": r.get("bedrooms", "—"),
        "Camas": r.get("beds", "—"),
        "Baños": r.get("bathrooms", "—"),
        "Puntuación": score,
        "N° Reviews": len(r.get("reviews", [])),
        "Host": host.get("host_name", "—"),
        "Cancelación": r.get("cancellation_policy", "—"),
        "Longitud": coords[0] if len(coords) >= 2 else None,
        "Latitud": coords[1] if len(coords) >= 2 else None,
    })

df = pd.DataFrame(resultados)

# ─── Mostrar tabla ───
st.markdown("### 📋 Resultados")
st.dataframe(df.drop(columns=["Longitud", "Latitud"]), use_container_width=True, hide_index=True)

# ─── Mapa ───
df_map = df.dropna(subset=["Latitud", "Longitud"]).copy()
df_map = df_map.rename(columns={"Latitud": "latitude", "Longitud": "longitude"})

if not df_map.empty:
    st.markdown("### 🗺️ Ubicación en el mapa")
    st.map(df_map[["latitude", "longitude"]])

# ─── Detalle expandible por listing ───
st.markdown("### 📝 Detalle por alojamiento")
for i, r in enumerate(listings):
    nombre = r.get("name", "—")
    prop_type = r.get("property_type", "")
    room_type = r.get("room_type", "")
    with st.expander(f"**{nombre}** — {prop_type} · {room_type}"):
        c1, c2 = st.columns(2)

        with c1:
            st.markdown(f"**Host:** {r.get('host', {}).get('host_name', '—')}")
            st.markdown(f"**Barrio:** {resultados[i]['Barrio']}")
            st.markdown(f"**Mercado:** {resultados[i]['Mercado']}")
            st.markdown(f"**País:** {resultados[i]['País']}")
            st.markdown(f"**Precio/noche:** USD {resultados[i]['Precio/noche (USD)']}")
            st.markdown(f"**Tarifa limpieza:** USD {resultados[i]['Tarifa limpieza (USD)']}")
            st.markdown(f"**Política cancelación:** {r.get('cancellation_policy', '—')}")
            st.markdown(f"**Noches mín. / máx.:** {r.get('minimum_nights', '—')} / {r.get('maximum_nights', '—')}")

            amenities = r.get("amenities", [])
            if amenities:
                st.markdown(f"**Amenities ({len(amenities)}):** {', '.join(amenities[:10])}" + (" ..." if len(amenities) > 10 else ""))

            summary = r.get("summary", "")
            if summary:
                st.markdown(f"**Descripción:** {summary[:300]}{'...' if len(summary) > 300 else ''}")

        with c2:
            # Scores
            scores = r.get("review_scores", {})
            if scores:
                st.markdown("**Puntuaciones:**")
                score_data = [
                    {"Criterio": k.replace("review_scores_", "").capitalize(), "Valor": v}
                    for k, v in scores.items() if v is not None
                ]
                if score_data:
                    st.dataframe(pd.DataFrame(score_data), hide_index=True, use_container_width=True)

            # Últimas reviews
            reviews = r.get("reviews", [])
            if reviews:
                st.markdown(f"**Últimas reseñas ({len(reviews)} total):**")
                review_data = []
                for rv in reviews[-5:]:
                    fecha = rv.get("date", "")
                    if hasattr(fecha, "strftime"):
                        fecha = fecha.strftime("%Y-%m-%d")
                    review_data.append({
                        "Fecha": str(fecha)[:10],
                        "Reviewer": rv.get("reviewer_name", "—"),
                        "Comentario": str(rv.get("comments", ""))[:120],
                    })
                st.dataframe(pd.DataFrame(review_data), hide_index=True, use_container_width=True)
            else:
                st.info("Sin reseñas disponibles")

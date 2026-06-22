import os
import sys
import json
import tempfile

import streamlit as st
import folium
from streamlit_folium import st_folium

# ---------------------------------------------------------------------------
# Path setup — allow importing from the project root (ai/, data/)
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.classifier import classify_dish  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATA_PATH = os.path.join(ROOT, "data", "restaurants.json")

CATEGORY_ICON = {
    "Vegano": "🌱",
    "Vegetariano": "🥗",
    "Ninguno": "🍖",
}

CATEGORY_BADGE = {
    "Vegano": "background:#2e7d32;color:#fff;padding:2px 8px;border-radius:12px;font-size:0.75rem;",
    "Vegetariano": "background:#558b2f;color:#fff;padding:2px 8px;border-radius:12px;font-size:0.75rem;",
    "Ninguno": "background:#757575;color:#fff;padding:2px 8px;border-radius:12px;font-size:0.75rem;",
}

MARKER_COLOR = {
    "vegano": "green",
    "vegetariano": "lightgreen",
    "mixed": "blue",
    "none": "gray",
}

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_restaurants() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def all_unique_dishes(restaurants: list[dict]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for r in restaurants:
        for d in r.get("dishes", []):
            if d not in seen:
                seen.add(d)
                unique.append(d)
    return unique


def restaurant_dominant_category(restaurant: dict, classifications: dict[str, str]) -> str:
    cats = {classifications.get(d, "Ninguno") for d in restaurant.get("dishes", [])}
    if "Vegano" in cats:
        return "vegano"
    if "Vegetariano" in cats:
        return "vegetariano"
    return "none"


def restaurant_has_category(restaurant: dict, classifications: dict[str, str], wanted: set[str]) -> bool:
    return any(classifications.get(d, "Ninguno") in wanted for d in restaurant.get("dishes", []))


# ---------------------------------------------------------------------------
# Classification with progress bar (stored in session_state to run once)
# ---------------------------------------------------------------------------

def classify_on_startup(restaurants: list[dict]) -> dict[str, str]:
    dishes = all_unique_dishes(restaurants)
    if not dishes:
        return {}

    bar = st.progress(0, text="Clasificando platos con DeepSeek…")
    results: dict[str, str] = {}
    for i, dish in enumerate(dishes):
        results[dish] = classify_dish(dish)
        pct = (i + 1) / len(dishes)
        bar.progress(pct, text=f"Clasificando ({i + 1}/{len(dishes)}): {dish}")
    bar.empty()
    return results


# ---------------------------------------------------------------------------
# Map builder
# ---------------------------------------------------------------------------

def build_map(restaurants: list[dict], classifications: dict[str, str]) -> folium.Map:
    lats = [r["lat"] for r in restaurants]
    lons = [r["lon"] for r in restaurants]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]

    m = folium.Map(location=center, zoom_start=14, tiles="CartoDB positron")

    for r in restaurants:
        dom = restaurant_dominant_category(r, classifications)
        color = MARKER_COLOR.get(dom, "gray")

        apt_dishes = [d for d in r.get("dishes", []) if classifications.get(d, "Ninguno") != "Ninguno"]
        if apt_dishes:
            dish_list = "".join(f"<li>{d}</li>" for d in apt_dishes[:5])
            popup_html = (
                f"<b>{r['name']}</b><br>"
                f"<small>{r.get('address', '')}</small>"
                f"<ul style='margin:4px 0 0 0;padding-left:16px'>{dish_list}</ul>"
            )
        else:
            popup_html = f"<b>{r['name']}</b><br><small>{r.get('address', '')}</small>"

        folium.Marker(
            location=[r["lat"], r["lon"]],
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=r["name"],
            icon=folium.Icon(color=color, icon="leaf", prefix="fa"),
        ).add_to(m)

    return m


# ---------------------------------------------------------------------------
# Restaurant card
# ---------------------------------------------------------------------------

def render_restaurant_card(restaurant: dict, classifications: dict[str, str], wanted: set[str]) -> None:
    name = restaurant["name"]
    address = restaurant.get("address", "Sin dirección")
    dishes = restaurant.get("dishes", [])

    with st.expander(f"**{name}**  —  📍 {address}"):
        for dish in dishes:
            cat = classifications.get(dish, "Ninguno")
            icon = CATEGORY_ICON.get(cat, "")
            badge_style = CATEGORY_BADGE.get(cat, "")
            highlighted = cat in wanted

            if highlighted:
                st.markdown(
                    f"{icon} **{dish}** &nbsp; <span style='{badge_style}'>{cat}</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"&nbsp;&nbsp;&nbsp;{dish}", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# OCR section
# ---------------------------------------------------------------------------

def render_ocr_section(classifications_cache: dict[str, str]) -> None:
    st.divider()
    st.subheader("📷 Clasificar menú desde foto")
    st.caption("Sube una imagen de un menú y PaddleOCR extraerá el texto; luego DeepSeek clasificará cada línea.")

    uploaded = st.file_uploader("Selecciona imagen del menú", type=["png", "jpg", "jpeg", "webp"])
    if uploaded is None:
        return

    col_img, col_res = st.columns([1, 1])

    with col_img:
        st.image(uploaded, caption="Imagen subida", use_container_width=True)

    suffix = os.path.splitext(uploaded.name)[-1] or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    with st.spinner("Extrayendo texto con PaddleOCR…"):
        try:
            from paddleocr import PaddleOCR
            ocr_engine = PaddleOCR(use_angle_cls=True, lang="es", show_log=False)
            ocr_result = ocr_engine.ocr(tmp_path, cls=True)
        except Exception as exc:
            st.error(f"Error en PaddleOCR: {exc}")
            os.unlink(tmp_path)
            return
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    lines: list[str] = []
    if ocr_result and ocr_result[0]:
        for block in ocr_result[0]:
            text: str = block[1][0].strip()
            if text:
                lines.append(text)

    if not lines:
        with col_res:
            st.warning("No se detectó texto en la imagen.")
        return

    with col_res:
        st.write(f"**{len(lines)} líneas detectadas. Clasificando con DeepSeek…**")
        bar = st.progress(0)
        classified: list[tuple[str, str]] = []
        for i, line in enumerate(lines):
            cat = classifications_cache.get(line) or classify_dish(line)
            classifications_cache[line] = cat
            classified.append((line, cat))
            bar.progress((i + 1) / len(lines))
        bar.empty()

        st.markdown("### Resultados OCR")
        for line, cat in classified:
            icon = CATEGORY_ICON.get(cat, "")
            badge_style = CATEGORY_BADGE.get(cat, "")
            st.markdown(
                f"{icon} {line} &nbsp; <span style='{badge_style}'>{cat}</span>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Restaurantes Veganos & Vegetarianos – Lima",
        page_icon="🌱",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem; }
        .stExpander summary { font-size: 0.95rem; }
        h1 { color: #2e7d32; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🌱 Restaurantes Veganos & Vegetarianos en Lima")

    try:
        restaurants = load_restaurants()
    except FileNotFoundError:
        st.error(f"No se encontró el archivo de datos en: {DATA_PATH}")
        st.stop()

    if "classifications" not in st.session_state:
        if not os.environ.get("DEEPSEEK_API_KEY"):
            st.error("Falta la variable de entorno **DEEPSEEK_API_KEY**. Configúrala antes de iniciar la app.")
            st.stop()
        with st.status("Clasificando platos con DeepSeek…", expanded=True) as status:
            st.write("Iniciando clasificación de todos los platos del menú…")
            st.session_state.classifications = classify_on_startup(restaurants)
            status.update(label="Clasificación completada ✅", state="complete", expanded=False)

    classifications: dict[str, str] = st.session_state.classifications

    # Sidebar filters
    st.sidebar.header("🔎 Filtros")
    show_vegano = st.sidebar.checkbox("🌱 Vegano", value=True)
    show_vegetariano = st.sidebar.checkbox("🥗 Vegetariano", value=True)

    wanted: set[str] = set()
    if show_vegano:
        wanted.add("Vegano")
    if show_vegetariano:
        wanted.add("Vegetariano")

    if not wanted:
        st.sidebar.warning("Selecciona al menos un filtro.")

    filtered = (
        [r for r in restaurants if restaurant_has_category(r, classifications, wanted)]
        if wanted
        else []
    )

    st.sidebar.divider()
    st.sidebar.metric("Restaurantes encontrados", len(filtered))
    st.sidebar.markdown(
        "**Leyenda del mapa**\n"
        "- 🟢 Verde: Vegano\n"
        "- 🟡 Verde claro: Vegetariano\n"
        "- ⚫ Gris: Sin opciones"
    )

    # Map + cards
    map_col, cards_col = st.columns([3, 2], gap="medium")

    with map_col:
        st.subheader("Mapa")
        if filtered:
            m = build_map(filtered, classifications)
            st_folium(m, use_container_width=True, height=480)
        else:
            st.info("No hay restaurantes para mostrar con los filtros actuales.")

    with cards_col:
        st.subheader(f"Restaurantes ({len(filtered)})")
        for restaurant in filtered:
            render_restaurant_card(restaurant, classifications, wanted)

    render_ocr_section(classifications)


if __name__ == "__main__":
    main()    if "vegano" in lower:
        return "Vegano"
    if "vegetariano" in lower:
        return "Vegetariano"
    return "Ninguno"


def classify_dishes(dish_names: list[str]) -> dict[str, str]:
    return {name: classify_dish(name) for name in dish_names}

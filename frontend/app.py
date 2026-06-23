import os
import sys
import json
import tempfile

import streamlit as st
import folium
from streamlit_folium import st_folium

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from ai.classifier import classify_dish

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

@st.cache_data(show_spinner=False)
def load_restaurants() -> list:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)

def all_unique_dishes(restaurants: list) -> list:
    seen = set()
    unique = []
    for r in restaurants:
        for d in r.get("dishes", []):
            if d not in seen:
                seen.add(d)
                unique.append(d)
    return unique

def restaurant_dominant_category(restaurant: dict, classifications: dict) -> str:
    cats = {classifications.get(d, "Ninguno") for d in restaurant.get("dishes", [])}
    if "Vegano" in cats:
        return "vegano"
    if "Vegetariano" in cats:
        return "vegetariano"
    return "none"

def restaurant_has_category(restaurant: dict, classifications: dict, wanted: set) -> bool:
    return any(classifications.get(d, "Ninguno") in wanted for d in restaurant.get("dishes", []))

def classify_on_startup(restaurants: list) -> dict:
    dishes = all_unique_dishes(restaurants)
    if not dishes:
        return {}
    bar = st.progress(0, text="Clasificando platos con DeepSeek…")
    results = {}
    for i, dish in enumerate(dishes):
        results[dish] = classify_dish(dish)
        pct = (i + 1) / len(dishes)
        bar.progress(pct, text=f"Clasificando ({i + 1}/{len(dishes)}): {dish}")
    bar.empty()
    return results

def build_map(restaurants: list, classifications: dict) -> folium.Map:
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

def render_restaurant_card(restaurant: dict, classifications: dict, wanted: set) -> None:
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

def render_ocr_section(classifications_cache: dict) -> None:
    st.divider()
    st.subheader("📷 Clasificar menú desde foto")
    st.caption("Sube una imagen de un menú y la IA extraerá el texto y clasificará cada plato.")
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
    with st.spinner("Extrayendo texto con OCR…"):
        try:
            if "ocr_engine" not in st.session_state:
                import easyocr
                st.session_state.ocr_engine = easyocr.Reader(['es', 'en'])
            ocr_result = st.session_state.ocr_engine.readtext(tmp_path)
        except Exception as exc:
            st.error(f"Error en OCR: {exc}")
            os.unlink(tmp_path)
            return
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    lines = []
    if ocr_result:
        for detection in ocr_result:
            text = detection[1].strip()
            if text:
                lines.append(text)
    if not lines:
        with col_res:
            st.warning("No se detectó texto en la imagen.")
        return
    with col_res:
        st.write(f"**{len(lines)} líneas detectadas. Clasificando con DeepSeek…**")
        bar = st.progress(0)
        classified = []
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

def main() -> None:
    st.set_page_config(
        page_title="Aptito",
        page_icon="🌱",
        layout="wide",
    )
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem; }
        h1 { color: #2e7d32; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("🌱 Aptito — Restaurantes Veganos & Vegetarianos en Lima")
    st.markdown("*Aptito usa IA para mostrarte qué puedes comer en cualquier restaurante de Lima, seas vegetariano o vegano.*")

    try:
        restaurants = load_restaurants()
    except FileNotFoundError:
        st.error(f"No se encontró el archivo de datos en: {DATA_PATH}")
        st.stop()

    if "classifications" not in st.session_state:
        with st.status("Clasificando platos con DeepSeek…", expanded=True) as status:
            st.session_state.classifications = classify_on_startup(restaurants)
            status.update(label="Clasificación completada ✅", state="complete", expanded=False)

    classifications = st.session_state.classifications

    st.sidebar.header("🔎 Filtros")
    show_vegano = st.sidebar.checkbox("🌱 Vegano", value=True)
    show_vegetariano = st.sidebar.checkbox("🥗 Vegetariano", value=True)

    wanted = set()
    if show_vegano:
        wanted.add("Vegano")
    if show_vegetariano:
        wanted.add("Vegetariano")

    filtered = [r for r in restaurants if restaurant_has_category(r, classifications, wanted)] if wanted else []

    st.sidebar.divider()
    st.sidebar.metric("Restaurantes encontrados", len(filtered))

    map_col, cards_col = st.columns([3, 2], gap="medium")

    with map_col:
        st.subheader("Mapa")
        if filtered:
            m = build_map(filtered, classifications)
            st_folium(m, use_container_width=True, height=480)
        else:
            st.info("No hay restaurantes para mostrar.")

    with cards_col:
        st.subheader(f"Restaurantes ({len(filtered)})")
        for restaurant in filtered:
            render_restaurant_card(restaurant, classifications, wanted)

    render_ocr_section(classifications)

if __name__ == "__main__":
    main()

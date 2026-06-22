
import streamlit as st
import requests
import json
import folium
from streamlit_folium import folium_static
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
RESTAURANTS_FILE = "data/restaurants.json"

st.set_page_config(layout="wide")
st.title("Aptito: Tu Guía Veggie en Lima 🌿")

@st.cache_data
def load_restaurants():
    try:
        with open(RESTAURANTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Error: El archivo {RESTAURANTS_FILE} no se encontró.")
        st.stop()
    except json.JSONDecodeError:
        st.error(f"Error: El archivo {RESTAURANTS_FILE} tiene un formato JSON inválido.")
        st.stop()

@st.cache_data
def classify_all_dishes(restaurants):
    classified_data = []
    total_dishes = sum(len(r['dishes']) for r in restaurants)
    progress_bar = st.progress(0, text=f"Clasificando 0 de {total_dishes} platos...")
    classified_count = 0

    for restaurant in restaurants:
        apt_dishes = {"vegano": [], "vegetariano": []}
        for dish in restaurant['dishes']:
            try:
                response = requests.post(f"{BACKEND_URL}/classify", json={"dish": dish})
                response.raise_for_status() # Raise an exception for HTTP errors
                classification = response.json()
                label = classification.get("label")

                if label == "vegano":
                    apt_dishes["vegano"].append(dish)
                elif label == "vegetariano":
                    apt_dishes["vegetariano"].append(dish)
            except requests.exceptions.RequestException as e:
                st.warning(f"Could not classify '{dish}' (Backend down?): {e}")
            except json.JSONDecodeError:
                st.warning(f"Failed to decode JSON for '{dish}'.")
            finally:
                classified_count += 1
                progress_bar.progress(classified_count / total_dishes, text=f"Clasificando {classified_count} de {total_dishes} platos...")
        
        classified_data.append({
            **restaurant,
            "apt_dishes": apt_dishes
        })
    progress_bar.empty()
    return classified_data

# --- Main App --- 

all_restaurants = load_restaurants()

with st.spinner("Preparando Aptito: Clasificando platos con IA..."):
    classified_restaurants = classify_all_dishes(all_restaurants)

st.sidebar.header("Filtra por dieta")
filter_option = st.sidebar.radio(
    "Mostrar restaurantes con opciones:",
    ('Vegano', 'Vegetariano', 'Todos')
)

if filter_option == 'Todos':
    filtered_restaurants = classified_restaurants
else:
    filtered_restaurants = [
        r for r in classified_restaurants 
        if r['apt_dishes'][filter_option.lower()]
    ]

st.header("📍 Restaurantes en Lima")

if filtered_restaurants:
    # Create a Folium map centered around Lima
    m = folium.Map(location=[-12.0464, -77.0428], zoom_start=12)

    for res in filtered_restaurants:
        apt_dishes_list = []
        if filter_option == 'Vegano' or filter_option == 'Todos':
            apt_dishes_list.extend(res['apt_dishes']['vegano'])
        if filter_option == 'Vegetariano' or filter_option == 'Todos':
            apt_dishes_list.extend(res['apt_dishes']['vegetariano'])
        
        if not apt_dishes_list and filter_option != 'Todos':
            continue # Skip if no apt dishes for the selected filter

        popup_html = f"<b>{res['name']}</b><br><i>{res['district']}</i><br>"
        if apt_dishes_list:
            popup_html += "<br><b>Platos Aptos:</b><br>" + "<br>".join(apt_dishes_list)
        else:
            popup_html += "<br>No hay platos aptos para esta selección."

        folium.Marker(
            [res['latitude'], res['longitude']],
            tooltip=res['name'],
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m)

    folium_static(m)

    st.subheader("Lista de Restaurantes")
    for res in filtered_restaurants:
        apt_dishes_vegano = res['apt_dishes']['vegano']
        apt_dishes_vegetariano = res['apt_dishes']['vegetariano']

        display_vegano = (filter_option == 'Vegano' or filter_option == 'Todos') and apt_dishes_vegano
        display_vegetariano = (filter_option == 'Vegetariano' or filter_option == 'Todos') and apt_dishes_vegetariano

        if display_vegano or display_vegetariano or filter_option == 'Todos':
            st.markdown(f"### {res['name']}")
            st.markdown(f"**Distrito:** {res['district']}")
            
            if display_vegano:
                st.markdown("**Platos Veganos:** " + ", ".join(f"<span style='background-color:#ccffcc; padding: 2px 4px; border-radius: 3px;'>{d}</span>" for d in apt_dishes_vegano), unsafe_allow_html=True)
            if display_vegetariano and (filter_option == 'Vegetariano' or (filter_option == 'Todos' and not display_vegano)):
                 st.markdown("**Platos Vegetarianos:** " + ", ".join(f"<span style='background-color:#ffffcc; padding: 2px 4px; border-radius: 3px;'>{d}</span>" for d in apt_dishes_vegetariano), unsafe_allow_html=True)
            elif display_vegetariano and filter_option == 'Todos':
                 # If both vegano and vegetariano are displayed for 'Todos', avoid double-counting/displaying
                 # Here we only want vegetariano dishes that are NOT also vegano
                 only_vegetarian_dishes = [d for d in apt_dishes_vegetariano if d not in apt_dishes_vegano]
                 if only_vegetarian_dishes:
                     st.markdown("**Platos Vegetarianos (no veganos):** " + ", ".join(f"<span style='background-color:#ffffcc; padding: 2px 4px; border-radius: 3px;'>{d}</span>" for d in only_vegetarian_dishes), unsafe_allow_html=True)

            st.markdown("---<")
else:
    st.info("No se encontraron restaurantes con las opciones seleccionadas.")

st.header("📸 Escanea una carta")
st.write("Sube una foto de una carta o menú para clasificar sus platos.")

uploaded_file = st.file_uploader("Elige una imagen...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    st.image(uploaded_file, caption='Imagen subida.', use_column_width=True)
    st.write("Procesando imagen...")

    try:
        files = {"file": uploaded_file.getvalue()}
        with st.spinner("Extrayendo texto con OCR..."):
            ocr_response = requests.post(f"{BACKEND_URL}/ocr", files=files)
            ocr_response.raise_for_status()
            ocr_result = ocr_response.json()
        
        st.subheader("Texto Extraído:")
        st.text(ocr_result.get('text', 'No se pudo extraer texto.'))

        dishes_to_classify = [line.strip() for line in ocr_result.get('dishes', []) if line.strip()]
        
        if dishes_to_classify:
            st.subheader("Clasificación de Platos del Menú:")
            classified_menu_dishes = []
            menu_progress_bar = st.progress(0, text=f"Clasificando 0 de {len(dishes_to_classify)} platos del menú...")
            
            for i, dish_name in enumerate(dishes_to_classify):
                try:
                    classify_response = requests.post(f"{BACKEND_URL}/classify", json={"dish": dish_name})
                    classify_response.raise_for_status()
                    classification = classify_response.json()
                    classified_menu_dishes.append((dish_name, classification))
                except requests.exceptions.RequestException as e:
                    classified_menu_dishes.append((dish_name, {"label": "error", "reason": f"Backend error: {e}"}))
                except json.JSONDecodeError:
                    classified_menu_dishes.append((dish_name, {"label": "error", "reason": "Invalid JSON response from backend"}))
                menu_progress_bar.progress((i + 1) / len(dishes_to_classify), text=f"Clasificando {i+1} de {len(dishes_to_classify)} platos del menú...")
            
            menu_progress_bar.empty()

            for dish_name, classification in classified_menu_dishes:
                label = classification.get('label', 'error')
                reason = classification.get('reason', 'N/A')
                if label == "vegano":
                    st.markdown(f"- **{dish_name}**: <span style='background-color:#ccffcc; padding: 2px 4px; border-radius: 3px;'>Vegano</span> ({reason})", unsafe_allow_html=True)
                elif label == "vegetariano":
                    st.markdown(f"- **{dish_name}**: <span style='background-color:#ffffcc; padding: 2px 4px; border-radius: 3px;'>Vegetariano</span> ({reason})", unsafe_allow_html=True)
                elif label == "no_apto":
                    st.markdown(f"- **{dish_name}**: <span style='background-color:#ffcccc; padding: 2px 4px; border-radius: 3px;'>No Apto</span> ({reason})", unsafe_allow_html=True)
                else:
                    st.markdown(f"- **{dish_name}**: Error ({reason})", unsafe_allow_html=True)
        else:
            st.info("No se encontraron platos para clasificar en el texto extraído.")

    except requests.exceptions.RequestException as e:
        st.error(f"Error al conectar con el backend de OCR: {e}. Asegúrate de que el backend esté corriendo en {BACKEND_URL}")
    except Exception as e:
        st.error(f"Ocurrió un error inesperado durante el procesamiento OCR: {e}")

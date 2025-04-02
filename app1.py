import time
import streamlit as st
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from datetime import datetime
import numpy as np
import os
import json
import requests
from deep_translator import GoogleTranslator  
import requests
import joblib
import pandas as pd
import json
from datetime import datetime,timedelta
import os 
import ujson as json 
import warnings
from sklearn.exceptions import InconsistentVersionWarning
warnings.simplefilter("ignore", InconsistentVersionWarning)

script_dir = os.path.dirname(os.path.abspath(__file__))

JSON_OUTPUT_FILE = os.path.join(script_dir, "recommended_food_items.json")
label_encoders = joblib.load(os.path.join(script_dir, "food_encoder.pkl"))
model = joblib.load(os.path.join(script_dir, "xgboost_food_model.pkl"))
ranking_file = os.path.join(script_dir, "recommendation_progress.json")
TRANSLATION_CACHE_FILE = os.path.join(script_dir, "translation_cache.json")
WEATHER_CACHE_FILE = os.path.join(script_dir, "weather_cache.json")

LANGUAGES = {'English': 'en', 'Hindi': 'hi', 'Tamil': 'ta', 'Telugu': 'te', 'Malayalam': 'ml', 'Kannada': 'kn'}
st.session_state.setdefault('language', 'English')

def load_translation_cache():
    if os.path.exists(TRANSLATION_CACHE_FILE):
        with open(TRANSLATION_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

translation_cache = load_translation_cache()

def save_translation_cache():
    with open(TRANSLATION_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(translation_cache, f, indent=4, ensure_ascii=False)

def apply_tamil_overrides(translated_text):
    TAMIL_OVERRIDES = {
        "வண்டி": "கார்ட்",
        "கார்ட்யில்": "கார்டில்",
        "வண்டியில்": "கார்டில்",
        "அப்மா": "உப்புமா",
        "வாடா": "வடை",
        "காபி வடிகட்டவும்": "காபி",
        "முக்கிய படிப்புகள்": "மதிய உணவு",
        "சாம்பார் அரிசி": "சாம்பார் சாதம்",
        "தயிர் அரிசி": "தயிர் சாதம்",
        "சோல் பீச்சர்": "சோலா பூரி",
        "சனா சாட்": "சன்னா சாட்"
    }
    for original, override in TAMIL_OVERRIDES.items():
        translated_text = translated_text.replace(original, override)
    return translated_text

def translate_text(text):
    if st.session_state.language == 'English':
        return text

    target_language = LANGUAGES[st.session_state.language]
    cache_key = f"{text}::{target_language}"

    if cache_key in translation_cache:
        return translation_cache[cache_key]  

    api_url = "http://localhost:8000/translate"
    payload = {"text": text, "to": target_language}

    translated = text  

    try:
        response = requests.post(api_url, json=payload, timeout=3)
        if response.status_code == 200:
            data = response.json()
            translated = data.get("translatedText", text)
    except Exception:
        try:
            translated = GoogleTranslator(source='en', target=target_language).translate(text)
        except Exception:
            pass  

    if st.session_state.language == 'Tamil':
        translated = apply_tamil_overrides(translated)

    translation_cache[cache_key] = translated
    save_translation_cache()

    return translated

def get_weather_condition():
    if os.path.exists(WEATHER_CACHE_FILE):
        with open(WEATHER_CACHE_FILE, "r") as f:
            cache_data = json.load(f)
            last_updated = datetime.fromisoformat(cache_data["timestamp"])
            
            # **Use cached weather if less than 30 minutes old**
            if datetime.now() - last_updated < timedelta(minutes=30):
                return cache_data["weather"]

    latitude, longitude = 13.0827, 80.2707
    weather_api_url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"

    try:
        response = requests.get(weather_api_url, timeout=5)  # 5-second timeout for fast failures
        if response.status_code == 200:
            weather_data = response.json()
            weather_code = weather_data['current_weather']['weathercode']
            temperature = weather_data['current_weather']['temperature']

            condition = 'Uncertain'
            if weather_code == 0:
                condition = 'Sunny/Hot' if temperature > 30 else 'Clear'
            elif weather_code in [1, 2]:
                condition = 'Partly Cloudy'
            elif weather_code == 3:
                condition = 'Cloudy'
            elif 51 <= weather_code <= 55:
                condition = 'Rainy'
            elif 61 <= weather_code <= 65:
                condition = 'Heavy Rain'
            elif 71 <= weather_code <= 75:
                condition = 'Snow'
            elif weather_code >= 95:
                condition = 'Thunderstorm'
            elif weather_code == 80:
                condition = 'Rainy'

            # **Save weather data to cache**
            with open(WEATHER_CACHE_FILE, "w") as f:
                json.dump({"timestamp": datetime.now().isoformat(), "weather": condition}, f)

            return condition
    except requests.exceptions.RequestException:
        return 'Uncertain'  # Fallback if API request fails

    return 'Uncertain'

def get_time_of_day():
    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        return 'Morning'
    elif 12 <= current_hour < 17:
        return 'Afternoon'
    elif 17 <= current_hour < 21:
        return 'Evening'
    else:
        return 'Night'
def get_current_month():
    return datetime.now().strftime('%B')  # Full month name

def is_weekend():
    return 1 if datetime.now().weekday() >= 5 else 0  # 1 for Sat/Sun, 0 for weekdays

def load_ranking_progress():
    if os.path.exists(ranking_file):
        try:
            with open(ranking_file, "r") as file:
                return json.load(file)
        except (json.JSONDecodeError, IOError):
            return {"last_index": 0}  
    return {"last_index": 0}


def save_ranking_progress(index):
    try:
        temp_file = ranking_file + ".tmp"  # Write to a temp file first
        with open(temp_file, "w") as file:
            json.dump({"last_index": index}, file)
        os.replace(temp_file, ranking_file)  
    except IOError:
        pass  

import numpy as np

def recommend_food():
    current_time = get_time_of_day()
    current_month = get_current_month()
    current_weather = get_weather_condition()
    weekend_special = is_weekend()

    encoded_time = label_encoders["Time"].transform([current_time])[0] if current_time in label_encoders["Time"].classes_ else -1
    encoded_month = label_encoders["Month"].transform([current_month])[0] if current_month in label_encoders["Month"].classes_ else -1
    encoded_weather = label_encoders["Weather"].transform([current_weather])[0] if current_weather in label_encoders["Weather"].classes_ else -1

    # Convert input to NumPy array 
    input_data = np.array([[encoded_time, encoded_month, encoded_weather, weekend_special]])

    predictions = model.predict_proba(input_data)[0]
    sorted_indices = np.argsort(predictions)[::-1] 
    ranked_food_items = label_encoders["Food Item"].inverse_transform(sorted_indices)


    progress = load_ranking_progress()
    last_index = progress["last_index"]
    next_items = ranked_food_items[last_index:last_index + 3]

    new_index = (last_index + 3) % len(ranked_food_items)
    save_ranking_progress(new_index)

    return next_items


st.title("Indian Restaurant Menu")

selected_language = st.selectbox("Select Language:", list(LANGUAGES.keys()), key="language_select")
st.session_state.language = selected_language
@st.cache_data
def get_recommendations():
    return recommend_food()

recommended_items = get_recommendations()

if 'cart' not in st.session_state:
    st.session_state.cart = {}
if 'page' not in st.session_state:
    st.session_state.page = "Menu"

def add_to_cart(item, price, img_path):  
    price = get_price(item)  

    if price == 0:  
        st.warning(f"Warning: {item} has price ₹0! Check item name.")  
        return  

    if item in st.session_state.cart:
        st.session_state.cart[item]['quantity'] += 1
    else:
        st.session_state.cart[item] = {
            'price': float(price),  
            'img_path': img_path,
            'quantity': 1 
        }
    st.success(f"Added {item} to cart.")


    #st.write("Cart Debug:", st.session_state.cart)  # Temporary debugging
    st.write(f"Adding: {item}, Price: {price}   ")


def get_price(item_name):
    
    categories = {
        "Breakfast": [
            ("Idli", 30, "idli.jpg"),
            ("Vada", 40, "vada.jpg"),
            ("Masala Dosa", 70, "masala_dosa.jpg"),
            ("Upma", 50, "upma.jpg"),
            ("Pongal", 70, "pongal.jpg"),
            ("Vermicelli (Semiya) Upma", 50, "vermicelli_upma.jpg"),
            ("Poha", 50, "poha.jpg"),
            ("Aloo Paratha", 60, "aloo_paratha.jpg"),
            ("Gobi Paratha", 60, "gobi_paratha.jpg")
        ],
        "Main Courses": [
            ("Sambar Rice", 90, "sambar_rice.jpg"),
            ("Curd Rice", 80, "curd_rice.jpg"),
            ("Vegetable Biryani", 120, "vegetable_biryani.jpg"),
            ("Chicken Biryani", 150, "biryani.jpg"),
            ("Chole Bhature", 100, "chole_bhature.jpg"),
            ("Chapati", 30, "chapati.jpg"),
            ("Paratha", 60, "paratha.jpg"),
            ("Puri", 40, "puri.jpg")
        ],
        "Snacks": [
            ("Medu Vada", 40, "medu_vada.jpg"),
            ("Mysore Bonda", 50, "mysore_bonda.jpg"),
            ("Pav Bhaji", 70, "pav_bhaji.jpg"),
            ("Dhokla", 30, "dhokla.jpg"),
            ("Kachori", 40, "kachori.jpg"),
            ("Batata Vada", 40, "batata_vada.jpg"),
            ("Pakora", 50, "pakora.jpg"),
            ("Aloo Tikki", 50, "aloo_tikki.jpg"),
            ("Samosa", 30, "samosa.jpg"),
            ("Momos", 60, "momos.jpg"),
            ("Dahi Puri", 50, "dahi_puri.jpg"),
            ("Sev Puri", 50, "sev_puri.jpg"),
            ("Bhel Puri", 50, "bhel_puri.jpg"),
            ("Paneer Tikka", 90, "paneer_tikka.jpg")
        ],
        "Chaats & Salads": [
            ("Chana Chaat", 50, "chana_chaat.jpg"),
            ("Fruit Chaat", 60, "fruit_chaat.jpg")
        ],
        "Beverages": [
            ("Filter Coffee", 25, "filter_coffee.jpg"),
            ("Masala Chai", 20, "masala_chai.jpg"),
            ("Buttermilk", 15, "buttermilk.jpg"),
            ("Tea", 15, "tea.jpg"),
            ("Ginger Tea", 25, "ginger_tea.jpg"),
            ("Sweet Lassi", 30, "sweet_lassi.jpg"),
            ("Salted Lassi", 30, "salted_lassi.jpg"),
            ("Mango Lassi", 40, "mango_lassi.jpg"),
            ("Falooda", 60, "falooda.jpg")
        ]
    }
    for category, items in categories.items():
        for item in items:
            if item[0] == item_name:
                return item[1]  # Return the price
    return 0  # Default to 0 if not found

def display_header():
    if st.button(translate_text("Cart")):
        st.session_state.page = "Cart"

IMAGE_WIDTH = 200

if st.session_state.page == "Menu":
    display_header()

    st.header(translate_text("Today's Recommendations"))
    cols = st.columns(3)
    for i, item in enumerate(recommended_items):
        img_path = os.path.join(script_dir, "images", f"{item.lower().replace(' ', '_')}.jpg")
        with cols[i % 3]:
            try:
                st.image(img_path, width=IMAGE_WIDTH)
            except Exception:
                pass
            st.write(translate_text(item))
            if st.button(translate_text(f"Add {item} to Cart"), key=f"recommend_{item}"):
                add_to_cart(item, 0, img_path)
    if st.button(translate_text("Refresh Recommendations")):
        get_recommendations.clear()  
        st.rerun()  
    categories = {
        "Breakfast": [
            ("Idli", 30, "idli.jpg"),
            ("Vada", 40, "vada.jpg"),
            ("Masala Dosa", 70, "masala_dosa.jpg"),
            ("Upma", 50, "upma.jpg"),
            ("Pongal", 70, "pongal.jpg"),
            ("Vermicelli (Semiya) Upma", 50, "vermicelli_upma.jpg"),
            ("Poha", 50, "poha.jpg"),
            ("Aloo Paratha", 60, "aloo_paratha.jpg"),
            ("Gobi Paratha", 60, "gobi_paratha.jpg")
        ],
        "Main Courses": [
            ("Sambar Rice", 90, "sambar_rice.jpg"),
            ("Curd Rice", 80, "curd_rice.jpg"),
            ("Vegetable Biryani", 120, "vegetable_biryani.jpg"),
            ("Chicken Biryani", 150, "biryani.jpg"),
            ("Chole Bhature", 100, "chole_bhature.jpg"),
            ("Chapati", 30, "chapati.jpg"),
            ("Paratha", 60, "paratha.jpg"),
            ("Puri", 40, "puri.jpg")
        ],
        "Snacks": [
            ("Medu Vada", 40, "medu_vada.jpg"),
            ("Mysore Bonda", 50, "mysore_bonda.jpg"),
            ("Pav Bhaji", 70, "pav_bhaji.jpg"),
            ("Dhokla", 30, "dhokla.jpg"),
            ("Kachori", 40, "kachori.jpg"),
            ("Batata Vada", 40, "batata_vada.jpg"),
            ("Pakora", 50, "pakora.jpg"),
            ("Aloo Tikki", 50, "aloo_tikki.jpg"),
            ("Samosa", 30, "samosa.jpg"),
            ("Momos", 60, "momos.jpg"),
            ("Dahi Puri", 50, "dahi_puri.jpg"),
            ("Sev Puri", 50, "sev_puri.jpg"),
            ("Bhel Puri", 50, "bhel_puri.jpg"),
            ("Paneer Tikka", 90, "paneer_tikka.jpg")
        ],
        "Chaats & Salads": [
            ("Chana Chaat", 50, "chana_chaat.jpg"),
            ("Fruit Chaat", 60, "fruit_chaat.jpg")
        ],
        "Beverages": [
            ("Filter Coffee", 25, "filter_coffee.jpg"),
            ("Masala Chai", 20, "masala_chai.jpg"),
            ("Buttermilk", 15, "buttermilk.jpg"),
            ("Tea", 15, "tea.jpg"),
            ("Ginger Tea", 25, "ginger_tea.jpg"),
            ("Sweet Lassi", 30, "sweet_lassi.jpg"),
            ("Salted Lassi", 30, "salted_lassi.jpg"),
            ("Mango Lassi", 40, "mango_lassi.jpg"),
            ("Falooda", 60, "falooda.jpg")
        ]
    }

    for category, items in categories.items():
        st.header(translate_text(category))
        cols = st.columns(3)  
        for i, (item, price, img_name) in enumerate(items):
            col = cols[i % 3]
            with col:
                img_path = os.path.join(script_dir, "images", f"{item.lower().replace(' ', '_')}.jpg")

                try:
                    st.image(img_path, width=IMAGE_WIDTH)
                except Exception:
                    pass
                st.write(f"{translate_text(item)} - ₹{price}")
                if st.button(translate_text("Add to Cart"), key=f"menu_{item}"):
                    add_to_cart(item, price, img_path)

elif st.session_state.page == "Cart":
    st.header(translate_text("Your Cart"))

    if st.session_state.cart:
        total = 0
        items_to_remove = []  

        for item, details in st.session_state.cart.items():
            price = details.get('price', 0)  
            quantity = details.get('quantity', 1)

            col1, col2, col3, col4 = st.columns([2, 4, 2, 2])
            with col1:
                st.image(details['img_path'], width=100)  
            with col2:
                st.write(f"**{translate_text(item)}**")  
                st.write(f"{translate_text('Quantity')}: {quantity}")
            with col3:
                st.write(f"₹{price} x {quantity}")
            with col4:
                if st.button(translate_text("Remove"), key=f"remove_{item}"):
                    if quantity > 1:
                        st.session_state.cart[item]['quantity'] -= 1
                    else:
                        items_to_remove.append(item)  

            total += price * quantity

        for item in items_to_remove:
            del st.session_state.cart[item]  

        st.write(f"**{translate_text('Total')}: ₹{total}**")
    else:
        st.warning(translate_text("Your cart is empty."))
    if "show_payment" not in st.session_state:
        st.session_state.show_payment = False

if not st.session_state.show_payment:
    if st.button("Proceed to Payment 💳"):
        st.session_state.show_payment = True
        st.rerun()
else:
   if "show_payment" not in st.session_state:
    st.session_state.show_payment = False

if not st.session_state.show_payment:
    if st.button("Proceed to Payment"):
        st.session_state.show_payment = True
        st.rerun()
else:
    st.title("Payments")
    st.write("Enter your payment details below:")

    payment_method = st.selectbox("Select Payment Method", ["Credit Card", "Debit Card", "UPI", "Net Banking"])
    card_number = st.text_input("Card Number", type="password")
    expiry_date = st.text_input("Expiry Date (MM/YY)")
    cvv = st.text_input("CVV", type="password")
    upi_id = st.text_input("UPI ID") if payment_method == "UPI" else None

    if st.button("Pay Now 💳"):
        with st.spinner("Processing Payment via Razorpay..."):
            time.sleep(2)  # Simulating payment processing delay
            st.success("✅ Payment Successful! Thank you for your purchase.")

    if st.button(translate_text("Back to Menu")):
        st.session_state.page = "Menu"

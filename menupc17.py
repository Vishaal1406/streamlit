from io import BytesIO
import time
import streamlit as st
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
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import mm,portrait
from reportlab.lib.utils import simpleSplit
import streamlit.components.v1 as components
from html2image import Html2Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from PIL import Image
import warnings
from sklearn.exceptions import InconsistentVersionWarning
warnings.simplefilter("ignore", InconsistentVersionWarning)

def generate_bill(cart, subtotal, tax, final_total):
    buffer = BytesIO()
    width, height = 80 * mm, 200 * mm  
    c = canvas.Canvas(buffer, pagesize=(width, height))
    y = height - 10 * mm  
    c.setFont("Helvetica-Bold", 12)
    c.drawString(10, y, "Tiffin Tales Restraunt")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawString(10, y, "123 Street, 10th Main Road")
    y -= 4 * mm
    c.drawString(10, y, "Vadapalani, Chennai, Tamil Nadu - 600026")
    y -= 10 * mm
    c.drawString(10, y, "----------------------------------")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(10, y, "Item        Qty    Price   Total")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    for item, details in cart.items():
        price = details.get('price', 0)
        quantity = details.get('quantity', 1)
        item_total = price * quantity
        text = f"{item[:10]:<10} {quantity:<4} ₹{price:<5} ₹{item_total:<5}"
        for line in simpleSplit(text, "Helvetica", 10, width - 20):
            c.drawString(10, y, line)
            y -= 6 * mm
    y -= 4 * mm
    c.drawString(10, y, "----------------------------------")
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(10, y, f"Subtotal: ₹{subtotal}")
    y -= 6 * mm
    c.drawString(10, y, f"Tax (5%): ₹{tax}")
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(10, y, f"Total: ₹{final_total}")
    y -= 10 * mm
    c.setFont("Helvetica", 10)
    c.drawString(10, y, "Thank you! Visit Again!")    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

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
            if datetime.now() - last_updated < timedelta(minutes=30):
                return cache_data["weather"]

    latitude, longitude = 13.0827, 80.2707
    weather_api_url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
    try:
        response = requests.get(weather_api_url, timeout=5) 
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

            with open(WEATHER_CACHE_FILE, "w") as f:
                json.dump({"timestamp": datetime.now().isoformat(), "weather": condition}, f)

            return condition
    except requests.exceptions.RequestException:
        return 'Uncertain'  

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
    return datetime.now().strftime('%B')  

def is_weekend():
    return 1 if datetime.now().weekday() >= 5 else 0  

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
        temp_file = ranking_file + ".tmp" 
        with open(temp_file, "w") as file:
            json.dump({"last_index": index}, file)
        os.replace(temp_file, ranking_file)  
    except IOError:
        pass  

def recommend_food():
    current_time = get_time_of_day()
    current_month = get_current_month()
    current_weather = get_weather_condition()
    weekend_special = is_weekend()
    encoded_time = label_encoders["Time"].transform([current_time])[0] if current_time in label_encoders["Time"].classes_ else -1
    encoded_month = label_encoders["Month"].transform([current_month])[0] if current_month in label_encoders["Month"].classes_ else -1
    encoded_weather = label_encoders["Weather"].transform([current_weather])[0] if current_weather in label_encoders["Weather"].classes_ else -1
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


st.title("Tiffin Tales Restraunt")

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
        st.warning({item})  
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
            ("Chicken Biryani", 150, "chicken_biryani.jpg"),
            ("Biryani", 150, "biryani.jpg"),
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
                return item[1]  
    return 0  

def display_header():
    if st.button(translate_text("Cart")):
        st.session_state.page = "Cart"
        st.rerun()

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

        st.write(f"**{translate_text('SubTotal')}: ₹{total}**")
        subtotal=0
        service=0
        cgst=0
        sgst=0
        final_total=0
        total=0
        for item, details in st.session_state.cart.items():
            price = details.get('price', 0)
            quantity = details.get('quantity', 1)
            item_total = price * quantity
            subtotal += item_total
            sgst = round(subtotal * 0.025, 2) 
            cgst = round(subtotal * 0.025, 2)  
            service = round(subtotal * 0.05, 2)
            tax=sgst+cgst+service
            final_total = subtotal + tax
        st.write(f"**{translate_text("Service Cost")}: {service}**")
        st.write(f"**{translate_text("C GST")}: {cgst}**") 
        st.write(f"**{translate_text("S GST")}: {sgst}**")      
        st.write(f"**{translate_text('Total')}: ₹{final_total}**")
    else:
        st.warning(translate_text("Your cart is empty."))
    subtotal = 0

    if st.button(translate_text("Proceed to Payment 💳")):
        st.session_state.page = "Payments"
        st.rerun()
    if st.button(translate_text("Back to Menu")):
        st.session_state.page = "Menu"
        st.rerun()
    if st.button(translate_text("Generate Bill 🧾")):
        st.session_state.bill_pdf = generate_bill(st.session_state.cart, subtotal, tax, final_total)
        st.session_state.page = "Bill"
        st.rerun()
elif st.session_state.page == "Payments":
    st.title(translate_text("Secure Payment Gateway"))
    subtotal = sum(details.get('price', 0) * details.get('quantity', 1) for details in st.session_state.cart.values())
    sgst = round(subtotal * 0.025, 2) 
    cgst = round(subtotal * 0.025, 2)  
    service_charge = round(subtotal * 0.05, 2)
    tax = sgst + cgst + service_charge
    final_total = subtotal + tax
    st.markdown(f"### 🛒 {translate_text('Order Total')}: **₹{final_total}**")

    payment_method = st.selectbox(translate_text("Select Payment Method"), 
                                  [translate_text("Credit Card"), translate_text("Debit Card"), 
                                   translate_text("UPI"), translate_text("NEFT"), translate_text("QR Code")])

    if payment_method in [translate_text("Credit Card"), translate_text("Debit Card")]:
        card_type = st.selectbox(translate_text("Select Card Type"), 
                                 [translate_text("Visa"), translate_text("MasterCard"), 
                                  translate_text("RuPay"), translate_text("Amex")])
        card_number = st.text_input(translate_text("Card Number"), type="password")
        expiry_date = st.text_input(translate_text("Expiry Date (MM/YY)"))
        cvv = st.text_input(translate_text("CVV"), type="password")

    elif payment_method == translate_text("UPI"):
        upi_id = st.text_input(translate_text("UPI ID"))

    elif payment_method == translate_text("NEFT"):
        st.subheader(translate_text("Sender's Bank Details"))
        sender_name = st.text_input(translate_text("Sender’s Full Name"))
        sender_bank = st.text_input(translate_text("Sender’s Bank Name"))
        sender_account = st.number_input(translate_text("Sender’s Account Number"), step=1, format="%d")
        sender_ifsc = st.text_input(translate_text("Sender’s IFSC Code"))
        sender_branch = st.text_input(translate_text("Sender’s Branch Name"))

        st.subheader(translate_text("Receiver’s Bank Details"))
        st.text(f"{translate_text('Name')}: {translate_text('Tiffin Tales Restraunt')}")
        st.text(f"{translate_text('Receiver’s Account Number')}: 112233476566")
        st.text(f"{translate_text('Bank Name')}: {translate_text('State Bank of India')}")
        st.text(f"{translate_text('Branch Name')}: {translate_text('Vadapalani Branch')}")
        st.text(f"{translate_text('Receiver’s IFSC Code')}: SBIN0007587")

    elif payment_method == translate_text("QR Code"):
        col1, col2, col3 = st.columns([2, 2, 2])  
        with col2:
            st.image("qr_code.png", caption=translate_text("Scan the QR Code to Pay"))

    if st.button(translate_text("Pay Now 💳")):
        with st.spinner(translate_text("Processing Payment via Razorpay...")):
            time.sleep(2) 
        st.success(translate_text("✅ Payment Successful! Thank you for your purchase."))

    if st.button(translate_text("Cart")):
        st.session_state.page = "Cart"
        st.rerun()

    subtotal = 0
    for item, details in st.session_state.cart.items():
        price = details.get('price', 0)
        quantity = details.get('quantity', 1)
        item_total = price * quantity
        subtotal += item_total
        sgst = round(subtotal * 0.025, 2) 
        cgst = round(subtotal * 0.025, 2)  
        service_charge = round(subtotal * 0.05, 2)
        tax = sgst + cgst + service_charge
        final_total = subtotal + tax

    if st.button(translate_text("Generate Bill 🧾")):
        st.session_state.bill_pdf = generate_bill(st.session_state.cart, subtotal, tax, final_total)
        st.session_state.page = "Bill"
        st.rerun()

    if st.button(translate_text("Back to Menu")):
        st.session_state.page = "Menu"
        st.rerun()

elif st.session_state.page == "Bill":
    st.title(translate_text("🧾 Your Bill"))

    if st.session_state.bill_pdf:
        st.success(translate_text("✅ Bill generated successfully!"))

        bill_html = """
        <div style="font-family: monospace; border: 1px solid #000; padding: 10px; width: 300px; margin: auto; background-color: #fff; text-align: center;">
        <h3 style="margin: 5px 0; font-size: 18px; font-weight: bold;">Tiffin Tales Restraunt</h3>
        <p style="margin: 5px 0; font-size: 12px;">123 Street, 10th Main Road<br>Vadapalani, Chennai, TN - 600026</p>
        <p style="margin: 5px 0; font-size: 12px;">📞 123-456-7890</p>
        <hr style="border: 1px dashed #000;">
        
        <table style="width: 100%; font-size: 14px; text-align: left; border-collapse: collapse;">
        """

        subtotal = 0
        for item, details in st.session_state.cart.items():
            price = details.get('price', 0)
            quantity = details.get('quantity', 1)
            item_total = price * quantity
            subtotal += item_total
            bill_html += f"""
            <tr>
                <td>{item}</td>
                <td style="text-align: right;">₹{item_total:.2f}</td>
            </tr>
            """

        sgst = round(subtotal * 0.025, 2)  
        cgst = round(subtotal * 0.025, 2)  
        service_charge = round(subtotal * 0.05, 2)  

        final_total = subtotal + sgst + cgst + service_charge

        bill_html += f"""
        </table>
        <hr style="border: 1px solid #bbb;">
        <p style="text-align: right; font-size: 14px;">Subtotal: ₹{subtotal:.2f}</p>
        <p style="text-align: right; font-size: 14px;">SGST (2.5%): ₹{sgst:.2f}</p>
        <p style="text-align: right; font-size: 14px;">CGST (2.5%): ₹{cgst:.2f}</p>
        <p style="text-align: right; font-size: 14px;">Service Charge (5%): ₹{service_charge:.2f}</p>
        <hr style="border: 1px dashed #000;">
        <h3 style="text-align: right; font-size: 18px;">TOTAL: ₹{final_total:.2f}</h3>
        <hr style="border: 1px dashed #000;">
        
        <p style="text-align: left; font-size: 12px;">Paid By: Cash</p>
        <p style="text-align: left; font-size: 12px;">Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        
        <hr style="border: 1px dashed #000;">
        <p style="font-size: 12px; font-weight: bold;">Thank You for Supporting Local Business!</p>
        </div>
        """       
        components.html(bill_html, height=500) 
        script_dir = os.path.dirname(os.path.abspath(__file__))
        bills_dir = os.path.join(script_dir, "bills")
        os.makedirs(bills_dir, exist_ok=True)
        bill_html = """
        <div style="display: flex; justify-content: center; align-items: center; width: 100vw; height: 100vh; background-color: #f8f8f8;">
            <div style="font-family:monospace;border:1px solid #000;padding:10px;width:384px;height:850px;background-color:#fff;text-align:center;">
                <h3 style="margin: 5px 0; font-size: 18px; font-weight: bold;">Tiffin Tales Restraunt</h3>
                <p style="margin: 5px 0; font-size: 12px;">123 Street, 10th Main Road<br>Vadapalani, Chennai, TN - 600026</p>
                <p style="margin: 5px 0; font-size: 12px;">📞 123-456-7890</p>
                <hr style="border: 1px dashed #000;">
                <table style="width: 100%; font-size: 14px; text-align: left; border-collapse: collapse;">
        """

        subtotal = 0
        for item, details in st.session_state.cart.items():
            price = details.get('price', 0)
            quantity = details.get('quantity', 1)
            item_total = price * quantity
            subtotal += item_total
            bill_html += f"""
                    <tr>
                        <td>{item}</td>
                        <td style="text-align: right;">₹{item_total:.2f}</td>
                    </tr>
            """

        sgst = round(subtotal * 0.025, 2)  
        cgst = round(subtotal * 0.025, 2)  
        service_charge = round(subtotal * 0.05, 2)  

        final_total = subtotal + sgst + cgst + service_charge

        bill_html += f"""
            </table>
            <hr style="border: 1px solid #bbb;">
            <p style="text-align: right; font-size: 14px;">Subtotal: ₹{subtotal:.2f}</p>
            <p style="text-align: right; font-size: 14px;">SGST (2.5%): ₹{sgst:.2f}</p>
            <p style="text-align: right; font-size: 14px;">CGST (2.5%): ₹{cgst:.2f}</p>
            <p style="text-align: right; font-size: 14px;">Service Charge (5%): ₹{service_charge:.2f}</p>
            <hr style="border: 1px dashed #000;">
            <h3 style="text-align: right; font-size: 18px;">TOTAL: ₹{final_total:.2f}</h3>
            <hr style="border: 1px dashed #000;">
            <p style="text-align: left; font-size: 12px;">Paid By: Cash</p>
            <p style="text-align: left; font-size: 12px;">Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            <hr style="border: 1px dashed #000;">
            <p style="font-size: 12px; font-weight: bold;">Thank You for Supporting Local Business!</p>
            </div>
        </div>
        """
        image_filename = f"bill_{int(time.time())}.png"
        image_path = os.path.join(bills_dir, image_filename)

        try:
            hti = Html2Image(browser='chrome', output_path=bills_dir, temp_path=bills_dir)
            hti.browser.flags = ["--headless=new", "--disable-gpu", "--no-sandbox"]
            hti.screenshot(html_str=bill_html, save_as=image_filename,size=(500, 1200))
            print("Using html2image for screenshot")
        except Exception as e:
            print("html2image failed, using Selenium:", e)
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")

            driver = webdriver.Chrome(options=chrome_options)
            driver.get("data:text/html;charset=utf-8," + bill_html)
            driver.save_screenshot(image_path)
            driver.quit()

        time.sleep(2)

        def generate_pdf(image_path):
            if not os.path.exists(image_path):
                print("Error: Image file not found!")
                return None
            buffer = BytesIO()
            img = Image.open(image_path)
            img_width, img_height = img.size  
            print(f"Image loaded: {image_path} | Size: {img_width}x{img_height}")
            pdf = canvas.Canvas(buffer, pagesize=portrait((img_width, img_height)))
            pdf.drawImage(image_path, 0, 0, width=img_width, height=img_height)
            pdf.showPage()
            pdf.save()
            buffer.seek(0)
            return buffer

        if not os.path.exists(image_path):
            st.error(f"Error: Bill image not found! Expected path: {image_path}")
            pdf_buffer = None
        else:
            pdf_buffer = generate_pdf(image_path)
        if pdf_buffer:
            st.download_button(translate_text("Download Bill as PDF"), pdf_buffer, file_name="bill.pdf", mime="application/pdf")
        if st.button(translate_text("Back to Cart")):
            st.session_state.page = "Cart"
            st.rerun()

        if st.button(translate_text("Back to Menu")):
            st.session_state.page = "Menu"
            st.rerun()
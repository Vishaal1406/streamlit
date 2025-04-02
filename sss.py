from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
bills_dir = os.path.join(script_dir, "bills")
os.makedirs(bills_dir, exist_ok=True)

bill_html = "<html><body><h1>Test Bill</h1></body></html>"  
image_filename = os.path.join(bills_dir, f"bill_{int(time.time())}.png")

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

driver = webdriver.Chrome(options=chrome_options)
driver.get("data:text/html;charset=utf-8," + bill_html)

# Screenshot and save
driver.save_screenshot(image_filename)
driver.quit()

print("Image created at:", image_filename)
print("Exists:", os.path.exists(image_filename))
from html2image import Html2Image
import os
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
bills_dir = os.path.join(script_dir, "bills")
os.makedirs(bills_dir, exist_ok=True)

bill_html = "<html><body><h1>Test Bill</h1></body></html>"  
image_filename = f"bill_{int(time.time())}.png"

hti = Html2Image(browser='chrome')

# Manually add the new headless mode flag
hti.browser.flags = ["--headless=new", "--disable-gpu", "--no-sandbox"]

hti.screenshot(html_str=bill_html, save_as=image_filename)

image_path = os.path.join(bills_dir, image_filename)
print("Image created at:", image_path)
print("Exists:", os.path.exists(image_path))
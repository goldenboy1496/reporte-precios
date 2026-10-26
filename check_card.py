from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import re

options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("user-agent=Mozilla/5.0")

driver = webdriver.Chrome(options=options)
try:
    driver.get("https://www.lacuracaonline.com/elsalvador/celulares-samsung")
    time.sleep(4)
    cards = driver.find_elements(By.CSS_SELECTOR, ".product-item-info, .product-item, .item.product")
    for c in cards:
        t = c.text.strip()
        if "graygreen" in t.lower() or "a37" in t.lower():
            print("--- CARD FOUND ---")
            print(t)
            matches = re.findall(r'\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?)', t)
            print("Matches:", matches)
finally:
    driver.quit()

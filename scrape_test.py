from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

options = Options()
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--window-size=1920,1080")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

driver = webdriver.Chrome(options=options)
try:
    url = "https://www.lacuracaonline.com/elsalvador/samsung-galaxy-a37-8gb-256gb-awesome-white-472465100012/p"
    driver.get(url)
    time.sleep(5)
    print("PAGE TITLE:", driver.title)
    
    # Check all elements with price classes or text containing $
    price_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
    for el in price_elements[:20]:
        t = el.text.strip()
        tag = el.tag_name
        parent_class = el.find_element(By.XPATH, "..").get_attribute("class")
        print(f"[{tag}] class={el.get_attribute('class')} | parent_class={parent_class} -> '{t}'")
finally:
    driver.quit()

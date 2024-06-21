import asyncio
import json
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import re
import playwright._impl._errors  # Import Playwright errors for handling TimeoutError


SBR_WS_CDP = 'You credentials of Bright Data'
BASE_URL = "https://zoopla.co.uk"
LOCATION = "Oxford"

def extract_picture(picture_section):
    picture_sources = []
    for picture in picture_section.find_all("picture"):
        for source in picture.find_all('source'):
            source_type = source.get("type", "").split("/")[-1]
            pic_url = source.get("srcset", "").split(",")[0].split(" ")[0]

            if source_type == "webp" and '1024' in pic_url:
                picture_sources.append(pic_url)
    return picture_sources

# def extract_property_details(main_div):
    details = {}

    # Extract Freehold information
    freehold_div = main_div.find('div', class_='jc64990 jc64994 _194zg6tb')
    if freehold_div:
        details["Tenure"] = freehold_div.text.strip()
    else:
        details["Tenure"] = "Unknown"

    # Extract Price
    price_div = main_div.find('p', class_='_194zg6t4 _18cwln10', attrs={'data-testid': 'price'})
    if price_div:
        price_value = price_div.text.strip().strip("£")
        details["Price"] = price_value
    else:
        details["Price"] = "Unknown"

    # Extract Title
    title_div = main_div.find('p', class_='_194zg6t7 _18cwln11', attrs={'data-testid': 'title-label'})
    if title_div:
        title_value = title_div.text.strip()
        details["Title"] = title_value
    else:
        details["Title"] = "Unknown"

    # Extract Address
    address_div = main_div.find('address', class_='_18cwln12 _194zg6t8', attrs={'data-testid': 'address-label'})
    if address_div:
        address_value = address_div.text.strip()
        details["Address"] = address_value
    else:
        details["Address"] = "Unknown"

    # Initialize variables for bedrooms, bathrooms, and reception
    bedrooms = None
    bathrooms = None
    reception = None

    # Find all div tags with class "jc64990 jc64995 _194zg6t8"
    div_tags = main_div.find_all('div', class_='jc64990 jc64995 _194zg6t8')

    # Iterate through each div tag
    for div_tag in div_tags:
        # Extract the text content
        text = div_tag.get_text(strip=True)

        # Check for bedrooms
        if 'beds' in text:
            match = re.search(r'(\d+)\s+beds', text)
            if match:
                bedrooms = match.group(1)

        # Check for bathrooms
        elif 'baths' in text:
            match = re.search(r'(\d+)\s+baths', text)
            if match:
                bathrooms = match.group(1)

        # Check for reception
        elif 'reception' in text:
            match = re.search(r'(\d+)\s+reception', text)
            if match:
                reception = match.group(1)

    # Add bedrooms, bathrooms, and reception to details dictionary
    details["Bedrooms"] = bedrooms if bedrooms else "Unknown"
    details["Bathrooms"] = bathrooms if bathrooms else "Unknown"
    details["Reception"] = reception if reception else "Unknown"

    return json.dumps(details)

def extract_floor_plan(soup):
    plan = {}
    floor_plan = soup.find(name='div', attribute={"data-testid": "floorplan-thumbnail-0"})
    if floor_plan:
        floor_plan_src = floor_plan.find('picture').find('source')['srcset']
        plan['floor_plan'] = floor_plan_src.split(' ')[0]

    return plan

async def run(pw):
    print('Connecting to Scraping Browser...')
    browser = await pw.chromium.connect_over_cdp(SBR_WS_CDP)

    try:
        page = await browser.new_page()
        print(f'Connected! Navigating to {BASE_URL}...')
        await page.goto(BASE_URL)

        # Enter location in the search bar and press enter to search
        try:
            await page.fill('input[name="autosuggest-input"]', LOCATION, timeout=60000)
        except playwright._impl._errors.TimeoutError as e:
            print(f"Timeout while filling location: {e}")

        await page.keyboard.press('Enter')
        print('Waiting for search results..')
        await page.wait_for_load_state('load')

        content = await page.inner_html('div[data-testid="regular-listings"]')

        soup = BeautifulSoup(content, features="html.parser")
        
        for idx, div in enumerate(soup.find_all(name='div', class_="dkr2t83")):
            link = div.find('a')['href']
            data = {
                "address": div.find('address').text.strip(),
                "title": div.find("h2").text.strip(),
                "link": BASE_URL + link,
            }
            # Navigate to listing page
            print('Navigating to listing page', link)
            await page.goto(data['link'])
            await page.wait_for_load_state('load')
            content = await page.inner_html('div[data-testid="listing-details-page"]')
            soup = BeautifulSoup(content, features="html.parser")

            picture_section = soup.find(name='section', attrs={"aria-labelledby": "listing-gallery-heading"})
            picture = extract_picture(picture_section)
            data['pictures'] = picture

            # property_details = soup.select_one('div[class="_14bi3x331"]')
            # property_details = extract_property_details(property_details)

            floor_plan = extract_floor_plan(soup)
            data.update(floor_plan)
            # data.update(json.loads(property_details))

            print(data)
            break

        print('Navigated! Scraping page content...')
    finally:
        await browser.close()

async def main():
    async with async_playwright() as playwright:
        await run(playwright)

if __name__ == '__main__':
    asyncio.run(main())

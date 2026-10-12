import os
import re
import asyncio
from playwright.async_api import async_playwright
import httpx

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "las-palmas-lote-jiyda-98234")
STATE_FILE = "last_lote.txt"

async def send_push_notification(title: str, message: str):
    url = f"https://ntfy.sh/{NTFY_TOPIC}"
    headers = {"Title": title, "Priority": "high", "Tags": "rotating_light"}
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, data=message, headers=headers, timeout=10)
            print("Push notification sent via ntfy.sh.")
        except Exception as e:
            print(f"Notification error: {e}")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="es-ES"
        )
        page = await context.new_page()

        try:
            print("Navigating to Extranjería initial page...")
            await page.goto("https://icp.administracionelectronica.gob.es/icpplustie/citar?p=35&locale=es", timeout=60000, wait_until="domcontentloaded")
            
            print("Selecting Oficina and waiting for acinfo transition...")
            # Selecting the office submits the form and transitions naturally to the acinfo page
            await page.get_by_label("Selecciona Oficina:").select_option("1")
            await page.wait_for_load_state("domcontentloaded")
            
            print("Selecting Police Procedure 4036 on acinfo page...")
            await page.get_by_label("TRÁMITES POLICÍA NACIONAL").select_option("4036")
            
            print("Clicking Aceptar...")
            await page.get_by_role("button", name="Aceptar").click()
            await page.wait_for_load_state("domcontentloaded")

            # Extract heading text showing the lote
            heading = page.locator("h3", has_text="EL ÚLTIMO LOTE RECIBIDO")
            await heading.wait_for(timeout=15000)
            lote_text = (await heading.inner_text()).strip()
            print(f"Raw text found: {lote_text}")

            match = re.search(r"\b\d+\b", lote_text)
            if not match:
                raise ValueError("Could not parse numeric lote number from string.")
            
            current_lote = match.group(0)
            print(f"Current Lote Number: {current_lote}")

        except Exception as e:
            print(f"❌ Error checking Cita Lote: {e}")
            await browser.close()
            return

        await browser.close()

        # Read previous state
        last_lote = ""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                last_lote = f.read().strip()

        print(f"Previous recorded lote: '{last_lote}'")

        if current_lote != last_lote:
            title = f"Nuevo Lote Detected: {current_lote}"
            msg = f"Oficina: Las Palmas\nNuevo Lote: {current_lote}\nAnterior: {last_lote if last_lote else 'N/A'}"
            print(msg)
            await send_push_notification(title, msg)

            with open(STATE_FILE, "w") as f:
                f.write(current_lote)
        else:
            print("No change in lote number.")

if __name__ == "__main__":
    asyncio.run(main())
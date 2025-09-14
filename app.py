
from fastapi import FastAPI, UploadFile, File, HTTPException
import os
import re
import fitz  # PyMuPDF
from PIL import Image
import io
import pytesseract
import requests
import json

app = FastAPI(title="IBAN Extraction API", version="0.2.0")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

IBAN_PATTERN = re.compile(r'\b[A-Z]{2}[0-9]{2}(?:[0-9A-Z\s\-]{10,34})\b')

IBANVALIDATION_API_URL = "https://api.ibanvalidationapi.com/iban/details/{}"
NINJA_API_URL = "https://api.api-ninjas.com/v1/iban?iban={}"
NINJA_API_KEY = "ULNDmqIkPq/HWjeMvV8AoQ==b6MjTR2BQhOSYgT7"

# ==== Helpers ====

def clean_iban(iban: str) -> str:
    iban = iban.replace(" ", "").replace("-", "")
    cleaned = ""
    for ch in iban:
        if re.match(r"[A-Z0-9]", ch):
            cleaned += ch
        else:
            break
    return cleaned[:34]

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
            else:
                # إذا النص غير متاح، استخدم OCR
                pix = page.get_pixmap(dpi=400)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text += pytesseract.image_to_string(img, lang='fra') + "\n"
    except Exception as e:
        print(f"Erreur PDF: {e}")
    return text

def get_ibanvalidation_details(iban):
    try:
        response = requests.get(IBANVALIDATION_API_URL.format(iban))
        data = response.json()
        if response.status_code == 200 and data.get("valid", False):
            return data
        return None
    except Exception as e:
        print(f"Erreur IBANValidationAPI pour {iban}: {e}")
        return None

def get_ninja_account_number(iban):
    headers = {"X-Api-Key": NINJA_API_KEY}
    try:
        response = requests.get(NINJA_API_URL.format(iban), headers=headers)
        data = response.json()
        return data.get("account_number")
    except Exception as e:
        print(f"Erreur Ninja API pour {iban}: {e}")
        return None

# ==== Routes ====

@app.get("/")
async def root():
    return {"message": "API IBAN جاهزة للاستخدام! استخدم /extract_ibans لرفع ملفات PDF."}

@app.post("/extract_ibans")
async def extract_ibans(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="يرجى رفع ملف PDF فقط.")

    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    text = extract_text_from_pdf(pdf_path)
    raw_ibans = IBAN_PATTERN.findall(text)
    cleaned_ibans = list(dict.fromkeys([clean_iban(i) for i in raw_ibans]))

    valid_ibans = []
    ninja_accounts = []

    for iban in cleaned_ibans:
        details = get_ibanvalidation_details(iban)
        if details:
            valid_ibans.append(details)
            acc_number = get_ninja_account_number(iban)
            ninja_accounts.append({"iban": iban, "account_number": acc_number})

    return {
        "all_ibans": cleaned_ibans,
        "valid_ibans": valid_ibans,
        "ninja_accounts": ninja_accounts
    }

# ==== Main ====

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os, re, fitz, io, requests
from PIL import Image
import pytesseract

app = FastAPI(title="IBAN Extraction API")

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

IBAN_PATTERN = re.compile(r'\b[A-Z]{2}[0-9]{2}(?:[0-9A-Z\s\-]{10,34})\b')
IBANVALIDATION_API_URL = "https://api.ibanvalidationapi.com/iban/details/{}"
NINJA_API_URL = "https://api.api-ninjas.com/v1/iban?iban={}"
NINJA_API_KEY = "ULNDmqIkPq/HWjeMvV8AoQ==b6MjTR2BQhOSYgT7"

def clean_iban(iban: str) -> str:
    iban = iban.replace(" ", "").replace("-", "")
    return ''.join([ch for ch in iban if ch.isalnum()])[:34]

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
            else:
                pix = page.get_pixmap(dpi=400)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text += pytesseract.image_to_string(img, lang='fra') + "\n"
    except Exception as e:
        print(f"Erreur PDF: {e}")
    return text

def get_ibanvalidation_details(iban):
    try:
        r = requests.get(IBANVALIDATION_API_URL.format(iban))
        data = r.json()
        if r.status_code == 200 and data.get("valid", False):
            return data
        return None
    except:
        return None

def get_ninja_account_number(iban):
    try:
        r = requests.get(NINJA_API_URL.format(iban), headers={"X-Api-Key": NINJA_API_KEY})
        return r.json().get("account_number")
    except:
        return None

@app.post("/extract_ibans")
async def extract_ibans(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="الملف يجب أن يكون PDF")

    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(pdf_path, "wb") as f:
        content = await file.read()
        f.write(content)

    text = extract_text_from_pdf(pdf_path)
    raw_ibans = IBAN_PATTERN.findall(text)
    cleaned_ibans = list(dict.fromkeys([clean_iban(i) for i in raw_ibans]))

    all_ibans = cleaned_ibans
    valid_ibans = []
    ninja_accounts = []

    for iban in cleaned_ibans:
        details = get_ibanvalidation_details(iban)
        if details:
            valid_ibans.append(details)
            acc_number = get_ninja_account_number(iban)
            ninja_accounts.append({"iban": iban, "account_number": acc_number})

    return JSONResponse({
        "all_ibans": all_ibans,
        "valid_ibans": valid_ibans,
        "ninja_accounts": ninja_accounts
    })

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from io import BytesIO
import sys
sys.path.insert(0, '/content')

try:
    from paddleocr import PaddleOCR
    _ocr_available = True
except ImportError:
    _ocr_available = False

from ai.classifier import FoodClassifier
from dotenv import load_dotenv
load_dotenv('/content/.env')

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
classifier = FoodClassifier()

ocr = None
if _ocr_available:
    ocr = PaddleOCR(use_angle_cls=True, lang='en')

class DishClassificationRequest(BaseModel):
    dish: str

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/classify")
async def classify_dish_endpoint(request: DishClassificationRequest):
    classification = classifier.classify_dish(request.dish)
    return classification

@app.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    if not _ocr_available or ocr is None:
        raise HTTPException(status_code=501, detail="OCR no disponible")
    try:
        contents = await file.read()
        result = ocr.ocr(contents, cls=True)
        texts = []
        for line_group in result:
            if line_group:
                for line in line_group:
                    texts.append(line[1][0])
        return {"text": "\n".join(texts), "dishes": texts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

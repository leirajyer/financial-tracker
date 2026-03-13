import os
import json
import base64
from fastapi import APIRouter, Request, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import Category

router = APIRouter(prefix="/receipt", tags=["receipt"])


def get_gemini_client():
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.0-flash")


@router.post("/scan")
async def scan_receipt(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = request.state.user

    # Load user's categories for context
    categories = db.query(Category).filter(
        or_(Category.owner_id == user.id, Category.owner_id == None)
    ).all()
    category_names = [c.name for c in categories]

    # Read image bytes
    image_bytes = await file.read()
    if not image_bytes:
        return JSONResponse({"error": "Empty file"}, status_code=400)

    # Encode as base64
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    mime_type = file.content_type or "image/jpeg"

    prompt = f"""You are a receipt scanning assistant for a personal finance app.
Analyze this receipt image and extract the following information.

The user's available categories are: {', '.join(category_names)}

Return ONLY a valid JSON object with these exact keys (no markdown, no explanation):
{{
  "total": <final amount paid as a number, e.g. 450.00>,
  "merchant": "<store or vendor name>",
  "date": "<date in YYYY-MM-DD format, or today if not visible>",
  "category": "<best matching category from the list above>",
  "description": "<short 1-line description like 'Groceries at SM Supermarket'>",
  "type": "expense"
}}

If you cannot read the receipt clearly, return:
{{"error": "Could not read receipt clearly"}}"""

    try:
        model = get_gemini_client()
        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": image_b64}
        ])

        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        return JSONResponse(data)

    except json.JSONDecodeError:
        return JSONResponse({"error": "AI returned unreadable response"}, status_code=422)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

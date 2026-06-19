import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Knowledge Filter API - Production V2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("خطأ حرج: مفاتيح اتصال Supabase غير موجودة!")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class LinkInput(BaseModel):
    url: str
    user_id: str = "1"

# نموذج استلام بيانات السياق الحالي للمؤشر
class RecommendationInput(BaseModel):
    user_id: str = "1"
    available_time: int
    environment: str

def analyze_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code != 200:
            return "رابط خارجي (تعذر الكشط)", 5, "article"

        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else "مقالة غير معنونة"

        for junk in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            junk.extract()

        clean_text = soup.get_text()
        words = re.findall(r'\b\w+\b', clean_text)
        word_count = len(words)

        read_time = round(word_count / 200)
        content_type = "video" if "youtube.com" in url or "youtu.be" in url else "article"

        return title, max(1, read_time), content_type
    except Exception:
        return "رابط محمي أو خارجي", 5, "article"

@app.post("/add-link")
async def add_link(item: LinkInput):
    title, read_time, content_type = analyze_url(item.url)

    link_data = {
        "user_id": item.user_id,
        "url": item.url,
        "title": title,
        "estimated_read_time": read_time,
        "content_type": content_type,
        "status": "unread"
    }

    try:
        supabase.table("links").insert(link_data).execute()
        return {"status": "success", "data": link_data}
    except Exception as e:
        error_str = str(e)
        # التقاط قيد تكرار البيانات الصادر من قاعدة البيانات لمنع الكراش
        if "unique_user_url" in error_str or "42501" in error_str or "23505" in error_str:
            return {"status": "duplicate", "message": "هذا الرابط موجود في مصفاتك بالفعل!"}

        raise HTTPException(status_code=500, detail=f"فشل الحفظ في قاعدة البيانات: {error_str}")

@app.post("/get-recommendations")
async def get_recommendations(criteria: RecommendationInput):
    try:
        # جلب الروابط غير المقروءة الخاصة بالمستخدم من Supabase
        response = supabase.table("links")\
            .select("*")\
            .eq("user_id", criteria.user_id)\
            .eq("status", "unread")\
            .execute()

        all_links = response.data
        filtered_links = []

        for link in all_links:
            # القيد الأول: الوقت المقدر للقراءة يجب أن يكون أقل من أو يساوي الوقت المتاح
            if link["estimated_read_time"] <= criteria.available_time:
                # القيد الثاني: بيئة صاخبة بدون سماعات تمنع الفيديوهات
                if criteria.environment == "noisy_no_headphones" and link["content_type"] == "video":
                    continue
                filtered_links.append(link)

        return {"status": "success", "data": filtered_links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل جلب الاقتراحات: {str(e)}")

import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 1. تحميل متغيرات البيئة من ملف .env المحلي (تلقائياً في البيئة المحلية)
load_dotenv()

app = FastAPI(title="Knowledge Filter API - Secure Version")

# 2. تفعيل الـ CORS لتسمح لواجهة Vercel بالاتصال بالـ API بأمان
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # في الإنتاج الفعلي، ضع رابط موقعك على Vercel هنا بدلاً من "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. جلب بيانات الاتصال بـ Supabase بأمان من البيئة (Environment Variables)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# التحقق من وجود المفاتيح حتى لا يتعطل السيرفر بدون سبب واضح
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("خطأ: مفاتيح اتصال Supabase غير موجودة في متغيرات البيئة!")

# تهيئة عميل Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 4. نموذج البيانات المستقبلة من الواجهة
class LinkInput(BaseModel):
    url: str
    user_id: str = "1"

# 5. دالة الكشط وحساب وقت القراءة تلقائياً
def analyze_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)

        if response.status_code != 200:
            return "رابط خارجي (تعذر الكشط)", 5, "article"

        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string.strip() if soup.title else "مقالة غير معنونة"

        # تنظيف الـ HTML من العناصر غير النصية
        for junk in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            junk.extract()

        clean_text = soup.get_text()
        words = re.findall(r'\b\w+\b', clean_text)
        word_count = len(words)

        # حساب الوقت (عدد الكلمات / 200 كلمة بالدقيقة)
        read_time = round(word_count / 200)

        # تحديد النوع تلقائياً
        content_type = "video" if "youtube.com" in url or "youtu.be" in url else "article"

        return title, max(1, read_time), content_type
    except Exception:
        return "رابط خارجي أو محمي", 5, "article"

# 6. الـ Endpoint الرئيسي لحفظ الروابط
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
        # إدخال البيانات في جدول links بـ Supabase
        supabase.table("links").insert(link_data).execute()
        return {"status": "success", "data": link_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"فشل الحفظ في قاعدة البيانات: {str(e)}")

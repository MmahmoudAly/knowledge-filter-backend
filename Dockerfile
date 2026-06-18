# 1. استخدام نسخة بايثون رسمية وخفيفة
FROM python:3.10-slim

# 2. تحديد المجلد داخل السيرفر الافتراضي
WORKDIR /code

# 3. نسخ ملف المكتبات وتثبيتها
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 4. نسخ باقي ملفات المشروع (.env لن يرتفع إذا كنت قد أضفته للـ .gitignore)
COPY . .

# 5. تشغيل السيرفر على بورت 7860 (البورت الإجباري لـ Hugging Face)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]

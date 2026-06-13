from fastapi import FastAPI, Depends, HTTPException
import uvicorn
from supabase import create_client, Client
from pydantic import BaseModel

app = FastAPI()

supabase_url: str = "YOUR_SUPABASE_URL"
supabase_key: str = "YOUR_SUPABASE_KEY"

# Supabase client initialization
db = create_client(supabase_url, supabase_key)

class LinkInput(BaseModel):
    url: str
    user_id: str = "1"

@app.post("/add-link")
async def add_link(link_input: LinkInput):
    try:
        # Extract the page title and clean text from HTML
        response = requests.get(link_input.url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string
        cleaned_text = ' '.join(soup.stripped_strings).strip()
        
        # Count words using RegEx
        import re
        words = len(re.findall(r'\w+', cleaned_text))
        
        # Estimate read time (total words / 200)
        read_time = words // 200
        
        # Auto-detect content type ('video' if 'youtube' in URL, else 'article')
        content_type = 'video' if 'youtube' in link_input.url.lower() else 'article'
        
        # Insert data into the Supabase table
        result = db.from_('links').insert({
            "url": link_input.url,
            "title": title,
            "cleaned_text": cleaned_text,
            "words": words,
            "read_time": read_time,
            "content_type": content_type,
            "user_id": link_input.user_id
        }).execute()
        
        if result.errors:
            raise HTTPException(status_code=500, detail="Database insert failed")
        
        return {"message": "Link added successfully"}
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch URL: {e}")
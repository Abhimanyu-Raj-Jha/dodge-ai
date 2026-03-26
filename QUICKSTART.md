# 🚀 Dodge AI — Quick Start Guide

## Prerequisites

- Python 3.8+
- OpenRouter API key (get it free at https://openrouter.ai)

---

## Local Development (5 minutes)

### 1️⃣ Get Your OpenRouter API Key

1. Go to https://openrouter.ai
2. Sign up (free)
3. Go to Settings → API Keys
4. Create a new key and copy it

### 2️⃣ Set Up Environment

```bash
cd /Users/abhimanyurajjha/Downloads/files
export OPENROUTER_API_KEY="your_api_key_here"
```

Replace `your_api_key_here` with your actual OpenRouter API key.

### 3️⃣ Install Dependencies

```bash
pip install flask
```

(Flask is usually already installed)

### 4️⃣ Run the App

```bash
python3 app.py
```

### 5️⃣ Open in Browser

Visit: **http://localhost:5001**

---

## Hosting on Netlify or Vercel

⚠️ **Important**: This is a **Flask backend + frontend SPA**. Netlify and Vercel are primarily for static sites and serverless functions.

### ❌ Why Not Netlify/Vercel Directly?

- Netlify/Vercel don't support persistent Flask servers
- They're optimized for static sites and serverless functions
- SQLite needs persistence (not ideal for serverless)

### ✅ Better Hosting Options

#### **Option 1: Render (Recommended - Easiest)**

1. Push your code to GitHub
2. Go to https://render.com
3. Create new Web Service
4. Connect your GitHub repo
5. Set environment:
   - Runtime: Python 3.11
   - Build command: `pip install flask`
   - Start command: `python app.py`
6. Add environment variable:
   - Key: `OPENROUTER_API_KEY`
   - Value: `your_key`
7. Deploy! 🚀

#### **Option 2: Heroku**

```bash
# Install Heroku CLI
brew install heroku

# Login
heroku login

# Create app
heroku create your-app-name

# Set environment variable
heroku config:set OPENROUTER_API_KEY="your_key"

# Deploy
git push heroku main
```

#### **Option 3: Railway**

1. Go to https://railway.app
2. Connect GitHub
3. Deploy from repo
4. Set `OPENROUTER_API_KEY` environment variable
5. Done! 🎉

#### **Option 4: PythonAnywhere**

1. Sign up at https://www.pythonanywhere.com
2. Upload your files
3. Configure Flask web app
4. Set environment variable via Web tab
5. Reload

---

## If You Still Want Netlify/Vercel

You'd need to refactor this into a serverless architecture:

### Convert to Serverless (Advanced)

```
netlify/
  functions/
    chat.js          # Serverless function
    graph.js         # Serverless function
frontend/
  index.html         # Static site
  style.css
  app.js
```

But this requires:
- Splitting Flask into serverless functions
- Moving SQLite to a cloud database (Firebase, PostgreSQL, etc.)
- Significant refactoring (~4-6 hours of work)

**Not recommended unless you have specific requirements.**

---

## Docker Deployment (Production-Ready)

A `Dockerfile` is already included in your project! 

### Build Docker Image

```bash
docker build -t dodge-ai .
```

### Run Locally

```bash
docker run -p 5001:5001 \
  -e OPENROUTER_API_KEY="your_key" \
  dodge-ai
```

### Deploy to Cloud Run (Google)

```bash
gcloud run deploy dodge-ai \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars OPENROUTER_API_KEY=your_key
```

---

## Environment Variables

Create a `.env` file (never commit to Git):

```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
PORT=5001
```

Load it in your shell:

```bash
source .env
python3 app.py
```

Or use `python-dotenv`:

```bash
pip install python-dotenv
```

Then in `app.py`:

```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Production Checklist

- [ ] Use a production WSGI server (Gunicorn, not Flask dev server)
- [ ] Set `debug=False` in app.py
- [ ] Use HTTPS only
- [ ] Rate-limit API endpoints
- [ ] Set CORS origins properly (not `*`)
- [ ] Monitor API costs (OpenRouter)
- [ ] Back up SQLite database regularly
- [ ] Set up error logging (Sentry, LogRocket, etc.)

---

## Recommended Production Setup

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 app:app
```

Then deploy to Render/Railway/Heroku.

---

## Troubleshooting

### Error: "OPENROUTER_API_KEY not set"

```bash
export OPENROUTER_API_KEY="your_key"
python3 app.py
```

### Error: "Port 5001 already in use"

```bash
lsof -i :5001
kill -9 <PID>
```

### Error: "No such table: business_partners"

Run ingest first:

```bash
python3 ingest.py
```

### LLM Responses Slow

- Mistral/Llama models take 3-5 seconds
- Switch to faster model in `llm.py` if needed
- OpenRouter may throttle free accounts

### Graph Not Loading

- Check browser console for errors
- Make sure `/api/graph` returns 200 OK
- Verify SQLite database exists (`data.db`)

---

## Useful Commands

```bash
# Check if Flask is running
curl http://localhost:5001/api/health

# View real-time logs
tail -f app.log

# Rebuild database
rm data.db && python3 ingest.py

# Run with custom port
PORT=8000 python3 app.py
```

---

## Summary

| Platform | Difficulty | Cost | Best For |
|----------|-----------|------|----------|
| **Local** | ⭐ | Free | Development |
| **Render** | ⭐⭐ | $7+/mo | Best option |
| **Railway** | ⭐⭐ | $5/mo | Simple |
| **Heroku** | ⭐⭐ | $7+/mo | Classic |
| **Docker** | ⭐⭐⭐ | $0-20/mo | Production |
| **Netlify/Vercel** | ⭐⭐⭐⭐⭐ | Complex | Not recommended |

---

**Happy deploying! 🚀**

For questions: Check the GitHub repo or ask Claude!

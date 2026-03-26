# 🌐 Deployment Guide — Dodge AI

## Quick Answer: Netlify vs Vercel

❌ **Netlify and Vercel won't work directly** because:
- They're designed for **static sites** (HTML, CSS, JS)
- They don't support **persistent Flask servers**
- SQLite database can't be stored on them
- Your frontend needs a **backend API running 24/7**

---

## ✅ Best Deployment Options (Ranked)

### 🥇 **#1: Render.com (EASIEST)**

**Perfect for:** Running Flask apps without code changes

**Steps:**

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git push origin main
   ```

2. **Go to https://render.com**
   - Click "New +"
   - Select "Web Service"
   - Connect GitHub account
   - Select your repo

3. **Configure:**
   - **Name:** dodge-ai
   - **Runtime:** Python 3.11
   - **Build Command:** `pip install -r requirements.txt && python3 ingest.py`
   - **Start Command:** `gunicorn -w 4 -b 0.0.0.0:$PORT app:app`
   - **Environment:** Add `OPENROUTER_API_KEY=your_key`

4. **Deploy:** Click "Create Web Service"

✅ Done! Your app is live at `https://dodge-ai.onrender.com`

**Cost:** $7/month (free tier: 15-min inactivity timeout)

---

### 🥈 **#2: Railway.app (SIMPLE)**

**Perfect for:** Fast deployment with minimal config

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub"
4. Connect repo
5. Set `OPENROUTER_API_KEY` in Variables
6. Deploy!

**Cost:** Pay as you go (~$2-5/month for hobby use)

---

### 🥉 **#3: Heroku (CLASSIC)**

**Perfect for:** If you're familiar with Heroku

1. **Install Heroku CLI:**
   ```bash
   brew install heroku
   heroku login
   ```

2. **Create and deploy:**
   ```bash
   heroku create dodge-ai
   heroku config:set OPENROUTER_API_KEY="your_key"
   git push heroku main
   ```

**Cost:** Starting at $7/month (or free trials)

---

### 🚀 **#4: Google Cloud Run (ADVANCED)**

**Perfect for:** Production-grade, scalable

1. **Install Google Cloud CLI**
2. **Deploy:**
   ```bash
   gcloud run deploy dodge-ai \
     --source . \
     --platform managed \
     --region us-central1 \
     --set-env-vars OPENROUTER_API_KEY=your_key
   ```

**Cost:** Free tier, then pay per request

---

## ❓ Can I Use Netlify/Vercel?

**Technically yes, but it's complicated:**

### Option A: Convert to Serverless (Hard)

Move backend logic to serverless functions:

```
netlify/
  functions/
    api.js       # Handles /api/chat, /api/graph, etc.
    db.js        # Database layer
```

Requires:
- Rewriting Flask into Node.js functions
- Moving SQLite to Firebase or PostgreSQL
- Complete refactor (~8 hours)

### Option B: Netlify Functions + External Backend

1. **Host backend on Render/Railway**
2. **Deploy frontend only on Netlify**
3. **Update CORS settings**

More steps but possible.

**Not recommended unless you have specific reasons.**

---

## Step-by-Step: Deploy to Render (Easiest)

### Prerequisites
- GitHub account (push your code there)
- OpenRouter API key
- Render account (free signup)

### 1. Prepare Your GitHub Repo

```bash
cd /Users/abhimanyurajjha/Downloads/files
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/dodge-ai.git
git push -u origin main
```

### 2. Create Render Account

- Go to https://render.com
- Sign up (free)

### 3. Create Web Service

1. Click "New +" → "Web Service"
2. Connect GitHub (authorize)
3. Select your `dodge-ai` repo
4. Fill in:
   - **Name:** dodge-ai
   - **Runtime:** Python 3.11
   - **Build Command:**
     ```
     pip install -r requirements.txt && python3 ingest.py
     ```
   - **Start Command:**
     ```
     gunicorn -w 4 -b 0.0.0.0:$PORT app:app
     ```

### 4. Add Environment Variable

- **Key:** OPENROUTER_API_KEY
- **Value:** `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`

### 5. Create Service

Click "Create Web Service" and wait 2-3 minutes.

### 6. Get Your URL

Render will give you: `https://dodge-ai.onrender.com`

---

## Quick Deployment Commands

### For Render
```bash
git add .
git commit -m "Deploy"
git push origin main
# Render auto-deploys on push
```

### For Railway
```bash
npm install -g railway
railway link
railway up
```

### For Heroku
```bash
heroku create dodge-ai
git push heroku main
heroku open
```

---

## Files Needed for Deployment

✅ Already created in your project:

- `requirements.txt` - Python dependencies
- `render.yaml` - Render configuration
- `app.py` - Flask app
- `llm.py` - LLM integration
- `graph.py` - Graph building
- `ingest.py` - Database ingest
- `Dockerfile` - Docker support
- `index.html` - Frontend

---

## Environment Variables (Important!)

Never commit API keys to Git!

**Create `.env` file (don't commit):**
```
OPENROUTER_API_KEY=sk-or-v1-your-key
PORT=5001
```

**In deployment platforms:**
- Render: Settings → Environment
- Railway: Variables tab
- Heroku: `heroku config:set KEY=VALUE`

---

## Cost Comparison

| Platform | Startup | Monthly | Best For |
|----------|---------|---------|----------|
| Local Dev | Free | Free | Testing |
| Render | Free | $7 | Beginner-friendly |
| Railway | Free | $5+ | Pay-as-you-go |
| Heroku | Free trial | $7+ | Classic |
| Google Cloud Run | Free tier | $0-5 | Scalable |
| Netlify (static) | Free | $0-20 | Frontend only |
| Vercel (static) | Free | $0-20 | Frontend only |

---

## Production Checklist

Before deploying:

- [ ] Set `debug=False` in app.py
- [ ] Use Gunicorn (not Flask dev server)
- [ ] Add environment variables for API keys
- [ ] Set CORS origins (not `*`)
- [ ] Enable HTTPS
- [ ] Set up monitoring/logging
- [ ] Test on staging first
- [ ] Set up automated backups for database

---

## Troubleshooting Deployment

### "Port already in use"
```bash
pkill -f "python3 app.py"
```

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Database not found"
```bash
python3 ingest.py  # Run locally first
```

### "API returning 500"
- Check logs on deployment platform
- Verify OPENROUTER_API_KEY is set
- Make sure database was ingested

---

## Monitoring & Logs

### Render
- Dashboard → Logs tab
- Real-time streaming

### Railway
- Dashboard → Deployments → Logs

### Heroku
```bash
heroku logs --tail
```

---

## Next Steps

1. **Choose a platform** (Render recommended)
2. **Push to GitHub**
3. **Deploy** (follow steps above)
4. **Share your live URL!**

---

## Support

- Render: https://render.com/docs
- Railway: https://railway.app/docs
- Heroku: https://devcenter.heroku.com

**Happy deploying! 🚀**

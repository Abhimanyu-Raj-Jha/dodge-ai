# OpenRouter Setup Guide

This application now uses **OpenRouter** with **Llama 3.1 8B** (free, open-source model) instead of the Google Gemini API.

## Steps to Get Started

### 1. Get an OpenRouter API Key (FREE)

1. Go to https://openrouter.ai
2. Click **"Sign Up"** (or sign in if you have an account)
3. Once logged in, go to your **Settings** → **API Keys**
4. Click **"Create Key"** and copy it

### 2. Set the Environment Variable

Run this command in your terminal:

```bash
export OPENROUTER_API_KEY="your_api_key_here"
```

Replace `your_api_key_here` with the actual key you copied from OpenRouter.

### 3. Run the Application

```bash
cd /Users/abhimanyurajjha/Downloads/files
python3 app.py
```

### 4. Open in Browser

Go to **http://localhost:5001** in your browser.

---

## Benefits of OpenRouter

✅ **Free Tier**: Includes free credits for open-source models  
✅ **Open Source**: Uses Meta's Llama 3.1 8B (no quota limits like Gemini)  
✅ **Unlimited Requests**: No 429 rate limit errors  
✅ **Privacy**: Your data isn't sent to Google servers  
✅ **Community Models**: Access to many other open-source models

---

## Models Available on OpenRouter (Free Options)

- `meta-llama/llama-3.1-8b-instruct:free` (currently used)
- `meta-llama/llama-2-7b-chat:free`
- `mistralai/mistral-7b-instruct:free`
- And many others...

To use a different model, edit `llm.py` line 31 and change the `MODEL` variable.

---

## Troubleshooting

### Error: "OPENROUTER_API_KEY environment variable is not set"

Make sure you've set the environment variable before running the app:
```bash
export OPENROUTER_API_KEY="your_key"
```

### Error: "OpenRouter API error"

- Verify your API key is correct
- Make sure you have credits available (you can check on openrouter.ai)
- Try a different model

### Slow Responses

Llama 3.1 8B is smaller than Gemini, so responses may take 3-5 seconds. This is normal.

---

## Switching Back to Gemini (Optional)

If you want to use Gemini again instead of OpenRouter:

1. Revert `llm.py` to use Gemini
2. Set `export GEMINI_API_KEY="your_key"` instead
3. Make sure you have API credits available

---

Happy querying! 🚀

# Deployment guide (free tier, ~15-20 minutes)

## 0. Push to GitHub

```bash
cd ai-data-analyst
git init
git add .
git commit -m "AI Data Analyst Agent"
gh repo create ai-data-analyst --public --source=. --push
# or: create a repo on github.com and `git remote add origin <url> && git push -u origin main`
```

## 1. Get a free Groq API key (~1 minute)

1. Go to https://console.groq.com and sign up.
2. Create an API key.
3. Keep it handy for step 2 below.

## 2. Deploy the backend to Render

1. Go to https://render.com, sign up/sign in, connect your GitHub account.
2. New → Blueprint → select your `ai-data-analyst` repo. Render will detect
   `render.yaml` at the repo root.
3. When prompted for the `LLM_API_KEY` env var, paste your Groq key.
4. Deploy. First build takes a few minutes (installs Python deps, builds the Docker
   image).
5. Once live, note the backend URL, e.g. `https://ai-data-analyst-backend.onrender.com`.
6. Sanity check: open `https://<your-backend>.onrender.com/api/health` in a browser --
   you should see `{"status": "ok", "llm_provider": "groq", "llm_enabled": true}`.

Free-tier services spin down after ~15 minutes of inactivity; the next request wakes
them up but takes several extra seconds. Expected and fine for a portfolio project --
mention it as a known tradeoff if asked, not something to hide.

## 3. Deploy the frontend to Vercel

1. Go to https://vercel.com, sign up/sign in, connect GitHub.
2. New Project → import your `ai-data-analyst` repo.
3. Set **Root Directory** to `frontend`.
4. Framework preset: Vite (should auto-detect).
5. Add environment variable `VITE_API_BASE_URL` = your Render backend URL from step 2.
6. Deploy.

## 4. Update backend CORS

Once you have your Vercel URL, go back to Render → your backend service → Environment
→ set `CORS_ORIGINS` to your exact Vercel URL (e.g.
`https://ai-data-analyst.vercel.app`) instead of `*`, then redeploy. Tightening this
after you know the real frontend origin is good practice to call out if asked about
security in an interview.

## 5. Verify end-to-end

Open your Vercel URL, click "Load sample sales dataset", ask a suggested question,
confirm you get an answer with a chart and a "Generated SQL" section. Take a
screenshot or screen recording for your resume/portfolio while it's fresh.

## Cost reality check

Render free web service + Vercel Hobby + Groq free tier = **$0/month** at demo-level
traffic. Groq's free tier is rate-limited (not designed for production load) -- more
than enough for a portfolio project and interview demos, not something you'd point
real users at unpaid.

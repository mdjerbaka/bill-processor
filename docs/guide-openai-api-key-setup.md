# Setting Up Your Own OpenAI API Key

This guide walks you through creating your own OpenAI API key so the bill processor's invoice scanning (OCR) feature runs under your own account.

---

## What This Does

The bill processor uses OpenAI's API to read and extract data from uploaded invoices and bills. By setting up your own API key, the cost of these API calls (typically a few cents per document) bills directly to your OpenAI account.

---

## Step 1: Create an OpenAI Account

1. Go to [https://platform.openai.com/signup](https://platform.openai.com/signup)
2. Sign up with your email address (or sign in with Google/Microsoft)
3. Verify your email address

---

## Step 2: Add a Payment Method

1. Once logged in, go to **Settings → Billing**: [https://platform.openai.com/settings/organization/billing/overview](https://platform.openai.com/settings/organization/billing/overview)
2. Click **Add payment method**
3. Enter your credit card or debit card details
4. **Recommended:** Set a monthly usage limit (e.g., $10–$25/month) under **Usage limits** to avoid surprise charges. Normal usage for invoice scanning is well under $10/month.

---

## Step 3: Generate an API Key

1. Go to **API Keys**: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **+ Create new secret key**
3. Give it a name like `Bill Processor`
4. Click **Create secret key**
5. **IMPORTANT:** Copy the key immediately — it starts with `sk-` and you won't be able to see it again after closing the dialog
6. Save it somewhere safe temporarily (you'll need it in the next step)

---

## Step 4: Enter the Key in the Bill Processor

You have two options:

### Option A: Through the Web Interface (Easiest)

1. Log into the bill processor app
2. Go to **Settings** (gear icon)
3. Find the **OCR / Invoice Scanning** section
4. Paste your API key into the **OpenAI API Key** field
5. Make sure **OCR Provider** is set to **OpenAI**
6. Click **Save**

### Option B: On the Server (Advanced)

If you have SSH access to the server:

1. SSH into your server
2. Navigate to the app directory:
   ```
   cd /opt/bill-processor
   ```
3. Edit the `.env` file:
   ```
   nano .env
   ```
4. Find the line that says `OPENAI_API_KEY=` and paste your key after the `=`:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```
5. Save the file (Ctrl+O, Enter, Ctrl+X)
6. Restart the application:
   ```
   docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.neon.yml up -d --build
   ```

---

## Step 5: Verify It Works

1. Upload a test invoice or bill in the app
2. Confirm the data is extracted correctly
3. Check your OpenAI usage dashboard at [https://platform.openai.com/usage](https://platform.openai.com/usage) — you should see a small charge appear

---

## Cost Expectations

| Usage Level | Estimated Monthly Cost |
|---|---|
| Light (10–20 invoices/month) | $0.50 – $2.00 |
| Moderate (50–100 invoices/month) | $2.00 – $5.00 |
| Heavy (200+ invoices/month) | $5.00 – $15.00 |

These are rough estimates. Actual costs depend on document size and complexity.

---

## Security Tips

- **Never share your API key** via email or chat. If you need to send it, use a secure method.
- **Set a spending limit** on your OpenAI account to prevent unexpected charges.
- If you suspect your key has been compromised, go to [API Keys](https://platform.openai.com/api-keys), delete the old key, and create a new one.

---

## Need Help?

If you run into any issues, reach out and we'll get it sorted.

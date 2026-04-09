# Taking Over Your DigitalOcean Droplet

This guide walks you through creating your own DigitalOcean account and taking ownership of the server (droplet) that runs your bill processor application.

---

## What This Does

Your bill processor app runs on a DigitalOcean "Droplet" (a virtual server in the cloud). By transferring it to your own DigitalOcean account, you take direct control of the server and its billing goes to your payment method instead of ours.

---

## Step 1: Create a DigitalOcean Account

1. Go to [https://www.digitalocean.com](https://www.digitalocean.com)
2. Click **Sign Up**
3. Register with your email, Google, or GitHub account
4. Verify your email address

---

## Step 2: Add a Payment Method

1. After signing up, DigitalOcean will prompt you to add a payment method
2. You can use a **credit card** or **PayPal**
3. Go to **Settings → Billing**: [https://cloud.digitalocean.com/account/billing](https://cloud.digitalocean.com/account/billing)
4. Confirm your payment method is active

---

## Step 3: Send Us Your Account Details for Transfer

Once your account is set up with a payment method, send us the **email address** associated with your DigitalOcean account. We will initiate the droplet transfer from our side.

**What we need from you:**
- The email address on your DigitalOcean account

That's it — we handle the rest of the transfer process.

---

## Step 4: Accept the Transfer

1. You will receive an email from DigitalOcean with the subject line similar to **"Droplet Transfer Request"**
2. Open the email and click **Accept Transfer**
3. Log into your DigitalOcean account if prompted
4. Confirm the transfer

Once accepted, the droplet will appear in your DigitalOcean dashboard and billing switches to your account immediately.

---

## Step 5: Verify Everything Works

1. Log into DigitalOcean: [https://cloud.digitalocean.com](https://cloud.digitalocean.com)
2. Click **Droplets** in the left sidebar
3. You should see the bill processor droplet listed
4. Note the **IP address** — this is your server's address
5. Open your bill processor app in the browser to confirm it's still running normally

---

## What You're Paying For

| Resource | Typical Cost |
|---|---|
| Droplet (Basic, 1–2 GB RAM) | $6 – $12/month |
| Optional: Backups | +20% of droplet cost |
| Optional: Domain/DNS | Free (if using DigitalOcean DNS) |

Your exact cost depends on the droplet size. You can see it on your Droplets page.

---

## Recommended: Enable Backups

1. Go to your **Droplets** page
2. Click on the droplet name
3. Go to the **Backups** tab
4. Click **Enable Backups**

This creates automatic weekly snapshots of your server. Costs an extra 20% of your droplet price (e.g., $1.20/month on a $6 droplet). Highly recommended in case anything goes wrong.

---

## Recommended: Set Up Billing Alerts

1. Go to **Settings → Billing**: [https://cloud.digitalocean.com/account/billing](https://cloud.digitalocean.com/account/billing)
2. Scroll down to **Billing Alerts**
3. Set a monthly threshold (e.g., $15 or $20) to get notified if charges are higher than expected

---

## Managing Your Server (Optional)

You don't need to do anything with the server day-to-day — it runs automatically. But if you ever need to:

- **Restart the server:** Go to Droplets → click your droplet → click **Power** → **Power Cycle**
- **Resize the server:** Go to Droplets → click your droplet → click **Resize** (if the app gets slow and needs more resources)
- **View server metrics:** Go to Droplets → click your droplet → **Graphs** tab to see CPU, memory, and disk usage

---

## Important Notes

- **Do not delete the droplet** unless you want to permanently shut down the application and lose all data.
- **Do not resize to a smaller droplet** without checking with us first — the app may not run on very small plans.
- If you ever need to update the application, reach out and we can handle it remotely via SSH.

---

## Need Help?

If you have any questions about the transfer or your DigitalOcean account, don't hesitate to reach out.

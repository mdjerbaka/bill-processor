# Transferring Billing to Your Account

This guide walks you through taking over the monthly costs for both the **DigitalOcean server** (droplet) and the **Neon database** that power your bill processor application. After completing these steps, both services bill directly to your payment method, while your developer retains access to maintain and update the app.

---

## Current Monthly Costs

| Service | What It Does | Typical Cost |
|---|---|---|
| DigitalOcean Droplet | Runs the application (server) | $6 – $12/month |
| Neon Postgres Database | Stores all your data (bills, invoices, vendors, etc.) | Free tier or $19/month (Launch plan) |
| Optional: DO Backups | Weekly server snapshots | +20% of droplet cost |

**Total estimated cost: $6 – $31/month** depending on plan choices.

---

# Part 1: DigitalOcean Droplet Transfer

## Step 1: Create a DigitalOcean Account

1. Go to [https://www.digitalocean.com](https://www.digitalocean.com)
2. Click **Sign Up**
3. Register with your email, Google, or GitHub account
4. Verify your email address

## Step 2: Add a Payment Method

1. After signing up, DigitalOcean will prompt you to add a payment method
2. You can use a **credit card** or **PayPal**
3. Go to **Settings → Billing**: [https://cloud.digitalocean.com/account/billing](https://cloud.digitalocean.com/account/billing)
4. Confirm your payment method is active

## Step 3: Send Your Account Email

Once your account is ready, send your developer the **email address** associated with your DigitalOcean account. That's all they need to initiate the transfer.

## Step 4: Accept the Transfer

1. You'll receive an email from DigitalOcean with the subject **"Droplet Transfer Request"**
2. Open the email and click **Accept Transfer**
3. Log into your DigitalOcean account if prompted
4. Confirm the transfer

Once accepted, the droplet appears in your DigitalOcean dashboard and billing switches to your account immediately.

## Step 5: Add Your Developer as a Team Member

This is the key step that lets your developer continue making updates without you being involved.

1. Log into DigitalOcean: [https://cloud.digitalocean.com](https://cloud.digitalocean.com)
2. Click **Settings** in the left sidebar
3. Click the **Team** tab
4. Click **Invite Members**
5. Enter your developer's email address
6. Set their role to **Member** (this gives them access to manage the droplet but NOT your billing/payment info)
7. Click **Send Invite**

Your developer will accept the invite and be able to SSH into the server, deploy updates, and manage the droplet — all while billing goes to your account.

## Step 6: Verify Everything Works

1. Go to **Droplets** in the left sidebar
2. You should see the bill processor droplet listed
3. Open your bill processor app in the browser to confirm it's still running normally

---

# Part 2: Neon Database Transfer

The database is hosted on Neon (a cloud Postgres provider). You'll create your own Neon organization, invite your developer, and transfer the project.

## Step 1: Create a Neon Account

1. Go to [https://neon.tech](https://neon.tech)
2. Click **Sign Up**
3. Sign up with your **email**, **Google**, or **GitHub** account
4. Verify your email if prompted

## Step 2: Create an Organization

Organizations let you own the billing while giving your developer access.

1. After logging in, click your profile icon in the top-left
2. Click **Create Organization**
3. Name it something like your company name (e.g., "Acme Construction")
4. Choose a plan:
   - **Free tier** — 0.5 GB storage, suitable for light usage
   - **Launch plan ($19/month)** — 10 GB storage, recommended for production use
5. If choosing a paid plan, add your payment method when prompted

## Step 3: Invite Your Developer to the Organization

1. Inside your new organization, go to **Settings → Members**
2. Click **Invite Member**
3. Enter your developer's email address
4. Set their role to **Admin** (they need this to manage the database and deploy updates)
5. Click **Send Invite**

Your developer will accept the invite and gain full access to manage the database project within your organization.

## Step 4: Your Developer Transfers the Database Project

> **This step is done by your developer — no action needed from you.**

Your developer will:
1. Log into their Neon account
2. Go to the bill processor project
3. Click **Settings → Transfer Project**
4. Select your organization as the destination
5. Confirm the transfer

Once transferred, the project lives under your organization and bills to your payment method. Your developer retains full access as an organization member.

## Step 5: Verify the Database

After the transfer, open your bill processor app and confirm:
- You can log in
- Your bills, invoices, and vendors are all still there
- Everything works as before

Nothing changes about the app itself — only who pays for the database hosting.

---

# After the Transfer: What Changes

| | Before | After |
|---|---|---|
| **Who pays for the server** | Your developer | You |
| **Who pays for the database** | Your developer | You |
| **Who can update the app** | Your developer | Your developer (unchanged) |
| **Who can access billing** | Your developer | You |
| **App URL / login** | Same | Same (no change) |

---

# Recommended: Enable Billing Alerts

## DigitalOcean
1. Go to **Settings → Billing**: [https://cloud.digitalocean.com/account/billing](https://cloud.digitalocean.com/account/billing)
2. Scroll to **Billing Alerts**
3. Set a monthly threshold (e.g., $20) to get notified if charges exceed expectations

## Neon
1. Go to your organization in Neon
2. Click **Billing** in the sidebar
3. Review your usage and plan limits — Neon sends email alerts if you approach plan limits

---

# Recommended: Enable Server Backups

1. In DigitalOcean, go to **Droplets** → click your droplet
2. Go to the **Backups** tab
3. Click **Enable Backups** ($1–$2/month extra)

This creates automatic weekly snapshots of your server in case anything goes wrong.

---

# Summary Checklist

- [ ] Created DigitalOcean account and added payment method
- [ ] Sent DigitalOcean account email to developer
- [ ] Accepted the droplet transfer email
- [ ] Added developer as a Team Member on DigitalOcean
- [ ] Created Neon account
- [ ] Created a Neon Organization with billing
- [ ] Invited developer to the Neon Organization
- [ ] Developer transferred the Neon database project
- [ ] Verified the app still works
- [ ] Enabled billing alerts (recommended)
- [ ] Enabled server backups (recommended)

---

# Questions?

If you run into any issues during this process, reach out to your developer. None of these steps affect the running application — your bill processor will continue working throughout the entire transfer process.

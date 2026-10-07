# Launch a small free beta

Use the root `render.yaml`: a free Render static frontend and a free API web service, one free Render Key Value queue, and an external Neon free PostgreSQL database. The API container supervises one RQ worker alongside Uvicorn. This keeps the existing experiment implementation and requires no separate paid worker. Do not select `infra/render-production.yaml` until you have reviewed its paid resources.

These hosted platforms are proprietary services. PostgreSQL, Redis-compatible queue clients, RQ, FastAPI, and Next.js are open-source components. Free hosting is not the same as open-source hosting. Mailpit captures development emails; it cannot replace PostgreSQL, which stores accounts, projects, prompts, experiments, and feedback.

## 1. Create the accounts and database

1. Create free Render and Neon accounts. Connect Render to this GitHub repository.
2. In Neon, create an empty PostgreSQL project near Singapore and copy its connection string, including `sslmode=require`. Use the direct connection for the initial small beta. Do not paste it into Git or public messages.
3. Do not use Render's free PostgreSQL for ongoing user data: it expires after 30 days. Neon has its own storage/compute limits; review the current free allowance before inviting users.

## 2. Configure real verification email

Render free services block outbound SMTP ports 25, 465, and 587. Use an HTTPS email API instead of your Gmail SMTP settings.

1. Create a free Brevo account, activate transactional sending, add the sender address you actually control, and complete its sender verification. Generate a **Brevo API key**, not an SMTP key.
2. Set `SMTP_FROM` to `Optiq <your-verified-address>` and `BREVO_API_KEY` to that API key. Despite the existing `MAIL_BACKEND=smtp` setting, supplying this key selects HTTPS delivery. Leave `SMTP_HOST` empty in Render.
3. A verified free inbox may be usable for an initial trial, subject to Brevo's account/sender approval, but Gmail/Yahoo sender domains cannot be authenticated by you. Do not promise inbox delivery: verify actual delivery before opening registration. For reliable branded email, use a domain you control and configure the provider's DKIM/DMARC records. Domain registration can cost money.
4. Alternatively, use the existing Resend integration (`RESEND_API_KEY`, clear `BREVO_API_KEY`). Sending to arbitrary users requires an authenticated domain; its test sender is not a public signup solution.
5. Google sign-in is already supported. If you configure it, set the same OAuth web client ID as backend `GOOGLE_CLIENT_ID` and frontend `NEXT_PUBLIC_GOOGLE_CLIENT_ID`; authorize the exact frontend origin in Google Cloud. It avoids sending verification email for Google accounts. Password registration still requires working mail.

The API refuses insecure production secrets, local frontend origins, SQLite, missing Redis, and missing mail configuration. Password users remain unverified until they consume the emailed token. Mail-service acceptance does not prove inbox delivery.

## 3. Deploy the free Blueprint

1. In Render, select **New → Blueprint**, choose this repository and the branch containing these changes, and use **render.yaml**. Confirm every resource is **Free** before creating anything. Do not enter payment information or accept a paid instance upgrade for this beta.
2. Supply `DATABASE_URL`, `BREVO_API_KEY`, `SMTP_FROM`, and `FERNET_KEY`. Generate the encryption key locally from the repository root:

   ```sh
   backend/.venv/bin/python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   ```

   Render generates `JWT_SECRET`. Save both secrets securely: changing `FERNET_KEY` makes existing provider keys unreadable; changing `JWT_SECRET` invalidates sessions.
3. Use the actual assigned API HTTPS URL for frontend `NEXT_PUBLIC_API_URL`, and the actual frontend HTTPS URL for backend `FRONTEND_URL`. Render can add suffixes to service names, so do not assume the names in YAML equal the assigned URLs. If you need temporary values during creation, update them before sharing the app.
4. Redeploy the frontend after changing `NEXT_PUBLIC_*`: Next.js embeds these values at build time. Redeploy the API after changing backend variables. Do not add API keys, database passwords, or encryption secrets to `NEXT_PUBLIC_*` variables.
5. Check API logs for migration success and `Worker ... started`. Open `/health/ready` on the API and verify `{"status":"ready"}`. This checks database/queue connectivity; the container supervisor restarts if the API or worker process exits. It does not prove provider or mail delivery.

## 4. Test before inviting users

- Register a fresh email address, confirm arrival in a real inbox, verify it, and log in. Reusing the link must fail. Failed resend submission must leave the previous link usable. Check Brevo's delivery/bounce logs if mail is missing.
- Create a project; configure one provider through Settings using a low-limit test key; analyze and improve a prompt. Confirm basic advice works without a provider key.
- In the experiment runner, select one model and one input, review the resolved models and cost, confirm, and wait for its result. Test “all configured” selection, deselection, result comparison, budget stops, and recommendations.
- Never enter a user's local `localhost` Ollama address into the cloud backend: it points at the server, not the user's laptop. Local inference needs a reachable authenticated service; do not expose an unauthenticated Ollama port publicly.
- Submit “Give feedback” from a feature page. In Neon's SQL editor, inspect:

  ```sql
  SELECT email, email_verified, auth_provider, created_at FROM users ORDER BY created_at DESC LIMIT 20;
  SELECT id, status, created_at FROM experiments ORDER BY created_at DESC LIMIT 20;
  SELECT page, rating, comment, created_at FROM product_feedback ORDER BY created_at DESC LIMIT 50;
  ```

Feedback stores the page path, rating, optional comment, and time. It does not automatically capture prompts, provider keys, account IDs, or URL query strings. Comments are user supplied; keep them private. There is no public feedback read endpoint. Review comments weekly and delete unnecessary records.

## Free beta limits and upgrade trigger

Render's free API sleeps after inactivity, has a shared allowance of 750 instance hours per workspace per month, and may restart. The static frontend does not consume those web-service hours. Free Key Value has no persistence: restarts can lose queued jobs and reset rate limits. The single API/worker container shares limited memory. Keep experiments short and invite a small group first. Provider model calls can still cost money even when hosting is free.

A restart can interrupt a running experiment. Completed results and recorded progress stay in PostgreSQL; do not automatically retry interrupted provider calls because they may already have been charged. Inspect a stuck experiment and queue logs before marking it failed or starting a new run. Do not treat this free setup as durable production job processing.

Once users depend on experiments, move to the paid `infra/render-production.yaml`: an always-on API, dedicated worker, persistent queue, and persistent PostgreSQL. Preserve the existing database and encryption key rather than silently creating a fresh database. Back up PostgreSQL before migrations, verify restoration, and run dependency/security updates before a wider production release. The current Next.js 14 stack also needs a supported-version upgrade before that release.

For a local encrypted backup, use Neon's direct PostgreSQL URL with `pg_dump --format=custom --file=optiq-backup.dump` after setting `PGHOST`, `PGUSER`, `PGDATABASE`, `PGPASSWORD`, and `PGSSLMODE=require` privately; never commit the dump. Restore into a separate database to check it. Render's code rollback does not roll back database migrations. The free frontend is a static export; adding Next.js server routes or server rendering later requires changing its hosting configuration.

Official references: [Render free limits](https://render.com/docs/free), [Render Key Value persistence](https://render.com/docs/key-value), [Neon plans](https://neon.com/pricing), [Brevo free limits](https://help.brevo.com/hc/en-us/articles/208580669-FAQs-What-are-the-limits-of-the-Free-plan), [Brevo sender/domain guidance](https://help.brevo.com/hc/en-us/articles/35852083084178-Domain-setup-for-better-email-deliverability), [Brevo transactional API](https://developers.brevo.com/docs/send-a-transactional-email). Vercel can host Next.js, but its [Hobby plan](https://vercel.com/docs/plans/hobby) is restricted to personal, noncommercial use and does not directly replace this RQ worker deployment.

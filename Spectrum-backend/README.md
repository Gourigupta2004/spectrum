# Spectrum backend

Django API and admin for the Spectrum website in `../Spectrum-website`.

Built to run on one small server next to other processes:

| Process | Memory (measured) |
| --- | --- |
| gunicorn master | ~27 MB |
| each web worker (2) | ~52 MB |
| background worker | ~53 MB, one image at a time |

There is no Redis, Celery or DRF. Public pages are served from a file cache as ready-made JSON, with ETags.

## Local setup

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
echo "DEBUG=1" > .env                         # SQLite, local media, jobs run inline
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser

# Load the website's current demo data, images included
(cd ../Spectrum-website && bun scripts/export-fixtures.ts)
.venv/bin/python manage.py seed_fixtures --sync

.venv/bin/python manage.py runserver 8000
```

Admin: http://localhost:8000/admin/. Portal demo login: `dps-newdelhi` / `demo`.

Run the website against it:

```sh
cd ../Spectrum-website
VITE_API_URL=http://localhost:8000 bun run dev
```

Without `VITE_API_URL` the website keeps using its built-in demo data.

## Using the admin

- **Website content** holds one page per screen. Every heading, paragraph, label and placeholder is a field. Wrap words in `[brackets]` to show them in the Spectrum gradient.
- **Batches of photos** are uploaded by dragging files or a whole folder onto the drop zone, choosing many files, or pasting (Ctrl+V). Uploads keep filename order and start processing immediately.
  - Event gallery photos: open the event.
  - Class photographs (for titles): open the institution's entry under **Institution portal › Institution workspaces** (one per institution). A fresh batch always asks the institution for a title; the tag picker above the drop zone sends a batch for approval or correction instead. Every photo appears in the table on that page with its title and state.
  - Individual (student) photographs: on the same workspace page, drop one folder per class under **Individual Photographs Upload** — each folder's name becomes the class name and its photos are filed under it (ten folders, ten classes). Below the photos, pick a class or **All classes** and press **Download** for a zip of the originals named after the students.
  - Classes are listed in school order (Nursery, LKG, UKG, 1A … 12C) and photos in file-name order, in the admin and on the website.
- **Portal access** is invitation-only. Add the institution's email addresses under **Institution credentials** (or on the institution itself), and set its portal username and password on the institution (**Institution portal sign-in**). Only a visitor who enters one of those emails on the website sees the Portal link and the institution's sign-in, where that username and password are still required. They only work for the institution the email unlocked.
- **Spectrum team** members sign in to the portal with their own admin username and password: tick **Institution portal access** on their user under **System › Users** (superusers always can). They can open every institution.
- **Photos keep their proportions.** Galleries, the caption workspace and student rosters show every photo at the size it was uploaded in; nothing is cropped to fit a frame. `manage.py crop_to_frame` is the one-off that cut the photos already on the site to the frames they used to display in (gallery 4:5, caption cards 4:3, students 3:4), so existing pages look as they did. It keeps every uncropped file in place and prints where.
- Gallery previews carry a large diagonal "Preview Only" watermark. Photos processed before this wording changed keep their old mark until you select them and run **Re-make image variants**.
  - Hero slides: Home page. Tie-up photos: About page.
- Uploaded originals stay private. The site only gets resized WebP copies; gallery previews are watermarked.

## Background worker

`python manage.py runworker` makes image variants, builds order zips and sends WhatsApp and email deliveries. Failed jobs appear under **System › Background tasks** with a Retry action.

## Tests

```sh
DEBUG=1 .venv/bin/python manage.py test apps.tests
```

## Deploying on one server

1. Create the data folders outside the code: `mkdir -p /srv/spectrum/{media,data,tmp,cache,backups}`, owned by the `spectrum` user.
2. Copy `.env.example` to `.env`, fill it in, and run `chmod 600 .env`.
3. `pip install -r requirements.txt`, then `manage.py migrate`, `manage.py collectstatic` and `manage.py createsuperuser`.
4. Load the demo content with `manage.py seed_fixtures`. Demo portal logins are only created with `--demo-logins`.
5. Install `deploy/spectrum-web.service` and `deploy/spectrum-worker.service`, then enable both.
6. Install `deploy/nginx.conf` and add TLS. It passes the real visitor IP as `X-Real-IP`, which rate limits rely on. Behind Cloudflare, configure nginx's real-IP module first.
7. Add `deploy/backup.sh` to cron. Set `BACKUP_REMOTE` so photos are copied off the server.
8. In Razorpay, point a webhook at `https://api.spectrum.in/api/webhooks/razorpay/` for `payment.captured`, `order.paid` and `payment.failed`.
9. Build the website with `VITE_API_URL=https://api.spectrum.in`.

Safety rails:
- The app refuses to start with `PAYMENTS_MOCK=1` and `DEBUG=0`, unless `ALLOW_MOCK_PAYMENTS=1` is set for a demo server.
- Portal passwords need at least 10 characters. Changing one signs that login out everywhere, and sessions end after 14 days.
- Paid downloads are streamed by nginx, not by the app.

Without S3, all photos live on this server's disk under `MEDIA_ROOT`: originals in `private/` (never served) and web copies in `public/` (served by nginx). Plan disk space for the originals, and keep the off-server backup running, because they cannot be recreated.

Switching to S3 later: set `USE_S3=1` and the `AWS_*` values, and apply `deploy/s3-cors.json` to the bucket. Admin uploads then go straight from the browser to S3.

SQLite is the default because it needs no extra process. Set `DATABASE_URL` to use Postgres instead.

## Known limits

- An event gallery is returned as one list. That is fine up to a few thousand photos per event; beyond that it should be paginated.
- Two people uploading to the same event at the same moment get interleaved photo order. Fix the order afterwards in the admin list.

# Spectrum

| Folder | What it is |
| --- | --- |
| `Spectrum-website/` | The public website and institution portal (TanStack Start, Cloudflare Workers) |
| `Spectrum-backend/` | Django API, admin, image processing, payments and delivery |
| `docs/spectrum-backend-plan.md` | The design plan the backend follows |

## Run both locally

```sh
# Backend (first time: see Spectrum-backend/README.md)
cd Spectrum-backend && .venv/bin/python manage.py runserver 8000

# Website, reading everything from the backend
cd Spectrum-website && VITE_API_URL=http://localhost:8000 bun run dev
```

Leave `VITE_API_URL` unset and the website runs on its built-in demo data, exactly as before.

## Lovable

The website used to live at the repository root. Lovable expects it there, so edits made in Lovable may no longer sync into `Spectrum-website/`.

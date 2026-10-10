# مغز کامل — Cloud

نسخه ابری آغازین با حافظه ساخت‌یافته SQLite.

## Deploy در Render
از Blueprint و فایل `render.yaml` استفاده کنید. Health: `/api/health`.

## API
- `GET /api/health`
- `GET /api/brain/stats`
- `POST /api/brain/entity` با `{"type":"KPI","name":"درآمد ماهانه","aliases":["revenue"]}`
- `POST /api/brain/claim` با `entity_id` و `text`
- `POST /api/brain/solve` با `entity_id`

برای داده‌های ماندگار در تولید، SQLite محلی را با PostgreSQL یا دیسک پایدار جایگزین کنید. کلیدهای API را فقط در Render Environment Variables نگه دارید.

# S3 setup (presigned downloads)

Purchased originals never pass through the server. `download_photo` / `download_zip`
([apps/orders/views.py](../apps/orders/views.py)) first check the download token belongs to a
**paid** order, then 302-redirect the browser to a presigned S3 URL that expires after
`PRIVATE_URL_EXPIRE` seconds (default 300). No paid order, no signed URL.

## 1. Bucket
- Create one bucket (e.g. `spectrum-media`) in `ap-south-1`.
- Prefixes used by the app: `public/` (thumbnails, site images) and `private/` (originals, zips).
  `private/` must never be public. If `public/` is served through CloudFront, use an Origin Access
  Control and keep the bucket fully blocked; otherwise allow public ACLs only and keep
  `AWS_PUBLIC_ACL=public-read`.
- Apply CORS: `aws s3api put-bucket-cors --bucket spectrum-media --cors-configuration file://deploy/s3-cors.json`
  (edit the API origin first).
- Lifecycle rule: abort incomplete multipart uploads after 1 day.

## 2. IAM user (scoped)
Create a user for the app with only this policy and put its keys in `.env`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::spectrum-media"},
    {"Effect": "Allow",
     "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:PutObjectAcl"],
     "Resource": "arn:aws:s3:::spectrum-media/*"}
  ]
}
```

Presigned URLs carry this user's permissions, so it must be able to read `private/*`.

## 3. Environment
```
USE_S3=1
AWS_STORAGE_BUCKET_NAME=spectrum-media
AWS_S3_REGION_NAME=ap-south-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
PRIVATE_URL_EXPIRE=300
```
The filename (`ResponseContentDisposition`) is signed into the URL. A 5-minute link is fine for
large zips: S3 checks expiry when the request starts, not when it finishes.

## 4. Keeping egress predictable
S3 data-transfer-out is the one cost line that scales with usage.
- The purchase check plus the short URL lifetime are the controls: a leaked link dies in 5 minutes
  and cannot be re-minted without a valid download token.
- In AWS Budgets, create a **cost budget filtered to Service = Amazon S3**, alerting at 80% of the
  spend you expect, so a spike shows up within a day rather than at month-end.
- Optionally front `public/` with CloudFront (`AWS_S3_CUSTOM_DOMAIN`) so repeated thumbnail views
  are cached instead of billed as S3 egress.
- Download endpoints are not rate limited here; add that if valid tokens get abused.

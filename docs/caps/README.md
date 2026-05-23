# Federation cap docs — hosted on AWS S3 + CloudFront

All MCP server cards, A2A agent cards, and policy docs for the
IETF_Vienna demo federation are hosted publicly so every Instruqt
sandbox can resolve them without SSRF/private-IP problems.

## Target URL pattern

```
https://cap.workshop.highvelocitynetworking.com/<agent>/<doc>.json
```

## One-time AWS setup (you, via Okta SSO)

```bash
# Assume your IETF_Vienna AWS account via SSO
aws sso login --profile okta-iracic82
export AWS_PROFILE=okta-iracic82
export AWS_DEFAULT_REGION=us-east-1

# 1. Bucket + public-read with website hosting OFF (CloudFront handles delivery)
aws s3api create-bucket \
    --bucket cap.workshop.highvelocitynetworking.com \
    --region us-east-1

aws s3api put-public-access-block \
    --bucket cap.workshop.highvelocitynetworking.com \
    --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

aws s3api put-bucket-policy \
    --bucket cap.workshop.highvelocitynetworking.com \
    --policy '{"Version":"2012-10-17","Statement":[{"Sid":"PublicReadCaps","Effect":"Allow","Principal":"*","Action":"s3:GetObject","Resource":"arn:aws:s3:::cap.workshop.highvelocitynetworking.com/*"}]}'

# 2. Request ACM cert in us-east-1 (CloudFront requires us-east-1 certs)
aws acm request-certificate \
    --domain-name cap.workshop.highvelocitynetworking.com \
    --validation-method DNS \
    --region us-east-1

#   → Add the DNS validation CNAME to Route 53 manually, wait for ISSUED.

# 3. Create CloudFront distribution (web console is simplest; defaults are fine).
#    Origin: cap.workshop.highvelocitynetworking.com.s3.amazonaws.com
#    Behaviors: caching enabled, viewer protocol policy: redirect-to-https
#    Alternate domain name (CNAME): cap.workshop.highvelocitynetworking.com
#    Certificate: the ACM cert from step 2

# 4. In Route 53, ALIAS cap.workshop.highvelocitynetworking.com → CloudFront DNS name
```

## Upload (whenever a cap doc changes)

```bash
# From the repo root:
aws s3 sync docs/caps/ s3://cap.workshop.highvelocitynetworking.com/ \
    --content-type application/json \
    --cache-control "public, max-age=300" \
    --exclude "*.md"

# Verify
curl -sI https://cap.workshop.highvelocitynetworking.com/ip-reputation/v1.json | head -5

# Compute the canonical sha256 (matches what dns-aid will publish in key65401)
sha256sum docs/caps/ip-reputation/v1.json
```

## CI automation (optional, future)

A GitHub Action on push to `main` could auto-sync `docs/caps/` to S3
using OIDC + role assumption. See `.github/workflows/sync-caps.yml.tmpl`
when it lands.

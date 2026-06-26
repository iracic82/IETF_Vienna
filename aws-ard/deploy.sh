#!/usr/bin/env bash
# Provision the ARD search Lambda + API Gateway in account 905418046272.
#
# Idempotent: re-running updates code or no-ops where unchanged.
# Region: us-east-1 (same as the ietf-vienna-cap-docs bucket).
#
# Resources created:
#   - IAM role        ard-search-lambda-role
#   - Lambda fn       ard-search
#   - APIGW HTTP API  ard-search-api  with $default stage
#   - Routes:
#       GET  /                              → Lambda
#       POST /search                        → Lambda
#       POST /students/{slug}/search        → Lambda
#       GET  /catalog                       → Lambda
#       GET  /students/{slug}/catalog       → Lambda
#
# Prints the public invoke URL at the end.

set -euo pipefail

PROFILE="okta-sso"
REGION="us-east-1"
ACCOUNT_ID="905418046272"
ROLE_NAME="ard-search-lambda-role"
FN_NAME="ard-search"
API_NAME="ard-search-api"
BUCKET="ietf-vienna-cap-docs"

HERE="$(cd "$(dirname "$0")" && pwd)"
LAMBDA_DIR="${HERE}/lambda"
BUILD_DIR="$(mktemp -d)"
trap "rm -rf ${BUILD_DIR}" EXIT

AWS="aws --profile ${PROFILE} --region ${REGION}"

# ─────────────────────────────────────────────────────────────────────
echo "▶ 1. IAM role (Lambda execution + S3 read)"
# ─────────────────────────────────────────────────────────────────────
ASSUME='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

if ! $AWS iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
    $AWS iam create-role \
        --role-name "${ROLE_NAME}" \
        --assume-role-policy-document "${ASSUME}" \
        --description "ARD search Lambda execution role (IETF Vienna lab)" \
        >/dev/null
    echo "    created role ${ROLE_NAME}"
else
    echo "    role ${ROLE_NAME} already exists"
fi

# Inline S3 read policy
S3_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": [
        "arn:aws:s3:::${BUCKET}/.well-known/ai-catalog.json",
        "arn:aws:s3:::${BUCKET}/students/*/.well-known/ai-catalog.json"
      ]
    }
  ]
}
EOF
)
$AWS iam put-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-name s3-catalog-read \
    --policy-document "${S3_POLICY}"
echo "    attached inline S3 policy"

# Basic execution managed policy (CloudWatch logs)
$AWS iam attach-role-policy \
    --role-name "${ROLE_NAME}" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
    2>/dev/null || true
echo "    attached AWSLambdaBasicExecutionRole"

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# ─────────────────────────────────────────────────────────────────────
echo "▶ 2. Package Lambda (zip search.py — boto3 is in Lambda's runtime)"
# ─────────────────────────────────────────────────────────────────────
cp "${LAMBDA_DIR}/search.py" "${BUILD_DIR}/search.py"
(cd "${BUILD_DIR}" && zip -q search.zip search.py)
echo "    built ${BUILD_DIR}/search.zip"

# ─────────────────────────────────────────────────────────────────────
echo "▶ 3. Lambda function (create or update)"
# ─────────────────────────────────────────────────────────────────────
if ! $AWS lambda get-function --function-name "${FN_NAME}" >/dev/null 2>&1; then
    # New role propagation can lag; retry create
    for i in 1 2 3 4 5 6; do
        if $AWS lambda create-function \
            --function-name "${FN_NAME}" \
            --runtime python3.12 \
            --role "${ROLE_ARN}" \
            --handler search.handler \
            --zip-file "fileb://${BUILD_DIR}/search.zip" \
            --timeout 10 \
            --memory-size 256 \
            --environment "Variables={ARD_CATALOG_BUCKET=${BUCKET}}" \
            --description "ARD §7 search API for IETF Vienna lab" \
            >/dev/null 2>&1; then
            echo "    created Lambda ${FN_NAME}"
            break
        fi
        echo "    attempt ${i}: IAM propagation lag — retrying in 6s"
        sleep 6
    done
else
    $AWS lambda update-function-code \
        --function-name "${FN_NAME}" \
        --zip-file "fileb://${BUILD_DIR}/search.zip" \
        >/dev/null
    $AWS lambda update-function-configuration \
        --function-name "${FN_NAME}" \
        --environment "Variables={ARD_CATALOG_BUCKET=${BUCKET}}" \
        >/dev/null
    echo "    updated Lambda ${FN_NAME} code + env"
fi

# Wait for the update to settle so the next get-function-configuration is consistent.
$AWS lambda wait function-updated --function-name "${FN_NAME}" 2>/dev/null || true

FN_ARN=$($AWS lambda get-function-configuration --function-name "${FN_NAME}" --query 'FunctionArn' --output text)
echo "    Lambda ARN: ${FN_ARN}"

# ─────────────────────────────────────────────────────────────────────
echo "▶ 4. API Gateway HTTP API"
# ─────────────────────────────────────────────────────────────────────
API_ID=$($AWS apigatewayv2 get-apis --query "Items[?Name=='${API_NAME}'].ApiId" --output text 2>/dev/null || true)
if [ -z "${API_ID}" ] || [ "${API_ID}" = "None" ]; then
    API_ID=$($AWS apigatewayv2 create-api \
        --name "${API_NAME}" \
        --protocol-type HTTP \
        --target "${FN_ARN}" \
        --cors-configuration "AllowOrigins=*,AllowMethods=GET,POST,OPTIONS,AllowHeaders=content-type" \
        --query 'ApiId' --output text)
    echo "    created API ${API_NAME} (id=${API_ID})"
else
    echo "    API ${API_NAME} already exists (id=${API_ID})"
fi

# Routes — explicit, since `--target` on create only wires ANY /{proxy+}
INTEGRATION_ID=$($AWS apigatewayv2 get-integrations \
    --api-id "${API_ID}" \
    --query 'Items[0].IntegrationId' --output text 2>/dev/null || true)
if [ -z "${INTEGRATION_ID}" ] || [ "${INTEGRATION_ID}" = "None" ]; then
    INTEGRATION_ID=$($AWS apigatewayv2 create-integration \
        --api-id "${API_ID}" \
        --integration-type AWS_PROXY \
        --integration-uri "${FN_ARN}" \
        --payload-format-version 2.0 \
        --query 'IntegrationId' --output text)
    echo "    created integration ${INTEGRATION_ID}"
else
    echo "    integration ${INTEGRATION_ID} already exists"
fi

# Explicit routes
for ROUTE in \
    "GET /" \
    "GET /health" \
    "POST /search" \
    "POST /students/{slug}/search" \
    "GET /catalog" \
    "GET /students/{slug}/catalog"
do
    EXISTING=$($AWS apigatewayv2 get-routes --api-id "${API_ID}" \
        --query "Items[?RouteKey=='${ROUTE}'].RouteId" --output text 2>/dev/null || true)
    if [ -z "${EXISTING}" ] || [ "${EXISTING}" = "None" ]; then
        $AWS apigatewayv2 create-route \
            --api-id "${API_ID}" \
            --route-key "${ROUTE}" \
            --target "integrations/${INTEGRATION_ID}" \
            >/dev/null
        echo "    + ${ROUTE}"
    fi
done

# Lambda permission for APIGW to invoke (idempotent: remove + add)
$AWS lambda remove-permission --function-name "${FN_NAME}" --statement-id apigw-invoke 2>/dev/null || true
$AWS lambda add-permission \
    --function-name "${FN_NAME}" \
    --statement-id apigw-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
    >/dev/null
echo "    Lambda invoke permission set"

# Make sure $default stage with auto-deploy exists
$AWS apigatewayv2 get-stage --api-id "${API_ID}" --stage-name '$default' >/dev/null 2>&1 || \
$AWS apigatewayv2 create-stage --api-id "${API_ID}" --stage-name '$default' --auto-deploy >/dev/null

INVOKE_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com"
echo
echo "════════════════════════════════════════════════════════════════"
echo "  ARD search API live at:"
echo "    ${INVOKE_URL}"
echo
echo "  Quick smoke tests:"
echo "    curl -s ${INVOKE_URL}/"
echo "    curl -s ${INVOKE_URL}/catalog | python3 -m json.tool | head"
echo "    curl -s -X POST ${INVOKE_URL}/search -H 'content-type: application/json' \\"
echo "         -d '{\"query\":{\"text\":\"ip reputation\"}}' | python3 -m json.tool"
echo "════════════════════════════════════════════════════════════════"

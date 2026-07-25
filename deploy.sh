#!/bin/bash
set -e

# ============================================================
# RDS-NLB Registration - Deployment Script
# ============================================================
# This script:
# 1. Packages the Lambda code into a ZIP
# 2. Uploads the ZIP and CloudFormation template to an S3 bucket
# 3. Prints instructions for deploying via the AWS Console
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIP_FILE="populate_NLB_TG_with_RDS_RR.zip"
CFN_TEMPLATE="infrastructure/cloudformation_NLB_TG_with_RDS_RR.json"
S3_CODE_KEY="lambda-code/${ZIP_FILE}"
S3_CFN_KEY="cloudformation/cloudformation_NLB_TG_with_RDS_RR.json"

echo "============================================================"
echo "  RDS-NLB Registration - Deployment Setup"
echo "============================================================"
echo ""

# ----------------------------------------------------------
# Step 1: Verify AWS CLI is available
# ----------------------------------------------------------
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI is not installed or not in PATH."
    echo "Install it from: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# ----------------------------------------------------------
# Step 2: Get STS caller identity to confirm account/region
# ----------------------------------------------------------
echo "Verifying AWS identity..."
echo ""

IDENTITY=$(aws sts get-caller-identity --output json 2>&1)
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to get AWS identity. Check your AWS credentials."
    echo "$IDENTITY"
    exit 1
fi

ACCOUNT_ID=$(echo "$IDENTITY" | python3 -c "import sys, json; print(json.load(sys.stdin)['Account'])")
CALLER_ARN=$(echo "$IDENTITY" | python3 -c "import sys, json; print(json.load(sys.stdin)['Arn'])")

# Get the configured region
REGION=$(aws configure get region 2>/dev/null)
if [ -z "$REGION" ]; then
    REGION="${AWS_DEFAULT_REGION:-us-east-1}"
fi

echo "  Account:  $ACCOUNT_ID"
echo "  Region:   $REGION"
echo "  Identity: $CALLER_ARN"
echo ""

read -p "Is this the correct account and region? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo ""
    read -p "Enter the desired AWS region (e.g., us-west-2): " NEW_REGION
    if [ -z "$NEW_REGION" ]; then
        echo "ERROR: No region provided. Exiting."
        exit 1
    fi
    REGION="$NEW_REGION"
    export AWS_DEFAULT_REGION="$REGION"
    echo ""
    echo "  Region updated to: $REGION"
    echo "  Note: If you need a different account, switch your AWS credentials and re-run."
    echo ""
fi
echo ""

# ----------------------------------------------------------
# Step 3: Ask about S3 bucket
# ----------------------------------------------------------
echo "The Lambda code and CloudFormation template need to be uploaded to S3."
echo ""
read -p "Do you have an existing S3 bucket to use? (y/n): " HAS_BUCKET

if [[ "$HAS_BUCKET" == "y" || "$HAS_BUCKET" == "Y" ]]; then
    read -p "Enter the S3 bucket name (not ARN, just the name): " BUCKET_NAME
    echo ""
    echo "Verifying bucket access..."
    if ! aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
        echo "ERROR: Cannot access bucket '$BUCKET_NAME'. Check the name and your permissions."
        exit 1
    fi
    echo "  Bucket verified: $BUCKET_NAME"
else
    echo ""
    echo "Creating a new S3 bucket in account-regional namespace..."
    BUCKET_NAME="rdsnlbrr-deploy-${ACCOUNT_ID}-${REGION}-an"
    echo "  Bucket name: $BUCKET_NAME"
    echo ""

    # Create bucket with account-regional namespace
    if [ "$REGION" == "us-east-1" ]; then
        aws s3api create-bucket \
            --bucket "$BUCKET_NAME" \
            --region "$REGION" \
            --bucket-namespace "account-regional" \
            --output text > /dev/null 2>&1
    else
        aws s3api create-bucket \
            --bucket "$BUCKET_NAME" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION" \
            --bucket-namespace "account-regional" \
            --output text > /dev/null 2>&1
    fi

    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create bucket. It may already exist or you lack permissions."
        echo "Trying to use existing bucket with the same name..."
        if ! aws s3api head-bucket --bucket "$BUCKET_NAME" 2>/dev/null; then
            echo "ERROR: Cannot access bucket '$BUCKET_NAME'."
            exit 1
        fi
    fi

    echo "  Bucket created successfully: $BUCKET_NAME"
fi
echo ""

# ----------------------------------------------------------
# Step 4: Package Lambda code
# ----------------------------------------------------------
echo "Packaging Lambda code..."
cd "$SCRIPT_DIR"

# Remove old zip if exists
rm -f "$ZIP_FILE"

# Create ZIP with Python files and bundled dnspython library
zip -r "$ZIP_FILE" *.py dns/ dnspython-2.6.1.dist-info/ > /dev/null 2>&1

if [ ! -f "$ZIP_FILE" ]; then
    echo "ERROR: Failed to create ZIP file."
    exit 1
fi

ZIP_SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo "  Created: $ZIP_FILE ($ZIP_SIZE)"
echo ""

# ----------------------------------------------------------
# Step 5: Upload ZIP and CloudFormation template to S3
# ----------------------------------------------------------
echo "Uploading to S3..."

aws s3 cp "$ZIP_FILE" "s3://${BUCKET_NAME}/${S3_CODE_KEY}" --region "$REGION" > /dev/null
echo "  Uploaded: s3://${BUCKET_NAME}/${S3_CODE_KEY}"

aws s3 cp "$CFN_TEMPLATE" "s3://${BUCKET_NAME}/${S3_CFN_KEY}" --region "$REGION" > /dev/null
echo "  Uploaded: s3://${BUCKET_NAME}/${S3_CFN_KEY}"

# Clean up local ZIP
rm -f "$ZIP_FILE"
echo ""

# ----------------------------------------------------------
# Step 6: Generate CloudFormation Console URL
# ----------------------------------------------------------
TEMPLATE_URL="https://${BUCKET_NAME}.s3.${REGION}.amazonaws.com/${S3_CFN_KEY}"

echo "============================================================"
echo "  DEPLOYMENT READY"
echo "============================================================"
echo ""
echo "Your artifacts are uploaded. Deploy via the AWS Console:"
echo ""
echo "  1. Open the CloudFormation Console:"
echo "     https://${REGION}.console.aws.amazon.com/cloudformation/home?region=${REGION}#/stacks/create"
echo ""
echo "  2. Select 'Amazon S3 URL' and paste:"
echo "     ${TEMPLATE_URL}"
echo ""
echo "  3. Fill in the parameters:"
echo "     - Lambda Code S3 Bucket: ${BUCKET_NAME}"
echo "     - Set Create* flags as needed"
echo "     - Provide existing resource ARNs/names where applicable"
echo ""
echo "  4. Check 'I acknowledge that AWS CloudFormation might create IAM resources'"
echo ""
echo "  5. Click 'Create stack'"
echo ""
echo "------------------------------------------------------------"
echo "  NOTE: The bucket '${BUCKET_NAME}' contains your deployment"
echo "  artifacts. You can delete it when you no longer plan to"
echo "  update the stack:"
echo ""
echo "    aws s3 rm s3://${BUCKET_NAME} --recursive --region ${REGION}"
echo "    aws s3api delete-bucket --bucket ${BUCKET_NAME} --region ${REGION}"
echo "------------------------------------------------------------"
echo ""

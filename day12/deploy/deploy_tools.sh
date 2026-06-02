#!/bin/bash
# =============================================================================
# SIGMA INTELLIGENCE PLATFORM — Deploy All Lambda Tool Functions
# =============================================================================
# Run from the day12/ directory:
#   bash deploy/deploy_tools.sh
#
# Prerequisites:
#   - .env file in lab/ with LAMBDA_ROLE_ARN, AWS_DEFAULT_REGION
#   - AWS CLI configured with permissions to create/update Lambda functions
#   - pip install python-dotenv (for the Python test at the end)
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAB_DIR="$SCRIPT_DIR/../lab"
ENV_FILE="$LAB_DIR/.env"

# Load env vars
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | grep -v '^$' | xargs)
else
    echo "[ERROR] $ENV_FILE not found. Copy lab/.env.example to lab/.env and fill in values."
    exit 1
fi

REGION="${AWS_DEFAULT_REGION:-us-east-1}"
ROLE="${LAMBDA_ROLE_ARN}"

if [ -z "$ROLE" ]; then
    echo "[ERROR] LAMBDA_ROLE_ARN not set in lab/.env"
    exit 1
fi

echo "========================================================"
echo "SIGMA INTELLIGENCE PLATFORM — LAMBDA TOOL DEPLOYMENT"
echo "========================================================"
echo "  Region : $REGION"
echo "  Role   : $ROLE"
echo "========================================================"

# Tool definitions: "function-name:source-file"
TOOLS=(
    "sigma-tool-check-cloudwatch:tools/check_cloudwatch.py"
    "sigma-tool-get-kinesis-records:tools/get_kinesis_records.py"
    "sigma-tool-query-snowflake:tools/query_snowflake.py"
    "sigma-tool-rollback-lambda:tools/rollback_lambda_version.py"
    "sigma-tool-create-alarm:tools/create_cloudwatch_alarm.py"
    "sigma-tool-quarantine-rows:tools/quarantine_rows.py"
    "sigma-tool-load-snowflake:tools/load_to_snowflake.py"
    "sigma-tool-write-report:tools/write_incident_report.py"
    "sigma-tool-send-alert:tools/send_sns_alert.py"
    "sigma-mcp-server:mcp/sigma_mcp_server.py"
)

# Tools that need snowflake-connector-python bundled (not in Lambda runtime)
SNOWFLAKE_TOOLS=("sigma-tool-query-snowflake" "sigma-tool-load-snowflake")

needs_snowflake() {
    local name="$1"
    for t in "${SNOWFLAKE_TOOLS[@]}"; do
        [[ "$t" == "$name" ]] && return 0
    done
    return 1
}

TOTAL=${#TOOLS[@]}
COUNT=0

for ENTRY in "${TOOLS[@]}"; do
    FUNC_NAME="${ENTRY%%:*}"
    SOURCE_FILE="${ENTRY##*:}"
    FULL_PATH="$LAB_DIR/$SOURCE_FILE"
    COUNT=$((COUNT + 1))

    echo ""
    echo "[$COUNT/$TOTAL] Deploying $FUNC_NAME..."

    if [ ! -f "$FULL_PATH" ]; then
        echo "  [ERROR] Source not found: $FULL_PATH"
        exit 1
    fi

    ZIP_FILE="/tmp/${FUNC_NAME}.zip"
    HANDLER_NAME=$(basename "$SOURCE_FILE" .py)

    if needs_snowflake "$FUNC_NAME"; then
        # Bundle snowflake-connector-python into the zip (not in Lambda runtime)
        echo "  Bundling snowflake-connector-python (takes ~30s)..."
        PKG_DIR="/tmp/pkg_${FUNC_NAME}"
        rm -rf "$PKG_DIR" && mkdir -p "$PKG_DIR"
        pip install snowflake-connector-python -t "$PKG_DIR/" -q \
            --only-binary :all:
        cp "$FULL_PATH" "$PKG_DIR/${HANDLER_NAME}.py"
        rm -f "$ZIP_FILE"
        cd "$PKG_DIR" && zip -qr "$ZIP_FILE" . && cd - > /dev/null
        rm -rf "$PKG_DIR"
    else
        # Single-file deploy (boto3 and standard lib are in Lambda runtime)
        cp "$FULL_PATH" "/tmp/${HANDLER_NAME}.py"
        rm -f "$ZIP_FILE"
        cd /tmp && zip -q "$ZIP_FILE" "${HANDLER_NAME}.py" && cd - > /dev/null
        rm -f "/tmp/${HANDLER_NAME}.py"
    fi

    # Check if function exists
    if aws lambda get-function --function-name "$FUNC_NAME" \
       --region "$REGION" > /dev/null 2>&1; then
        # Update existing function
        aws lambda update-function-code \
            --function-name "$FUNC_NAME" \
            --zip-file "fileb://$ZIP_FILE" \
            --region "$REGION" \
            --output text --query 'FunctionName' > /dev/null

        # Update environment variables
        aws lambda update-function-configuration \
            --function-name "$FUNC_NAME" \
            --environment "Variables={
                AWS_DEFAULT_REGION=$REGION,
                SIGMA_S3_BUCKET=${SIGMA_S3_BUCKET:-},
                SIGMA_STREAM=${SIGMA_STREAM:-sigma-transactions},
                PRODUCER_LAMBDA_NAME=${PRODUCER_LAMBDA_NAME:-sigma-kinesis-producer},
                PRODUCER_LAMBDA_ALIAS=${PRODUCER_LAMBDA_ALIAS:-LIVE},
                SNOWFLAKE_ACCOUNT=${SNOWFLAKE_ACCOUNT:-},
                SNOWFLAKE_USER=${SNOWFLAKE_USER:-},
                SNOWFLAKE_PASSWORD=${SNOWFLAKE_PASSWORD:-},
                SNOWFLAKE_DATABASE=${SNOWFLAKE_DATABASE:-SIGMA},
                SNOWFLAKE_SCHEMA=${SNOWFLAKE_SCHEMA:-SILVER},
                SNOWFLAKE_WAREHOUSE=${SNOWFLAKE_WAREHOUSE:-SIGMA_WH},
                SNS_TOPIC_ARN=${SNS_TOPIC_ARN:-},
                LAMBDA_ROLE_ARN=${LAMBDA_ROLE_ARN:-}
            }" \
            --region "$REGION" \
            --output text --query 'FunctionName' > /dev/null

        echo "  Updated."
    else
        # Create new function
        aws lambda create-function \
            --function-name "$FUNC_NAME" \
            --runtime python3.12 \
            --role "$ROLE" \
            --handler "${HANDLER_NAME}.lambda_handler" \
            --zip-file "fileb://$ZIP_FILE" \
            --timeout 120 \
            --memory-size 256 \
            --environment "Variables={
                AWS_DEFAULT_REGION=$REGION,
                SIGMA_S3_BUCKET=${SIGMA_S3_BUCKET:-},
                SIGMA_STREAM=${SIGMA_STREAM:-sigma-transactions},
                PRODUCER_LAMBDA_NAME=${PRODUCER_LAMBDA_NAME:-sigma-kinesis-producer},
                PRODUCER_LAMBDA_ALIAS=${PRODUCER_LAMBDA_ALIAS:-LIVE},
                SNOWFLAKE_ACCOUNT=${SNOWFLAKE_ACCOUNT:-},
                SNOWFLAKE_USER=${SNOWFLAKE_USER:-},
                SNOWFLAKE_PASSWORD=${SNOWFLAKE_PASSWORD:-},
                SNOWFLAKE_DATABASE=${SNOWFLAKE_DATABASE:-SIGMA},
                SNOWFLAKE_SCHEMA=${SNOWFLAKE_SCHEMA:-SILVER},
                SNOWFLAKE_WAREHOUSE=${SNOWFLAKE_WAREHOUSE:-SIGMA_WH},
                SNS_TOPIC_ARN=${SNS_TOPIC_ARN:-},
                LAMBDA_ROLE_ARN=${LAMBDA_ROLE_ARN:-}
            }" \
            --region "$REGION" \
            --output text --query 'FunctionName' > /dev/null

        # Wait for function to be active
        aws lambda wait function-active \
            --function-name "$FUNC_NAME" \
            --region "$REGION"

        echo "  Created."
    fi

    # Clean up zip
    rm -f "$ZIP_FILE"
done

echo ""
echo "========================================================"
echo "All $TOTAL tools deployed."
echo "========================================================"
echo ""
echo "Testing MCP tool discovery..."
cd "$LAB_DIR"
python mcp/test_mcp.py

echo ""
echo "Next steps:"
echo "  1. Confirm all 10/10 tools reachable (output above)"
echo "  2. Fill in lab/.env with Bedrock agent IDs from Anil"
echo "  3. Run a health check:"
echo "     python lab/trigger/pipeline_trigger.py --health-check"
echo "========================================================"

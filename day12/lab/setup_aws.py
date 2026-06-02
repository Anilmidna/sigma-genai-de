#!/usr/bin/env python3
"""
setup_aws.py
Creates all required AWS infrastructure for the Day 12 lab.
Run this FIRST — before deploy_tools.sh or anything else.

Creates:
  - S3 bucket (sigma-datatech-<your-name>)
  - SNS topic (sigma-alerts) + subscribes your email
  - IAM role (sigma-lambda-role) with all needed permissions
  - Writes ARNs to lab/.env automatically

Usage (from repo/day12/ directory):
    python lab/setup_aws.py
"""

import boto3, json, os, re, sys, time
from pathlib import Path

REGION     = "us-east-1"
SCRIPT_DIR = Path(__file__).parent
ENV_PATH   = SCRIPT_DIR / ".env"


def log(msg): print(msg, flush=True)


def load_env():
    env = {}
    if not ENV_PATH.exists():
        return env
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def update_env(updates):
    content = ENV_PATH.read_text() if ENV_PATH.exists() else ""
    for key, val in updates.items():
        pattern = rf"^{re.escape(key)}\s*=.*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{key}={val}", content, flags=re.MULTILINE)
        else:
            content = content.rstrip("\n") + f"\n{key}={val}\n"
    ENV_PATH.write_text(content)


# ── S3 Bucket ──────────────────────────────────────────────────────────────────

def create_s3_bucket(s3, sts, bucket_name):
    log(f"\n[1/3] Creating S3 bucket: {bucket_name}")

    # Derive bucket name if placeholder
    if "YOURTEAM" in bucket_name or not bucket_name:
        account_id  = sts.get_caller_identity()["Account"]
        bucket_name = f"sigma-datatech-{account_id[-6:]}"
        log(f"  No bucket name set — using: {bucket_name}")

    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        log(f"  Created: {bucket_name}")
    except s3.exceptions.BucketAlreadyOwnedByYou:
        log(f"  Already exists: {bucket_name}")
    except s3.exceptions.BucketAlreadyExists:
        # Bucket name taken — add account suffix
        account_id  = sts.get_caller_identity()["Account"]
        bucket_name = f"sigma-datatech-{account_id[-8:]}"
        s3.create_bucket(Bucket=bucket_name)
        log(f"  Created with suffix: {bucket_name}")

    # Create folder structure via zero-byte objects
    for prefix in ["bronze/", "quarantine/", "reports/"]:
        s3.put_object(Bucket=bucket_name, Key=prefix)
    log(f"  Folders created: bronze/ quarantine/ reports/")

    return bucket_name


# ── SNS Topic ──────────────────────────────────────────────────────────────────

def create_sns_topic(sns, email):
    log(f"\n[2/3] Creating SNS topic: sigma-alerts")

    resp      = sns.create_topic(Name="sigma-alerts")
    topic_arn = resp["TopicArn"]
    log(f"  ARN: {topic_arn}")

    if email:
        try:
            sns.subscribe(TopicArn=topic_arn, Protocol="email", Endpoint=email)
            log(f"  Subscription sent to {email} — check inbox to confirm")
        except Exception as e:
            log(f"  Could not subscribe {email}: {e}")
    else:
        log(f"  No email set in .env — skipping subscription")

    return topic_arn


# ── IAM Role ───────────────────────────────────────────────────────────────────

def create_lambda_role(iam, account_id, bucket_name):
    log(f"\n[3/3] Creating IAM role: sigma-lambda-role")

    role_name = "sigma-lambda-role"

    # Trust policy — Lambda service can assume this role
    trust = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action":    "sts:AssumeRole",
        }],
    }

    # Permissions policy
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "S3Access",
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject",
                           "s3:ListBucket", "s3:GetBucketLocation"],
                "Resource": [
                    f"arn:aws:s3:::{bucket_name}",
                    f"arn:aws:s3:::{bucket_name}/*",
                    "arn:aws:s3:::sigma-datatech-*",
                    "arn:aws:s3:::sigma-datatech-*/*",
                ],
            },
            {
                "Sid": "CloudWatchAccess",
                "Effect": "Allow",
                "Action": [
                    "cloudwatch:GetMetricStatistics", "cloudwatch:ListMetrics",
                    "cloudwatch:PutMetricData", "cloudwatch:PutMetricAlarm",
                    "cloudwatch:DescribeAlarms", "cloudwatch:DeleteAlarms",
                ],
                "Resource": "*",
            },
            {
                "Sid": "LambdaAccess",
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction", "lambda:GetFunction",
                    "lambda:ListVersionsByFunction", "lambda:ListAliases",
                    "lambda:UpdateAlias", "lambda:CreateAlias",
                    "lambda:PublishVersion", "lambda:UpdateFunctionCode",
                    "lambda:GetAlias", "lambda:CreateFunction",
                    "lambda:UpdateFunctionConfiguration",
                ],
                "Resource": "*",
            },
            {
                "Sid": "SNSAccess",
                "Effect": "Allow",
                "Action": ["sns:Publish", "sns:Subscribe", "sns:ListTopics"],
                "Resource": "*",
            },
            {
                "Sid": "CloudWatchLogs",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup", "logs:CreateLogStream",
                    "logs:PutLogEvents", "logs:DescribeLogGroups",
                ],
                "Resource": "*",
            },
            {
                "Sid": "BedrockAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeAgent", "bedrock:InvokeModel",
                    "bedrock-agent-runtime:InvokeAgent",
                    "bedrock-agent-runtime:Retrieve",
                ],
                "Resource": "*",
            },
        ],
    }

    try:
        resp = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust),
            Description="Sigma Intelligence Platform — Lambda execution role",
        )
        role_arn = resp["Role"]["Arn"]
        log(f"  Role created: {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        log(f"  Already exists: {role_arn}")

    # Attach managed policy for basic Lambda execution
    try:
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
    except iam.exceptions.EntityAlreadyExistsException:
        pass
    except Exception:
        pass

    # Put inline policy with all permissions
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="sigma-platform-policy",
        PolicyDocument=json.dumps(policy),
    )
    log(f"  Permissions attached.")
    log(f"  Waiting 10 seconds for IAM propagation...")
    time.sleep(10)

    return role_arn


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("SIGMA INTELLIGENCE PLATFORM — AWS SETUP")
    log("Creates: S3 bucket, SNS topic, IAM role")
    log("=" * 60)

    env = load_env()

    sts = boto3.client("sts", region_name=REGION)
    try:
        identity   = sts.get_caller_identity()
        account_id = identity["Account"]
        log(f"\nAccount : {account_id}")
        log(f"Region  : {REGION}")
    except Exception as e:
        log(f"\n[ERROR] AWS credentials not configured: {e}")
        log("Run: aws configure")
        sys.exit(1)

    s3  = boto3.client("s3",  region_name=REGION)
    sns = boto3.client("sns", region_name=REGION)
    iam = boto3.client("iam", region_name=REGION)

    # 1. S3 bucket
    bucket_name = env.get("SIGMA_S3_BUCKET", "sigma-datatech-YOURTEAM")
    bucket_name = create_s3_bucket(s3, sts, bucket_name)

    # 2. SNS topic
    email     = env.get("ALERT_EMAIL", "")
    topic_arn = create_sns_topic(sns, email)

    # 3. IAM role
    role_arn = create_lambda_role(iam, account_id, bucket_name)

    # Write all values to .env
    update_env({
        "SIGMA_S3_BUCKET":  bucket_name,
        "SNS_TOPIC_ARN":    topic_arn,
        "LAMBDA_ROLE_ARN":  role_arn,
        "ACCOUNT_ID":       account_id,
    })

    log("\n" + "=" * 60)
    log("SETUP COMPLETE — values written to lab/.env")
    log("=" * 60)
    log(f"  S3 Bucket       : {bucket_name}")
    log(f"  SNS Topic ARN   : {topic_arn}")
    log(f"  Lambda Role ARN : {role_arn}")
    log("")
    log("Next step: bash deploy/deploy_tools.sh")
    log("=" * 60)


if __name__ == "__main__":
    main()

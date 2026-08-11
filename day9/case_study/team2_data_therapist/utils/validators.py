"""
Validators — Data Therapist
Downstream validation checks to detect AI fix corruption.
"""

import pandas as pd


def validate_refund_integrity(bronze_df: pd.DataFrame, silver_df: pd.DataFrame) -> dict:
    """
    Check if refund amounts are correctly preserved (negative) in Silver.
    THE TRAP: If negative amounts were converted to positive, this will catch it.
    """
    results = {"passed": True, "checks": []}

    if silver_df.empty:
        results["passed"] = False
        results["checks"].append({"name": "Silver Not Empty", "status": "FAIL", "detail": "Silver table is empty"})
        return results

    # Check 1: Refund count preservation
    bronze_refunds = bronze_df[bronze_df["transaction_type"] == "REFUND"]
    silver_refunds = silver_df[silver_df["transaction_type"] == "REFUND"] if "transaction_type" in silver_df.columns else pd.DataFrame()

    bronze_ref_count = len(bronze_refunds)
    silver_ref_count = len(silver_refunds)
    ref_count_ok = abs(bronze_ref_count - silver_ref_count) <= 2  # allow for some filtering

    results["checks"].append({
        "name": "Refund Count Preservation",
        "status": "PASS" if ref_count_ok else "WARN",
        "detail": f"Bronze: {bronze_ref_count} refunds | Silver: {silver_ref_count} refunds",
        "bronze_value": bronze_ref_count,
        "silver_value": silver_ref_count,
    })

    # Check 2: Refund amounts remain negative
    if not silver_refunds.empty:
        positive_refunds = silver_refunds[silver_refunds["transaction_amount"] > 0]
        refund_sign_ok = len(positive_refunds) == 0

        results["checks"].append({
            "name": "Refund Amounts Are Negative",
            "status": "PASS" if refund_sign_ok else "FAIL",
            "detail": f"{len(positive_refunds)} refunds have POSITIVE amounts (should be negative) — revenue is corrupted!",
            "bronze_value": 0,
            "silver_value": len(positive_refunds),
        })

        if not refund_sign_ok:
            results["passed"] = False
            corrupted_revenue = positive_refunds["transaction_amount"].sum()
            results["corruption_amount"] = corrupted_revenue
    else:
        results["checks"].append({
            "name": "Refund Amounts Are Negative",
            "status": "WARN",
            "detail": "No refund records in Silver to check",
            "bronze_value": bronze_ref_count,
            "silver_value": 0,
        })

    # Check 3: Revenue variance Bronze → Silver
    bronze_completed = bronze_df[bronze_df["status"] == "COMPLETED"]
    silver_completed = silver_df[silver_df["status"] == "COMPLETED"] if not silver_df.empty else pd.DataFrame()

    bronze_rev = bronze_completed["transaction_amount"].sum()
    silver_rev = silver_completed["transaction_amount"].sum() if not silver_completed.empty else 0

    if bronze_rev != 0:
        rev_variance_pct = abs((silver_rev - bronze_rev) / bronze_rev * 100)
        rev_ok = rev_variance_pct <= 10  # Allow up to 10% variance from fixes
    else:
        rev_variance_pct = 0
        rev_ok = True

    results["checks"].append({
        "name": "Revenue Variance < 10%",
        "status": "PASS" if rev_ok else "FAIL",
        "detail": f"Bronze Revenue: ₹{bronze_rev:,.2f} | Silver Revenue: ₹{silver_rev:,.2f} | Variance: {rev_variance_pct:.1f}%",
        "bronze_value": bronze_rev,
        "silver_value": silver_rev,
    })

    if not rev_ok:
        results["passed"] = False

    # Check 4: No negative amounts in non-refund records (data entry error check)
    if not silver_df.empty and "transaction_type" in silver_df.columns:
        non_refund_negatives = silver_df[
            (silver_df["transaction_amount"] < 0) &
            (silver_df["transaction_type"] != "REFUND")
        ]
        non_refund_neg_ok = len(non_refund_negatives) == 0

        results["checks"].append({
            "name": "No Non-Refund Negatives",
            "status": "PASS" if non_refund_neg_ok else "WARN",
            "detail": f"{len(non_refund_negatives)} non-refund records still have negative amounts",
            "bronze_value": len(bronze_df[(bronze_df["transaction_amount"] < 0) & (bronze_df.get("transaction_type", "") != "REFUND")]),
            "silver_value": len(non_refund_negatives),
        })

    return results


def validate_deduplication(bronze_df: pd.DataFrame, silver_df: pd.DataFrame) -> dict:
    """Check that Silver has no duplicate transaction IDs."""
    if silver_df.empty:
        return {"passed": False, "duplicate_count": 0, "detail": "Silver is empty"}

    non_null_silver = silver_df.dropna(subset=["transaction_id"])
    dup_count = non_null_silver["transaction_id"].duplicated().sum()

    return {
        "passed": dup_count == 0,
        "duplicate_count": int(dup_count),
        "detail": f"{dup_count} duplicate transaction IDs remain in Silver" if dup_count > 0 else "No duplicates — ✅",
    }


def validate_null_constraints(silver_df: pd.DataFrame) -> dict:
    """Check Silver null rates against defined thresholds."""
    if silver_df.empty:
        return {"passed": False, "details": {}}

    n = len(silver_df)
    results = {"passed": True, "details": {}}

    null_checks = {
        "transaction_id": 0.0,  # 0% null allowed
        "merchant_name": 0.05,  # 5% null allowed after fixes
        "customer_id": 0.10,    # 10% null allowed
        "transaction_amount": 0.0,  # 0% null allowed
    }

    for col, threshold in null_checks.items():
        if col in silver_df.columns:
            null_rate = silver_df[col].isnull().sum() / n
            passed = null_rate <= threshold
            results["details"][col] = {
                "null_count": int(silver_df[col].isnull().sum()),
                "null_rate_pct": round(null_rate * 100, 2),
                "threshold_pct": round(threshold * 100, 1),
                "passed": passed,
            }
            if not passed:
                results["passed"] = False

    return results


def run_all_validations(bronze_df: pd.DataFrame, silver_df: pd.DataFrame) -> dict:
    """Run all downstream validation checks."""
    return {
        "refund_integrity": validate_refund_integrity(bronze_df, silver_df),
        "deduplication": validate_deduplication(bronze_df, silver_df),
        "null_constraints": validate_null_constraints(silver_df),
    }

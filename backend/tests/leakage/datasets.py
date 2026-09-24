"""Synthetic Datasets for Comprehensive Data Leakage Testing.

Provides deterministic synthetic datasets for every leakage scenario:
- Direct target copy (target_copy == target)
- Target-derived features (squared, scaled, ranked, category, encoded)
- Perfect correlation (y, 1-y, 2*y)
- Near-perfect correlation (correlation ~ 0.999 with noise)
- Future / Temporal leakage (admission vs discharge date, final diagnosis, treatment cost)
- Post-target leakage (post_target_status, resolution_date, final_amount)
- Semantic duplicate leakage (status_code vs status_label)
- Duplicate / Contaminated records across dataset
- Group leakage (repeated customer_id / patient_id)
- Legitimate predictive features (age, income, experience - false positive tests)
- Subtle non-linear / complex leakage (false negative tests)
"""

import numpy as np
import pandas as pd


def make_direct_target_leakage_dataset(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Dataset with an exact copy of the target column."""
    rng = np.random.default_rng(seed)
    age = rng.integers(18, 70, n)
    income = rng.normal(50000, 15000, n).round(2)
    target = (age * 0.4 + (income / 1000) * 0.6 + rng.normal(0, 5, n) > 40).astype(int)
    target_copy = target.copy()

    return pd.DataFrame({
        "age": age,
        "income": income,
        "target_copy": target_copy,
        "target": target,
    })


def make_derived_target_leakage_dataset(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Dataset with target-derived non-linear/transformed features."""
    rng = np.random.default_rng(seed)
    f1 = rng.normal(10, 2, n).round(2)
    f2 = rng.normal(20, 5, n).round(2)
    target = (f1 * 1.5 + f2 * 0.8 + rng.normal(0, 1, n)).round(2)

    return pd.DataFrame({
        "feature_1": f1,
        "feature_2": f2,
        "target_squared": np.round(target ** 2, 2),
        "target_scaled": np.round((target - target.mean()) / target.std(), 4),
        "target_rank": pd.Series(target).rank().values,
        "target_category": pd.qcut(target, q=3, labels=["low", "med", "high"]).astype(str),
        "target": target,
    })


def make_perfect_correlation_leakage_dataset(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Dataset with features that have mathematical r = 1.0 or -1.0 with target."""
    rng = np.random.default_rng(seed)
    f1 = rng.uniform(1, 100, n).round(2)
    f2 = rng.uniform(1, 50, n).round(2)
    target = rng.integers(0, 2, n)
    leak_direct = target.copy()
    leak_inverse = 1 - target
    leak_scaled = target * 10.0

    return pd.DataFrame({
        "f1": f1,
        "f2": f2,
        "leak_direct": leak_direct,
        "leak_inverse": leak_inverse,
        "leak_scaled": leak_scaled,
        "target": target,
    })


def make_near_perfect_leakage_dataset(n: int = 300, noise_level: float = 0.01, seed: int = 42) -> pd.DataFrame:
    """Dataset with a feature having near-perfect correlation (e.g., 0.999) but small noise."""
    rng = np.random.default_rng(seed)
    f1 = rng.normal(0, 1, n).round(3)
    target = rng.normal(100, 15, n).round(2)
    # Near perfect with tiny Gaussian noise
    near_leak = target + rng.normal(0, noise_level, n)

    return pd.DataFrame({
        "f1": f1,
        "proxy_target": np.round(near_leak, 2),
        "target": target,
    })


def make_temporal_future_leakage_dataset(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Dataset representing hospital admission where prediction occurs at admission.
    
    Contains features that happen post-admission (future leakage).
    """
    rng = np.random.default_rng(seed)
    patient_id = [f"P_{i:04d}" for i in range(n)]
    age = rng.integers(20, 85, n)
    admission_systolic = rng.integers(100, 180, n)
    # Target: 30-day readmission or mortality (1/0)
    target = (age > 65).astype(int) & (admission_systolic > 140).astype(int)

    # Future information only available after discharge
    length_of_stay = rng.integers(1, 20, n) + target * 5
    discharge_date = [f"2026-03-{min(28, d):02d}" for d in length_of_stay]
    final_diagnosis = ["Resolved" if t == 0 else "Severe Complications" for t in target]
    treatment_cost = length_of_stay * 1200.0 + rng.normal(500, 100, n).round(2)

    return pd.DataFrame({
        "patient_id": patient_id,
        "age": age,
        "admission_systolic": admission_systolic,
        "discharge_date": discharge_date,
        "final_diagnosis": final_diagnosis,
        "treatment_cost": treatment_cost,
        "target": target,
    })


def make_post_target_leakage_dataset(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Dataset containing post-target event outcomes."""
    rng = np.random.default_rng(seed)
    amount = rng.uniform(100, 5000, n).round(2)
    target = rng.integers(0, 2, n)
    post_target_status = ["Settled" if t == 1 else "Defaulted" for t in target]
    resolution_date = ["2026-09-01" if t == 1 else "2026-12-01" for t in target]
    final_amount = amount * (1.0 + 0.1 * target)

    return pd.DataFrame({
        "amount": amount,
        "post_target_status": post_target_status,
        "resolution_date": resolution_date,
        "final_amount": np.round(final_amount, 2),
        "target": target,
    })


def make_semantic_duplicate_leakage_dataset(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Dataset where semantic status columns duplicate the target."""
    rng = np.random.default_rng(seed)
    f1 = rng.normal(50, 10, n).round(2)
    status_code = rng.choice([0, 1, 2], size=n)
    status_label = pd.Series(status_code).map({0: "Inactive", 1: "Active", 2: "Suspended"}).values
    target = status_code.copy()

    return pd.DataFrame({
        "f1": f1,
        "status_code": status_code,
        "status_label": status_label,
        "target": target,
    })


def make_duplicate_rows_dataset(n_unique: int = 100, repeats: int = 3, seed: int = 42) -> pd.DataFrame:
    """Dataset containing exact duplicate rows (train/test contamination risk)."""
    rng = np.random.default_rng(seed)
    f1 = rng.normal(0, 1, n_unique).round(3)
    f2 = rng.integers(0, 10, n_unique)
    target = rng.integers(0, 2, n_unique)

    base_df = pd.DataFrame({"f1": f1, "f2": f2, "target": target})
    df_repeated = pd.concat([base_df] * repeats, ignore_index=True)
    return df_repeated


def make_group_leakage_dataset(n_groups: int = 50, rows_per_group: int = 6, seed: int = 42) -> pd.DataFrame:
    """Dataset with clustered customer_id entries across multiple rows."""
    rng = np.random.default_rng(seed)
    records = []
    for g in range(n_groups):
        cid = f"CUST_{g:04d}"
        cust_target = int(rng.integers(0, 2))
        for _ in range(rows_per_group):
            records.append({
                "customer_id": cid,
                "feature_1": round(float(rng.normal(25, 5)), 2),
                "feature_2": round(float(rng.normal(100, 20)), 2),
                "target": cust_target,
            })
    return pd.DataFrame(records)


def make_legitimate_predictive_dataset(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Dataset with legitimate strong predictive signals that must NOT be dropped as leakage."""
    rng = np.random.default_rng(seed)
    age = rng.integers(22, 65, n)
    experience = np.maximum(0, age - 22 + rng.integers(-2, 3, n))
    education_years = rng.choice([12, 14, 16, 18, 20], size=n)
    # Legitimate income formula correlated with age & experience
    income = (experience * 2500 + education_years * 3000 + rng.normal(10000, 3000, n)).round(2)
    target = (income > 65000).astype(int)

    return pd.DataFrame({
        "age": age,
        "experience": experience,
        "education_years": education_years,
        "income": income,
        "target": target,
    })

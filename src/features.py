import numpy as np
import pandas as pd

# Production-safe feature contract. These can be entered/derived without requiring a credit bureau file.
FEATURES = [
 'age_years','annual_income','loan_amount','annuity_amount','employment_years',
 'family_size','children','education','income_type','housing_type',
 'phone_changed_years','external_score','prior_loans','prior_defaults',
 'on_time_payment_ratio','avg_days_late','credit_card_utilization','monthly_txn_count',
 'avg_monthly_balance','income_stability','digital_payment_ratio','savings_ratio'
]
CATEGORICAL=['education','income_type','housing_type']
NUMERIC=[c for c in FEATURES if c not in CATEGORICAL]

def engineer(df: pd.DataFrame) -> pd.DataFrame:
    x=df.copy()
    # Guardrails / derived behavioral signals
    x['loan_to_income']=x['loan_amount']/(x['annual_income'].clip(lower=1))
    x['annuity_to_income']=(12*x['annuity_amount'])/(x['annual_income'].clip(lower=1))
    x['default_history_ratio']=x['prior_defaults']/(x['prior_loans'].clip(lower=1))
    x['balance_to_income']=(12*x['avg_monthly_balance'])/(x['annual_income'].clip(lower=1))
    return x.replace([np.inf,-np.inf],np.nan)

def model_features():
    return FEATURES+['loan_to_income','annuity_to_income','default_history_ratio','balance_to_income']

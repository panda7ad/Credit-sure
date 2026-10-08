from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

POLICY_VERSION = "2026-10-08-research-v1"


class Applicant(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    applicant_name: str = Field(min_length=1, max_length=120)
    age_years: int = Field(ge=18, le=100)
    annual_income: float = Field(gt=0, le=1_000_000_000)
    loan_amount: float = Field(gt=0, le=1_000_000_000)
    annuity_amount: float = Field(gt=0, le=100_000_000)
    employment_years: float | None = Field(default=None, ge=0, le=70)
    family_size: int | None = Field(default=None, ge=1, le=30)
    children: int | None = Field(default=None, ge=0, le=20)
    education: Literal["Higher education", "Secondary / secondary special", "Incomplete higher", "Lower secondary"] | None = None
    income_type: Literal["Working", "Commercial associate", "Pensioner", "State servant"] | None = None
    housing_type: Literal["House / apartment", "With parents", "Rented apartment", "Municipal apartment"] | None = None
    phone_changed_years: float | None = Field(default=None, ge=0, le=50)
    external_score: float | None = Field(default=None, ge=0, le=1)
    prior_loans: int | None = Field(default=None, ge=0, le=1000)
    prior_defaults: int | None = Field(default=None, ge=0, le=1000)
    on_time_payment_ratio: float | None = Field(default=None, ge=0, le=1)
    avg_days_late: float | None = Field(default=None, ge=0, le=3650)
    credit_card_utilization: float | None = Field(default=None, ge=0, le=5)
    monthly_txn_count: int | None = Field(default=None, ge=0, le=100000)
    avg_monthly_balance: float | None = Field(default=None, ge=0, le=1_000_000_000)
    income_stability: float | None = Field(default=None, ge=0, le=1)
    digital_payment_ratio: float | None = Field(default=None, ge=0, le=1)
    savings_ratio: float | None = Field(default=None, ge=0, le=1)

    @field_validator("applicant_name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Use a nonempty synthetic identifier without control characters")
        return value


class AssessmentRequest(Applicant):
    research_confirmed: StrictBool

    @field_validator("research_confirmed")
    @classmethod
    def synthetic_only(cls, value):
        if value is not True:
            raise ValueError("Confirm that this assessment uses synthetic research data")
        return value


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_version: Literal["2026-10-08-research-v1"]
    accepted: StrictBool

    @field_validator("accepted")
    @classmethod
    def require_acceptance(cls, value):
        if value is not True:
            raise ValueError("Policy acceptance is required")
        return value


class DeleteAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["DELETE MY ACCOUNT"]

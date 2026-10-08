"""Create a production-shaped training table from Home Credit tables.
The target comes from application_train. Behavioral features are aggregated from
installments, credit cards and previous applications. Missing modern behavioral
fields are proxied from available anonymized Home Credit signals.
"""
import numpy as np, pandas as pd
from config import RAW,PROCESSED

def safe_read(name,usecols=None): return pd.read_csv(RAW/name,usecols=usecols)

def main():
    app=safe_read('application_train.csv')
    out=pd.DataFrame({'SK_ID_CURR':app.SK_ID_CURR,'TARGET':app.TARGET})
    out['age_years']=(-app.DAYS_BIRTH/365.25).clip(18,100)
    out['annual_income']=app.AMT_INCOME_TOTAL
    out['loan_amount']=app.AMT_CREDIT
    out['annuity_amount']=app.AMT_ANNUITY
    out['employment_years']=(-app.DAYS_EMPLOYED/365.25).where(app.DAYS_EMPLOYED<0,0).clip(0,60)
    out['family_size']=app.CNT_FAM_MEMBERS
    out['children']=app.CNT_CHILDREN
    out['education']=app.NAME_EDUCATION_TYPE.astype(str)
    out['income_type']=app.NAME_INCOME_TYPE.astype(str)
    out['housing_type']=app.NAME_HOUSING_TYPE.astype(str)
    out['phone_changed_years']=(-app.DAYS_LAST_PHONE_CHANGE/365.25).clip(0,30)
    ext=app[[c for c in ['EXT_SOURCE_1','EXT_SOURCE_2','EXT_SOURCE_3'] if c in app]].mean(axis=1)
    out['external_score']=ext
    # proxy stability from employment relative to age
    out['income_stability']=(out.employment_years/out.age_years).clip(0,1)

    prev=safe_read('previous_application.csv', ['SK_ID_CURR','NAME_CONTRACT_STATUS'])
    g=prev.groupby('SK_ID_CURR').agg(prior_loans=('NAME_CONTRACT_STATUS','size'), prior_defaults=('NAME_CONTRACT_STATUS',lambda s:(s=='Refused').sum())).reset_index()
    out=out.merge(g,on='SK_ID_CURR',how='left')

    inst=safe_read('installments_payments.csv',['SK_ID_CURR','DAYS_INSTALMENT','DAYS_ENTRY_PAYMENT','AMT_INSTALMENT','AMT_PAYMENT'])
    inst['days_late']=(inst.DAYS_ENTRY_PAYMENT-inst.DAYS_INSTALMENT).clip(lower=0)
    inst['ontime']=(inst.days_late<=0).astype(float)
    ig=inst.groupby('SK_ID_CURR').agg(on_time_payment_ratio=('ontime','mean'),avg_days_late=('days_late','mean'),monthly_txn_count=('days_late','size')).reset_index()
    # scale count into a rough monthly intensity proxy
    ig['monthly_txn_count']=(ig.monthly_txn_count/24).clip(0,100)
    out=out.merge(ig,on='SK_ID_CURR',how='left')

    cc=safe_read('credit_card_balance.csv',['SK_ID_CURR','AMT_BALANCE','AMT_CREDIT_LIMIT_ACTUAL','AMT_PAYMENT_TOTAL_CURRENT'])
    cc['util']=cc.AMT_BALANCE/cc.AMT_CREDIT_LIMIT_ACTUAL.replace(0,np.nan)
    cg=cc.groupby('SK_ID_CURR').agg(credit_card_utilization=('util','mean'),avg_monthly_balance=('AMT_BALANCE','mean'),digital_payment_proxy=('AMT_PAYMENT_TOTAL_CURRENT','mean')).reset_index()
    out=out.merge(cg,on='SK_ID_CURR',how='left')
    # Home Credit lacks literal digital/savings fields; transparent proxies for demo.
    out['digital_payment_ratio']=(out.get('digital_payment_proxy',0)/(out.annual_income/12).replace(0,np.nan)).clip(0,1)
    out['savings_ratio']=(1-(12*out.annuity_amount/out.annual_income.replace(0,np.nan))).clip(0,1)
    out.drop(columns=['digital_payment_proxy'],errors='ignore',inplace=True)
    out.to_csv(PROCESSED/'credit_training.csv',index=False)
    print('Saved',out.shape,PROCESSED/'credit_training.csv','default rate=',out.TARGET.mean())
if __name__=='__main__': main()

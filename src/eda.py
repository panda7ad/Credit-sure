import json, pandas as pd, matplotlib.pyplot as plt, seaborn as sns
from config import PROCESSED,REPORTS

def main():
 d=pd.read_csv(PROCESSED/'credit_training.csv')
 summary={'rows':len(d),'columns':len(d.columns),'default_rate':float(d.TARGET.mean()),'duplicates':int(d.duplicated().sum()),'missing_pct':{k:float(v) for k,v in (d.isna().mean()*100).sort_values(ascending=False).items()}}
 (REPORTS/'eda_summary.json').write_text(json.dumps(summary,indent=2))
 plt.figure(figsize=(6,4)); sns.countplot(data=d,x='TARGET'); plt.title('Target distribution'); plt.tight_layout(); plt.savefig(REPORTS/'target_distribution.png'); plt.close()
 num=d.select_dtypes('number'); corr=num.corr(numeric_only=True)['TARGET'].drop('TARGET').abs().sort_values(ascending=False).head(15)
 plt.figure(figsize=(8,6)); corr.sort_values().plot(kind='barh'); plt.title('Top absolute correlations with default'); plt.tight_layout(); plt.savefig(REPORTS/'top_correlations.png'); plt.close()
 print(json.dumps({k:v for k,v in summary.items() if k!='missing_pct'},indent=2))
if __name__=='__main__': main()

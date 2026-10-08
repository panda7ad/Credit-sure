import json, time, joblib, numpy as np, pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score,average_precision_score,accuracy_score,precision_score,recall_score,f1_score,confusion_matrix
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier
from config import PROCESSED,MODELS,REPORTS,RANDOM_STATE
from src.features import engineer,FEATURES,CATEGORICAL,NUMERIC,model_features

def metrics(y,p,thr=.5):
 pred=(p>=thr).astype(int)
 return {'roc_auc':roc_auc_score(y,p),'pr_auc':average_precision_score(y,p),'accuracy':accuracy_score(y,pred),'precision':precision_score(y,pred,zero_division=0),'recall':recall_score(y,pred,zero_division=0),'f1':f1_score(y,pred,zero_division=0),'confusion_matrix':confusion_matrix(y,pred).tolist()}

def choose_threshold(y,p):
 # prioritize catching defaults while retaining reasonable approvals; maximize F2
 best=(.5,-1)
 for t in np.arange(.1,.71,.01):
  pred=p>=t; pr=precision_score(y,pred,zero_division=0); rc=recall_score(y,pred,zero_division=0)
  f2=5*pr*rc/(4*pr+rc) if (4*pr+rc) else 0
  if f2>best[1]: best=(float(t),f2)
 return best[0]

def main():
 d=pd.read_csv(PROCESSED/'credit_training.csv'); y=d.pop('TARGET').astype(int); X=engineer(d[FEATURES])
 Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=.2,stratify=y,random_state=RANDOM_STATE)
 cats=CATEGORICAL; nums=[c for c in model_features() if c not in cats]
 prep=ColumnTransformer([('num',Pipeline([('imp',SimpleImputer(strategy='median')),('scale',StandardScaler())]),nums),('cat',Pipeline([('imp',SimpleImputer(strategy='most_frequent')),('ohe',OneHotEncoder(handle_unknown='ignore'))]),cats)])
 models={
 'logistic_regression':LogisticRegression(max_iter=1000,class_weight='balanced'),
 'random_forest':RandomForestClassifier(n_estimators=350,max_depth=14,min_samples_leaf=5,class_weight='balanced_subsample',n_jobs=-1,random_state=RANDOM_STATE),
 'lightgbm':LGBMClassifier(n_estimators=500,learning_rate=.04,num_leaves=31,subsample=.85,colsample_bytree=.85,class_weight='balanced',random_state=RANDOM_STATE,verbosity=-1),
 'xgboost':XGBClassifier(n_estimators=450,max_depth=5,learning_rate=.04,subsample=.85,colsample_bytree=.85,eval_metric='logloss',random_state=RANDOM_STATE,n_jobs=-1)
 }
 results={}; best=None
 for name,m in models.items():
  pipe=Pipeline([('prep',prep),('model',m)]); start=time.time(); pipe.fit(Xtr,ytr); p=pipe.predict_proba(Xte)[:,1]; th=choose_threshold(yte,p); r=metrics(yte,p,th); r['threshold']=th;r['train_seconds']=round(time.time()-start,2);results[name]=r
  print(name,r)
  if best is None or r['roc_auc']>best[0]: best=(r['roc_auc'],name,th)
 # Refit a fresh pipeline for the winning algorithm so no shared transformer state leaks across candidates.
 winner=Pipeline([('prep',prep),('model',models[best[1]])]); winner.fit(Xtr,ytr)
 joblib.dump(winner,MODELS/'credit_model.joblib')
 meta={'best_model':best[1],'threshold':best[2],'feature_contract':FEATURES,'results':results,'note':'15% NPA reduction is a business target; validate prospectively against lender portfolio outcomes.'}
 (MODELS/'metadata.json').write_text(json.dumps(meta,indent=2)); (REPORTS/'model_results.json').write_text(json.dumps(results,indent=2))
 print('BEST',best[1],'ROC-AUC',best[0],'threshold',best[2])
if __name__=='__main__': main()

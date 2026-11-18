"""Monthly cashflow proxy forecasting, matching the supplied OLS model."""
import io
import numpy as np
import pandas as pd

FEATURES = ['trend', 'month_sin', 'month_cos', 'lag1', 'lag12']
REQUIRED = ['order_date', 'sales', 'discount', 'shipping_cost', 'revenue', 'expenses']

def load_transactions(content, filename):
    if filename.lower().endswith('.xlsx'):
        df = pd.read_excel(io.BytesIO(content))
    elif filename.lower().endswith('.csv'):
        df = pd.read_csv(io.BytesIO(content))
    else:
        raise ValueError('Please upload an .xlsx or .csv file.')
    df.columns = df.columns.astype(str).str.strip().str.lower()
    if df.columns.duplicated().any():
        raise ValueError('Column names must be unique after trimming spaces.')
    missing = [c for c in REQUIRED if c not in df]
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
    for c in REQUIRED[1:]:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    bad = df[REQUIRED].isna().any(axis=1) | ~np.isfinite(df[REQUIRED[1:]]).all(axis=1)
    if bad.any():
        raise ValueError(f'{int(bad.sum())} rows contain missing or invalid dates/financial values. Correct them before uploading.')
    if not len(df):
        raise ValueError('The file has no transactions.')
    if ((df.discount < 0) | (df.discount > 1)).any():
        raise ValueError('Discount must be a fraction between 0 and 1 (for example 0.10 for 10%).')
    if not np.allclose(df.revenue, df.sales * (1-df.discount) + df.shipping_cost):
        raise ValueError('Revenue must equal sales × (1 − discount) + shipping_cost, as required by the supplied model.')
    df['cashflow'] = df.revenue - df.expenses
    counts = df.set_index('order_date').resample('MS').size()
    if (counts == 0).any():
        raise ValueError('Some calendar months have no transactions. Complete the missing months before forecasting.')
    monthly = df.set_index('order_date').resample('MS').cashflow.sum()
    if len(monthly) < 30:
        raise ValueError('Upload at least 30 consecutive months: 12 for lags, at least 12 for training, and 6 for evaluation.')
    return monthly, {'rows': len(df), 'duplicates': int(df.duplicated().sum())}

def feature(index, first, history):
    trend = (index.year-first.year)*12 + index.month-first.month
    return [trend, np.sin(2*np.pi*index.month/12), np.cos(2*np.pi*index.month/12), history[index-pd.DateOffset(months=1)], history[index-pd.DateOffset(months=12)]]

def fit(x, y):
    # Centered least squares with intercept, equivalent to LinearRegression.
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    coef = np.linalg.lstsq(x-x.mean(axis=0), y-y.mean(), rcond=None)[0]
    return float(y.mean()-x.mean(axis=0)@coef), coef

def predict(params, x):
    return params[0] + np.asarray(x) @ params[1]

def metrics(actual, predicted):
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    err = predicted-actual
    mse = float(np.mean(err**2))
    denominator = float(np.sum((actual-actual.mean())**2))
    return {'mae': float(np.mean(abs(err))), 'mse': mse, 'rmse': float(np.sqrt(mse)), 'r2': float(1-np.sum(err**2)/denominator) if denominator else None, 'wape': float(np.sum(abs(err))/np.sum(abs(actual))*100) if np.sum(abs(actual)) else None, 'bias': float(err.mean())}

def forecast(monthly, end):
    target = pd.Timestamp(end).to_period('M').to_timestamp()
    first, last = monthly.index[0], monthly.index[-1]
    horizon = (target.year-last.year)*12 + target.month-last.month
    if not 1 <= horizon <= 60:
        raise ValueError('Choose an end month 1–60 months after the last historical month.')
    history = monthly.to_dict()
    dates = monthly.index[12:]
    x = np.array([feature(d, first, history) for d in dates])
    y = monthly.iloc[12:].to_numpy()
    ntest = min(12, len(y)-12)
    train = fit(x[:-ntest], y[:-ntest])
    one_step = predict(train, x[-ntest:])
    # Also evaluate true multi-step recursion without using holdout actuals.
    recursive_history = monthly.iloc[:-ntest].to_dict()
    recursive = []
    for d in dates[-ntest:]:
        p = float(predict(train, feature(d, first, recursive_history)))
        recursive_history[d] = p
        recursive.append(p)
    final = fit(x, y)
    future = []
    for step in range(1, horizon+1):
        d = last + pd.DateOffset(months=step)
        p = float(predict(final, feature(d, first, history)))
        if not np.isfinite(p):
            raise ValueError('The model produced an unstable forecast. Review the data or use a shorter horizon.')
        history[d] = p
        future.append({'date': d.strftime('%Y-%m'), 'cashflow': p})
    return {'history': [{'date': d.strftime('%Y-%m'), 'cashflow': float(v)} for d,v in monthly.items()], 'forecast': future, 'metrics': metrics(y[-ntest:], one_step), 'recursive_metrics': metrics(y[-ntest:], recursive), 'baseline_metrics': metrics(y[-ntest:], x[-ntest:,4]), 'evaluation': [{'date': d.strftime('%Y-%m'), 'actual': float(a), 'predicted': float(p), 'recursive': float(r)} for d,a,p,r in zip(dates[-ntest:],y[-ntest:],one_step,recursive)], 'coefficients': dict(zip(FEATURES, map(float, final[1]))), 'intercept': final[0], 'training_months': len(y)-ntest, 'test_months': ntest, 'total': float(sum(p['cashflow'] for p in future))}

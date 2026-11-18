# ShopFlow — cashflow forecasting prototype

A small fourth-year project with password registration/login, isolated shop datasets, Excel/CSV upload, recursive monthly cashflow forecasts, interactive charts, model evaluation, and CSV downloads. Runs on your computer; no external API or paid service is needed.

## Run

On this Mac, double-click **Start ShopFlow.command** to start the server and open the app in your browser. Keep its Terminal window open while using the prototype. Press Ctrl+C there to stop it. On another computer, install the dependencies below first.

```sh
cd /Users/newton/Documents/ChatGPT/Forecast/cashflow-prototype
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:8000, choose **Create an account**, then upload your workbook or choose **Try sample data**. The sample defaults to a six-month horizon; choose **August 2016** to reproduce the requested 20-month forecast after December 2014. Stop the server with Ctrl+C.

On the current Codex computer, the bundled runtime already has the dependencies:

```sh
/Users/newton/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 server.py
```

## Data format

Use `.xlsx` (first worksheet) or `.csv`, up to 30 MB, with these columns:

| Column | Meaning |
| --- | --- |
| order_date | Transaction date, preferably YYYY-MM-DD |
| sales | Sales before discount |
| discount | Fraction from 0 to 1, e.g. 0.10 |
| shipping_cost | Shipping amount |
| revenue | sales × (1 − discount) + shipping_cost |
| expenses | Transaction expenses |

Column spaces and capitalization are normalized. Invalid numbers, missing values, inconsistent revenue, or months with no transactions are rejected. At least 30 consecutive months are required to reserve 12 lag months, at least 12 training observations, and at least 6 holdout observations. Duplicates are reported and retained, following the supplied code. Currency is a display label; changing it never converts values.

Uploaded transaction rows are validated in memory. Only monthly totals and summary metadata are retained in the account database. Uploads replace the previous dataset for that account. The bundled sample contains monthly aggregates from the supplied workbook, with no customer-level fields. Its original currency was not specified; choose the appropriate display label. The source workbook contains 20 duplicate records, which are retained.

## Model and scoring

`model.py` preserves the supplied model: cashflow proxy = revenue − expenses; monthly sums; trend, month sine/cosine, lag1 and lag12; ordinary least squares with intercept; then final refit on all eligible months. NumPy centered least squares implements the same estimator as scikit-learn's `LinearRegression`, avoiding an additional dependency.

For this 2011–2014 dataset, evaluation trains on 2012–2013 and tests on 2014, as in the source. Other uploads use the latest 6–12 months as chronological holdout. One-month-ahead scores use observed lagged values, matching the source evaluation. Recursive holdout scores are also shown and never use held-out actuals as lag inputs. Future forecasts recursively insert each prediction into history, including lag12 when the horizon exceeds one year. Future end dates normalize to month start and are limited to 1–60 months ahead.

The dashboard shows MAE, RMSE, R², WAPE, bias, coefficients, and a seasonal-naive baseline. MSE is included in the forecast API response. Undefined scores appear as “Not defined.” No score is invented, and these metrics are not a credit or lending score. Cashflow is a proxy because payment dates are unavailable. No prediction intervals are claimed. Long-range forecasts can accumulate error and negative predictions are preserved.

## Architecture and limitations

- Frontend: responsive HTML, CSS, and JavaScript with SVG charts; no CDN dependencies.
- Backend: Python standard-library HTTP server plus pandas, NumPy, and openpyxl.
- Authentication: PBKDF2-SHA256 salted password hashes, random server-side 8-hour sessions, HttpOnly/SameSite cookies, same-origin mutation checks.
- Storage: local SQLite; every dataset lookup is restricted to the signed-in account. Database is gitignored. There is no seeded account or shared demo password.
- This is a local academic prototype, bound to loopback. It has not been deployed to Sites because Sites hosting runs Cloudflare Workers and cannot run this Python/pandas backend. Production hosting would require a Python-capable host or a backend port, HTTPS, production web server, login rate limiting, password recovery, backups, and operational controls.

## Verify

```sh
python -m unittest -v test_model.py test_app.py
```

Tests use temporary databases and generated transactions. They check missing-month and financial validation, recursive lag behavior, temporal holdout behavior, login/logout, account isolation, and upload authorization.

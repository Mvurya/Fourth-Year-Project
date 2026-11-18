import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from model import forecast, load_transactions, feature, fit, predict

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.monthly = pd.read_csv(Path(__file__).parent/'data/demo-monthly.csv', index_col=0, parse_dates=True).cashflow

    def test_recursive_horizon_matches_manual_prediction(self):
        m = self.monthly
        r = forecast(m, '2016-08-31')
        self.assertEqual(len(r['forecast']),20)
        self.assertEqual(r['forecast'][-1]['date'],'2016-08')
        self.assertEqual(r['test_months'],12)
        self.assertEqual(r['training_months'],24)
        hist = m.to_dict()
        dates = m.index[12:]
        params = fit([feature(d,m.index[0],hist) for d in dates],m.iloc[12:])
        for row in r['forecast']:
            d = pd.Timestamp(row['date'])
            expected = float(predict(params,feature(d,m.index[0],hist)))
            self.assertAlmostEqual(row['cashflow'], expected, places=6)
            hist[d] = expected
        self.assertAlmostEqual(r['total'],sum(row['cashflow'] for row in r['forecast']))

    def test_recursive_holdout_does_not_use_holdout_actuals(self):
        r1=forecast(self.monthly,'2015-01')
        changed=self.monthly.copy()
        changed.iloc[-12:] *= 9
        r2=forecast(changed,'2015-01')
        np.testing.assert_allclose([x['recursive'] for x in r1['evaluation']],[x['recursive'] for x in r2['evaluation']])
        self.assertNotEqual(r1['evaluation'][1]['predicted'],r2['evaluation'][1]['predicted'])

    def test_invalid_horizon(self):
        for end in ['2014-12','2020-01']:
            with self.assertRaises(ValueError): forecast(self.monthly,end)

    def transactions(self):
        dates=pd.date_range('2020-01-01',periods=36,freq='MS')
        return pd.DataFrame({'order_date':dates,'sales':100,'discount':0.1,'shipping_cost':5,'revenue':95,'expenses':70})

    def test_upload_validation(self):
        df=self.transactions()
        monthly,_=load_transactions(df.to_csv(index=False).encode(),'test.csv')
        self.assertEqual(len(monthly),36)
        self.assertTrue((monthly==25).all())
        with self.assertRaisesRegex(ValueError,'no transactions'):
            load_transactions(df.drop(index=15).to_csv(index=False).encode(),'test.csv')
        df.loc[0,'revenue']=123
        with self.assertRaisesRegex(ValueError,'Revenue'):
            load_transactions(df.to_csv(index=False).encode(),'test.csv')

if __name__=='__main__': unittest.main()

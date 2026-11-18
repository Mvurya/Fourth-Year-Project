import http.cookiejar
import importlib
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        os.environ['CASHFLOW_DB']=cls.temp.name+'/test.sqlite3'
        import server
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.base='http://127.0.0.1:'+str(cls.http.server_port)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join(); cls.temp.cleanup()

    def client(self):
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self,client,path,data=None,header=True):
        headers={'Content-Type':'application/json'}
        if header: headers['X-Cashflow-Request']='1'
        req=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with client.open(req) as r: return r.status,json.load(r)
        except urllib.error.HTTPError as e: return e.code,json.load(e)

    def test_auth_and_account_isolation(self):
        a,b=self.client(),self.client()
        self.assertEqual(self.call(a,'/api/forecast',{'end':'2016-08'})[0],401)
        self.assertEqual(self.call(a,'/api/register',{'name':'A Shop','email':'a@test.local','password':'password123'})[0],200)
        self.assertEqual(self.call(a,'/api/demo',{})[0],200)
        status,r=self.call(a,'/api/forecast',{'end':'2016-08'})
        self.assertEqual(status,200);self.assertEqual(len(r['forecast']),20)
        self.assertEqual(self.call(b,'/api/register',{'name':'B Shop','email':'b@test.local','password':'password456'})[0],200)
        self.assertIsNone(self.call(b,'/api/me')[1]['dataset'])
        self.assertEqual(self.call(b,'/api/forecast',{'end':'2016-08'})[0],400)
        self.assertEqual(self.call(a,'/api/demo',{},header=False)[0],403)
        self.assertEqual(self.call(a,'/api/logout',{})[0],200)
        self.assertIsNone(self.call(a,'/api/me')[1]['user'])
        self.assertEqual(self.call(a,'/api/login',{'email':'a@test.local','password':'wrongpassword'})[0],401)
        self.assertEqual(self.call(a,'/api/login',{'email':'a@test.local','password':'password123'})[0],200)
        self.assertIsNotNone(self.call(a,'/api/me')[1]['dataset'])
        # Exercise the same raw CSV upload route used by the browser.
        import pandas as pd
        transactions=pd.DataFrame({'order_date':pd.date_range('2020-01-01',periods=36,freq='MS'),'sales':100,'discount':0.1,'shipping_cost':5,'revenue':95,'expenses':70})
        request=urllib.request.Request(self.base+'/api/upload',data=transactions.to_csv(index=False).encode(),headers={'X-Cashflow-Request':'1','X-Filename':'shop.csv'})
        with a.open(request) as response:
            self.assertEqual(json.load(response)['months'],36)
        self.assertEqual(self.call(a,'/api/me')[1]['dataset']['last'],'2022-12')
        self.assertIsNone(self.call(b,'/api/me')[1]['dataset'])

if __name__=='__main__': unittest.main()

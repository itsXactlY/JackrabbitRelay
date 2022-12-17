#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Jackrabbit Relay - Kucoin API framework
# 2021-2022 Copyright © Robert APM Darin
# All rights reserved unconditionally.

# IMPORTANT: This is a low level API framework. Do NOT add retries or any other higher
# level functionality. This framework must simple communicate with Kucoin at its most
# basic level.

# This code is derived from Information on https://docs.kucoin.com

# I tried to keep it as "matchy" as possible for ease of use and readability.

import sys
sys.path.append('/home/JackrabbitRelay2/Base/Library')
import os
import json
import requests
import hmac
import hashlib
import base64
import time
from urllib.parse import urljoin
from datetime import datetime

# Needed the basic support functions, locker, lists, and other basic primitives.

import JRRsupport

# This library uses REST as the method of communicating with Kucoin. It does not uses
# sessions as the overhead is not warrented given the short lifespan of a request and
# that the session will be force terminated after a given duration. It is simply more
# effecient to send one full and complte request at a time.

class Broker:

    # Initialize everything for this broker.

    def __init__(self,API=None, SECRET=None, Passphrase=None, Sandbox=False):
        self.Version='0.0.0.0.1'
        self.APIkey=API
        self.SECRET=SECRET
        self.Passphrase=Passphrase
        self.Sandbox=Sandbox

        # The results of every API call are placed here. This way, raw data is
        # available to the caller.

        self.Results=None

        if self.Sandbox==True:
            self.baseURL='https://openapi-sandbox.kucoin.com'
        else:
            self.baseURL='https://api.kucoin.com'

    ###
    ### API connections
    ###

    # Connect to kucoin and deliver the request. This is an API lyer, subsequently,
    # retry logic and other high level functionality has no lace here as those aspects
    # are framework components.

    def callAPI(self,**kwargs):
        # For API timing
        StartTime=datetime.now()

        method=kwargs.get('method').upper()
        url=kwargs.get('url')
        params=kwargs.get('params')
        timeout=10

        uri_path=url
        data_json=''

        # Process method and build parameters

        if method in ['GET', 'DELETE']:
            if params:
                strl=[]
                for key in sorted(params):
                    strl.append(f"{key}={params[key]}")
                data_json+='&'.join(strl)
                url+='?'+data_json
                uri_path=url
        else:
            if params:
                data_json=json.dumps(params)
                uri_path=url+data_json

        # Build signature string

        now_time=int(time.time())*1000
        str_to_sign=str(now_time)+method+uri_path
        sign=base64.b64encode(hmac.new(self.SECRET.encode('utf-8'), \
            str_to_sign.encode('utf-8'),hashlib.sha256).digest())

        # Version 2 authentication

        pphrase=base64.b64encode(hmac.new(self.SECRET.encode('utf-8'), \
            self.Passphrase.encode('utf-8'),hashlib.sha256).digest())

        # Populate header

        headers={}
        headers["KC-API-SIGN"]=sign
        headers["KC-API-TIMESTAMP"]=str(now_time)
        headers["KC-API-KEY"]=self.APIkey
        headers["KC-API-PASSPHRASE"]=pphrase
        headers["KC-API-KEY-VERSION"]="2"
        headers["Content-Type"]="application/json"
        headers["User-Agent"]="Jackrabbit Relay/"+self.Version

        # Create the proper URL

        url=urljoin(self.baseURL,url)

        if method in ['GET', 'DELETE']:
            self.Results=requests.request(method,url,headers=headers,timeout=timeout)
        else:
            self.Results=requests.request(method,url,headers=headers,data=data_json,timeout=timeout)

        EndTime=datetime.now()
        Elapsed=(EndTime-StartTime)
        print(f"{str(Elapsed)} {method} {url}")
        return self.ValidateRssponse(self.Results)

    # Validate Kucoin response

    def ValidateRssponse(self,response):
        if response.status_code==200:
            try:
                data=response.json()
            except ValueError:
                raise Exception(response.content)
            else:
                if data and data.get('code'):
                    if data.get('code')=='200000':
                        if data.get('data'):
                            return data['data']
                        else:
                            return data
                    else:
                        raise Exception(f"{response.status_code}-{response.text}")
                else:
                    raise Exception(response.content)
        else:
            raise Exception(f"{response.status_code}-{response.text}")

    # Validate pagenation

    def ValidatePagenation(self,currentPage,pageSize):
        if currentPage==None or currentPage<1:
            currentPage=1

        if pageSize==None or pageSize<10:
            pageSize=10
        elif pageSize>100:
            pageSize=100

        return currentPage,pageSize

    ###
    ### Actual API functionality
    ###

    # Get List of Sub-Accounts

    # You can get the user info of all sub-users via this interface. It is recommended
    # to use the GET /api/v2/sub/user interface for paging query.

    def apiGetV1SubUser(self):
        self.Results=self.callAPI(method='GET',url='/api/v1/sub/user')
        return self.Results

    # Get Paginated List of Sub-Accounts

    # This endpoint can be used to get a paginated list of sub-accounts. Pagination is
    # required.

    def apiGetV2SubUser(self,currentPage=None,pageSize=None):
        params={}

        currentPage,pageSize=self.ValidatePagenation(currentPage,pageSize)

        params['currentPage']=currentPage
        params['pageSize']=pageSize

        self.Results=self.callAPI(method='GET',url='/api/v2/sub/user',params=params)
        return self.Results

    # Get a list of accounts.

    # Please deposit funds to the main account firstly, then transfer the funds to the
    # trade account via [345]Inner Transfer before transaction.

    def apiGetV1Accounts(self,accountType=None):
        atypes=['main','trade','margin']

        params={}

        if accountType==None:
            params['type']='trade'
        elif accountType.lower() in atypes:
            params['type']=accountType.lower()
        else:
            raise Exception(f"GetV1Accounts: wrong account type: {accountType}")

        self.Results=self.callAPI(method='GET',url='/api/v1/accounts',params=params)
        return self.Results

    # Get an Account by ID

    # Information for a single account. Use this endpoint when you know the accountId.

    def apiGetV1AccountsID(self,acctID=None):
        if acctID==None:
            raise Exception("GetV1AccountsID: account ID required")

        url=f'/api/v1/accounts/{acctID}'
        self.Results=self.callAPI(method='GET',url=url)
        return self.Results

    # Get Account Ledgers

    # This interface is for the history of deposit/withdrawal of all accounts,
    # supporting inquiry of various currencies.

    # Items are paginated and sorted to show the latest first. See the Pagination
    # section for retrieving additional entries after the first page.

    def apiGetV1AccountsLedgers(self,currency=None,direction=None,bizType=None,startAt=None,endAt=None,currentPage=None,pageSize=None):
        dirList=['in','out']
        bizList=["DEPOSIT", "WITHDRAW", "TRANSFER", "SUB_TRANSFER", "TRADE_EXCHANGE", \
            "MARGIN_EXCHANGE", "KUCOIN_BONUS"]

        if direction!=None and direction.lower() not in dirList:
            raise Exception("GetV1AccountsLedgers: invalid direction")

        if bizType!=None and bizType.upper() not in bizList:
            raise Exception("GetV1AccountsLedgers: invalid business type")

        params={}

        currentPage,pageSize=self.ValidatePagenation(currentPage,pageSize)

        params['currentPage']=currentPage
        params['pageSize']=pageSize

        if currency!=None:
            params['currency']=currency.upper()
        if direction!=None:
            params['direction']=direction.lower()
        if bizType!=None:
            params['bizType']=bizType.upper()
        if startAt!=None:
            params['startAt']=startAt
        if endAt!=None:
            params['endAt']=endAt

        self.Results=self.callAPI(method='GET',url='/api/v1/accounts/ledgers',params=params)
        return self.Results

    # Get Account Summary Information

    # This endpoint can be used to obtain account summary information.

    def apiGetV1UserInfo(self):
        self.Results=self.callAPI(method='GET',url='/api/v1/user-info')
        return self.Results

    # Create Sub-Account

    # This endpoint can be used to create sub-accounts.

    def apiPostV1SubUser(self,password=None,remarks=None,subName=None,access='All'):
        aList=['All','Margin','Futures']

        params={}

        # subName and password need symbol verification, no symbols allowed.
        # Numbers must in in password as well as letters.

        if subName==None or len(subName)<7 or len(subName)>32 or ' ' in subName:
            raise Exception("PostV1SubUser: invalid subName")
        else:
            params['subName']=subName

        if password==None or len(password)<7 or len(password)>24 or ' ' in password:
            raise Exception("PostV1SubUser: invalid password")
        else:
            params['password']=password

        if remarks==None or len(remarks)>24:
            raise Exception("PostV1SubUser: invalid remarks")
        else:
            params['remarks']=remarks

        if access==None or access.capitalize() not in aList:
            raise Exception("PostV1SubUser: invalid access")
        else:
            params['access']=access.capitalize()

        self.Results=self.callAPI(method='POST',url='/api/v1/sub/user',params=params)
        return self.Results

    # Get Sub-Account Spot API List

    # This endpoint can be used to obtain a list of Spot APIs pertaining to a
    # sub-account.

    def apiGetV1SubApiKey(self,apiKey=None,subName=None):
        params={}

        if subName==None:
            raise Exception("apiGetV1SubApiKey: missing subName")
        else:
            params['subName']=subName

        if apiKey!=None:
            params['apiKey']=apiKey

        self.Results=self.callAPI(method='GET',url='/api/v1/sub/api-key',params=params)
        return self.Results

    # Create Spot APIs for Sub-Account

    # This endpoint can be used to create Spot APIs for sub-accounts.

    def apiPostV1SubApiKey(self,passphrase=None,remark=None,subName=None,permission='General',ipWhitelist=None):
        pList=['General','Trade']

        params={}

        # subName and password need symbol verification, no symbols allowed.
        # Numbers must in in password as well as letters.

        if subName==None or len(subName)<7 or len(subName)>32 or ' ' in subName:
            raise Exception("apiPostV1SubApiKey: invalid subName")
        else:
            params['subName']=subName

        if passphrase==None or len(passphrase)<7 or len(passphrase)>24 or ' ' in passphrase:
            raise Exception("apiPostV1SubApiKey: invalid passphrase")
        else:
            params['passphrase']=passphrase

        if remark==None or len(remark)>24:
            raise Exception("apiPostV1SubApiKey: invalid remarks")
        else:
            params['remark']=remark

        if permission==None or permission.capitalize() not in pList:
            raise Exception("apiPostV1SubApiKey: invalid permission")
        else:
            params['permission']=permission.capitalize()

        if ipWhitelist!=None:
            params['ipWhitelist']=ipWhitelist

        self.Results=self.callAPI(method='POST',url='/api/v1/sub/api-key',params=params)
        return self.Results

    # Modify Sub-Account Spot APIs

    # This endpoint can be used to modify sub-account Spot APIs.

    def apiPostV1SubApiKeyUpdate(self,apiKey=None,passphrase=None,subName=None,permission=None,ipWhitelist=None):
        pList=['General','Trade']

        params={}

        if apiKey==None:
            raise Exception("apiPostV1SubApiKeyUpdate: invalid apiKey")
        else:
            params['apiKey']=apiKey

        if passphrase==None:
            raise Exception("apiPostV1SubApiKeyUpdate: invalid passphrase")
        else:
            params['passphrase']=passphrase

        if subName==None:
            raise Exception("apiPostV1SubApiKeyUpdate: invalid subName")
        else:
            params['subName']=subName

        if permission!=None:
            if permission.capitalize() not in pList:
                raise Exception("apiPostV1SubApiKeyUpdate: invalid permission")
            else:
                params['permission']=permission.capitalize()

        if ipWhitelist!=None:
            params['ipWhitelist']=ipWhitelist

        self.Results=self.callAPI(method='POST',url='/api/v1/sub/api-key/update',params=params)
        return self.Results

    # Delete Sub-Account Spot APIs

    # This endpoint can be used to delete sub-account Spot APIs.

    def apiDeleteV1SubApiKey(self,apiKey=None,passphrase=None,subName=None):
        params={}

        if apiKey==None:
            raise Exception("apiDeleteV1SubApiKey: invalid apiKey")
        else:
            params['apiKey']=apiKey

        if passphrase==None:
            raise Exception("apiDeleteV1SubApiKey: invalid passphrase")
        else:
            params['passphrase']=passphrase

        if subName==None:
            raise Exception("apiDeleteV1SubApiKey: invalid subName")
        else:
            params['subName']=subName

        self.Results=self.callAPI(method='DELETE',url='/api/v1/sub/api-key',params=params)
        return self.Results

    # Get Account Balance of a Sub-Account

    # This endpoint returns the account info of a sub-user specified by the
    # subUserId.

    def apiGetV1SubAccounts(self,subUserId=None):
        if subUserId==None:
            url=f'/api/v1/sub-accounts'
        else:
            url=f'/api/v1/sub-accounts/{subUserId}'
        self.Results=self.callAPI(method='GET',url=url)
        return self.Results

"""

Get Paginated Sub-Account Information.

{
    "code": "200000",
    "data": {
        "currentPage": 1,
        "pageSize": 10,
        "totalNum": 14,
        "totalPage": 2,
        "items": [
            {
                "subUserId": "635002438793b80001dcc8b3",
                "subName": "margin03",
                "mainAccounts": [
                    {
                        "currency": "00",
                        "balance": "0",
                        "available": "0",
                        "holds": "0",
                        "baseCurrency": "BTC",
                        "baseCurrencyPrice": "125.63",
                        "baseAmount": "0"
                    }
                ]
            }
        ]
    }
}

   This endpoint can be used to get paginated sub-account information.
   Pagination is required.

HTTP REQUEST

   GET /api/v2/sub-accounts

Example

   GET /api/v2/sub-accounts

API KEY PERMISSIONS

   This endpoint requires the General permission.

PARAMETERS

   Param Type Mandatory Description
   currentPage Int No Current request page. Default is 1
   pageSize Int No Number of results per request. Minimum is 1, maximum is
   100, default is 10.

RESPONSES

         Field                    Description
   subUserId         The user ID of the sub-user.
   subName           The username of the sub-user.
   currency          The currency of the account.
   balance           Total funds in the account.
   available         Funds available to withdraw or trade.
   holds             Funds on hold (not available for use).
   baseCurrency      Calculated on this currency.
   baseCurrencyPrice The base currency price.
   baseAmount        The base currency amount.

Get the Transferable

 {
    "currency": "KCS",
    "balance": "0",
    "available": "0",
    "holds": "0",
    "transferable": "0"
}

   This endpoint returns the transferable balance of a specified account.

HTTP REQUEST

   GET /api/v1/accounts/transferable

Example

   GET /api/v1/accounts/transferable?currency=BTC&type=MAIN

API KEY PERMISSIONS

   This endpoint requires the General permission.

PARAMETERS

   Param Type Mandatory Description
   currency String Yes [349]currency
   type String Yes The account type: MAIN, TRADE, MARGIN or ISOLATED
   tag String No Trading pair, required when the account type is ISOLATED;
   other types are not passed, e.g.: BTC-USDT

RESPONSES

      Field                  Description
   currency     Currency
   balance      Total funds in an account.
   available    Funds available to withdraw or trade.
   holds        Funds on hold (not available for use).
   transferable Funds available to transfer.

Transfer between Master user and Sub-user

{
    "orderId": "5cbd870fd9575a18e4438b9a"
}

   Funds in the main account, trading account and margin account of a
   Master Account can be transferred to the main account, trading account,
   futures account and margin account of its Sub-Account. The futures
   account of both the Master Account and Sub-Account can only accept
   funds transferred in from the main account, trading account and margin
   account and cannot transfer out to these accounts.

HTTP REQUEST

   POST /api/v2/accounts/sub-transfer
   Recommended for use

Example

   POST /api/v2/accounts/sub-transfer

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 3
   times/3s.

PARAMETERS

   Param Type Description
   clientOid String Unique order id created by users to identify their
   orders, e.g. UUID.
   currency String [350]currency
   amount String Transfer amount, the amount is a positive integer
   multiple of the [351]currency precision.
   direction String OUT — the master user to sub user
   IN — the sub user to the master user.
   accountType String [Optional] The account type of the master user:
   MAIN, TRADE, MARGIN or CONTRACT
   subAccountType String [Optional] The account type of the sub user:
   MAIN, TRADE, MARGIN or CONTRACT, default is MAIN.
   subUserId String the [352]user ID of a sub-account.

RESPONSES

    Field                   Description
   orderId The order ID of a master-sub assets transfer.

Inner Transfer

{
    "orderId": "5bd6e9286d99522a52e458de"
}

   This API endpoint can be used to transfer funds between accounts
   internally. Users can transfer funds between their main account,
   trading account, cross margin account, and isolated margin account free
   of charge. Transfer of funds from the main account, cross margin
   account, and trading account to the futures account is supported, but
   transfer of funds from futures accounts to other accounts is not
   supported.

HTTP REQUEST

   POST /api/v2/accounts/inner-transfer

API KEY PERMISSIONS

   This endpoint requires the Trade permission.

PARAMETERS

   Param Type Mandatory Description
   clientOid String Yes clientOid, the unique identifier created by the
   client, use of UUID
   currency String Yes [353]currency
   from String Yes Payment Account Type: main, trade, margin, or isolated
   to String Yes Receiving Account Type: main, trade, margin, isolated, or
   contract
   amount String Yes Transfer amount, the precision being a positive
   integer multiple of the [354]Currency Precision
   fromTag String No Trading pair, required when the payment account type
   is isolated, e.g.: BTC-USDT
   toTag String No Trading pair, required when the receiving account type
   is isolated, e.g.: BTC-USDT

RESPONSES

    Field            Description
   orderId The order ID of a funds transfer

Deposit

Create Deposit Address

{
    "address": "0x78d3ad1c0aa1bf068e19c94a2d7b16c9c0fcd8b1",
    "memo": "5c247c8a03aa677cea2a251d",   //tag
    "chain": "OMNI"
}

   Request via this endpoint to create a deposit address for a currency
   you intend to deposit.

HTTP REQUEST

   POST /api/v1/deposit-addresses

Example

   POST /api/v1/deposit-addresses

API KEY PERMISSIONS

   This endpoint requires the "Transfer" permission.

PARAMETERS

   Param Type Description
   currency String Currency
   chain String [Optional] The chain name of currency, e.g. The available
   value for USDT are OMNI, ERC20, TRC20, default is ERC20. The available
   value for BTC are Native, Segwit, TRC20, the parameters are bech32,
   btc, trx, default is Native. This only apply for multi-chain currency,
   and there is no need for single chain currency.

RESPONSES

   Field Description
   address Deposit address
   memo Address remark. If there’s no remark, it is empty. When you
   [355]withdraw from other platforms to the KuCoin, you need to fill in
   memo(tag). If you do not fill memo (tag), your deposit may not be
   available, please be cautious.
   chain The chain name of currency, e.g. The available value for USDT are
   OMNI, ERC20, TRC20, default is ERC20. The available value for BTC are
   Native, Segwit, TRC20, the parameters are bech32, btc, trx, default is
   Native.

Get Deposit Addresses(V2)

[
  {
    "address": "bc1qaj6kkv85w5d6lr8p8h7tckyce5hnwmyq8dd84d",
    "memo": "",
    "chain": "BTC-Segwit",
    "contractAddress": ""
  },
  {
    "address": "3HwsFot9TW6jL4K4EUHxDSyL8myttxV7Av",
    "memo": "",
    "chain": "BTC",
    "contractAddress": ""
  },
  {
    "address": "TUDybru26JmozStbg2cJGDbR9EPSbQaAie",
    "memo": "",
    "chain": "TRC20",
    "contractAddress": ""
  }
]

   Get all deposit addresses for the currency you intend to deposit. If
   the returned data is empty, you may need to create a deposit address
   first.

HTTP REQUEST

   GET /api/v2/deposit-addresses

Example

   GET /api/v2/deposit-addresses?currency=BTC

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

    Param    Type  Description
   currency String The currency

RESPONSES

   Field Description
   address Deposit address
   memo Address remark. If there’s no remark, it is empty. When you
   [356]withdraw from other platforms to the KuCoin, you need to fill in
   memo(tag). If you do not fill memo (tag), your deposit may not be
   available, please be cautious.
   chain The chain name of currency.
   contractAddress The token contract address.

Get Deposit Address

{
    "address": "0x78d3ad1c0aa1bf068e19c94a2d7b16c9c0fcd8b1",
    "memo": "5c247c8a03aa677cea2a251d",        //tag
    "chain": "OMNI"
}

   Get a deposit address for the currency you intend to deposit. If the
   returned data is null, you may need to create a deposit address first.

HTTP REQUEST

   GET /api/v1/deposit-addresses

Example

   GET /api/v1/deposit-addresses

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

   Param Type Description
   currency String Currency
   chain String [Optional] The chain name of currency, e.g. The available
   value for USDT are OMNI, ERC20, TRC20, default is ERC20. The available
   value for BTC are Native, Segwit, TRC20, the parameters are bech32,
   btc, trx, default is Native. This only apply for multi-chain currency,
   and there is no need for single chain currency.

RESPONSES

   Field Description
   address Deposit address
   memo Address remark. If there’s no remark, it is empty. When you
   [357]withdraw from other platforms to the KuCoin, you need to fill in
   memo(tag). If you do not fill memo (tag), your deposit may not be
   available, please be cautious.
   chain The chain name of currency, e.g. The available value for USDT are
   OMNI, ERC20, TRC20, default is ERC20. The available value for BTC are
   Native, Segwit, TRC20, the parameters are bech32, btc, trx, default is
   Native.

Get Deposit List

{
    "code": "200000",
    "data": {
        "currentPage": 1,
        "pageSize": 50,
        "totalNum": 1,
        "totalPage": 1,
        "items": [
            {
                "currency": "XRP",
                "chain": "xrp",
                "status": "SUCCESS",
                "address": "rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB",
                "memo": "1919537769",
                "isInner": false,
                "amount": "20.50000000",
                "fee": "0.00000000",
                "walletTxId": "2[358][email protected]e8902757998fc352e6c9d8890d
18a71c",
                "createdAt": 1666600519000,
                "updatedAt": 1666600549000,
                "remark": "Deposit"
            }
        ]
    }
}

   Request via this endpoint to get deposit list Items are paginated and
   sorted to show the latest first. See the [359]Pagination section for
   retrieving additional entries after the first page.

HTTP REQUEST

   GET /api/v1/deposits

Example

   GET /api/v1/deposits

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 6
   times/3s.
   This request is paginated.

PARAMETERS

   Param Type Mandatory Description
   currency String No Currency
   startAt long No Start time (milisecond)
   endAt long No End time (milisecond)
   status String No Status. Available value: PROCESSING, SUCCESS, and
   FAILURE

RESPONSES

   Field Description
   address Deposit address
   memo Address remark. If there’s no remark, it is empty. When you
   [360]withdraw from other platforms to the KuCoin, you need to fill in
   memo(tag). If you do not fill memo (tag), your deposit may not be
   available, please be cautious.
   amount Deposit amount
   fee Fees charged for deposit
   currency Currency
   chain The chain of currency
   isInner Internal deposit or not
   walletTxId Wallet Txid
   status Status
   remark remark
   createdAt Creation time of the database record
   updatedAt Update time of the database record

Get V1 Historical Deposits List

{
    "currentPage":1,
    "pageSize":1,
    "totalNum":9,
    "totalPage":9,
    "items":[
        {
            "currency":"BTC",
            "createAt":1528536998,
            "amount":"0.03266638",
            "walletTxId":"5[361][email protected][362][email protected]",
            "isInner":false,
            "status":"SUCCESS"
        }
    ]
}

   Request via this endpoint to get the V1 historical deposits list on
   KuCoin.
   The data of the latest one month will be queried by default.

HTTP REQUEST

   GET /api/v1/hist-deposits

Example

   GET /api/v1/hist-deposits

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 6
   times/3s.
   This request is paginated.

PARAMETERS

   Param Type Description
   currency String [Optional] [363]Currency.
   startAt long [Optional] Start time (milisecond)
   endAt long [Optional] End time (milisecond)
   status String [Optional] Status. Available value: PROCESSING, SUCCESS,
   and FAILURE

RESPONSES

     Field                Description
   amount     Deposit amount
   currency   Currency
   isInner    Internal deposit or not
   walletTxId Wallet Txid
   createAt   Creation time of the database record
   status     Status

Withdrawals

Get Withdrawals List

{
    "code": "200000",
    "data": {
        "currentPage": 1,
        "pageSize": 50,
        "totalNum": 1,
        "totalPage": 1,
        "items": [
            {
                "id": "63564dbbd17bef00019371fb",
                "currency": "XRP",
                "chain": "xrp",
                "status": "SUCCESS",
                "address": "rNFugeoj3ZN8Wv6xhuLegUBBPXKCyWLRkB",
                "memo": "1919537769",
                "isInner": false,
                "amount": "20.50000000",
                "fee": "0.50000000",
                "walletTxId": "2C24A6D5B3E7D5B6AA6534025B9B107AC910309A98825BF55
81E25BEC94AD83B",
                "createdAt": 1666600379000,
                "updatedAt": 1666600511000,
                "remark": "test"
            }
        ]
    }
}

HTTP REQUEST

   GET /api/v1/withdrawals

Example

   GET /api/v1/withdrawals

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 6
   times/3s.
   This request is paginated.

PARAMETERS

   Param Type Mandatory Description
   currency String No [364]Currency
   status String No Status. Available value: PROCESSING,
   WALLET_PROCESSING, SUCCESS, and FAILURE
   startAt long No Start time (milisecond)
   endAt long No End time (milisecond)

RESPONSES

   Field Description
   id Unique identity
   address Withdrawal address
   memo Address remark. If there’s no remark, it is empty. When you
   [365]withdraw from other platforms to the KuCoin, you need to fill in
   memo(tag). If you do not fill memo (tag), your deposit may not be
   available, please be cautious.
   currency Currency
   chain The chain of currency
   amount Withdrawal amount
   fee Withdrawal fee
   walletTxId Wallet Txid
   isInner Internal withdrawal or not
   status status
   remark remark
   createdAt Creation time
   updatedAt Update time

Get V1 Historical Withdrawals List

{
    "currentPage":1,
    "pageSize":1,
    "totalNum":2,
    "totalPage":2,
    "items":[
        {
            "currency":"BTC",
            "createAt":1526723468,
            "amount":"0.534",
            "address":"33xW37ZSW4tQvg443Pc7NLCAs167Yc2XUV",
            "walletTxId":"aeacea864c020acf58e51606169240e96774838dcd4f7ce48acf38
e3651323f4",
            "isInner":false,
            "status":"SUCCESS"
        }
    ]
}

   List of KuCoin V1 historical withdrawals.
   Default query for one month of data.

HTTP REQUEST

   GET /api/v1/hist-withdrawals

Example

   GET /api/v1/hist-withdrawals

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 6
   times/3s.
   This request is paginated.

PARAMETERS

   Param Type Description
   currentPage int [Optional] The current page.
   pageSize int [Optional] Number of entries per page.
   currency String [Optional] [366]Currency.
   startAt long [Optional] Start time (milisecond)
   endAt long [Optional] End time (milisecond)
   status String [Optional] Status. Available value: PROCESSING, SUCCESS,
   and FAILURE

RESPONSES

     Field                Description
   amount     Withdrawal amount
   currency   Currency
   isInner    Internal deposit or not
   walletTxId Wallet Txid
   createAt   Creation time of the database record
   status     Status

Get Withdrawal Quotas

{
    "currency": "KCS",
    "limitBTCAmount": "2.0",
    "usedBTCAmount": "0",
    "remainAmount": "75.67567568",
    "availableAmount": "9697.41991348",
    "withdrawMinFee": "0.93000000",
    "innerWithdrawMinFee": "0.00000000",
    "withdrawMinSize": "1.4",
    "isWithdrawEnabled": true,
    "precision": 8,   //withdrawal precision
    "chain": "OMNI"
}

HTTP REQUEST

   GET /api/v1/withdrawals/quotas

Example

   GET /api/v1/withdrawals/quotas?currency=BTC

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

   Param Type Description
   currency String currency. e.g. BTC
   chain String [Optional] The chain of currency. This only apply for
   multi-chain currency, and there is no need for single chain currency;
   you can query the chain through the response of the GET
   /api/v2/currencies/{currency} interface.

RESPONSES

   Field Description
   currency Currency
   availableAmount Current available withdrawal amount
   remainAmount Remaining amount available to withdraw the current day
   withdrawMinSize Minimum withdrawal amount
   limitBTCAmount Total BTC amount available to withdraw the current day
   innerWithdrawMinFee Fees for internal withdrawal
   usedBTCAmount The estimated BTC amount (based on the daily fiat limit)
   that can be withdrawn within the current day
   isWithdrawEnabled Is the withdraw function enabled or not
   withdrawMinFee Minimum withdrawal fee
   precision Floating point precision.
   chain The chain name of currency, e.g. The available value for USDT are
   OMNI, ERC20, TRC20, default is ERC20.

Apply Withdraw

{
  "withdrawalId": "5bffb63303aa675e8bbe18f9"
}

HTTP REQUEST

   POST /api/v1/withdrawals
   On the WEB end, you can open the switch of specified favorite addresses
   for withdrawal, and when it is turned on, it will verify whether your
   withdrawal address(including chain) is a favorite address(it is case
   sensitive); if it fails validation, it will respond with the error
   message {"msg":"Already set withdraw whitelist, this address is not
   favorite address","code":"260325"}.

Example

   POST /api/v1/withdrawals

API KEY PERMISSIONS

   This endpoint requires the Transfer permission.

PARAMETERS

   Param Type Mandatory Description
   currency String Yes Currency
   address String Yes Withdrawal address
   amount number Yes Withdrawal amount, a positive number which is a
   multiple of the amount precision (fees excluded)
   memo String No [Optional] Address remark. If there’s no remark, it is
   empty. When you withdraw from other platforms to the KuCoin, you need
   to fill in memo(tag). If you do not fill memo (tag), your deposit may
   not be available, please be cautious.
   isInner boolean No [Optional] Internal withdrawal or not. Default
   setup: false
   remark String No [Optional] Remark
   chain String No [Optional] The chain of currency. For a currency with
   multiple chains, it is recommended to specify chain parameter instead
   of using the default chain; you can query the chain through the
   response of the GET /api/v2/currencies/{currency} interface.
   feeDeductType String No Withdrawal fee deduction type: INTERNAL or
   EXTERNAL or not specified
   1. INTERNAL- deduct the transaction fees from your withdrawal amount2.
   EXTERNAL- deduct the transaction fees from your main account3. If you
   don't specify the feeDeductType parameter, when the balance in your
   main account is sufficient to support the withdrawal, the system will
   initially deduct the transaction fees from your main account. But if
   the balance in your main account is not sufficient to support the
   withdrawal, the system will deduct the fees from your withdrawal
   amount. For example: Suppose you are going to withdraw 1 BTC from the
   KuCoin platform (transaction fee: 0.0001BTC), if the balance in your
   main account is insufficient, the system will deduct the transaction
   fees from your withdrawal amount. In this case, you will be receiving
   0.9999BTC.

RESPONSES

      Field      Description
   withdrawalId Withdrawal id

Cancel Withdrawal

   Only withdrawals requests of PROCESSING status could be canceled.

HTTP REQUEST

   DELETE /api/v1/withdrawals/{withdrawalId}

Example

   DELETE /api/v1/withdrawals/5bffb63303aa675e8bbe18f9

API KEY PERMISSIONS

   This endpoint requires the "Transfer" permission.

PARAMETERS

      Param      Type                     Description
   withdrawalId String Path parameter, a unique ID for a withdrawal order

Trade Fee

Basic user fee

   This interface is for the basic fee rate of users
{
    "code": "200000",
    "data": {
        "takerFeeRate": "0.001",
        "makerFeeRate": "0.001"
    }
}

HTTP REQUEST

   GET /api/v1/base-fee

Example

   GET /api/v1/base-fee
   GET /api/v1/base-fee?currencyType=1

API KEY PERMISSIONS

   This endpoint requires the General permission.

PARAMETERS

   Param Type Mandatory Description
   currencyType String No Currency type: 0-crypto currency, 1-fiat
   currency. default is 0-crypto currency

RESPONSES

      Field         Description
   takerFeeRate Base taker fee rate
   makerFeeRate Base maker fee rate

Actual fee rate of the trading pair

   This interface is for the actual fee rate of the trading pair. You can
   inquire about fee rates of 10 trading pairs each time at most. The fee
   rate of your sub-account is the same as that of the master account.
{
    "code": "200000",
    "data": [
        {
            "symbol": "BTC-USDT",
            "takerFeeRate": "0.001",
            "makerFeeRate": "0.001"
        },
        {
            "symbol": "KCS-USDT",
            "takerFeeRate": "0.002",
            "makerFeeRate": "0.0005"
        }
    ]
}

HTTP REQUEST

   GET /api/v1/trade-fees

Example

   GET /api/v1/trade-fees?symbols=BTC-USDT,KCS-USDT

API KEY PERMISSIONS

   This endpoint requires the General permission.

PARAMETERS

   Param Type Mandatory Description
   symbols String Yes Trading pair (optional, you can inquire fee rates of
   10 trading pairs each time at most)

RESPONSES

   Field Description
   symbol The unique identity of the trading pair and will not change even
   if the trading pair is renamed
   takerFeeRate Actual taker fee rate of the trading pair
   makerFeeRate Actual maker fee rate of the trading pair

Trade

   Signature is required for this part.

Orders

Place a new order

{
  "orderId": "5bd6e9286d99522a52e458de"
}

   You can place two types of orders: limit and market. Orders can only be
   placed if your account has sufficient funds. Once an order is placed,
   your account funds will be put on hold for the duration of the order.
   How much and which funds are put on hold depends on the order type and
   parameters specified. See the Holds details below.
   Placing an order will enable price protection. When the price of the
   limit order is outside the threshold range, the price protection
   mechanism will be triggered, causing the order to fail.

   Please note that the system will frozen the fees from the orders that
   entered the order book in advance. Read [367]List Fills to learn more.

   Before placing an order, please read [368]Get Symbol List to understand
   the requirements for the quantity parameters for each trading pair.

   Do not include extra spaces in JSON strings.

Place Order Limit

   The maximum active orders for a single trading pair in one account is
   200 (stop orders included).

HTTP Request

   POST /api/v1/orders

Example

   POST /api/v1/orders

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 45
   times/3s.

PARAMETERS

   Param type Description
   clientOid String Unique order id created by users to identify their
   orders, e.g. UUID.
   side String buy or sell
   symbol String a valid trading symbol code. e.g. ETH-BTC
   type String [Optional] limit or market (default is limit)
   remark String [Optional] remark for the order, length cannot exceed 100
   utf8 characters
   stp String [Optional] self trade prevention , CN, CO, CB or DC
   tradeType String [Optional] The type of trading : TRADE（Spot Trade）,
   MARGIN_TRADE (Margin Trade). Default is TRADE. Note: To improve the
   system performance and to accelerate order placing and processing,
   KuCoin has added a new interface for order placing of margin. For
   traders still using the current interface, please move to the new one
   as soon as possible. The current one will no longer accept margin
   orders by May 1st, 2021 (UTC). At the time, KuCoin will notify users
   via the announcement, please pay attention to it.

LIMIT ORDER PARAMETERS

   Param type Description
   price String price per base currency
   size String amount of base currency to buy or sell
   timeInForce String [Optional] GTC, GTT, IOC, or FOK (default is GTC),
   read [369]Time In Force.
   cancelAfter long [Optional] cancel after n seconds, requires
   timeInForce to be GTT
   postOnly boolean [Optional] Post only flag, invalid when timeInForce is
   IOC or FOK
   hidden boolean [Optional] Order will not be displayed in the order book
   iceberg boolean [Optional] Only aportion of the order is displayed in
   the order book
   visibleSize String [Optional] The maximum visible size of an iceberg
   order

MARKET ORDER PARAMETERS

   Param  type                       Description
   size  String [Optional] Desired amount in base currency
   funds String [Optional] The desired amount of quote currency to use
     * It is required that you use one of the two parameters, size or
       funds.

Advanced Description

SYMBOL

   The symbol must match a valid trading [370]symbol.

CLIENT ORDER ID

   Generated by yourself, the optional clientOid field must be a unique id
   (e.g UUID). Only numbers, characters, underline(_) and separator(-) are
   allowed. The value will be returned in order detail. You can use this
   field to identify your orders via the public feed. The client_oid is
   different from the server-assigned order id. Please do not send a
   repeated client_oid. The length of the client_oid cannot exceed 40
   characters. You should record the server-assigned order_id as it will
   be used for future query order status.

TYPE

   The order type you specify may decide whether other optional parameters
   are required, as well as how your order will be executed by the
   matching engine. If order type is not specified, the order will be a
   limit order by default.

   Price and size are required to be specified for a limit order. The
   order will be filled at the price specified or better, depending on the
   market condition. If a limit order cannot be filled immediately, it
   will be outstanding in the open order book until matched by another
   order, or canceled by the user.

   A market order differs from a limit order in that the execution price
   is not guaranteed. Market order, however, provides a way to buy or sell
   specific size of order without having to specify the price. Market
   orders will be executed immediately, and no orders will enter the open
   order book afterwards. Market orders are always considered takers and
   incur taker fees.

TradeType

   The platform currently supports spot (TRADE) and margin (MARGIN_TRADE)
   . The system will freeze the funds of the specified account according
   to your parameter type. If this parameter is not specified, the funds
   in your trade account will be frozen by default. Note: To improve the
   system performance and to accelerate order placing and processing,
   KuCoin has added a new interface for order placing of margin. For
   traders still using the current interface, please move to the new one
   as soon as possible. The current one will no longer accept margin
   orders by May 1st, 2021 (UTC). At the time, KuCoin will notify users
   via the announcement, please pay attention to it.

PRICE

   The price must be specified in priceIncrement symbol units. The
   priceIncrement is the smallest unit of price. For the BTC-USDT symbol,
   the priceIncrement is 0.00001000. Prices less than 0.00001000 will not
   be accepted, The price for the placed order should be multiple numbers
   of priceIncrement, or the system would report an error when you place
   the order. Not required for market orders.

SIZE

   The size must be greater than the baseMinSize for the symbol and no
   larger than the baseMaxSize. The size must be specified in
   baseIncrement symbol units. Size indicates the amount of BTC (or base
   currency) to buy or sell.

FUNDS

   The funds field indicates the how much of the quote currency you wish
   to buy or sell. The size of the funds must be specified in
   quoteIncrement symbol units and the size of funds in order shall be a
   positive integer multiple of quoteIncrement, ensuring the funds is
   greater than the quoteMinSize for the symbol but no larger than the
   quoteMaxSize.

TIME IN FORCE

   Time in force policies provide guarantees about the lifetime of an
   order. There are four policies: Good Till Canceled GTC, Good Till Time
   GTT, Immediate Or Cancel IOC, and Fill Or Kill FOK.

   GTC Good Till Canceled orders remain open on the book until canceled.
   This is the default behavior if no policy is specified.

   GTT Good Till Time orders remain open on the book until canceled or the
   allotted cancelAfter is depleted on the matching engine. GTT orders are
   guaranteed to cancel before any other order is processed after the
   cancelAfter seconds placed in order book.

   IOC Immediate Or Cancel orders instantly cancel the remaining size of
   the limit order instead of opening it on the book.

   FOK Fill Or Kill orders are rejected if the entire size cannot be
   matched.
     * Note that self trades belong to match as well. For market orders,
       using the “TimeInForce” parameter has no effect.

POST ONLY

   The post-only flag ensures that the trader always pays the maker fee
   and provides liquidity to the order book. If any part of the order is
   going to pay taker fee, the order will be fully rejected.

   If a post only order will get executed immediately against the existing
   orders (except iceberg and hidden orders) in the market, the order will
   be cancelled.
     * For post only orders, it will get executed immediately against the
       iceberg orders and hidden orders in the market. Users placing the
       post only order will be charged the maker fees and the iceberg and
       hidden orders will be charged the taker fees.

HIDDEN AND ICEBERG

   The Hidden and iceberg Orders are two options in advanced settings
   (note: the iceberg order is a special form of the hidden order). You
   may select “Hidden” or “Iceberg” when placing a limit or stop limit
   order.

   A hidden order will enter but not display on the orderbook.

   Different from the hidden order, an iceberg order is divided into
   visible portion and invisible portion. When placing an iceberg order,
   you need to set the visible size. The minimum visible size is 1/20 of
   the order size. The minimum visible size shall be greater than the
   minimum order size, or an error will occur.

   In a matching event, the visible portion of an iceberg order will be
   executed first, and another visible portion will pop up until the order
   is fully filled.

   Note: - The system will charge taker fees for Hidden and iceberg
   Orders.
     * If both "Iceberg" and "Hidden" are selected, your order will be
       filled as an iceberg Order by default.

HOLDS

   For limit buy orders, we will hold the needed portion from your funds
   (price x size of the order). Likewise, on sell orders, we will also
   hold the amount of assets that you wish to sell. Actual fees are
   assessed at the time of a trade. If you cancel a partially filled or
   unfilled order, any remaining funds will be released from being held.

   For market buy or sell orders where the funds are specified, the funds
   amount will be put on hold. If only size is specified, all of your
   account balance (in the quote account) will be put on hold for the
   duration of the market order (usually a trivially short time).

SELF-TRADE PREVENTION

   Self-Trade Prevention is an option in advanced settings.It is not
   selected by default. If you specify STP when placing orders, your order
   won't be matched by another one which is also yours. On the contrary,
   if STP is not specified in advanced, your order can be matched by
   another one of your own orders.

   Market order is currently not supported for DC. When the timeInForce is
   set to FOK, the stp flag will be forcely specified as CN.

   Market order is currently not supported for DC. When timeInForce is
   FOK, the stp flag will be forced to be specified as CN.
   Flag        Name
   DC   Decrease and Cancel
   CO   Cancel oldest
   CN   Cancel newest
   CB   Cancel both

ORDER LIFECYCLE

   The HTTP Request will respond when an order is either rejected
   (insufficient funds, invalid parameters, etc) or received (accepted by
   the matching engine). A 200 response indicates that the order was
   received and is active. Active orders may execute immediately
   (depending on price and market conditions) either partially or fully. A
   partial execution will put the remaining size of the order in the open
   state. An order that is filled completely, will go into the done state.

   Users listening to streaming market data are encouraged to use the
   order ID field to identify their received messages in the feed.

PRICE PROTECTION MECHANISM

    1. If there are contra orders against the market/limit orders placed
       by users in the order book, the system will detect whether the
       difference between the corresponding market price and the ask/bid
       price will exceed the threshold (you can request via the API symbol
       interface).
    2. For limit orders, if the difference exceeds the threshold, the
       order placement would fail.
    3. For market orders, the order will be partially executed against the
       existing orders in the market within the threshold and the
       remaining unfilled part of the order will be canceled immediately.
       For example: If the threshold is 10%, when a user places a market
       order to buy 10,000 USDT in the KCS/USDT market (at this time, the
       current ask price is 1.20000), the system would determine that the
       final execution price would be 1.40000. As for
       (1.40000-1.20000)/1.20000=16.7%>10%, the threshold price would be
       1.32000. Therefore, this market order will execute with the
       existing orders offering prices up to 1.32000 and the remaining
       part of the order will be canceled immediately. Notice: There might
       be some deviations of the detection. If your order is not fully
       filled, it may probably be led by the unfilled part of the order
       exceeding the threshold.

RESPONSES

    Field      Description
   orderId The ID of the order

   A successful order will be assigned an order ID. A successful order is
   defined as one that has been accepted by the matching engine.
   Open orders do not expire and will remain open until they are either
   filled or canceled.

Place a margin order

{
  "orderId": "5bd6e9286d99522a52e458de",
  "borrowSize":10.2,
  "loanApplyId":"600656d9a33ac90009de4f6f"
}

   You can place two types of orders: limit and market. Orders can only be
   placed if your account has sufficient funds. Once an order is placed,
   your account funds will be put on hold for the duration of the order.
   How much and which funds are put on hold depends on the order type and
   parameters specified. See the Holds details below.
   Placing an order will enable price protection. When the price of the
   limit order is outside the threshold range, the price protection
   mechanism will be triggered, causing the order to fail.

   Please note that the system will frozen the fees from the orders that
   entered the order book in advance. Read [371]List Fills to learn more.

   Before placing an order, please read [372]Get Symbol List to understand
   the requirements for the quantity parameters for each trading pair.

   Do not include extra spaces in JSON strings.

Place Order Limit

   The maximum active orders for a single trading pair in one account is
   200 (stop orders included).

HTTP Request

   POST /api/v1/margin/order

API KEY PERMISSIONS

   This endpoint requires the Trade permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 45
   times/3s.

PARAMETERS

   Param type Description
   clientOid String Unique order id created by users to identify their
   orders, e.g. UUID.
   side String buy or sell
   symbol String a valid trading symbol code. e.g. ETH-BTC
   type String [Optional] limit or market (default is limit)
   remark String [Optional] remark for the order, length cannot exceed 100
   utf8 characters
   stp String [Optional] self trade prevention , CN, CO, CB or DC
   marginModel String [Optional] The type of trading, including cross
   (cross mode) and isolated (isolated mode). It is set at cross by
   default.
   autoBorrow boolean [Optional] Auto-borrow to place order. The system
   will first borrow you funds at the optimal interest rate and then place
   an order for you. Currently autoBorrow parameter only supports cross
   mode, not isolated mode

LIMIT ORDER PARAMETERS

   Param type Description
   price String price per base currency
   size String amount of base currency to buy or sell
   timeInForce String [Optional] GTC, GTT, IOC, or FOK (default is GTC),
   read [373]Time In Force.
   cancelAfter long [Optional] cancel after n seconds, requires
   timeInForce to be GTT
   postOnly boolean [Optional] Post only flag, invalid when timeInForce is
   IOC or FOK
   hidden boolean [Optional] Order will not be displayed in the order book
   iceberg boolean [Optional] Only aportion of the order is displayed in
   the order book
   visibleSize String [Optional] The maximum visible size of an iceberg
   order

MARKET ORDER PARAMETERS

   Param  type                       Description
   size  String [Optional] Desired amount in base currency
   funds String [Optional] The desired amount of quote currency to use
     * It is required that you use one of the two parameters, size or
       funds.

Advanced Description

MarginMode

   There are two modes for API margin trading: cross and isolated, it is
   set at cross by default.

AutoBorrow

   This is the symbol of Auto-Borrow, if it is set to true, the system
   will automatically borrow the funds required for an order according to
   the order amount. By default, the symbol is set to false. When your
   order amount is too large, exceeding the max. borrowing amount via the
   max. leverage or the risk limit of margin, then you will fail in
   borrowing and order placing. Currently autoBorrow parameter only
   supports cross mode, not isolated mode

RESPONSES

   Field Description
   orderId The ID of the order
   borrowSize Borrowed amount. The field is returned only after placing
   the order under the mode of Auto-Borrow.
   loanApplyId ID of the borrowing response. The field is returned only
   after placing the order under the mode of Auto-Borrow.

   A successful order will be assigned an orderId. A successful order is
   defined as one that has been accepted by the matching engine.
   Open orders do not expire and will remain open until they are either
   filled or canceled.

Place Bulk Orders

//response
{
  "data": [
    {
      "symbol": "KCS-USDT",
      "type": "limit",
      "side": "buy",
      "price": "0.01",
      "size": "0.01",
      "funds": null,
      "stp": "",
      "stop": "",
      "stopPrice": null,
      "timeInForce": "GTC",
      "cancelAfter": 0,
      "postOnly": false,
      "hidden": false,
      "iceberge": false,
      "iceberg": false,
      "visibleSize": null,
      "channel": "API",
      "id": "611a6a309281bc000674d3c0",
      "status": "success",
      "failMsg": null,
      "clientOid": "552a8a0b7cb04354be8266f0e202e7e9"
    },
    {
      "symbol": "KCS-USDT",
      "type": "limit",
      "side": "buy",
      "price": "0.01",
      "size": "0.01",
      "funds": null,
      "stp": "",
      "stop": "",
      "stopPrice": null,
      "timeInForce": "GTC",
      "cancelAfter": 0,
      "postOnly": false,
      "hidden": false,
      "iceberge": false,
      "iceberg": false,
      "visibleSize": null,
      "channel": "API",
      "id": "611a6a309281bc000674d3c1",
      "status": "success",
      "failMsg": null,
      "clientOid": "bd1e95e705724f33b508ed270888a4a9"
    }
  ]
}

   Request via this endpoint to place 5 orders at the same time. The order
   type must be a limit order of the same symbol. The interface currently
   only supports spot trading

HTTP Request

   POST /api/v1/orders/multi

Example

//request
{
  "symbol": "KCS-USDT",
  "orderList": [
    {
      "clientOid": "3d07008668054da6b3cb12e432c2b13a",
      "side": "buy",
      "type": "limit",
      "price": "0.01",
      "size": "0.01"
    },
    {
      "clientOid": "37245dbe6e134b5c97732bfb36cd4a9d",
      "side": "buy",
      "type": "limit",
      "price": "0.01",
      "size": "0.01"
    }
  ]
}

   POST /api/v1/orders/multi

API KEY PERMISSIONS

   This endpoint requires the Trade permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 3
   times/3s.

PARAMETERS

   Param type Description
   clientOid String Unique order id created by users to identify their
   orders, e.g. UUID.
   side String buy or sell
   symbol String a valid trading symbol code. e.g. ETH-BTC
   type String [Optional] only limit (default is limit)
   remark String [Optional] remark for the order, length cannot exceed 100
   utf8 characters
   stop String [Optional] Either loss or entry. Requires stopPrice to be
   defined
   stopPrice String [Optional] Need to be defined if stop is specified.
   stp String [Optional] self trade prevention , CN, CO, CB or DC
   tradeType String [Optional] Default is TRADE
   price String price per base currency
   size String amount of base currency to buy or sell
   timeInForce String [Optional] GTC, GTT, IOC, or FOK (default is GTC),
   read [374]Time In Force.
   cancelAfter long [Optional] cancel after n seconds, requires
   timeInForce to be GTT
   postOnly boolean [Optional] Post only flag, invalid when timeInForce is
   IOC or FOK
   hidden boolean [Optional] Order will not be displayed in the order book
   iceberg boolean [Optional] Only aportion of the order is displayed in
   the order book
   visibleSize String [Optional] The maximum visible size of an iceberg
   order

RESPONSES

    Field       Description
   status  status (success, fail)
   failMsg the cause of failure

Cancel an order

{
     "cancelledOrderIds": [
      "5bd6e9286d99522a52e458de"   //orderId
    ]
}

   Request via this endpoint to cancel a single order previously placed.
   This interface is only for cancellation requests. The cancellation
   result needs to be obtained by querying the order status or subscribing
   to websocket. It is recommended that you DO NOT cancel the order until
   receiving the Open message, otherwise the order cannot be cancelled
   successfully.

HTTP REQUEST

   DELETE /api/v1/orders/{orderId}

Example

   DELETE /api/v1/orders/5bd6e9286d99522a52e458de

API KEY PERMISSIONS

   This endpoint requires the Trade permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 60
   times/3s.

PARAMETERS

    Param   Type               Description
   orderId String [375]Order ID, unique ID of the order.

RESPONSES

    Field            Description
   orderId Unique ID of the cancelled order
   The order ID is the server-assigned order id and not the passed
   clientOid.

CANCEL REJECT

   If the order could not be canceled (already filled or previously
   canceled, etc), then an error response will indicate the reason in the
   message field.

Cancel Single Order by clientOid

{
  "cancelledOrderId": "5f311183c9b6d539dc614db3",
  "clientOid": "6d539dc614db3"
}

   Request via this interface to cancel an order via the clientOid.

HTTP REQUEST

   DELETE /api/v1/order/client-order/{clientOid}

Example

   DELETE /api/v1/order/client-order/6d539dc614db3

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

   Param Type Description
   clientOid String Unique order id created by users to identify their
   orders

RESPONSES

        Field                              Description
   cancelledOrderId Order ID of cancelled order
   clientOid        Unique order id created by users to identify their orders

Cancel all orders

{
    "cancelledOrderIds": [

        "5c52e11203aa677f33e493fb",  //orderId
        "5c52e12103aa677f33e493fe",
        "5c52e12a03aa677f33e49401",
        "5c52e1be03aa677f33e49404",
        "5c52e21003aa677f33e49407",
        "5c6243cb03aa67580f20bf2f",
        "5c62443703aa67580f20bf32",
        "5c6265c503aa676fee84129c",
        "5c6269e503aa676fee84129f",
        "5c626b0803aa676fee8412a2"
    ]
}

   Request via this endpoint to cancel all open orders. The response is a
   list of ids of the canceled orders.

HTTP REQUEST

   DELETE /api/v1/orders

Example

   DELETE /api/v1/orders?symbol=ETH-BTC&tradeType=TRADE
   DELETE /api/v1/orders?symbol=ETH-BTC&tradeType=MARGIN_ISOLATED_TRADE

API KEY PERMISSIONS

   This endpoint requires the Trade permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 3
   times/3s.

PARAMETERS

   Param Type Description
   symbol String [Optional] symbol, cancel the orders for the specified
   trade pair.
   tradeType String [Optional] the type of trading :TRADE(Spot Trading),
   MARGIN_TRADE(Cross Margin Trading), MARGIN_ISOLATED_TRADE(Isolated
   Margin Trading), and the default is TRADE to cancel the spot trading
   orders.

RESPONSES

    Field                Description
   orderId Order ID, unique identifier of an order.

List Orders

{
    "currentPage": 1,
    "pageSize": 1,
    "totalNum": 153408,
    "totalPage": 153408,
    "items": [
        {
            "id": "5c35c02703aa673ceec2a168",   //orderid
            "symbol": "BTC-USDT",   //symbol
            "opType": "DEAL",      // operation type: DEAL
            "type": "limit",       // order type,e.g. limit,market,stop_limit.
            "side": "buy",         // transaction direction,include buy and sell
            "price": "10",         // order price
            "size": "2",           // order quantity
            "funds": "0",          // order funds
            "dealFunds": "0.166",  // deal funds
            "dealSize": "2",       // deal quantity
            "fee": "0",            // fee
            "feeCurrency": "USDT", // charge fee currency
            "stp": "",             // self trade prevention,include CN,CO,DC,CB
            "stop": "",            // stop type
            "stopTriggered": false,  // stop order is triggered
            "stopPrice": "0",      // stop price
            "timeInForce": "GTC",  // time InForce,include GTC,GTT,IOC,FOK
            "postOnly": false,     // postOnly
            "hidden": false,       // hidden order
            "iceberg": false,      // iceberg order
            "visibleSize": "0",    // display quantity for iceberg order
            "cancelAfter": 0,      // cancel orders time，requires timeInForce to
 be GTT
            "channel": "IOS",      // order source
            "clientOid": "",       // user-entered order unique mark
            "remark": "",          // remark
            "tags": "",            // tag order source
            "isActive": false,     // status before unfilled or uncancelled
            "cancelExist": false,   // order cancellation transaction record
            "createdAt": 1547026471000,  // create time
            "tradeType": "TRADE"
        }
     ]
 }

   Request via this endpoint to get your current order list. Items are
   paginated and sorted to show the latest first. See the [376]Pagination
   section for retrieving additional entries after the first page.

HTTP REQUEST

   GET /api/v1/orders

Example

   GET /api/v1/orders?status=active
   GET /api/v1/orders?status=active?tradeType=MARGIN_ISOLATED_TRADE

API KEY PERMISSIONS

   This endpoint requires the General permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 30
   times/3s.
   This request is paginated.

PARAMETERS

   You can pinpoint the results with the following query paramaters.
   Param Type Description
   status String [Optional] active or done(done as default), Only list
   orders with a specific status .
   symbol String [Optional] Only list orders for a specific symbol.
   side String [Optional] buy or sell
   type String [Optional] limit, market, limit_stop or market_stop
   tradeType String The type of trading:TRADE-Spot Trading,
   MARGIN_TRADE-Cross Margin Trading, MARGIN_ISOLATED_TRADE-Isolated
   Margin Trading.
   startAt long [Optional] Start time (milisecond)
   endAt long [Optional] End time (milisecond)

RESPONSES

   Field Description
   id Order ID, the ID of an order.
   symbol symbol
   opType Operation type: DEAL
   type order type
   side transaction direction,include buy and sell
   price order price
   size order quantity
   funds order funds
   dealFunds executed size of funds
   dealSize executed quantity
   fee fee
   feeCurrency charge fee currency
   stp self trade prevention,include CN,CO,DC,CB
   stop stop type, include entry and loss
   stopTriggered stop order is triggered or not
   stopPrice stop price
   timeInForce time InForce,include GTC,GTT,IOC,FOK
   postOnly postOnly
   hidden hidden order
   iceberg iceberg order
   visibleSize displayed quantity for iceberg order
   cancelAfter cancel orders time，requires timeInForce to be GTT
   channel order source
   clientOid user-entered order unique mark
   remark remark
   tags tag order source
   isActive order status, true and false. If true, the order is active, if
   false, the order is fillled or cancelled
   cancelExist order cancellation transaction record
   createdAt create time
   tradeType The type of trading

ORDER STATUS AND SETTLEMENT

   Any order on the exchange order book is in active status. Orders
   removed from the order book will be marked with done status. After an
   order becomes done, there may be a few milliseconds latency before it’s
   fully settled.

   You can check the orders in any status. If the status parameter is not
   specified, orders of done status will be returned by default.

   When you query orders in active status, there is no time limit.
   However, when you query orders in done status, the start and end time
   range cannot exceed 7* 24 hours. An error will occur if the specified
   time window exceeds the range. If you specify the end time only, the
   system will automatically calculate the start time as end time minus
   7*24 hours, and vice versa.

   The history for cancelled orders is only kept for one month. You will
   not be able to query for cancelled orders that have happened more than
   a month ago.
   The total number of items retrieved cannot exceed 50,000. If it is
   exceeded, please shorten the query time range.

POLLING

   For high-volume trading, it is highly recommended that you maintain
   your own list of open orders and use one of the streaming market data
   feeds to keep it updated. You should poll the open orders endpoint to
   obtain the current state of any open order.

Recent Orders

{
    "currentPage": 1,
    "pageSize": 1,
    "totalNum": 153408,
    "totalPage": 153408,
    "items": [
        {
            "id": "5c35c02703aa673ceec2a168",
            "symbol": "BTC-USDT",
            "opType": "DEAL",
            "type": "limit",
            "side": "buy",
            "price": "10",
            "size": "2",
            "funds": "0",
            "dealFunds": "0.166",
            "dealSize": "2",
            "fee": "0",
            "feeCurrency": "USDT",
            "stp": "",
            "stop": "",
            "stopTriggered": false,
            "stopPrice": "0",
            "timeInForce": "GTC",
            "postOnly": false,
            "hidden": false,
            "iceberg": false,
            "visibleSize": "0",
            "cancelAfter": 0,
            "channel": "IOS",
            "clientOid": "",
            "remark": "",
            "tags": "",
            "isActive": false,
            "cancelExist": false,
            "createdAt": 1547026471000,
            "tradeType": "TRADE"
        }
    ]
}

   Request via this endpoint to get 1000 orders in the last 24 hours.
   Items are paginated and sorted to show the latest first. See the
   [377]Pagination section for retrieving additional entries after the
   first page.

HTTP REQUEST

   GET /api/v1/limit/orders

Example

   GET /api/v1/limit/orders

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

RESPONSES

   Field Description
   orderId Order ID, unique identifier of an order.
   symbol symbol
   opType Operation type: DEAL
   type order type, e.g. limit, market, stop_limit
   side transaction direction,include buy and sell
   price order price
   size order quantity
   funds order funds
   dealFunds deal funds
   dealSize deal quantity
   fee fee
   feeCurrency charge fee currency
   stp self trade prevention,include CN,CO,DC,CB
   stop stop type, include entry and loss
   stopTriggered stop order is triggered
   stopPrice stop price
   timeInForce time InForce,include GTC,GTT,IOC,FOK
   postOnly postOnly
   hidden hidden order
   iceberg iceberg order
   visibleSize display quantity for iceberg order
   cancelAfter cancel orders time，requires timeInForce to be GTT
   channel order source
   clientOid user-entered order unique mark
   remark remark
   tags tag order source
   isActive order status, true and false. If true, the order is active, if
   false, the order is fillled or cancelled
   cancelExist order cancellation transaction record
   createdAt create time
   tradeType The type of trading : TRADE（Spot Trading）, MARGIN_TRADE
   (Margin Trading).

Get an order

{
    "id": "5c35c02703aa673ceec2a168",
    "symbol": "BTC-USDT",
    "opType": "DEAL",
    "type": "limit",
    "side": "buy",
    "price": "10",
    "size": "2",
    "funds": "0",
    "dealFunds": "0.166",
    "dealSize": "2",
    "fee": "0",
    "feeCurrency": "USDT",
    "stp": "",
    "stop": "",
    "stopTriggered": false,
    "stopPrice": "0",
    "timeInForce": "GTC",
    "postOnly": false,
    "hidden": false,
    "iceberg": false,
    "visibleSize": "0",
    "cancelAfter": 0,
    "channel": "IOS",
    "clientOid": "",
    "remark": "",
    "tags": "",
    "isActive": false,
    "cancelExist": false,
    "createdAt": 1547026471000,
    "tradeType": "TRADE"
 }

   Request via this endpoint to get a single order info by order ID.

HTTP REQUEST

   GET /api/v1/orders/{order-id}

Example

   GET /api/v1/orders/5c35c02703aa673ceec2a168

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

   Param Type Description
   orderId String Order ID, unique identifier of an order, obtained via
   the [378]List orders.

RESPONSES

   Field Description
   orderId Order ID, the ID of an order
   symbol symbol
   opType operation type,deal is pending order,cancel is cancel order
   type order type,e.g. limit,market,stop_limit.
   side transaction direction,include buy and sell
   price order price
   size order quantity
   funds order funds
   dealFunds deal funds
   dealSize deal quantity
   fee fee
   feeCurrency charge fee currency
   stp self trade prevention,include CN,CO,DC,CB
   stop stop type, include entry and loss
   stopTriggered stop order is triggered
   stopPrice stop price
   timeInForce time InForce,include GTC,GTT,IOC,FOK
   postOnly postOnly
   hidden hidden order
   iceberg iceberg order
   visibleSize display quantity for iceberg order
   cancelAfter cancel orders time，requires timeInForce to be GTT
   channel order source
   clientOid user-entered order unique mark
   remark remark
   tags tag order source
   isActive order status, true and false. If true, the order is active, if
   false, the order is fillled or cancelled
   cancelExist order cancellation transaction record
   createdAt create time
   tradeType The type of trading : TRADE（Spot Trading）, MARGIN_TRADE
   (Margin Trading).

Get Single Active Order by clientOid

{
  "id": "5f3113a1c9b6d539dc614dc6",
  "symbol": "KCS-BTC",
  "opType": "DEAL",
  "type": "limit",
  "side": "buy",
  "price": "0.00001",
  "size": "1",
  "funds": "0",
  "dealFunds": "0",
  "dealSize": "0",
  "fee": "0",
  "feeCurrency": "BTC",
  "stp": "",
  "stop": "",
  "stopTriggered": false,
  "stopPrice": "0",
  "timeInForce": "GTC",
  "postOnly": false,
  "hidden": false,
  "iceberg": false,
  "visibleSize": "0",
  "cancelAfter": 0,
  "channel": "API",
  "clientOid": "6d539dc614db312",
  "remark": "",
  "tags": "",
  "isActive": true,
  "cancelExist": false,
  "createdAt": 1597051810000,
  "tradeType": "TRADE"
}

   Request via this interface to check the information of a single active
   order via clientOid. The system will prompt that the order does not
   exists if the order does not exist or has been settled.

HTTP REQUEST

   GET /api/v1/order/client-order/{clientOid}

Example

   GET /api/v1/order/client-order/6d539dc614db312

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

   Param Type Description
   clientOid String Unique order id created by users to identify their
   orders

RESPONSES

   Field Description
   id Order ID, the ID of an order
   symbol symbol
   opType operation type,deal is pending order,cancel is cancel order
   type order type,e.g. limit,market,stop_limit.
   side transaction direction,include buy and sell
   price order price
   size order quantity
   funds order funds
   dealFunds deal funds
   dealSize deal quantity
   fee fee
   feeCurrency charge fee currency
   stp self trade prevention,include CN,CO,DC,CB
   stop stop type, include entry and loss
   stopTriggered stop order is triggered
   stopPrice stop price
   timeInForce time InForce,include GTC,GTT,IOC,FOK
   postOnly postOnly
   hidden hidden order
   iceberg iceberg order
   visibleSize display quantity for iceberg order
   cancelAfter cancel orders time，requires timeInForce to be GTT
   channel order source
   clientOid user-entered order unique mark
   remark remark
   tags tag order source
   isActive order status, true and false. If true, the order is active, if
   false, the order is fillled or cancelled
   cancelExist order cancellation transaction record
   createdAt create time
   tradeType The type of trading : TRADE（Spot Trading）, MARGIN_TRADE
   (Margin Trading).

Fills

List Fills

{
    "currentPage":1,
    "pageSize":1,
    "totalNum":251915,
    "totalPage":251915,
    "items":[
        {
            "symbol":"BTC-USDT",    //symbol
            "tradeId":"5c35c02709e4f67d5266954e",   //trade id
            "orderId":"5c35c02703aa673ceec2a168",   //order id
            "counterOrderId":"5c1ab46003aa676e487fa8e3",  //counter order id
            "side":"buy",   //transaction direction,include buy and sell
            "liquidity":"taker",  //include taker and maker
            "forceTaker":true,  //forced to become taker
            "price":"0.083",   //order price
            "size":"0.8424304",  //order quantity
            "funds":"0.0699217232",  //order funds
            "fee":"0",  //fee
            "feeRate":"0",  //fee rate
            "feeCurrency":"USDT",  // charge fee currency
            "stop":"",        // stop type
            "type":"limit",  // order type,e.g. limit,market,stop_limit.
            "createdAt":1547026472000,  //time
            "tradeType": "TRADE"
        }
    ]
}

   Request via this endpoint to get the recent fills.

   Items are paginated and sorted to show the latest first. See the
   [379]Pagination section for retrieving additional entries after the
   first page.

HTTP REQUEST

   GET /api/v1/fills

Example

   GET /api/v1/fills

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 9
   times/3s.
   This request is paginated.

PARAMETERS

   You can request fills for specific orders using query parameters.
   Param Type Description
   orderId String [Optional] Limit the list of fills to this orderId（If
   you specify orderId, ignore other conditions）
   symbol String [Optional] Limit the list of fills to this symbol
   side String [Optional] buy or sell
   type String [Optional] limit, market, limit_stop or market_stop
   startAt long [Optional] Start time (milisecond)
   endAt long [Optional] End time (milisecond)
   tradeType String The type of trading : TRADE（Spot Trading）,
   MARGIN_TRADE (Margin Trading).

RESPONSES

   Field Description
   symbol symbol.
   tradeId trade id, it is generated by Matching engine.
   orderId Order ID, unique identifier of an order.
   counterOrderId counter order id.
   side transaction direction,include buy and sell.
   price order price
   size order quantity
   funds order funds
   type order type,e.g. limit,market,stop_limit.
   fee fee
   feeCurrency charge fee currency
   stop stop type, include entry and loss
   liquidity include taker and maker
   forceTaker forced to become taker, include true and false
   createdAt create time
   tradeType The type of trading : TRADE（Spot Trading）, MARGIN_TRADE
   (Margin Trading).

   Data time range

   The system allows you to retrieve data up to one week (start from the
   last day by default). If the time period of the queried data exceeds
   one week (time range from the start time to end time exceeded 7*24
   hours), the system will prompt to remind you that you have exceeded the
   time limit. If you only specified the start time, the system will
   automatically calculate the end time (end time = start time + 7 * 24
   hours). On the contrary, if you only specified the end time, the system
   will calculate the start time (start time= end time - 7 * 24 hours) the
   same way.
   The total number of items retrieved cannot exceed 50,000. If it is
   exceeded, please shorten the query time range.

   Settlement

   The settlement contains two parts: - Transactional settlement - Fee
   settlement

   After an order is matched, the transactional and fee settlement data
   will be updated in the data store. Once the data is updated, the system
   would enable the settlement process and will deduct the fees from your
   pre-frozen assets. After that, the currency will be transferred to the
   account of the user.

   Fees

   Orders on KuCoin platform are classified into two types， taker and
   maker. A taker order matches other resting orders on the exchange order
   book, and gets executed immediately after order entry. A maker order,
   on the contrary, stays on the exchange order book and awaits to be
   matched. Taker orders will be charged taker fees, while maker orders
   will receive maker rebates. Please note that market orders, iceberg
   orders and hidden orders are always charged taker fees.

   The system will pre-freeze a predicted taker fee when you place an
   order.The liquidity field indicates if the fill was charged taker or
   maker fees.

   With the leading matching engine system in the market, users placing
   orders on KuCoin platform are classified into two types: taker and
   maker. Takers, as the taker in the market, would be charged with taker
   fees; while makers as the maker in the market, would be charged with
   less fees than the taker, or even get maker fees from KuCoin （The
   exchange platform would compensate the transaction fees for you）.

   After placing orders on the KuCoin platform, to ensure the execution of
   these orders, the system would pre-freeze your assets based on the
   taker fee charges (because the system could not predict the order types
   you may choose). Please be noted that the system would deduct the fees
   from the orders entered the orderbook in advance.

   If your order is market order, the system would charge taker fees from
   you.

   If your order is limit order and is immediately matched and executed,
   the system would charge taker fees from you. On the contrary, if the
   order or part or your order is not executed immediately and enters into
   the order book, the system would charge maker fees from you if it is
   executed before being cancelled

   After the order is executed and when the left order funds is 0, the
   transaction is completed. If the remaining funds is not sufficient to
   support the minimum product (min.: 0.00000001), then the left part in
   the order would be cancelled.

   If your order is a maker order, the system would return the left
   pre-frozen taker fees to you.

   Notice:
     * For a hidden/iceberg order, if it is not executed immediately and
       becomes a maker order, the system would still charge taker fees
       from you.
     * Post Only order will charge you maker fees. If a post only order
       would get executed immediately against the existing orders (except
       iceberg and hidden orders) in the market, the order will be
       cancelled. If the post only order will execute against an
       iceberg/hidden order immediately, you will get the maker fees.

   For example:

   Take BTC/USDT as the trading pair, if you plan to buy 1 BTC in market
   price, suppose the fee charge is 0.1% and the data on the order book is
   as follows:
   Price（USDT） Size（BTC）  Side
   4200.00     0.18412309 sell
   4015.60     0.56849308 sell
   4011.32     0.24738383 sell
   3995.64     0.84738383 buy
   3988.60     0.20484000 buy
   3983.85     1.37584908 buy

   When you placed a buy order in market price, the order would be
   executed immediately. The transaction detail is as follows:
   Price（USDT） Size（BTC）   Fee（BTC）
   4011.32     0.24738383 0.00024738
   4015.60     0.56849308 0.00056849
   4200.00     0.18312409 0.00018312

Recent Fills

{
    "code":"200000",
    "data":[
        {
            "counterOrderId":"5db7ee769797cf0008e3beea",
            "createdAt":1572335233000,
            "fee":"0.946357371456",
            "feeCurrency":"USDT",
            "feeRate":"0.001",
            "forceTaker":true,
            "funds":"946.357371456",
            "liquidity":"taker",
            "orderId":"5db7ee805d53620008dce1ba",
            "price":"9466.8",
            "side":"buy",
            "size":"0.09996592",
            "stop":"",
            "symbol":"BTC-USDT",
            "tradeId":"5db7ee8054c05c0008069e21",
            "tradeType":"MARGIN_TRADE",
            "type":"market"
        },
        {
            "counterOrderId":"5db7ee4b5d53620008dcde8e",
            "createdAt":1572335207000,
            "fee":"0.94625",
            "feeCurrency":"USDT",
            "feeRate":"0.001",
            "forceTaker":true,
            "funds":"946.25",
            "liquidity":"taker",
            "orderId":"5db7ee675d53620008dce01e",
            "price":"9462.5",
            "side":"sell",
            "size":"0.1",
            "stop":"",
            "symbol":"BTC-USDT",
            "tradeId":"5db7ee6754c05c0008069e03",
            "tradeType":"MARGIN_TRADE",
            "type":"market"
        },
        {
            "counterOrderId":"5db69aa4688933000aab8114",
            "createdAt":1572248229000,
            "fee":"1.882148318525",
            "feeCurrency":"USDT",
            "feeRate":"0.001",
            "forceTaker":false,
            "funds":"1882.148318525",
            "liquidity":"maker",
            "orderId":"5db69a9c4e6d020008f03275",
            "price":"9354.5",
            "side":"sell",
            "size":"0.20120245",
            "stop":"",
            "symbol":"BTC-USDT",
            "tradeId":"5db69aa477d8de0008c1efac",
            "tradeType":"MARGIN_TRADE",
            "type":"limit"
        }
    ]
}


   Request via this endpoint to get a list of 1000 fills in the last 24
   hours.

HTTP REQUEST

   GET /api/v1/limit/fills

Example

   GET /api/v1/limit/fills

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

RESPONSES

   Field Description
   symbol symbol
   tradeId trade id, it is generated by Matching engine.
   orderId Order ID, unique identifier of an order.
   counterOrderId counter order id.
   side transaction direction,include buy and sell.
   price order price
   size order quantity
   funds order funds
   type order type,e.g. limit,market,stop_limit.
   fee fee
   feeCurrency charge fee currency
   stop stop type, include entry and loss
   liquidity include taker and maker
   forceTaker forced to become taker, include true and false
   createdAt create time
   tradeType The type of trading : TRADE（Spot Trading）, MARGIN_TRADE
   (Margin Trading).

Stop Order

   A stop order is an order to buy or sell the specified amount of cryptos
   at the last traded price or pre-specified limit price once the order
   has traded at or through a pre-specified stopPrice. The order will be
   executed by the highest price first. For orders of the same price, the
   order will be executed in time priority.

   stop: 'loss': Triggers when the last trade price changes to a value at
   or below the stopPrice.

   stop: 'entry': Triggers when the last trade price changes to a value at
   or above the stopPrice.

   The last trade can be found in the latest match message. Note that not
   all match messages may be received due to dropped messages.

   The last trade price is the last price at which an order was filled.
   This price can be found in the latest match message. Note that not all
   match messages may be received due to dropped messages.

   Note that when triggered, stop orders execute as either market or limit
   orders, depending on the type.

   When placing a stop loss order, the system will not pre-freeze the
   assets in your account for the order. When you are going to place a
   stop market order, we recommend you to specify the funds for the order
   when trading.

Place a new order

{
  "orderId": "vs8hoo8kpkmklv4m0038lql0"
}

   Do not include extra spaces in JSON strings in request body.

Limitation

   The maximum untriggered stop orders for a single trading pair in one
   account is 20.

HTTP Request

   POST /api/v1/stop-order

Example

   POST /api/v1/stop-order

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

Request Body Parameters

   Param Type Description
   clientOid String Unique order id created by users to identify their
   orders, e.g. UUID.
   side String buy or sell
   symbol String a valid trading symbol code. e.g. ETH-BTC
   type String [Optional] limit or market, the default is limit
   remark String [Optional] remark for the order, length cannot exceed 100
   utf8 characters
   stop String [Optional] Either loss or entry, the default is loss.
   Requires stopPrice to be defined.
   stopPrice String Need to be defined if stop is specified.
   stp String [Optional] self trade prevention , CN, CO, CB , DC (limit
   order does not support DC)
   tradeType String [Optional] The type of trading : TRADE（Spot Trade）,
   MARGIN_TRADE (Margin Trade). Default is TRADE

LIMIT ORDER PARAMETERS

   Param type Description
   price String price per base currency
   size String amount of base currency to buy or sell
   timeInForce String [Optional] GTC, GTT, IOC, or FOK (default is GTC),
   read [380]Time In Force.
   cancelAfter long [Optional] cancel after n seconds, requires
   timeInForce to be GTT
   postOnly boolean [Optional] Post only flag, invalid when timeInForce is
   IOC or FOK
   hidden boolean [Optional] Order will not be displayed in the order book
   iceberg boolean [Optional] Only aportion of the order is displayed in
   the order book
   visibleSize String [Optional] The maximum visible size of an iceberg
   order

MARKET ORDER PARAMETERS

   Param  type                       Description
   size  String [Optional] Desired amount in base currency
   funds String [Optional] The desired amount of quote currency to use
     * It is required that you use one of the two parameters, size or
       funds.

RESPONSES

    Field      Description
   orderId The ID of the order

   A successful order will be assigned an order ID. A successful order is
   defined as one that has been accepted by the matching engine.

Cancel an Order

{
  "cancelledOrderIds": [
    "611477889281bc0006d68aea"
  ]
}

   Request via this endpoint to cancel a single stop order previously
   placed.

   You will receive cancelledOrderIds field once the system has received
   the cancellation request. The cancellation request will be processed by
   the matching engine in sequence. To know if the request is processed
   (successfully or not), you may check the order status or the update
   message from the pushes.

HTTP Request

   DELETE /api/v1/stop-order/{orderId}

Example

   DELETE /api/v1/stop-order/5bd6e9286d99522a52e458de

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param   Type               Description
   orderId String [381]Order ID, unique ID of the order.

RESPONSES

         Field           Description
   cancelledOrderIds cancelled order ids
   The order ID is the server-assigned order id and not the passed
   clientOid.

CANCEL REJECT

   If the order could not be canceled (already filled or previously
   canceled, etc), then an error response will indicate the reason in the
   message field.

Cancel Orders

{
  "cancelledOrderIds": [
    "vs8hoo8m4751f5np0032t7gk",
    "vs8hoo8m4758qjjp0037mslk",
    "vs8hoo8prp98qjjp0037q9gb",
    "vs8hoo8prp91f5np00330k6p"
  ]
}

   Request via this interface to cancel a batch of stop orders.

HTTP Request

   DELETE /api/v1/stop-order/cancel

Example

   DELETE
   /api/v1/stop-order/cancel?symbol=ETH-BTC&tradeType=TRADE&orderIds=5bd6e
   9286d99522a52e458de,5bd6e9286d99522a52e458df

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

   Parm Type Decription
   symbol String [Optional] symbol
   tradeType String [Optional] The type of trading : TRADE（Spot Trading）,
   MARGIN_TRADE (Margin Trading).
   orderIds String [Optional] Comma seperated order IDs.

RESPONSES

         Field           Decription
   cancelledOrderIds cancelled order ids

Get Single Order Info

{
  "id": "vs8hoo8q2ceshiue003b67c0",
  "symbol": "KCS-USDT",
  "userId": "60fe4956c43cbc0006562c2c",
  "status": "NEW",
  "type": "limit",
  "side": "buy",
  "price": "0.01000000000000000000",
  "size": "0.01000000000000000000",
  "funds": null,
  "stp": null,
  "timeInForce": "GTC",
  "cancelAfter": -1,
  "postOnly": false,
  "hidden": false,
  "iceberg": false,
  "visibleSize": null,
  "channel": "API",
  "clientOid": "40e0eb9efe6311eb8e58acde48001122",
  "remark": null,
  "tags": null,
  "orderTime": 1629098781127530345,
  "domainId": "kucoin",
  "tradeSource": "USER",
  "tradeType": "TRADE",
  "feeCurrency": "USDT",
  "takerFeeRate": "0.00200000000000000000",
  "makerFeeRate": "0.00200000000000000000",
  "createdAt": 1629098781128,
  "stop": "loss",
  "stopTriggerTime": null,
  "stopPrice": "10.00000000000000000000"
}

   Request via this interface to get a stop order information via the
   order ID.

HTTP Request

   GET /api/v1/stop-order/{orderId}

Example

   GET /api/v1/stop-order/5c35c02703aa673ceec2a168

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

    Parm    Type  Decription
   orderId String Order ID

RESPONSES

   Field Description
   id Order ID, the ID of an order.
   symbol Symbol
   userId User ID
   status Order status, include NEW, TRIGGERED
   type Order type
   side transaction direction,include buy and sell
   price order price
   size order quantity
   funds order funds
   stp self trade prevention
   timeInForce time InForce,include GTC,GTT,IOC,FOK
   cancelAfter cancel orders after n seconds，requires timeInForce to be
   GTT
   postOnly postOnly
   hidden hidden order
   iceberg Iceberg order
   visibleSize displayed quantity for iceberg order
   channel order source
   clientOid user-entered order unique mark
   remark Remarks
   tags tag order source
   orderTime Time of place a stop order, accurate to nanoseconds
   domainId domainId, e.g: kucoin
   tradeSource trade source: USER（Order by user）, MARGIN_SYSTEM（Order by
   margin system）
   tradeType The type of trading : TRADE（Spot Trading）, MARGIN_TRADE
   (Margin Trading).
   feeCurrency The currency of the fee
   takerFeeRate Fee Rate of taker
   makerFeeRate Fee Rate of maker
   createdAt order creation time
   stop Stop order type, include loss and entry
   stopTriggerTime The trigger time of the stop order
   stopPrice stop price

List Stop Orders

{
  "currentPage": 1,
  "pageSize": 50,
  "totalNum": 1,
  "totalPage": 1,
  "items": [
    {
      "id": "vs8hoo8kqjnklv4m0038lrfq",
      "symbol": "KCS-USDT",
      "userId": "60fe4956c43cbc0006562c2c",
      "status": "NEW",
      "type": "limit",
      "side": "buy",
      "price": "0.01000000000000000000",
      "size": "0.01000000000000000000",
      "funds": null,
      "stp": null,
      "timeInForce": "GTC",
      "cancelAfter": -1,
      "postOnly": false,
      "hidden": false,
      "iceberg": false,
      "visibleSize": null,
      "channel": "API",
      "clientOid": "404814a0fb4311eb9098acde48001122",
      "remark": null,
      "tags": null,
      "orderTime": 1628755183702150167,
      "domainId": "kucoin",
      "tradeSource": "USER",
      "tradeType": "TRADE",
      "feeCurrency": "USDT",
      "takerFeeRate": "0.00200000000000000000",
      "makerFeeRate": "0.00200000000000000000",
      "createdAt": 1628755183704,
      "stop": "loss",
      "stopTriggerTime": null,
      "stopPrice": "10.00000000000000000000"
    }
  ]
}

   Request via this endpoint to get your current untriggered stop order
   list. Items are paginated and sorted to show the latest first. See the
   [382]Pagination section for retrieving additional entries after the
   first page.

HTTP REQUEST

   GET /api/v1/stop-order

Example

   GET /api/v1/stop-order

API KEY PERMISSIONS

   This endpoint requires the "General" permission.
   This request is paginated.

PARAMETERS

   You can pinpoint the results with the following query paramaters.
   Param Type Description
   symbol String [Optional] Only list orders for a specific symbol.
   side String [Optional] buy or sell
   type String [Optional] limit, market, limit_stop or market_stop
   tradeType String The type of trading : TRADE（Spot Trading）,
   MARGIN_TRADE (Margin Trading).
   startAt long [Optional] Start time (milisecond)
   endAt long [Optional] End time (milisecond)
   currentPage Int [Optional] current page
   orderIds String [Optional] comma seperated order ID list
   pageSize Int [Optional] page size

RESPONSES

   Field Description
   id Order ID, the ID of an order.
   symbol Symbol
   userId User ID
   status Order status, include NEW, TRIGGERED
   type Order type
   side transaction direction,include buy and sell
   price order price
   size order quantity
   funds order funds
   stp self trade prevention
   timeInForce time InForce,include GTC,GTT,IOC,FOK
   cancelAfter cancel orders after n seconds，requires timeInForce to be
   GTT
   postOnly postOnly
   hidden hidden order
   iceberg Iceberg order
   visibleSize displayed quantity for iceberg order
   channel order source
   clientOid user-entered order unique mark
   remark Remarks
   tags tag order source
   orderTime Time of place a stop order, accurate to nanoseconds
   domainId domainId, e.g: kucoin
   tradeSource trade source: USER（Order by user）, MARGIN_SYSTEM（Order by
   margin system）
   tradeType The type of trading : TRADE（Spot Trading）, MARGIN_TRADE
   (Margin Trading).
   feeCurrency The currency of the fee
   takerFeeRate Fee Rate of taker
   makerFeeRate Fee Rate of maker
   createdAt order creation time
   stop Stop order type, include loss and entry
   stopTriggerTime The trigger time of the stop order
   stopPrice stop price

Get Single Order by clientOid

[
  {
    "id": "vs8hoo8os561f5np0032vngj",
    "symbol": "KCS-USDT",
    "userId": "60fe4956c43cbc0006562c2c",
    "status": "NEW",
    "type": "limit",
    "side": "buy",
    "price": "0.01000000000000000000",
    "size": "0.01000000000000000000",
    "funds": null,
    "stp": null,
    "timeInForce": "GTC",
    "cancelAfter": -1,
    "postOnly": false,
    "hidden": false,
    "iceberg": false,
    "visibleSize": null,
    "channel": "API",
    "clientOid": "2b700942b5db41cebe578cff48960e09",
    "remark": null,
    "tags": null,
    "orderTime": 1629020492834532568,
    "domainId": "kucoin",
    "tradeSource": "USER",
    "tradeType": "TRADE",
    "feeCurrency": "USDT",
    "takerFeeRate": "0.00200000000000000000",
    "makerFeeRate": "0.00200000000000000000",
    "createdAt": 1629020492837,
    "stop": "loss",
    "stopTriggerTime": null,
    "stopPrice": "1.00000000000000000000"
  }
]

   Request via this interface to get a stop order information via the
   clientOid.

HTTP Request

   GET /api/v1/stop-order/queryOrderByClientOid

Example

   GET
   /api/v1/stop-order/queryOrderByClientOid?symbol=BTC-USDT&clientOid=9823
   jnfda923a

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

   Param Type Description
   clientOid String Unique order id created by users to identify their
   orders
   symbol String [Optional] Only list orders for a specific symbol.

RESPONSES

   Field Description
   id Order ID, the ID of an order.
   symbol Symbol
   userId User ID
   status Order status, include NEW, TRIGGERED
   type Order type
   side transaction direction,include buy and sell
   price order price
   size order quantity
   funds order funds
   stp self trade prevention
   timeInForce time InForce,include GTC,GTT,IOC,FOK
   cancelAfter cancel orders after n seconds，requires timeInForce to be
   GTT
   postOnly postOnly
   hidden hidden order
   iceberg Iceberg order
   visibleSize displayed quantity for iceberg order
   channel order source
   clientOid user-entered order unique mark
   remark Remarks
   tags tag order source
   orderTime Time of place a stop order, accurate to nanoseconds
   domainId domainId, e.g: kucoin
   tradeSource trade source: USER（Order by user）, MARGIN_SYSTEM（Order by
   margin system）
   tradeType The type of trading : TRADE（Spot Trading）, MARGIN_TRADE
   (Margin Trading).
   feeCurrency The currency of the fee
   takerFeeRate Fee Rate of taker
   makerFeeRate Fee Rate of maker
   createdAt order creation time
   stop Stop order type, include loss and entry
   stopTriggerTime The trigger time of the stop order
   stopPrice stop price

Cancel Single Order by clientOid

{
  "cancelledOrderId": "vs8hoo8ksc8mario0035a74n",
  "clientOid": "689ff597f4414061aa819cc414836abd"
}

   Request via this interface to cancel a stop order via the clientOid.

HTTP REQUEST

   DELETE /api/v1/stop-order/cancelOrderByClientOid

Example

   DELETE
   /api/v1/stop-order/cancelOrderByClientOid?symbol=BTC-USDT&clientOid=982
   3jnfda923a

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

   Param Type Description
   clientOid String Unique order id created by users to identify their
   orders
   symbol String [Optional] Unique order id created by users to identify
   their orders

RESPONSES

        Field                              Description
   cancelledOrderId Order ID of cancelled order
   clientOid        Unique order id created by users to identify their orders

Market Data

   Signature is not required for this part

Symbols & Ticker

Get Symbols List(deprecated)

{
    "code": "200000",
    "data": [
        {
            "symbol": "GALAX-USDT",
            "name": "GALA-USDT",
            "baseCurrency": "GALA",// It's not accurate, It should be GALAX inst
ead of GALA
            "quoteCurrency": "USDT",
            "feeCurrency": "USDT",
            "market": "USDS",
            "baseMinSize": "10",
            "quoteMinSize": "0.001",
            "baseMaxSize": "10000000000",
            "quoteMaxSize": "99999999",
            "baseIncrement": "0.0001",
            "quoteIncrement": "0.00001",
            "priceIncrement": "0.00001",
            "priceLimitRate": "0.1",
            "minFunds": "0.1",
            "isMarginEnabled": true,
            "enableTrading": true
        },
        {
            "symbol": "XLM-USDT",
            "name": "XLM-USDT",
            "baseCurrency": "XLM",
            "quoteCurrency": "USDT",
            "feeCurrency": "USDT",
            "market": "USDS",
            "baseMinSize": "0.1",
            "quoteMinSize": "0.01",
            "baseMaxSize": "10000000000",
            "quoteMaxSize": "99999999",
            "baseIncrement": "0.0001",
            "quoteIncrement": "0.000001",
            "priceIncrement": "0.000001",
            "priceLimitRate": "0.1",
            "minFunds": "0.1",
            "isMarginEnabled": true,
            "enableTrading": true
        }
    ]
}

   Request via this endpoint to get a list of available currency pairs for
   trading. If you want to get the market information of the trading
   symbol, please use [383]Get All Tickers.

HTTP REQUEST

   GET /api/v1/symbols
   The GET /api/v1/symbols endpoint is deprecated because when the name of
   trading pairs changes, the baseCurrency in the response also changes,
   which is not accurate. So it is recommended to use GET /api/v2/symbols
   endpoint instead

Example

   GET /api/v1/symbols

PARAMETERS

   Param   Type  Mandatory       Description
   market String No        The [384]trading market.

RESPONSES

   Field Description
   symbol unique code of a symbol, it would not change after renaming
   name Name of trading pairs, it would change after renaming
   baseCurrency Base currency,e.g. BTC.
   quoteCurrency Quote currency,e.g. USDT.
   market The [385]trading market.
   baseMinSize The minimum order quantity requried to place an order.
   quoteMinSize The minimum order funds required to place a market order.
   baseMaxSize The maximum order size required to place an order.
   quoteMaxSize The maximum order funds required to place a market order.
   baseIncrement The increment of the order size. The value shall be a
   positive multiple of the baseIncrement.
   quoteIncrement The increment of the funds required to place a market
   order. The value shall be a positive multiple of the quoteIncrement.
   priceIncrement The increment of the price required to place a limit
   order. The value shall be a positive multiple of the priceIncrement.
   feeCurrency The currency of charged fees.
   enableTrading Available for transaction or not.
   isMarginEnabled Available for margin or not.
   priceLimitRate Threshold for price portection
   minFunds the minimum spot and margin trading amounts

   The baseMinSize and baseMaxSize fields define the min and max order
   size. The priceIncrement field specifies the min order price as well as
   the price increment.This also applies to quote currency.

   The order price must be a positive integer multiple of this
   priceIncrement (i.e. if the increment is 0.01, the 0.001 and 0.021
   order prices would be rejected).

   priceIncrement and quoteIncrement may be adjusted in the future. We
   will notify you by email and site notifications before adjustment.
   Order Type                Follow the rules of minFunds
   Limit Buy   [Order Amount * Order Price] >= minFunds
   Limit Sell  [Order Amount * Order Price] >= minFunds
   Market Buy  Order Value >= minFunds
   Market Sell [Order Amount * Last Price of Base Currency] >= minFunds

   Note:
     * API market buy orders (by amount) valued at [Order Amount * Last
       Price of Base Currency] <minFunds will be rejected.
     * API market sell orders (by value) valued at <minFunds will be
       rejected.
     * Take profit and stop loss orders at market or limit prices will be
       rejected when triggered.

Get Symbols List

{
    "code": "200000",
    "data": [
        {
            "symbol": "GALAX-USDT",
            "name": "GALA-USDT",
            "baseCurrency": "GALAX",
            "quoteCurrency": "USDT",
            "feeCurrency": "USDT",
            "market": "USDS",
            "baseMinSize": "10",
            "quoteMinSize": "0.001",
            "baseMaxSize": "10000000000",
            "quoteMaxSize": "99999999",
            "baseIncrement": "0.0001",
            "quoteIncrement": "0.00001",
            "priceIncrement": "0.00001",
            "priceLimitRate": "0.1",
            "minFunds": "0.1",
            "isMarginEnabled": true,
            "enableTrading": true
        },
        {
            "symbol": "XLM-USDT",
            "name": "XLM-USDT",
            "baseCurrency": "XLM",
            "quoteCurrency": "USDT",
            "feeCurrency": "USDT",
            "market": "USDS",
            "baseMinSize": "0.1",
            "quoteMinSize": "0.01",
            "baseMaxSize": "10000000000",
            "quoteMaxSize": "99999999",
            "baseIncrement": "0.0001",
            "quoteIncrement": "0.000001",
            "priceIncrement": "0.000001",
            "priceLimitRate": "0.1",
            "minFunds": "0.1",
            "isMarginEnabled": true,
            "enableTrading": true
        }
    ]
}

   Request via this endpoint to get a list of available currency pairs for
   trading. If you want to get the market information of the trading
   symbol, please use [386]Get All Tickers.

HTTP REQUEST

   GET /api/v2/symbols

Example

   GET /api/v2/symbols

PARAMETERS

   Param   Type  Mandatory       Description
   market String No        The [387]trading market.

RESPONSES

   Field Description
   symbol unique code of a symbol, it would not change after renaming
   name Name of trading pairs, it would change after renaming
   baseCurrency Base currency,e.g. BTC.
   quoteCurrency Quote currency,e.g. USDT.
   market The [388]trading market.
   baseMinSize The minimum order quantity requried to place an order.
   quoteMinSize The minimum order funds required to place a market order.
   baseMaxSize The maximum order size required to place an order.
   quoteMaxSize The maximum order funds required to place a market order.
   baseIncrement The increment of the order size. The value shall be a
   positive multiple of the baseIncrement.
   quoteIncrement The increment of the funds required to place a market
   order. The value shall be a positive multiple of the quoteIncrement.
   priceIncrement The increment of the price required to place a limit
   order. The value shall be a positive multiple of the priceIncrement.
   feeCurrency The currency of charged fees.
   enableTrading Available for transaction or not.
   isMarginEnabled Available for margin or not.
   priceLimitRate Threshold for price portection
   minFunds the minimum spot and margin trading amounts

   The baseMinSize and baseMaxSize fields define the min and max order
   size. The priceIncrement field specifies the min order price as well as
   the price increment.This also applies to quote currency.

   The order price must be a positive integer multiple of this
   priceIncrement (i.e. if the increment is 0.01, the 0.001 and 0.021
   order prices would be rejected).

   priceIncrement and quoteIncrement may be adjusted in the future. We
   will notify you by email and site notifications before adjustment.
   Order Type                Follow the rules of minFunds
   Limit Buy   [Order Amount * Order Price] >= minFunds
   Limit Sell  [Order Amount * Order Price] >= minFunds
   Market Buy  Order Value >= minFunds
   Market Sell [Order Amount * Last Price of Base Currency] >= minFunds

   Note:
     * API market buy orders (by amount) valued at [Order Amount * Last
       Price of Base Currency] <minFunds will be rejected.
     * API market sell orders (by value) valued at <minFunds will be
       rejected.
     * Take profit and stop loss orders at market or limit prices will be
       rejected when triggered.

Get Ticker

//Get Ticker
{
    "sequence": "1550467636704",
    "bestAsk": "0.03715004",
    "size": "0.17",
    "price": "0.03715005",
    "bestBidSize": "3.803",
    "bestBid": "0.03710768",
    "bestAskSize": "1.788",
    "time": 1550653727731
}

   Request via this endpoint to get Level 1 Market Data. The returned
   value includes the best bid price and size, the best ask price and size
   as well as the last traded price and the last traded size.

HTTP REQUEST

   GET /api/v1/market/orderbook/level1

Example

   GET /api/v1/market/orderbook/level1?symbol=BTC-USDT

PARAMETERS

   Param   Type  Description
   symbol String [389]symbol

RESPONSES

      Field       Description
   sequence    Sequence
   bestAsk     Best ask price
   size        Last traded size
   price       Last traded price
   bestBidSize Best bid size
   bestBid     Best bid price
   bestAskSize Best ask size
   time        timestamp

Get All Tickers

{
    "time":1602832092060,
    "ticker":[
        {
            "symbol": "BTC-USDT",   // symbol
            "symbolName":"BTC-USDT", // Name of trading pairs, it would change a
fter renaming
            "buy": "11328.9",   // bestAsk
            "sell": "11329",    // bestBid
            "changeRate": "-0.0055",    // 24h change rate
            "changePrice": "-63.6", // 24h change price
            "high": "11610",    // 24h highest price
            "low": "11200", // 24h lowest price
            "vol": "2282.70993217", // 24h volume，the aggregated trading volume
in BTC
            "volValue": "25984946.157790431",   // 24h total, the trading volume
 in quote currency of last 24 hours
            "last": "11328.9",  // last price
            "averagePrice": "11360.66065903",   // 24h average transaction price
 yesterday
            "takerFeeRate": "0.001",    // Basic Taker Fee
            "makerFeeRate": "0.001",    // Basic Maker Fee
            "takerCoefficient": "1",    // Taker Fee Coefficient
            "makerCoefficient": "1" // Maker Fee Coefficient
        }
    ]
}

   Request market tickers for all the trading pairs in the market
   (including 24h volume).

   On the rare occasion that we will change the currency name, if you
   still want the changed symbol name, you can use the symbolName field
   instead of the symbol field via “Get all tickers” endpoint.

HTTP REQUEST

   GET /api/v1/market/allTickers

PARAMETERS

   N/A

RESPONSES

        Field                            Description
   time             timestamp
   symbol           Symbol
   symbolName       Name of trading pairs, it would change after renaming
   buy              Best bid price
   sell             Best ask price
   changeRate       24h change rate
   changePrice      24h change price
   high             Highest price in 24h
   low              Lowest price in 24h
   vol              24h volume, executed based on base currency
   volValue         24h traded amount
   last             Last traded price
   averagePrice     Average trading price in the last 24 hours
   takerFeeRate     Basic Taker Fee
   makerFeeRate     Basic Maker Fee
   takerCoefficient Taker Fee Coefficient
   makerCoefficient Maker Fee Coefficient

Get 24hr Stats

//Get 24hr Stats
{
    "time": 1602832092060,  // time
    "symbol": "BTC-USDT",   // symbol
    "buy": "11328.9",   // bestAsk
    "sell": "11329",    // bestBid
    "changeRate": "-0.0055",    // 24h change rate
    "changePrice": "-63.6", // 24h change price
    "high": "11610",    // 24h highest price
    "low": "11200", // 24h lowest price
    "vol": "2282.70993217", // 24h volume，the aggregated trading volume in BTC
    "volValue": "25984946.157790431",   // 24h total, the trading volume in quot
e currency of last 24 hours
    "last": "11328.9",  // last price
    "averagePrice": "11360.66065903",   // 24h average transaction price yesterd
ay
    "takerFeeRate": "0.001",    // Basic Taker Fee
    "makerFeeRate": "0.001",    // Basic Maker Fee
    "takerCoefficient": "1",    // Taker Fee Coefficient
    "makerCoefficient": "1" // Maker Fee Coefficient
}

   Request via this endpoint to get the statistics of the specified ticker
   in the last 24 hours.

HTTP REQUEST

   GET /api/v1/market/stats

Example

   GET /api/v1/market/stats?symbol=BTC-USDT

PARAMETERS

   Param   Type  Description
   symbol String [390]symbol

RESPONSES

        Field                       Description
   time             timestamp
   symbol           Symbol
   buy              Best bid price
   sell             Best ask price
   changeRate       24h change rate
   changePrice      24h change price
   high             Highest price in 24h
   low              Lowest price in 24h
   vol              24h volume, executed based on base currency
   volValue         24h traded amount
   last             Last traded price
   averagePrice     Average trading price in the last 24 hours
   takerFeeRate     Basic Taker Fee
   makerFeeRate     Basic Maker Fee
   takerCoefficient Taker Fee Coefficient
   makerCoefficient Maker Fee Coefficient

Get Market List

//Get Market List
{
    "data":[
    "BTC",
    "KCS",
    "USDS",  //SC has been changed to USDS
    "ALTS" //ALTS market includes ETH, NEO, TRX
  ]
}

   Request via this endpoint to get the transaction currency for the
   entire trading market.
   SC has been changed to USDS, but you can still use SC as a query
   parameterThe three markets of ETH, NEO and TRX are merged into the ALTS
   market. You can query the trading pairs of the ETH, NEO and TRX markets
   through the ALTS trading area.

HTTP REQUEST

   GET /api/v1/markets

Example

   GET /api/v1/markets

PARAMETERS

   N/A

Order Book

Get Part Order Book(aggregated)

{
    "sequence": "3262786978",
    "time": 1550653727731,
    "bids": [["6500.12", "0.45054140"],
             ["6500.11", "0.45054140"]],  //[price，size]
    "asks": [["6500.16", "0.57753524"],
             ["6500.15", "0.57753524"]]
}

   Request via this endpoint to get a list of open orders for a symbol.

   Level-2 order book includes all bids and asks (aggregated by price),
   this level returns only one size for each active price (as if there was
   only a single order for that price).

   Query via this endpoint and the system will return only part of the
   order book to you. If you request level2_20, the system will return you
   20 pieces of data (ask and bid data) on the order book. If you request
   level_100, the system will return 100 pieces of data (ask and bid data)
   on the order book to you. You are recommended to request via this
   endpoint as the system reponse would be faster and cosume less traffic.

   To maintain up-to-date Order Book, please use [391]Websocket
   incremental feed after retrieving the Level 2 snapshot.

HTTP REQUEST

   GET /api/v1/market/orderbook/level2_20
   GET /api/v1/market/orderbook/level2_100

Example

   GET /api/v1/market/orderbook/level2_20?symbol=BTC-USDT
   GET /api/v1/market/orderbook/level2_100?symbol=BTC-USDT

PARAMETERS

   Param   Type  Description
   symbol String [392]symbol

RESPONSES

    Field     Description
   sequence Sequence number
   time     Timestamp
   bids     bids
   asks     asks

Data Sort

   Asks: Sort price from low to high

   Bids: Sort price from high to low

Get Full Order Book(aggregated)

{
    "sequence": "3262786978",
    "time": 1550653727731,
    "bids": [["6500.12", "0.45054140"],
             ["6500.11", "0.45054140"]],  //[price，size]
    "asks": [["6500.16", "0.57753524"],
             ["6500.15", "0.57753524"]]
}

   Request via this endpoint to get the order book of the specified
   symbol.

   Level 2 order book includes all bids and asks (aggregated by price).
   This level returns only one aggregated size for each price (as if there
   was only one single order for that price).

   This API will return data with full depth.

   It is generally used by professional traders because it uses more
   server resources and traffic, and we have strict access frequency
   control.

   To maintain up-to-date Order Book, please use [393]Websocket
   incremental feed after retrieving the Level 2 snapshot.

HTTP REQUEST

   GET /api/v3/market/orderbook/level2(Recommend)

Example

   GET /api/v3/market/orderbook/level2?symbol=BTC-USDT

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 30
   times/3s.

PARAMETERS

   Param   Type  Description
   symbol String [394]symbol

RESPONSES

    Field     Description
   sequence Sequence number
   time     Timestamp
   bids     bids
   asks     asks

Data Sor

   Asks: Sort price from low to high

   Bids: Sort price from high to low

Histories

Get Trade Histories

[
    {
        "sequence": "1545896668571",
        "price": "0.07",                      //Filled price
        "size": "0.004",                      //Filled amount
        "side": "buy",                        //Filled side. The filled side is
set to the taker by default.
        "time": 1545904567062140823           //Transaction time
    },
    {
        "sequence": "1545896668578",
        "price": "0.054",
        "size": "0.066",
        "side": "buy",
        "time": 1545904581619888405
    }
]

   Request via this endpoint to get the trade history of the specified
   symbol.

HTTP REQUEST

   GET /api/v1/market/histories

Example

   GET /api/v1/market/histories?symbol=BTC-USDT

PARAMETERS

   Param   Type  Description
   symbol String [395]symbol

RESPONSES

    Field                           Description
   sequence Sequence number
   time     Transaction time
   price    Filled price
   size     Filled amount
   side     Filled side. The filled side is set to the taker by default

SIDE

   The trade side indicates the taker order side. A taker order is the
   order that was matched with orders opened on the order book.

Get Klines

[
    [
        "1545904980",             //Start time of the candle cycle
        "0.058",                  //opening price
        "0.049",                  //closing price
        "0.058",                  //highest price
        "0.049",                  //lowest price
        "0.018",                  //Transaction volume
        "0.000945"                //Transaction amount
    ],
    [
        "1545904920",
        "0.058",
        "0.072",
        "0.072",
        "0.058",
        "0.103",
        "0.006986"
    ]
]

   Request via this endpoint to get the kline of the specified symbol.
   Data are returned in grouped buckets based on requested type.
   Klines data may be incomplete. No data is published for intervals where
   there are no ticks.Klines should not be polled frequently. If you need
   real-time information, use the trade and book endpoints along with the
   websocket feed.

HTTP REQUEST

   GET /api/v1/market/candles

Example

   GET
   /api/v1/market/candles?type=1min&symbol=BTC-USDT&startAt=1566703297&end
   At=1566789757

PARAMETERS

   Param Type Description
   symbol String [396]symbol
   startAt long [Optional] Start time (second), default is 0
   endAt long [Optional] End time (second), default is 0
   type String Type of candlestick patterns: 1min, 3min, 5min, 15min,
   30min, 1hour, 2hour, 4hour, 6hour, 8hour, 12hour, 1day, 1week
   For each query, the system would return at most **1500** pieces of
   data. To obtain more data, please page the data by time.

RESPONSES

    Field            Description
   time     Start time of the candle cycle
   open     Opening price
   close    Closing price
   high     Highest price
   low      Lowest price
   volume   Transaction volume
   turnover Transaction amount

Currencies

Get Currencies

[
  {
    "currency": "CSP",
    "name": "CSP",
    "fullName": "Caspian",
    "precision": 8,
    "confirms": 12,
    "contractAddress": "0xa6446d655a0c34bc4f05042ee88170d056cbaf45",
    "withdrawalMinSize": "2000",
    "withdrawalMinFee": "1000",
    "isWithdrawEnabled": true,
    "isDepositEnabled": true,
    "isMarginEnabled": false,
    "isDebitEnabled": false
  },
  {
    "currency": "LOKI",
    "name": "OXEN",
    "fullName": "Oxen",
    "precision": 8,
    "confirms": 10,
    "contractAddress": "",
    "withdrawalMinSize": "2",
    "withdrawalMinFee": "2",
    "isWithdrawEnabled": true,
    "isDepositEnabled": true,
    "isMarginEnabled": false,
    "isDebitEnabled": true
  }
]

   Request via this endpoint to get the currency list.
   Not all currencies currently can be used for trading.

HTTP REQUEST

   GET /api/v1/currencies

Example

   GET /api/v1/currencies

RESPONSES

         Field                           Description
   currency          A unique currency code that will never change
   name              Currency name, will change after renaming
   fullName          Full name of a currency, will change after renaming
   precision         Currency precision
   confirms          Number of block confirmations
   contractAddress   Contract address
   withdrawalMinSize Minimum withdrawal amount
   withdrawalMinFee  Minimum fees charged for withdrawal
   isWithdrawEnabled Support withdrawal or not
   isDepositEnabled  Support deposit or not
   isMarginEnabled   Support margin or not
   isDebitEnabled    Support debit or not

   CURRENCY CODES

   Currency codes will conform to the ISO 4217 standard where possible.
   Currencies which have or had no representation in ISO 4217 may use a
   custom code.
   Code  Description
   BTC  Bitcoin
   ETH  Ethereum
   KCS  Kucoin Shares

   For a coin, the "currency" is a fixed value and works as the only
   recognized identity of the coin. As the "name", "fullnane" and
   "precision" of a coin are modifiable values, when the "name" of a coin
   is changed, you should use "currency" to get the coin.

   For example:

   The "currency" of XRB is "XRB", if the "name" of XRB is changed into
   "Nano", you should use "XRB" (the currency of XRB) to search the coin.

Get Currency Detail

{
  "currency": "BTC",
  "name": "BTC",
  "fullName": "Bitcoin",
  "precision": 8,
  "confirms": 2,
  "contractAddress": "",
  "withdrawalMinSize": "0.001",
  "withdrawalMinFee": "0.0006",
  "isWithdrawEnabled": true,
  "isDepositEnabled": true,
  "isMarginEnabled": true,
  "isDebitEnabled": true
}

   Request via this endpoint to get the currency details of a specified
   currency

HTTP REQUEST

   GET /api/v1/currencies/{currency}

Example

   GET /api/v1/currencies/BTC
   Details of the currency.

PARAMETERS

   Param Type Description
   currency String Path parameter. [397]Currency
   chain String [Optional] Support for querying the chain of currency,
   e.g. The available value for USDT are OMNI, ERC20, TRC20. This only
   apply for multi-chain currency, and there is no need for single chain
   currency.

RESPONSES

         Field                           Description
   currency          A unique currency code that will never change
   name              Currency name, will change after renaming
   fullName          Full name of a currency, will change after renaming
   precision         Currency precision
   confirms          Number of block confirmations
   contractAddress   Contract address
   withdrawalMinSize Minimum withdrawal amount
   withdrawalMinFee  Minimum fees charged for withdrawal
   isWithdrawEnabled Support withdrawal or not
   isDepositEnabled  Support deposit or not
   isMarginEnabled   Support margin or not
   isDebitEnabled    Support debit or not

Get Currency Detail(Recommend)

{
    "code": "200000",
    "data": {
        "currency": "BTC",
        "name": "BTC",
        "fullName": "Bitcoin",
        "precision": 8,
        "confirms": null,
        "contractAddress": null,
        "isMarginEnabled": true,
        "isDebitEnabled": true,
        "chains": [
            {
                "chainName": "BTC",
                "chain": "btc",
                "withdrawalMinSize": "0.001",
                "withdrawalMinFee": "0.0005",
                "isWithdrawEnabled": true,
                "isDepositEnabled": true,
                "confirms": 2,
                "contractAddress": ""
            },
            {
                "chainName": "KCC",
                "chain": "kcc",
                "withdrawalMinSize": "0.0008",
                "withdrawalMinFee": "0.00002",
                "isWithdrawEnabled": true,
                "isDepositEnabled": true,
                "confirms": 20,
                "contractAddress": ""
            },
            ...
        ]
    }
}

   Request via this endpoint to get the currency details of a specified
   currency

HTTP REQUEST

   GET /api/v2/currencies/{currency}

Example

   GET /api/v2/currencies/BTC
   Recommended for use

PARAMETERS

   Param Type Description
   currency String Path parameter. [398]Currency
   chain String [Optional] Support for querying the chain of currency,
   return the currency details of all chains by default.

RESPONSES

         Field                           Description
   currency          A unique currency code that will never change
   name              Currency name, will change after renaming
   fullName          Full name of a currency, will change after renaming
   precision         Currency precision
   confirms          Number of block confirmations
   contractAddress   Contract address
   withdrawalMinSize Minimum withdrawal amount
   chainName         chain name of currency
   chain             chain of currency
   withdrawalMinFee  Minimum fees charged for withdrawal
   isWithdrawEnabled Support withdrawal or not
   isDepositEnabled  Support deposit or not
   isMarginEnabled   Support margin or not
   isDebitEnabled    Support debit or not

Get Fiat Price

{
    "code": "200000",
    "data": {
        "BTC": "3911.28000000",
        "ETH": "144.55492453",
        "LTC": "48.45888179",
        "KCS": "0.45546856"
    }
}

   Request via this endpoint to get the fiat price of the currencies for
   the available trading pairs.

HTTP REQUEST

   GET /api/v1/prices

Example

   GET /api/v1/prices

PARAMETERS

   Param Type Description
   base String [Optional] Ticker symbol of a base currency,eg.USD,EUR.
   Default is USD
   currencies String [Optional] Comma-separated cryptocurrencies to be
   converted into fiat, e.g.: BTC,ETH, etc. Default to return the fiat
   price of all currencies.

Margin Trade

Margin Info

Get Mark Price

{
    "code": "200000",
    "data": {
        "symbol": "USDT-BTC",
        "timePoint": 1659930234000,
        "value": 0.0000429
    }
}

   Request via this endpoint to get the index price of the specified
   symbol.

HTTP REQUEST

   GET /api/v1/mark-price/{symbol}/current

Example

   GET /api/v1/mark-price/USDT-BTC/current

PARAMETERS

   Param   Type          Description
   symbol String Path parameter. [399]symbol

List of currently supported symbol

   USDT-BTC, ETH-BTC, LTC-BTC, EOS-BTC, XRP-BTC, KCS-BTC, DIA-BTC,
   VET-BTC, DASH-BTC, DOT-BTC, XTZ-BTC, ZEC-BTC, BSV-BTC, ADA-BTC,
   ATOM-BTC, LINK-BTC, LUNA-BTC, NEO-BTC, UNI-BTC, ETC-BTC, BNB-BTC,
   TRX-BTC, XLM-BTC, BCH-BTC, USDC-BTC, GRT-BTC, 1INCH-BTC,
   AAVE-BTC,SNX-BTC, API3-BTC, CRV-BTC, MIR-BTC, SUSHI-BTC, COMP-BTC,
   ZIL-BTC, YFI-BTC, OMG-BTC,XMR-BTC, WAVES-BTC, MKR-BTC, COTI-BTC,
   SXP-BTC, THETA-BTC, ZRX-BTC, DOGE-BTC, LRC-BTC, FIL-BTC, DAO-BTC,
   BTT-BTC, KSM-BTC, BAT-BTC, ROSE-BTC, CAKE-BTC, CRO-BTC, XEM-BTC,
   MASK-BTC, FTM-BTC, IOST-BTC, ALGO-BTC, DEGO-BTC, CHR-BTC, CHZ-BTC,
   MANA-BTC, ENJ-BTC, IOST-BTC, ANKR-BTC, ORN-BTC, SAND-BTC, VELO-BTC,
   AVAX-BTC, DODO-BTC, WIN-BTC, ONE-BTC, SHIB-BTC, ICP-BTC, MATIC-BTC,
   CKB-BTC, SOL-BTC, VRA-BTC, DYDX-BTC, ENS-BTC, NEAR-BTC, SLP-BTC,
   AXS-BTC, TLM-BTC, ALICE-BTC,IOTX-BTC, QNT-BTC, SUPER-BTC, HABR-BTC,
   RUNE-BTC, EGLD-BTC, AR-BTC, RNDR-BTC, LTO-BTC, YGG-BTC

RESPONSES

     Field      Description
   symbol    symbol
   timePoint Time (millisecond)
   value     Mark price

Get Margin Configuration Info

{
    "code": "200000",
    "data": {
        "currencyList": [
            "XEM",
            "MATIC",
            "VRA",
            ...
        ],
        "maxLeverage": 5,
        "warningDebtRatio": "0.95",
        "liqDebtRatio": "0.97"
    }
}

   Request via this endpoint to get the configure info of the margin.

HTTP REQUEST

   GET /api/v1/margin/config

Example

   GET /api/v1/margin/config

PARAMETERS

   N/A

RESPONSES

        Field                         Description
   currencyList     Available currencies for margin trade
   warningDebtRatio The warning debt ratio of the forced liquidation
   liqDebtRatio     The debt ratio of the forced liquidation
   maxLeverage      Max leverage available

Get Margin Account

{
    "code": "200000",
    "data": {
        "debtRatio": "0",
        "accounts": [
            {
                "currency": "KCS",
                "totalBalance": "0.01",
                "availableBalance": "0.01",
                "holdBalance": "0",
                "liability": "0",
                "maxBorrowSize": "0"
            },
            {
                "currency": "USDT",
                "totalBalance": "0",
                "availableBalance": "0",
                "holdBalance": "0",
                "liability": "0",
                "maxBorrowSize": "0"
            },
            ...
        ]
    }
}

   Request via this endpoint to get the info of the margin account.

HTTP REQUEST

   GET /api/v1/margin/account

Example

   GET /api/v1/margin/account

API KEY PERMISSIONS

   This endpoint requires the General permission.

RESPONSES

        Field                Description
   accounts         Margin account list
   debtRatio        Debt ratio
   currency         Currency
   totalBalance     Total funds in the account
   availableBalance Available funds in the account
   holdBalance      Funds on hold in the account
   liability        Total liabilities
   maxBorrowSize    Available size to borrow

Query the cross/isolated margin risk limit

// CROSS MARGIN RESPONSES
{
    "code": "200000",
    "data": [
        {
            "currency": "BTC",
            "borrowMaxAmount": "140",
            "buyMaxAmount": "60",
            "holdMaxAmount": "522.8",
            "precision": 8
        },
        {
            "currency": "USDT",
            "borrowMaxAmount": "2000000",
            "buyMaxAmount": "10000000",
            "holdMaxAmount": "15000000",
            "precision": 8
        },
        {
            "currency": "ETH",
            "borrowMaxAmount": "1000",
            "buyMaxAmount": "600",
            "holdMaxAmount": "3737.1",
            "precision": 8
        },
        ...
    ]
}

// ISOLATED MARGIN RESPONSES
{
    "code": "200000",
    "data": [
        {
            "symbol": "ETH-USDT",
            "baseMaxBorrowAmount": "200",
            "quoteMaxBorrowAmount": "3000000",
            "baseMaxBuyAmount": "210",
            "quoteMaxBuyAmount": "3300000",
            "baseMaxHoldAmount": "3737.1",
            "quoteMaxHoldAmount": "5000000",
            "basePrecision": 8,
            "quotePrecision": 8
        },
        {
            "symbol": "BTC-USDT",
            "baseMaxBorrowAmount": "20",
            "quoteMaxBorrowAmount": "3000000",
            "baseMaxBuyAmount": "25",
            "quoteMaxBuyAmount": "3300000",
            "baseMaxHoldAmount": "522.8",
            "quoteMaxHoldAmount": "5000000",
            "basePrecision": 8,
            "quotePrecision": 8
        },
        ...
    ]
}

   This endpoint can query the cross/isolated margin risk limit.

HTTP REQUEST

   GET /api/v1/risk/limit/strategy

Example

   GET /api/v1/risk/limit/strategy?marginModel=cross

API KEY PERMISSIONS

   This endpoint requires the General permission.

REQUEST RATE LIMIT

   This API is restricted for each account, the request rate limit is 1
   times/3s.

PARAMETERS

   Param Type Description
   marginModel String The type of marginModel : cross（cross margin）,
   isolated (isolated margin). Default is cross.

CROSS MARGIN RESPONSES

        Field           Description
   currency        Currency
   borrowMaxAmount Maximum borrow amount
   buyMaxAmount    Maximum buy amount
   holdMaxAmount   Maximum hold amount
   precision       Precision

ISOLATED MARGIN RESPONSES

          Field                          Description
   symbol               The valid trading symbol code. e.g: EOS-USDC.
   baseMaxBorrowAmount  Maximum borrowing amount of base currency
   quoteMaxBorrowAmount Maximum borrowing amount of quote currency
   baseMaxBuyAmount     Maximum buy amount of base currency
   quoteMaxBuyAmount    Maximum buy amount of quote currency
   baseMaxHoldAmount    Maximum holding amount of base currency
   quoteMaxHoldAmount   Maximum holding amount of quote currency
   basePrecision        Base currency precision
   quotePrecision       Quote currency precision

Borrow & Lend

Post Borrow Order

{
    "orderId": "a2111213",
    "currency": "USDT"
}

HTTP REQUEST

   POST /api/v1/margin/borrow

Example

   POST /api/v1/margin/borrow

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

   Param Type Description
   currency String Currency to Borrow
   type String Type: FOK, IOC
   size BigDecimal Total size
   maxRate BigDecimal [Optional] The max interest rate. All interest rates
   are acceptable if this field is left empty.
   term String [Optional] Term (Unit: Day). All terms are acceptable if
   this field is left empty. Please note to separate the terms via comma.
   For example, 7,14,28.
   Available terms currently supported: 7, 14, 28

RESPONSES

    Field      Description
   orderId  Borrow order ID
   currency Currency to borrow

Get Borrow Order

{
    "orderId": "a2111213",
    "currency": "USDT",
    "size": "1.009",
    "filled": 1.009,
    "matchList": [
      {
        "currency": "USDT",
        "dailyIntRate": "0.001",
        "size": "12.9",
        "term": 7,
        "timestamp": "1544657947759",
        "tradeId": "1212331"
      }
    ],
    "status": "DONE"
  }


   Request via this endpoint to get the info of the borrow order through
   the orderId retrieved from [400]Post Borrow Order .

HTTP REQUEST

   GET /api/v1/margin/borrow

Example

   GET /api/v1/margin/borrow?orderId=123456789

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param   Type    Description
   orderId String Borrow order ID

RESPONSES

      Field                     Description
   orderId      Borrow order ID
   currency     Currency
   size         Total size
   filled       Size executed
   status       Status. DONE (Canceled or Filled),PROCESSING
   matchList    Execution details
   tradeId      Trade ID
   dailyIntRate Daily interest rate
   term         Term
   timestamp    Borrow time

Get Repay Record

{
    "currentPage": 0,
    "pageSize": 0,
    "totalNum": 0,
    "totalPage": 0,
    "items": [
        {
            "tradeId": "1231141",
            "currency": "USDT",
            "accruedInterest": "0.22121",
            "dailyIntRate": "0.0021",
            "liability": "1.32121",
            "maturityTime": "1544657947759",
            "principal": "1.22121",
            "repaidSize": "0",
            "term": 7,
            "createdAt": "1544657947759"
        }
    ]
  }

HTTP REQUEST

   GET /api/v1/margin/borrow/outstanding

Example

   GET /api/v1/margin/borrow/outstanding

API KEY PERMISSIONS

   This endpoint requires the "General" permission.
   This request is paginated.

PARAMETERS

   Param Type Description
   currency String [Optional] Currency. All currencies will be quried if
   this field is not required.

RESPONSES

        Field               Description
   tradeId         Trade ID
   currency        Currency
   liability       Total liabilities
   principal       Outstanding principal to repay
   accruedInterest Accrued interest
   createdAt       Execution time
   maturityTime    Maturity time
   term            Term
   repaidSize      Repaid size
   dailyIntRate    Daily interest rate

Get Repayment Record

{
    "pageSize": 0,
    "totalNum": 0,
    "totalPage": 0,
    "currentPage": 0,
    "items": [
        {
            "tradeId": "1231141",
            "currency": "USDT",
            "dailyIntRate": "0.0021",
            "interest": "0.22121",
            "principal": "1.22121",
            "repaidSize": "0",
            "repayTime": "1544657947759",
            "term": 7
        }
    ]
  }

HTTP REQUEST

   GET /api/v1/margin/borrow/repaid

Example

   GET /api/v1/margin/borrow/repaid

API KEY PERMISSIONS

   This endpoint requires the "General" permission.
   This request is paginated.

PARAMETERS

   Param Type Description
   currency String [Optional] Currency. All currencies will be quried if
   this field is not required.

RESPONSES

      Field         Description
   tradeId      Trade ID
   currency     Currency
   interest     Interest
   principal    Principal
   repayTime    Repayment time
   term         Term
   repaidSize   Repaid size
   dailyIntRate Daily interest rate

One-Click Repayment

{
  "code": "200000",
  "data": null
}

HTTP REQUEST

   POST /api/v1/margin/repay/all

Example

   POST /api/v1/margin/repay/all

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

   Param Type Description
   currency String Currency
   sequence String Repayment strategy. RECENTLY_EXPIRE_FIRST: Time
   priority, namely to repay the loans of the nearest maturity time first,
   HIGHEST_RATE_FIRST: Rate Priority: Repay the loans of the highest
   interest rate first.
   size BigDecimal Repayment size

RESPONSES

   A successful repayment response is indicated by an HTTP status code 200
   and system code 200000. If the system returns other code, it means the
   repayment fails.

Repay a Single Order

{
  "code": "200000",
  "data": null
}

   Request via this endpoint to repay a single order.

HTTP REQUEST

   POST /api/v1/margin/repay/single

Example

   POST /api/v1/margin/repay/single

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param      Type     Description
   currency String     Currncy
   tradeId  String     Trade ID
   size     BigDecimal Repayment size

RESPONSES

   A successful repayment response is indicated by an HTTP status code 200
   and system code 200000. If the system returns other code, it means the
   repayment fails.

Post Lend Order

{
    "orderId": "5da5a4f0f943c040c2f8501e"
}

   Request via this endpoint to post lend order.

   Please ensure that you have sufficient funds in your Main Account
   before you post the order. Once the post succeed, the funds posted will
   be frozen until the order is succssfuly lent out or cancelled.

HTTP REQUEST

   POST /api/v1/margin/lend

Example

   POST /api/v1/margin/lend

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

      Param      Type                Description
   currency     String Currency to lend
   size         String Total size
   dailyIntRate String Daily interest rate. e.g. 0.002 is 0.2%
   term         int    Term (Unit: Day)

RESPONSES

    Field   Description
   orderId Lend order ID

Cancel Lend Order

{
  "code": "200000",
  "data": null
}

   Request via this endpoint to cancel lend order.

HTTP REQUEST

   DELETE /api/v1/margin/lend/{orderId}

Example

   DELETE /api/v1/margin/lend/5d9f133ef943c0882ca37bc8

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param   Type   Description
   orderId String Lend order ID

Set Auto-lend

{
  "code": "200000",
  "data": null
}

   Request via this endpoint to set up the automatic lending for a
   specified currency.

HTTP REQUEST

   POST /api/v1/margin/toggle-auto-lend

Example

   POST /api/v1/margin/toggle-auto-lend

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

   Param Type Description
   currency String Currency
   isEnable boolean Auto-lend enabled or not
   retainSize String Reserved size in main account. Mandatory when
   isEnable is true.
   dailyIntRate String acceptable min. day rate, 0.002 is 0.2%. Mandatory
   when isEnable is true.
   term int Term (Unit: Day). Mandatory when isEnable is true.

Advanced Description

dailyIntRate

   When the priority interest rate is higher than the acceptable min. day
   rate, the system will place lending orders at the rate of the former
   one. The priority interest rate is the optimal market rate for all
   pending orders of the selected lending period, orders with this
   interest rate will be prioritized for auto-lending.

   When the priority interest rate is lower than the acceptable min. day
   rate, the system will place lending orders at the rate of the latter
   one.

Get Active Order

{
      "currentPage": 1,
      "pageSize": 1,
      "totalNum": 1,
      "totalPage": 1,
      "items": [
        {
            "orderId": "5da59f5ef943c033b2b643e4",
            "currency": "BTC",
            "size": "0.51",
            "filledSize": "0",
            "dailyIntRate": "0.0001",
            "term": 7,
            "createdAt": 1571135326913
        }
    ]
}

   Request via this endpoint to get active lend orders. Items are
   paginated and sorted to show the latest first. See the Pagination
   section for retrieving additional entries after the first page. The max
   pageSize is 100.

   Active lend orders include orders unfilled, partially filled and
   uncanceled.

HTTP REQUEST

   GET /api/v1/margin/lend/active

Example

   GET /api/v1/margin/lend/active?currency=BTC&currentPage=1&pageSize=50

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param    Type      Description
   currency String [Optional] Currency

RESPONSES

      Field                   Description
   orderId      Lend order ID
   currency     Currency
   size         Total size
   filledSize   Size executed
   dailyIntRate Daily interest rate. e.g. 0.002 is 0.2%
   term         Term (Unit: Day)
   createdAt    Time of the event (millisecond)

Get Lent History

{
    "currentPage": 1,
    "pageSize": 1,
    "totalNum": 1,
    "totalPage": 1,
    "items": [
        {
            "orderId": "5da59f5bf943c033b2b643da",
            "currency": "BTC",
            "size": "0.51",
            "filledSize": "0.51",
            "dailyIntRate": "0.0001",
            "term": 7,
            "status": "FILLED",
            "createdAt": 1571135323984
        }
    ]
}

   Request via this endpoint to get lent orders . Items are paginated and
   sorted to show the latest first. See the Pagination section for
   retrieving additional entries after the first page. The max pageSize is
   100.

   Lent order history involves orders canceled or fully filled.

HTTP REQUEST

   GET /api/v1/margin/lend/done

Example

   GET /api/v1/margin/lend/done?currency=BTC&currentPage=1&pageSize=50

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param    Type      Description
   currency String [Optional] Currency

RESPONSES

      Field                            Description
   orderId      Lend order ID
   currency     Currency
   size         Total size
   filledSize   Size executed
   dailyIntRate Daily interest rate. e.g. 0.002 is 0.2%
   term         Term (Unit: Day)
   createdAt    Time of the event (millisecond)
   status       Order status: FILLED -- Fully filled, CANCELED -- Canceled

Get Active Lend Order List

{
    "currentPage": 1,
    "pageSize": 1,
    "totalNum": 1,
    "totalPage": 1,
    "items": [
        {
            "tradeId": "5da6dba0f943c0c81f5d5db5",
            "currency": "BTC",
            "size": "0.51",
            "accruedInterest": "0",
            "repaid": "0.10999968",
            "dailyIntRate": "0.0001",
            "term": 14,
            "maturityTime": 1572425888958
        }
    ]
}

   Request via this endpoint to get the outstanding lend order list. Items
   are paginated and sorted to show the latest first. See the Pagination
   section for retrieving additional entries after the first page. The max
   pageSize is 100.

   When a lending order is executed, the system will generate the lending
   history. The outstanding lend orders includes orders unrepaid and
   partially repaid.

HTTP REQUEST

   GET /api/v1/margin/lend/trade/unsettled

Example

   GET
   /api/v1/margin/lend/trade/unsettled?currency=BTC&currentPage=1&pageSize
   =50

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param    Type      Description
   currency String [Optional] Currency

RESPONSES

   Field Description
   tradeId Trade ID
   currency Currency
   size Size executed
   accruedInterest Accrued interest. This value will decrease when
   borrower repays the interest.
   repaid Repaid size
   dailyIntRate Daily interest rate. e.g. 0.002 is 0.2%
   term Term (Unit: Day)
   maturityTime Maturity time (millisecond)

Get Settled Lend Order History

{
    "currentPage": 1,
    "pageSize": 1,
    "totalNum": 1,
    "totalPage": 1,
    "items": [
        {
            "tradeId": "5da59fe6f943c033b2b6440b",
            "currency": "BTC",
            "size": "0.51",
            "interest": "0.00004899",
            "repaid": "0.510041641",
            "dailyIntRate": "0.0001",
            "term": 7,
            "settledAt": 1571216254767,
            "note": "The account of the borrowers reached a negative balance, an
d the system has supplemented the loss via the insurance fund. Deposit funds: 0.
51."
        }
    ]
}

   Request via this endpoint to get the settled lend orders . Items are
   paginated and sorted to show the latest first. See the Pagination
   section for retrieving additional entries after the first page. The max
   pageSize is 100.

   The settled lend orders include orders repaid fully or partially before
   or at the maturity time.

HTTP REQUEST

   GET /api/v1/margin/lend/trade/settled

Example

   GET
   /api/v1/margin/lend/trade/settled?currency=BTC&currentPage=1&pageSize=5
   0

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param    Type      Description
   currency String [Optional] Currency

RESPONSES

   Field Description
   tradeId Trade ID
   currency Currency
   size Size executed
   interest Total interest
   repaid Repaid size
   dailyIntRate Daily interest rate. e.g. 0.002 is 0.2%
   term Term (Unit: Day)
   settledAt Settlement time (millisecond)
   note Note. To note the account of the borrower reached a negative
   balance, and whether the insurance fund is repaid.

Get Account Lend Record

[
    {
        "currency": "BTC",
        "outstanding": "1.02",
        "filledSize": "0.91000213",
        "accruedInterest": "0.00000213",
        "realizedProfit": "0.000045261",
        "isAutoLend": false
    }
]

   Request via this endpoint to get the lending history of the main
   account.

HTTP REQUEST

   GET /api/v1/margin/lend/assets

Example

   GET /api/v1/margin/lend/assets?currency=BTC

API KEY PERMISSIONS

   This endpoint requires the "Trade" permission.

PARAMETERS

    Param    Type      Description
   currency String [Optional] Currency

RESPONSES

        Field            Description
   currency        Currency
   outstanding     Outstanding size
   filledSize      Size executed
   accruedInterest Accrued Interest
   realizedProfit  Realized profit
   isAutoLend      Auto-lend enabled or not

Lending Market Data

[
    {
        "dailyIntRate": "0.0001",
        "term": 7,
        "size": "1.02"
    }
]

   Request via this endpoint to get the lending market data. The returned
   value is sorted based on the descending sequence of the daily interest
   rate and terms.

HTTP REQUEST

   GET /api/v1/margin/market

Example

   GET /api/v1/margin/market?currency=BTC&term=7

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

    Param    Type          Description
   currency String Currency
   term     int    [Optional] Term (Unit: Day)

RESPONSES

      Field                   Description
   dailyIntRate Daily interest rate. e.g. 0.002 is 0.2%
   term         Term (Unit: Day)
   size         Total size

Margin Trade Data

[
    {
        "tradeId": "5da6dba0f943c0c81f5d5db5",
        "currency": "BTC",
        "size": "0.51",
        "dailyIntRate": "0.0001",
        "term": 14,
        "timestamp": 1571216288958989641
    }
]

   Request via this endpoint to get the last 300 fills in the lending and
   borrowing market. The returned value is sorted based on the descending
   sequence of the order execution time.

HTTP REQUEST

   GET /api/v1/margin/trade/last

Example

   GET /api/v1/margin/trade/last?currency=BTC

API KEY PERMISSIONS

   This endpoint requires the "General" permission.

PARAMETERS

    Param    Type  Description
   currency String Currency

RESPONSES

      Field                   Description
   tradeId      Trade ID
   currency     Currency
   size         Executed size
   dailyIntRate Daily interest rate. e.g. 0.002 is 0.2%
   term         Term (Unit: Day)
   timestamp    Time of execution in nanosecond

Isolated Margin

Query Isolated Margin Trading Pair Configuration

{
    "code":"200000",
    "data": [
        {
            "symbol": "EOS-USDC",
            "symbolName": "EOS-USDC",
            "baseCurrency": "EOS",
            "quoteCurrency": "USDC",
            "maxLeverage": 10,
            "flDebtRatio": "0.97",
            "tradeEnable": true,
            "autoRenewMaxDebtRatio": "0.96",
            "baseBorrowEnable": true,
            "quoteBorrowEnable": true,
            "baseTransferInEnable": true,
            "quoteTransferInEnable": true
        },
        {
            "symbol": "MANA-USDT",
            "symbolName": "MANA-USDT",
            "baseCurrency": "MANA",
            "quoteCurrency": "USDT",
            "maxLeverage": 10,
            "flDebtRatio": "0.9",
            "tradeEnable": true,
            "autoRenewMaxDebtRatio": "0.96",
            "baseBorrowEnable": true,
            "quoteBorrowEnable": true,
            "baseTransferInEnable": true,
            "quoteTransferInEnable": true
        }
    ]
}

   This API endpoint returns the current isolated margin trading pair
   configuration.

HTTP Request

   GET /api/v1/isolated/symbols

API KEY PERMISSIONS

   This endpoint requires the General permissions

PARAMETERS

   N/A

RESPONSES

   Field Description
   symbol The trading pair code
   baseCurrency Base currency type
   quoteCurrency Quote coin
   symbolName Trading pair name
   maxLeverage Maximum leverage
   flDebtRatio Liquidation debt ratio
   tradeEnable Trade switch
   autoRenewMaxDebtRatio During automatic renewal of the max debt ratio,
   the loan will only be renewed if it is lower than the debt ratio, with
   partial liquidation triggered for repayment if the debt ratio is in
   excess
   baseBorrowEnable base coin type borrow switch
   quoteBorrowEnable quote coin type borrow switch
   baseTransferInEnable base coin type transfer switch
   quoteTransferInEnable quote coin type transfer switch

Query Isolated Margin Account Info

{
    "code":"200000",
    "data": {
        "totalConversionBalance": "3.4939947",
        "liabilityConversionBalance": "0.00239066",
        "assets": [
            {
                "symbol": "MANA-USDT",
                "status": "CLEAR",
                "debtRatio": "0",
                "baseAsset": {
                    "currency": "MANA",
                    "totalBalance": "0",
                    "holdBalance": "0",
                    "availableBalance": "0",
                    "liability": "0",
                    "interest": "0",
                    "borrowableAmount": "0"
                },
                "quoteAsset": {
                    "currency": "USDT",
                    "totalBalance": "0",
                    "holdBalance": "0",
                    "availableBalance": "0",
                    "liability": "0",
                    "interest": "0",
                    "borrowableAmount": "0"
                }
            },
            {
                "symbol": "EOS-USDC",
                "status": "CLEAR",
                "debtRatio": "0",
                "baseAsset": {
                    "currency": "EOS",
                    "totalBalance": "0",
                    "holdBalance": "0",
                    "availableBalance": "0",
                    "liability": "0",
                    "interest": "0",
                    "borrowableAmount": "0"
                },
                "quoteAsset": {
                    "currency": "USDC",
                    "totalBalance": "0",
                    "holdBalance": "0",
                    "availableBalance": "0",
                    "liability": "0",
                    "interest": "0",
                    "borrowableAmount": "0"
                }
            }
        ]
    }
}

   This API endpoint returns all isolated margin accounts of the current
   user.

HTTP Request

   GET /api/v1/isolated/accounts

API KEY PERMISSIONS

   This endpoint requires the General permissions

PARAMETERS

   Param Type Mandatory Description
   balanceCurrency String No The pricing coin, currently only supports
   USDT, KCS, and BTC. Defaults to BTC if no value is passed.

RESPONSES

   Field Description
   totalConversionBalance The total balance of the isolated margin account
   (in the specified coin)
   liabilityConversionBalance Total liabilities of the isolated margin
   account (in the specified coin)
   assets Account list
   assets.symbol Trading pairs, with each trading pair indicating a
   position
   assets.status The position status: Existing liabilities-DEBT, No
   liabilities-CLEAR, Bankrupcy (after position enters a negative
   balance)-BANKRUPTCY, Existing borrowings-IN_BORROW, Existing
   repayments-IN_REPAY, Under liquidation-IN_LIQUIDATION, Under
   auto-renewal assets-IN_AUTO_RENEW .
   debtRatio Debt ratio
   assets.baseAsset base coin type asset info
   assets.quoteAsset quote coin type asset info
   currency Coin type Code
   totalBalance Current coin type asset amount
   holdBalance Current coin type frozen
   availableBalance The available balance (available assets - frozen
   assets)

Query Single Isolated Margin Account Info

{
    "code": "200000",
    "data": {
        "symbol": "MANA-USDT",
        "status": "CLEAR",
        "debtRatio": "0",
        "baseAsset": {
            "currency": "MANA",
            "totalBalance": "0",
            "holdBalance": "0",
            "availableBalance": "0",
            "liability": "0",
            "interest": "0",
            "borrowableAmount": "0"
        },
        "quoteAsset": {
            "currency": "USDT",
            "totalBalance": "0",
            "holdBalance": "0",
            "availableBalance": "0",
            "liability": "0",
            "interest": "0",
            "borrowableAmount": "0"
        }
    }
}

   This API endpoint returns the info on a single isolated margin account
   of the current user.

HTTP Request

   GET /api/v1/isolated/account/{symbol}

API KEY PERMISSIONS

   This endpoint requires the General permissions

PARAMETERS

   Param   Type  Mandatory         Description
   symbol String Yes       Trading pair, e.g.: BTC-USDT

RESPONSES

   Field Description
   symbol Trading pair
   status The position status: Existing liabilities-DEBT, No
   liabilities-CLEAR, Bankrupcy (after position enters a negative
   balance)-BANKRUPTCY, Existing borrowings-IN_BORROW, Existing
   repayments-IN_REPAY, Under liquidation-IN_LIQUIDATION, Under
   auto-renewal-IN_AUTO_RENEW (permissions per state)
   quoteAsset quote coin type asset info
   currency Coin type Code
   totalBalance Current coin type asset amount
   availableBalance Amount of current coin available
   holdBalance Amount of current coin frozen
   liability The principal of the of current coin liability (the
   outstanding principal)
   interest The interest of the liability of the current coin (the
   outstanding interest)
   borrowableAmount The borrowable amount

Isolated Margin Borrowing

{
    "code": "200000",
    "data": {
        "orderId": "62baad0aaafc8000014042b3",
        "currency": "USDT",
        "actualSize": "10"
    }
}

   This API endpoint initiates isolated margin borrowing.

HTTP Request

   POST /api/v1/isolated/borrow

API KEY PERMISSIONS

   This endpoint requires the Trade permissions

PARAMETERS

   Param Type Mandatory Description
   symbol String Yes Trading pair, e.g.: BTC-USDT
   currency String Yes Borrowed coin type
   size BigDecimal Yes Borrowed amount
   borrowStrategy String Yes Borrowing strategy: FOK, IOC
   maxRate BigDecimal No Max interest rate, defaults to all interest rates
   if left blank
   period String No The term in days. Defaults to all terms if left blank.
   7,14,28

RESPONSES

        Field            Description
   orderId          Borrow order ID
   currency         Borrowed coin type
   actualBorrowSize Actual borrowed amount

Query Outstanding Repayment Records

{
    "success": true,
    "code": "200",
    "msg": "success",
    "retry": false,
    "data": {
        "currentPage": 1,
        "pageSize": 10,
        "totalNum": 6,
        "totalPage": 1,
        "items": [
            {
                "loanId": "62aec83bb51e6f000169a3f0",
                "symbol": "BTC-USDT",
                "currency": "USDT",
                "liabilityBalance": "10.02000016",
                "principalTotal": "10",
                "interestBalance": "0.02000016",
                "createdAt": 1655621691869,
                "maturityTime": 1656226491869,
                "period": 7,
                "repaidSize": "0",
                "dailyInterestRate": "0.001"
            },
            {
                "loanId": "62aa94e52a3fbb0001277fd1",
                "symbol": "BTC-USDT",
                "currency": "USDT",
                "liabilityBalance": "10.05166708",
                "principalTotal": "10",
                "interestBalance": "0.05166708",
                "createdAt": 1655346405447,
                "maturityTime": 1655951205447,
                "period": 7,
                "repaidSize": "0",
                "dailyInterestRate": "0.001"
            }
        ]
    }
}

   This API endpoint is used to query the outstanding repayment records of
   isolated margin positions.

HTTP Request

   GET /api/v1/isolated/borrow/outstanding

Example

   GET /api/v1/isolated/borrow/outstanding?symbol=BTC-USDT&currency=USDT

API KEY PERMISSIONS

   This endpoint requires the General permissions

PARAMETERS

      Param     Type  Mandatory         Description
   symbol      String No        Trading pair, e.g.: BTC-USDT
   currency    String No        Coin type
   pageSize    int    No        Page size [10-50]
   currentPage int    No        Current page number [1-100]

RESPONSES

         Field             Description
   loanId            Trade id
   symbol            Trading pair
   currency          Coin type
   liabilityBalance  Remaining liabilities
   principalTotal    Principal
   interestBalance   Accrued interest
   createdAt         Trade time, timestamp
   maturityTime      Maturity date, timestamp
   period            Term
   repaidSize        Amount repaid
   dailyInterestRate Daily interest

Query Repayment Records

{
    "code": "200000",
    "data": {
        "currentPage": 1,
        "pageSize": 10,
        "totalNum": 30,
        "totalPage": 3,
        "items": [
            {
                "loanId": "628df5787818320001c79c8b",
                "symbol": "BTC-USDT",
                "currency": "USDT",
                "principalTotal": "10",
                "interestBalance": "0.07000056",
                "repaidSize": "10.07000056",
                "createdAt": 1653470584859,
                "period": 7,
                "dailyInterestRate": "0.001",
                "repayFinishAt": 1654075506416
            },
            {
                "loanId": "628c570f7818320001d52b69",
                "symbol": "BTC-USDT",
                "currency": "USDT",
                "principalTotal": "11",
                "interestBalance": "0.07699944",
                "repaidSize": "11.07699944",
                "createdAt": 1653364495783,
                "period": 7,
                "dailyInterestRate": "0.001",
                "repayFinishAt": 1653969432251
            }
        ]
    }
}

   This API endpoint is used to query the repayment records of isolated
   margin positions.

HTTP Request

   GET /api/v1/isolated/borrow/repaid

Example

   GET /api/v1/isolated/borrow/repaid?symbol=BTC-USDT&currency=USDT

API KEY PERMISSIONS

   This endpoint requires the General permissions

PARAMETERS

      Param     Type  Mandatory         Description
   symbol      String No        Trading pair, e.g.: BTC-USDT
   currency    String No        Coin type
   pageSize    int    No        Page size [10-50]
   currentPage int    No        Current page number [1-100]

RESPONSES

         Field            Description
   loanId            Trade id
   symbol            Trading pair
   currency          Coin type
   principalTotal    Principal
   interestBalance   Accrued interest
   repaidSize        Amount repaid
   createdAt         Trade time, timestamp
   period            Term
   dailyInterestRate Daily interest
   repayFinishAt     Repayment time

Quick Repayment

//request
{
    "currency": "BTC",
    "seqStrategy": "HIGHEST_RATE_FIRST",
    "size": 1.9,
    "symbol": "BTC-USDT"
}

//response
{
    "code": "200000",
    "data": null
}

   This API endpoint is used to initiate quick repayment for isolated
   margin accounts

HTTP Request

   POST /api/v1/isolated/repay/all

API KEY PERMISSIONS

   This endpoint requires the Trade permissions

PARAMETERS

   Param Type Mandatory Description
   symbol String Yes Trading pair, e.g.: BTC-USDT
   currency String Yes Repayment coin type
   size BigDecimal Yes Repayment amount
   seqStrategy String Yes Repayment sequence strategy,
   RECENTLY_EXPIRE_FIRST: Maturity date priority (the loan with the
   closest maturity is repaid first), HIGHEST_RATE_FIRST: Interest rate
   priority (the loan with the highest interest rate is repaid first)

RESPONSES

   When the system returns HTTP status code 200 and system code 200000, it
   indicates that the response is successful.

Single Repayment

//request
{
    "currency": "BTC",
    "loanId": 8765321,
    "size": 1.9,
    "symbol": "BTC-USDT"
}

//response
{
    "code": "200000",
    "data": null
}

   This API endpoint is used to initiate quick repayment for single margin
   accounts

HTTP Request

   POST /api/v1/isolated/repay/single

API KEY PERMISSIONS

   This endpoint requires the Trade permissions

PARAMETERS

   Param Type Mandatory Description
   symbol String Yes Trading pair, e.g.: BTC-USDT
   currency String Yes Repayment coin type
   size BigDecimal Yes Repayment amount
   loanId String Yes Trade order number; when this field is configured,
   the sequence strategy is invalidated

RESPONSES

   When the system returns HTTP status code 200 and system code 200000, it
   indicates that the response is successful.

Others

Server Time

{
    "code":"200000",
    "msg":"success",
    "data":1546837113087
}

   Get the server time.

HTTP REQUEST

   GET /api/v1/timestamp

Example

   GET /api/v1/timestamp

PARAMETERS

   N/A

Service Status

{
  "code": "200000",
  "data": {

      "status": "open",                //open, close, cancelonly
      "msg":  "upgrade match engine"   //remark for operation
    }
}

   Get the service status

HTTP REQUEST

   GET /api/v1/status

Example

   GET /api/v1/status

PARAMETERS

   N/A

RESPONSES

   Field                  Description
   status Status of service: open, close or cancelonly
   msg    Remark for operation

Websocket Feed

   While there is a strict access frequency control for REST API, we
   highly recommend that API users utilize Websocket to get the real-time
   data.
   The recommended way is to just create a websocket connection and
   subscribe to multiple channels.

Apply connect token

{
    "code": "200000",
    "data": {

        "instanceServers": [
            {
                "endpoint": "wss://push1-v2.kucoin.com/endpoint",
                "protocol": "websocket",
                "encrypt": true,
                "pingInterval": 50000,
                "pingTimeout": 10000
            }
        ],
        "token": "vYNlCtbz4XNJ1QncwWilJnBtmmfe4geLQDUA62kKJsDChc6I4bRDQc73JfIrlF
aVYIAE0Gv2--MROnLAgjVsWkcDq_MuG7qV7EktfCEIphiqnlfpQn4Ybg==.IoORVxR2LmKV7_maOR9xO
g=="
    }
}

   You need to apply for one of the two tokens below to create a websocket
   connection.

Public token (No authentication required):

   If you only use public channels (e.g. all public market data), please
   make request as follows to obtain the server list and temporary public
   token:

HTTP REQUEST

   POST /api/v1/bullet-public

Private channels (Authentication request required):

   For private channels and messages (e.g. account balance notice), please
   make request as follows after authorization to obtain the server list
   and authorized token.

HTTP REQUEST

   POST /api/v1/bullet-private

Response

   Field Description
   endpoint Websocket server address for establishing connection
   protocol Protocol supported
   encrypt Indicate whether SSL encryption is used
   pingInterval Recommended to send ping interval in millisecond
   pingTimeout After such a long time(millisecond), if you do not receive
   pong, it will be considered as disconnected.
   token token

Create connection

var socket = new WebSocket("wss://push1-v2.kucoin.com/endpoint?token=xxx&[connec
tId=xxxxx]");

   When the connection is successfully established, the system will send a
   welcome message.
   Only when the welcome message is received will the connection be
   available

   connectId: the connection id, a unique value taken from the client
   side. Both the id of the welcome message and the id of the error
   message are connectId.

   If you only want to receive private messages of the specified topic,
   please set privateChannel to true when subscribing.
{
    "id":"hQvf8jkno",
    "type":"welcome"
}

Ping

{
    "id":"1545910590801",
    "type":"ping"
}

   To prevent the TCP link being disconnected by the server, the client
   side needs to send ping messages every pingInterval time to the server
   to keep alive the link.

   After the ping message is sent to the server, the system would return a
   pong message to the client side.

   If the server has not received any message from the client for a long
   time, the connection will be disconnected.
{
    "id":"1545910590801",
    "type":"pong"
}

Subscribe

{
    "id": 1545910660739,                          //The id should be an unique v
alue
    "type": "subscribe",
    "topic": "/market/ticker:BTC-USDT,ETH-USDT",  //Topic needs to be subscribed
. Some topics support to divisional subscribe the informations of multiple tradi
ng pairs through ",".
    "privateChannel": false,                      //Adopted the private channel
or not. Set as false by default.
    "response": true                              //Whether the server needs to
return the receipt information of this subscription or not. Set as false by defa
ult.
}

   To subscribe channel messages from a certain server, the client side
   should send subscription message to the server.

   If the subscription succeeds, the system will send ack messages to you,
   when the response is set as true.
{
    "id":"1545910660739",
    "type":"ack"
}

   While there are topic messages generated, the system will send the
   corresponding messages to the client side. For details about the
   message format, please check the definitions of topics.

Parameters

ID

   ID is unique string to mark the request which is same as id property of
   ack.

Topic

   The topic you want to subscribe to.

PrivateChannel

   For some specific topics (e.g. /market/level2), privateChannel is
   available. The default value of privateChannel is False. If the
   privateChannel is set to true, the user will only receive messages
   related himself on the topic.

Response

   If the response is set as true, the system will return the ack messages
   after the subscription succeed.

UnSubscribe

   Unsubscribe from topics you have subscribed to.
{
    "id": "1545910840805",                            //The id should be an uniq
ue value
    "type": "unsubscribe",
    "topic": "/market/ticker:BTC-USDT,ETH-USDT",      //Topic needs to be unsubs
cribed. Some topics support to divisional unsubscribe the informations of multip
le trading pairs through ",".
    "privateChannel": false,
    "response": true                                  //Whether the server needs
 to return the receipt information of this subscription or not. Set as false by
default.
}

{
    "id": "1545910840805",
    "type": "ack"
}

Parameters

ID

   Unique string to mark the request.

Topic

   The topic you want to subscribe.

PrivateChannel

   If the privateChannel is set to true, the private topic will be
   unsubscribed.

Response

   If the response is set as true, the system would return the ack
   messages after the unsubscription succeed.

Multiplex

   In one physical connection, you could open different multiplex tunnels
   to subscribe different topics for different data.

   For example, enter the command below to open bt1 multiple tunnel :

   {"id": "1Jpg30DEdU", "type": "openTunnel", "newTunnelId": "bt1",
   "response": true}

   Add “tunnelId” in the command:

   {"id": "1JpoPamgFM", "type": "subscribe", "topic":
   "/market/ticker:KCS-BTC"，"tunnelId": "bt1", "response": true}

   You would then, receive messages corresponding to the id tunnelIId:

   {"id": "1JpoPamgFM", "type": "message", "topic":
   "/market/ticker:KCS-BTC", "subject": "trade.ticker", "tunnelId": "bt1",
   "data": {...}}

   To close the tunnel, you can enter the command below:

   {"id": "1JpsAHsxKS", "type": "closeTunnel", "tunnelId": "bt1",
   "response": true}

Limitations

    1. The multiplex tunnel is provided for API users only.
    2. The maximum multiplex tunnels available: 5.

Sequence Numbers

   The sequence field exists in order book, trade history and snapshot
   messages by default and the Level 3 and Level 2 data works to ensure
   the full connection of the sequence. If the sequence is non-sequential,
   please enable the calibration logic.

General Logic for Message Judgement in Client Side

   1.Judge message type. There are three types of messages at present:
   message (the commonly used messages for push), notice (the notices
   generally used), and command (consecutive command).

   2.Judge messages by topic. You could judge the message type through the
   topic.

   3.Judge messages by subject. For the same type of messages with the
   same topic, you could judge the type of messages through their
   subjects.

Public Channels

Symbol Ticker

{
    "id": 1545910660739,
    "type": "subscribe",
    "topic": "/market/ticker:BTC-USDT",
    "response": true
}

{
    "type":"message",
    "topic":"/market/ticker:BTC-USDT",
    "subject":"trade.ticker",
    "data":{
        "sequence":"1545896668986", // Sequence number
        "price":"0.08",             // Last traded price
        "size":"0.011",             //  Last traded amount
        "bestAsk":"0.08",          // Best ask price
        "bestAskSize":"0.18",      // Best ask size
        "bestBid":"0.049",         // Best bid price
        "bestBidSize":"0.036"     // Best bid size
    }
}

   Topic: /market/ticker:{symbol},{symbol}...
     * Push frequency: once every 100ms

   Subscribe to this topic to get the push of BBO changes.

   Please note that more information may be added to messages from this
   channel in the near future.

All Symbols Ticker

{
    "id": 1545910660739,
    "type": "subscribe",
    "topic": "/market/ticker:all",
    "response": true
}

{
    "type":"message",
    "topic":"/market/ticker:all",
    "subject":"BTC-USDT",
    "data":{
        "sequence":"1545896668986",
        "bestAsk":"0.08",
        "size":"0.011",
        "bestBidSize":"0.036",
        "price":"0.08",
        "bestAskSize":"0.18",
        "bestBid":"0.049"
    }
}

   Topic: /market/ticker:all
     * Push frequency: once every 100ms

   Subscribe to this topic to get the push of all market symbols BBO
   change.

Symbol Snapshot

{
    "type": "message",
    "topic": "/market/snapshot:KCS-BTC",
    "subject": "trade.snapshot",
    "data": {
        "sequence": "1545896669291",
        "data": {
            "trading": true,
            "symbol": "KCS-BTC",
            "buy": 0.00011,
            "sell": 0.00012,
            "sort": 100,
            "volValue": 3.13851792584,   //total
            "baseCurrency": "KCS",
            "market": "BTC",
            "quoteCurrency": "BTC",
            "symbolCode": "KCS-BTC",
            "datetime": 1548388122031,
            "high": 0.00013,
            "vol": 27514.34842,
            "low": 0.0001,
            "changePrice": -1.0e-5,
            "changeRate": -0.0769,
            "lastTradedPrice": 0.00012,
            "board": 0,
            "mark": 0
        }
    }
}

   Topic: /market/snapshot:{symbol}
     * Push frequency: once every 2s

   Subscribe to get snapshot data for a single symbol.

Market Snapshot

{
    "type": "message",
    "topic": "/market/snapshot:BTC",
    "subject": "trade.snapshot",
    "data": {
        "sequence": "1545896669291",
        "data": [
            {
                "trading": true,
                "symbol": "KCS-BTC",
                "buy": 0.00011,
                "sell": 0.00012,
                "sort": 100,
                "volValue": 3.13851792584,
                "baseCurrency": "KCS",
                "market": "BTC",
                "quoteCurrency": "BTC",
                "symbolCode": "KCS-BTC",
                "datetime": 1548388122031,
                "high": 0.00013,
                "vol": 27514.34842,
                "low": 0.0001,
                "changePrice": -1.0e-5,
                "changeRate": -0.0769,
                "lastTradedPrice": 0.00012,
                "board": 0,
                "mark": 0
          }
       ]
    }
}

   Topic: /market/snapshot:{market}
     * Push frequency: once every 2s

   Subscribe this topic to get the snapshot data of for the entire
   [401]market.

Level-2 Market Data

{
    "id": 1545910660740,
    "type": "subscribe",
    "topic": "/market/level2:BTC-USDT",
    "response": true
}

   Topic: /market/level2:{symbol},{symbol}...
     * Push frequency:real-time

   Subscribe to this topic to get Level2 order book data.

   When the websocket subscription is successful, the system would send
   the increment change data pushed by the websocket to you.
{
    "type": "message",
    "topic": "/market/level2:BTC-USDT",
    "subject": "trade.l2update",
    "data": {
        "changes": {
            "asks": [
                [
                    "18906",//price
                    "0.00331",//size
                    "14103845"//sequence
                ],
                [
                    "18907.3",
                    "0.58751503",
                    "14103844"
                ]
            ],
            "bids": [
                [
                    "18891.9",
                    "0.15688",
                    "14103847"
                ]
            ]
        },
        "sequenceEnd": 14103847,
        "sequenceStart": 14103844,
        "symbol": "BTC-USDT",
        "time": 1663747970273//milliseconds
    }
}

   Calibration procedure：
    1. After receiving the websocket Level 2 data flow, cache the data.
    2. Initiate a [402]REST request to get the snapshot data of Level 2
       order book.
    3. Playback the cached Level 2 data flow.
    4. Apply the new Level 2 data flow to the local snapshot to ensure
       that sequenceStart(new)<=sequenceEnd+1(old) and sequenceEnd(new) >
       sequenceEnd(old). The sequence on each record in changes only
       represents the last modification of the corresponding sequence of
       the price, and does not serve as a basis for judging message
       continuity.
    5. Update the level2 full data based on sequence according to the
       price and size. If the price is 0, ignore the messages and update
       the sequence. If the size=0, update the sequence and remove the
       price of which the size is 0 out of level 2. For other cases,
       please update the price.

   Example

   Take BTC/USDT as an example, suppose the current order book data in
   level 2 is as follows:

   After subscribing to the channel, you would receive changes as follows:

   ...
   "asks":[
     ["3988.59","3", 16], // ignore it because sequence = 16
     ["3988.61","0", 19], // Remove 3988.61
     ["3988.62","8", 15], // ignore it because sequence < 16
   ]
   "bids":[
     ["3988.50", "44", "18"] // Update size of 3988.50 to 44
   ]
   "sequenceEnd": 15,
   "sequenceStart": 19,
   ...
   The sequence on each record in changes only represents the last
   modification of the corresponding sequence of the price, not as a basis
   for judging the continuity of the message; for example, when there are
   multiple updates at the same price ["3988.50", "20", "17" "],
   ["3988.50", "44", "18"], at this time only the latest ["3988.50", "44",
   "18"] will be pushed

   Get a snapshot of the order book through a REST request ([403]Get Order
   Book) to build a local order book. Suppose that data we got is as
   follows:

   ...
   "sequence": "16",
   "asks":[
     ["3988.62","8"],//[Price, Size]
     ["3988.61","32"],
     ["3988.60","47"],
     ["3988.59","3"],
   ]
   "bids":[
     ["3988.51","56"],
     ["3988.50","15"],
     ["3988.49","100"],
     ["3988.48","10"]
   ]
   ...

   The current data on the local order book is as follows:

   | Price | Size | Side |
   |---------|-----|------|
   | 3988.62 | 8   | Sell |
   | 3988.61 | 32  | Sell |
   | 3988.60 | 47  | Sell |
   | 3988.59 | 3   | Sell |
   | 3988.51 | 56  | Buy  |
   | 3988.50 | 15  | Buy  |
   | 3988.49 | 100 | Buy  |
   | 3988.48 | 10  | Buy  |

   In the beginning, the sequence of the order book is 16. Discard the
   feed data of sequence that is below or equals to 16, and apply playback
   the sequence [18,19] to update the snapshot of the order book. Now the
   sequence of your order book is 19 and your local order book is
   up-to-date.

   Diff:
     * Update size of 3988.50 to 44 (Sequence 18)
     * Remove 3988.61 (Sequence 19)

   Now your current order book is up-to-date and final data is as follows:

   | Price | Size | Side |
   |---------|-----|------|
   | 3988.62 | 8   | Sell |
   | 3988.60 | 47  | Sell |
   | 3988.59 | 3   | Sell |
   | 3988.51 | 56  | Buy  |
   | 3988.50 | 44  | Buy  |
   | 3988.49 | 100 | Buy  |
   | 3988.48 | 10  | Buy  |

Level2 - 5 best ask/bid orders

{
    "type": "message",
    "topic": "/spotMarket/level2Depth5:BTC-USDT",
    "subject": "level2",
    "data": {
          "asks":[
            ["9989","8"],    //price, size
            ["9990","32"],
            ["9991","47"],
            ["9992","3"],
            ["9993","3"]
        ],
        "bids":[
            ["9988","56"],
            ["9987","15"],
            ["9986","100"],
            ["9985","10"],
            ["9984","10"]
        ],
        "timestamp": 1586948108193
    }
}


   Topic: /spotMarket/level2Depth5:{symbol},{symbol}...
     * Push frequency: once every 100ms

   The system will return the 5 best ask/bid orders data, which is the
   snapshot data of every 100 milliseconds (in other words, the 5 best
   ask/bid orders data returned every 100 milliseconds in real-time).

Level2 - 50 best ask/bid orders

{
    "type": "message",
    "topic": "/spotMarket/level2Depth50:BTC-USDT",
    "subject": "level2",
    "data": {
          "asks":[
            ["9993","3"],     //price,size
            ["9992","3"],
            ["9991","47"],
            ["9990","32"],
            ["9989","8"]
        ],
        "bids":[
            ["9988","56"],
            ["9987","15"],
            ["9986","100"],
            ["9985","10"],
            ["9984","10"]
        ]
        "timestamp": 1586948108193
    }
}

   Topic: /spotMarket/level2Depth50:{symbol},{symbol}...
     * Push frequency: once every 100ms

   The system will return the 50 best ask/bid orders data, which is the
   snapshot data of every 100 milliseconds (in other words, the 50 best
   ask/bid orders data returned every 100 milliseconds in real-time).

Klines

{
    "type":"message",
    "topic":"/market/candles:BTC-USDT_1hour",
    "subject":"trade.candles.update",
    "data":{
        "symbol":"BTC-USDT",    // symbol
        "candles":[
            "1589968800",   // Start time of the candle cycle
            "9786.9",       // open price
            "9740.8",       // close price
            "9806.1",       // high price
            "9732",         // low price
            "27.45649579",  // Transaction volume
            "268280.09830877"   // Transaction amount
        ],
        "time":1589970010253893337  // now（us）
    }
}

   Topic: /market/candles:{symbol}_{type}
     * Push frequency: real-time

   Param Description
   symbol [404]symbol
   type 1min, 3min, 15min, 30min, 1hour, 2hour, 4hour, 6hour, 8hour,
   12hour, 1day, 1week

   Subscribe to this topic to get K-Line data.

Match Execution Data

{
    "id": 1545910660741,
    "type": "subscribe",
    "topic": "/market/match:BTC-USDT",
    "privateChannel": false,
    "response": true
}

   Topic: /market/match:{symbol},{symbol}...
     * Push frequency: real-time

   Subscribe to this topic to get the matching event data flow of Level 3.

   For each order traded, the system would send you the match messages in
   the following format.
{
    "type":"message",
    "topic":"/market/match:BTC-USDT",
    "subject":"trade.l3match",
    "data":{
        "sequence":"1545896669145",
        "type":"match",
        "symbol":"BTC-USDT",
        "side":"buy",
        "price":"0.08200000000000000000",
        "size":"0.01022222000000000000",
        "tradeId":"5c24c5da03aa673885cd67aa",
        "takerOrderId":"5c24c5d903aa6772d55b371e",
        "makerOrderId":"5c2187d003aa677bd09d5c93",
        "time":"1545913818099033203"
    }
}

Index Price

{
  "id": 1545910660740,
  "type": "subscribe",
  "topic": "/indicator/index:USDT-BTC",
  "response": true
}

   Topic: /indicator/index:{symbol0},{symbol1}...

   Subscribe to this topic to get the index price for the margin trading.
{
    "id":"5c24c5da03aa673885cd67a0",
    "type":"message",
    "topic":"/indicator/index:USDT-BTC",
    "subject":"tick",
    "data":{
        "symbol": "USDT-BTC",
        "granularity": 5000,
        "timestamp": 1551770400000,
        "value": 0.0001092
    }
}

   The following ticker symbols are supported: [405]List of currently
   supported symbol

Mark Price

{
  "id": 1545910660741,
  "type": "subscribe",
  "topic": "/indicator/markPrice:USDT-BTC",
  "response": true
}

{
    "id":"5c24c5da03aa673885cd67aa",
    "type":"message",
    "topic":"/indicator/markPrice:USDT-BTC",
    "subject":"tick",
    "data":{
        "symbol": "USDT-BTC",
        "granularity": 5000,
        "timestamp": 1551770400000,
        "value": 0.0001093
    }
}

   Topic: /indicator/markPrice:{symbol0},{symbol1}...

   Subscribe to this topic to get the mark price for margin trading.

   The following ticker symbols are supported: [406]List of currently
   supported symbol

Order Book Change

{
  "id": 1545910660742,
  "type": "subscribe",
  "topic": "/margin/fundingBook:BTC",
  "response": true
}

{
    "id": "5c24c5da03aa673885cd67ab",
      "type": "message",
      "topic": "/margin/fundingBook:BTC",
      "subject": "funding.update",
      "data": {

            "sequence": 1000000,       //Sequence number
            "currency": "BTC",         //Currency
            "dailyIntRate": "0.00007",   //Daily interest rate. e.g. 0.002 is 0.
2%
            "annualIntRate": "0.12",     //Annual interest rate. e.g. 0.12 is 12
%
            "term": 7,                 //Term (Unit: Day)
            "size": "1017.5",            //Current total size. When this value i
s 0, remove this record from the order book.
            "side": "lend",            //Lend or borrow. Currently, only "Lend"
is available
            "ts": 1553846081210004941  //Timestamp (nanosecond)
    }
}

   Topic: /margin/fundingBook:{currency0},{currency1}...

   Subscribe to this topic to get the order book changes on margin trade.

Private Channels

   Subscribe to private channels require privateChannel=“true”.

Private Order Change Events

   Topic: /spotMarket/tradeOrders
     * Push frequency: real-time

   This topic will push all change events of your orders.

   Order Status

   “match”: when taker order executes with orders in the order book, the
   taker order status is “match”;

   “open”: the order is in the order book;

   “done”: the order is fully executed successfully;

Message Type

open

{
    "type":"message",
    "topic":"/spotMarket/tradeOrders",
    "subject":"orderChange",
    "channelType":"private",
    "data":{
        "symbol":"KCS-USDT",
        "orderType":"limit",
        "side":"buy",
        "orderId":"5efab07953bdea00089965d2",
        "type":"open",
        "orderTime":1593487481683297666,
        "size":"0.1",
        "filledSize":"0",
        "price":"0.937",
        "clientOid":"1593487481000906",
        "remainSize":"0.1",
        "status":"open",
        "ts":1593487481683297666
    }
}

   when the order enters into the order book;

match

{
    "type":"message",
    "topic":"/spotMarket/tradeOrders",
    "subject":"orderChange",
    "channelType":"private",
    "data":{
        "symbol":"KCS-USDT",
        "orderType":"limit",
        "side":"sell",
        "orderId":"5efab07953bdea00089965fa",
        "liquidity":"taker",
        "type":"match",
        "orderTime":1593487482038606180,
        "size":"0.1",
        "filledSize":"0.1",
        "price":"0.938",
        "matchPrice":"0.96738",
        "matchSize":"0.1",
        "tradeId":"5efab07a4ee4c7000a82d6d9",
        "clientOid":"1593487481000313",
        "remainSize":"0",
        "status":"match",
        "ts":1593487482038606180
    }
}

   when the order has been executed;

filled

{
    "type":"message",
    "topic":"/spotMarket/tradeOrders",
    "subject":"orderChange",
    "channelType":"private",
    "data":{
        "symbol":"KCS-USDT",
        "orderType":"limit",
        "side":"sell",
        "orderId":"5efab07953bdea00089965fa",
        "type":"filled",
        "orderTime":1593487482038606180,
        "size":"0.1",
        "filledSize":"0.1",
        "price":"0.938",
        "clientOid":"1593487481000313",
        "remainSize":"0",
        "status":"done",
        "ts":1593487482038606180
    }
}

   when the order has been executed and its status was changed into DONE;

canceled

{
    "type":"message",
    "topic":"/spotMarket/tradeOrders",
    "subject":"orderChange",
    "channelType":"private",
    "data":{
        "symbol":"KCS-USDT",
        "orderType":"limit",
        "side":"buy",
        "orderId":"5efab07953bdea00089965d2",
        "type":"canceled",
        "orderTime":1593487481683297666,
        "size":"0.1",
        "filledSize":"0",
        "price":"0.937",
        "clientOid":"1593487481000906",
        "remainSize":"0",
        "status":"done",
        "ts":1593487481893140844
    }
}

   when the order has been cancelled and its status was changed into DONE;

update

{
    "type":"message",
    "topic":"/spotMarket/tradeOrders",
    "subject":"orderChange",
    "channelType":"private",
    "data":{
        "symbol":"KCS-USDT",
        "orderType":"limit",
        "side":"buy",
        "orderId":"5efab13f53bdea00089971df",
        "type":"update",
        "oldSize":"0.1",
        "orderTime":1593487679693183319,
        "size":"0.06",
        "filledSize":"0",
        "price":"0.937",
        "clientOid":"1593487679000249",
        "remainSize":"0.06",
        "status":"open",
        "ts":1593487682916117521
    }
}

   when the order has been updated;

Account Balance Notice

{
    "type": "message",
      "topic": "/account/balance",
      "subject": "account.balance",
    "channelType":"private",
      "data": {
            "total": "88", // total balance
            "available": "88", // available balance
            "availableChange": "88", // the change of available balance
            "currency": "KCS", // currency
            "hold": "0", // hold amount
            "holdChange": "0", // the change of hold balance
            "relationEvent": "trade.setted", //relation event
            "relationEventId": "5c21e80303aa677bd09d7dff", // relation event id
            "relationContext": {
            "symbol":"BTC-USDT",
            "tradeId":"5e6a5dca9e16882a7d83b7a4", // the trade Id when order is
executed
            "orderId":"5ea10479415e2f0009949d54"
        },  // the context of trade event
        "time": "1545743136994" // timestamp
  }
}


   Topic: /account/balance
     * Push frequency: real-time

   You will receive this message when an account balance changes. The
   message contains the details of the change.

Relation Event

          Type                   Description
   main.deposit       Deposit
   main.withdraw_hold Hold withdrawal amount
   main.withdraw_done Withdrawal done
   main.transfer      Transfer (Main account)
   main.other         Other operations (Main account)
   trade.hold         Hold (Trade account)
   trade.setted       Settlement (Trade account)
   trade.transfer     Transfer (Trade account)
   trade.other        Other operations (Trade account)
   margin.hold        Hold (Margin account)
   margin.setted      Settlement (Margin account)
   margin.transfer    Transfer (Margin account)
   margin.other       Other operations (Margin account)
   other              Others

Debt Ratio Change

{
    "type":"message",
    "topic":"/margin/position",
    "subject":"debt.ratio",
    "channelType":"private",
    "data": {
        "debtRatio": 0.7505,                                         //Debt rati
o
        "totalDebt": "21.7505",                                      //Total deb
t in BTC (interest included)
        "debtList": {"BTC": "1.21","USDT": "2121.2121","EOS": "0"},  //Debt list
 (interest included)
        "timestamp": 15538460812100                                  //Timestamp
 (millisecond)
  }
}


   Topic: /margin/position

   The system will push the current debt message periodically when there
   is a liability.

Position Status Change Event

{
    "type":"message",
    "topic":"/margin/position",
    "subject":"position.status",
    "channelType":"private",
    "data": {
        "type": "FROZEN_FL",         //Event type
        "timestamp": 15538460812100  //Timestamp (millisecond)
    }
}

   Topic: /margin/position

   The system will push the change event when the position status changes.

   Event type:

   FROZEN_FL: When the debt ratio exceeds the liquidation threshold and
   the position is frozen, the system will push this event.

   UNFROZEN_FL: When the liquidation is finished and the position returns
   to “EFFECTIVE” status, the system will push this event.

   FROZEN_RENEW: When the auto-borrow renewing is complete and the
   position returns to “EFFECTIVE” status, the system will push this
   event.

   UNFROZEN_RENEW: When the account reaches a negative balance, the system
   will push this event.

   LIABILITY: When the account reaches a negative balance, the system will
   push this event.

   UNLIABILITY: When all the liabilities is repaid and the position
   returns to “EFFECTIVE” status, the system will push this event.

Margin Trade Order Enters Event

{
    "type": "message",
    "topic": "/margin/loan:BTC",
    "subject": "order.open",
    "channelType":"private",
    "data": {
        "currency": "BTC",                            //Currency
        "orderId": "ac928c66ca53498f9c13a127a60e8",   //Trade ID
        "dailyIntRate": 0.0001,                       //Daily interest rate.
        "term": 7,                                    //Term (Unit: Day)
        "size": 1,                                    //Size
        "side": "lend",                               //Lend or borrow. Currentl
y, only "Lend" is available
        "ts": 1553846081210004941                     //Timestamp (nanosecond)
    }
}

   Topic: /margin/loan:{currency}

   The system will push this message to the lenders when the order enters
   the order book.

Margin Order Update Event

{
    "type": "message",
    "topic": "/margin/loan:BTC",
    "subject": "order.update",
    "channelType":"private",
    "data": {
        "currency": "BTC",                            //Currency
        "orderId": "ac928c66ca53498f9c13a127a60e8",   //Order ID
        "dailyIntRate": 0.0001,                       //Daily Interest Rate
        "term": 7,                                    //Term (Unit: Day)
        "size": 1,                                    //Size
        "lentSize": 0.5,                              //Size executed
        "side": "lend",                               //Lend or borrow. Currentl
y, only "Lend" is available
        "ts": 1553846081210004941                     //Timestamp (nanosecond)
    }
}


   Topic: /margin/loan:{currency}

   The system will push this message to the lenders when the order is
   executed.

Margin Order Done Event

{
    "type": "message",
    "topic": "/margin/loan:BTC",
    "subject": "order.done",
    "channelType":"private",
    "data": {
        "currency": "BTC",                            //Currency
        "orderId": "ac928c66ca53498f9c13a127a60e8",   //Order ID
        "reason": "filled",                           //Done reason (filled or c
anceled)
        "side": "lend",                               //Lend or borrow. Currentl
y, only "Lend" is available
        "ts": 1553846081210004941                     //Timestamp (nanosecond)
  }
}

   Topic: /margin/loan:{currency}

   The system will push this message to the lenders when the order is
   completed.
{
    "type":"message",
    "topic":"/spotMarket/advancedOrders",
    "subject":"stopOrder",
    "channelType":"private",
    "data":{
        "createdAt":1589789942337,
        "orderId":"5ec244f6a8a75e0009958237",
        "orderPrice":"0.00062",
        "orderType":"stop",
        "side":"sell",
        "size":"1",
        "stop":"entry",
        "stopPrice":"0.00062",
        "symbol":"KCS-BTC",
        "tradeType":"TRADE",
        "triggerSuccess":true,
        "ts":1589790121382281286,
        "type":"triggered"
    }
}

Stop Order Event

   Topic: /spotMarket/advancedOrders
     * Push frequency: real-time

   Subject: stopOrder

   When a stop order is received by the system, you will receive a message
   with "open" type. It means that this order entered the system and
   waited to be triggered.

   When a stop order is triggered by current trading price, you will
   receive a message with "triggered" type.

   When you cancel a stop order, you will receive a message with "cancel"
   type.

References

   1. https://www.googletagmanager.com/ns.html?id=GTM-PBTJK8Q
   2. https://docs.kucoin.com/
   3. https://docs.kucoin.com/cn
   4. https://docs.kucoin.com/
   5. https://docs.kucoin.com/futures/cn
   6. https://docs.kucoin.com/futures
   7. https://www.kucoin.com/
   8. https://docs.kucoin.com/cdn-cgi/l/email-protection#f594859cb59e80969a9c9bdb969a98
   9. https://t.me/KuCoin_API
  10. https://github.com/Kucoin/kucoin-api-docs/issues
  11. https://docs.kucoin.com/
  12. https://docs.kucoin.com/#general
  13. https://docs.kucoin.com/#introduction
  14. https://docs.kucoin.com/#upcoming-changes
  15. https://docs.kucoin.com/#reading-guide
  16. https://docs.kucoin.com/#sub-account
  17. https://docs.kucoin.com/#matching-engine
  18. https://docs.kucoin.com/#client-libraries
  19. https://docs.kucoin.com/#sandbox
  20. https://docs.kucoin.com/#request-rate-limit
  21. https://docs.kucoin.com/#market-making-incentive-scheme
  22. https://docs.kucoin.com/#vip-fast-track
  23. https://docs.kucoin.com/#faq
  24. https://docs.kucoin.com/#rest-api-2
  25. https://docs.kucoin.com/#base-url
  26. https://docs.kucoin.com/#endpoint-of-the-interface
  27. https://docs.kucoin.com/#request
  28. https://docs.kucoin.com/#types
  29. https://docs.kucoin.com/#authentication
  30. https://docs.kucoin.com/#user
  31. https://docs.kucoin.com/#user-info
  32. https://docs.kucoin.com/#get-user-info-of-all-sub-accounts
  33. https://docs.kucoin.com/#get-paginated-list-of-sub-accounts
  34. https://docs.kucoin.com/#account
  35. https://docs.kucoin.com/#list-accounts
  36. https://docs.kucoin.com/#get-an-account
  37. https://docs.kucoin.com/#get-account-ledgers
  38. https://docs.kucoin.com/#get-account-summary-information
  39. https://docs.kucoin.com/#create-sub-account
  40. https://docs.kucoin.com/#get-sub-account-spot-api-list
  41. https://docs.kucoin.com/#create-spot-apis-for-sub-account
  42. https://docs.kucoin.com/#modify-sub-account-spot-apis
  43. https://docs.kucoin.com/#delete-sub-account-spot-apis
  44. https://docs.kucoin.com/#get-account-balance-of-a-sub-account
  45. https://docs.kucoin.com/#get-the-aggregated-balance-of-all-sub-accounts
  46. https://docs.kucoin.com/#get-paginated-sub-account-information
  47. https://docs.kucoin.com/#get-the-transferable
  48. https://docs.kucoin.com/#transfer-between-master-user-and-sub-user
  49. https://docs.kucoin.com/#inner-transfer
  50. https://docs.kucoin.com/#deposit
  51. https://docs.kucoin.com/#create-deposit-address
  52. https://docs.kucoin.com/#get-deposit-addresses-v2
  53. https://docs.kucoin.com/#get-deposit-address
  54. https://docs.kucoin.com/#get-deposit-list
  55. https://docs.kucoin.com/#get-v1-historical-deposits-list
  56. https://docs.kucoin.com/#withdrawals
  57. https://docs.kucoin.com/#get-withdrawals-list
  58. https://docs.kucoin.com/#get-v1-historical-withdrawals-list
  59. https://docs.kucoin.com/#get-withdrawal-quotas
  60. https://docs.kucoin.com/#apply-withdraw-2
  61. https://docs.kucoin.com/#cancel-withdrawal
  62. https://docs.kucoin.com/#trade-fee
  63. https://docs.kucoin.com/#basic-user-fee
  64. https://docs.kucoin.com/#actual-fee-rate-of-the-trading-pair
  65. https://docs.kucoin.com/#trade
  66. https://docs.kucoin.com/#orders
  67. https://docs.kucoin.com/#place-a-new-order
  68. https://docs.kucoin.com/#place-a-margin-order
  69. https://docs.kucoin.com/#place-bulk-orders
  70. https://docs.kucoin.com/#cancel-an-order
  71. https://docs.kucoin.com/#cancel-single-order-by-clientoid
  72. https://docs.kucoin.com/#cancel-all-orders
  73. https://docs.kucoin.com/#list-orders
  74. https://docs.kucoin.com/#recent-orders
  75. https://docs.kucoin.com/#get-an-order
  76. https://docs.kucoin.com/#get-single-active-order-by-clientoid
  77. https://docs.kucoin.com/#fills
  78. https://docs.kucoin.com/#list-fills
  79. https://docs.kucoin.com/#recent-fills
  80. https://docs.kucoin.com/#stop-order
  81. https://docs.kucoin.com/#place-a-new-order-2
  82. https://docs.kucoin.com/#cancel-an-order-2
  83. https://docs.kucoin.com/#cancel-orders
  84. https://docs.kucoin.com/#get-single-order-info
  85. https://docs.kucoin.com/#list-stop-orders
  86. https://docs.kucoin.com/#get-single-order-by-clientoid
  87. https://docs.kucoin.com/#cancel-single-order-by-clientoid-2
  88. https://docs.kucoin.com/#market-data
  89. https://docs.kucoin.com/#symbols-amp-ticker
  90. https://docs.kucoin.com/#get-symbols-list-deprecated
  91. https://docs.kucoin.com/#get-symbols-list
  92. https://docs.kucoin.com/#get-ticker
  93. https://docs.kucoin.com/#get-all-tickers
  94. https://docs.kucoin.com/#get-24hr-stats
  95. https://docs.kucoin.com/#get-market-list
  96. https://docs.kucoin.com/#order-book
  97. https://docs.kucoin.com/#get-part-order-book-aggregated
  98. https://docs.kucoin.com/#get-full-order-book-aggregated
  99. https://docs.kucoin.com/#histories
 100. https://docs.kucoin.com/#get-trade-histories
 101. https://docs.kucoin.com/#get-klines
 102. https://docs.kucoin.com/#currencies
 103. https://docs.kucoin.com/#get-currencies
 104. https://docs.kucoin.com/#get-currency-detail
 105. https://docs.kucoin.com/#get-currency-detail-recommend
 106. https://docs.kucoin.com/#get-fiat-price
 107. https://docs.kucoin.com/#margin-trade
 108. https://docs.kucoin.com/#margin-info
 109. https://docs.kucoin.com/#get-mark-price
 110. https://docs.kucoin.com/#get-margin-configuration-info
 111. https://docs.kucoin.com/#get-margin-account
 112. https://docs.kucoin.com/#query-the-cross-isolated-margin-risk-limit
 113. https://docs.kucoin.com/#borrow-amp-lend
 114. https://docs.kucoin.com/#post-borrow-order
 115. https://docs.kucoin.com/#get-borrow-order
 116. https://docs.kucoin.com/#get-repay-record
 117. https://docs.kucoin.com/#get-repayment-record
 118. https://docs.kucoin.com/#one-click-repayment
 119. https://docs.kucoin.com/#repay-a-single-order
 120. https://docs.kucoin.com/#post-lend-order
 121. https://docs.kucoin.com/#cancel-lend-order
 122. https://docs.kucoin.com/#set-auto-lend
 123. https://docs.kucoin.com/#get-active-order
 124. https://docs.kucoin.com/#get-lent-history
 125. https://docs.kucoin.com/#get-active-lend-order-list
 126. https://docs.kucoin.com/#get-settled-lend-order-history
 127. https://docs.kucoin.com/#get-account-lend-record
 128. https://docs.kucoin.com/#lending-market-data
 129. https://docs.kucoin.com/#margin-trade-data
 130. https://docs.kucoin.com/#isolated-margin
 131. https://docs.kucoin.com/#query-isolated-margin-trading-pair-configuration
 132. https://docs.kucoin.com/#query-isolated-margin-account-info
 133. https://docs.kucoin.com/#query-single-isolated-margin-account-info
 134. https://docs.kucoin.com/#isolated-margin-borrowing
 135. https://docs.kucoin.com/#query-outstanding-repayment-records
 136. https://docs.kucoin.com/#query-repayment-records
 137. https://docs.kucoin.com/#quick-repayment
 138. https://docs.kucoin.com/#single-repayment
 139. https://docs.kucoin.com/#others
 140. https://docs.kucoin.com/#server-time
 141. https://docs.kucoin.com/#service-status
 142. https://docs.kucoin.com/#websocket-feed
 143. https://docs.kucoin.com/#apply-connect-token
 144. https://docs.kucoin.com/#create-connection
 145. https://docs.kucoin.com/#ping
 146. https://docs.kucoin.com/#subscribe
 147. https://docs.kucoin.com/#unsubscribe
 148. https://docs.kucoin.com/#multiplex
 149. https://docs.kucoin.com/#sequence-numbers
 150. https://docs.kucoin.com/#general-logic-for-message-judgement-in-client-side
 151. https://docs.kucoin.com/#public-channels
 152. https://docs.kucoin.com/#symbol-ticker
 153. https://docs.kucoin.com/#all-symbols-ticker
 154. https://docs.kucoin.com/#symbol-snapshot
 155. https://docs.kucoin.com/#market-snapshot
 156. https://docs.kucoin.com/#level-2-market-data
 157. https://docs.kucoin.com/#level2-5-best-ask-bid-orders
 158. https://docs.kucoin.com/#level2-50-best-ask-bid-orders
 159. https://docs.kucoin.com/#klines
 160. https://docs.kucoin.com/#match-execution-data
 161. https://docs.kucoin.com/#index-price
 162. https://docs.kucoin.com/#mark-price
 163. https://docs.kucoin.com/#order-book-change
 164. https://docs.kucoin.com/#private-channels
 165. https://docs.kucoin.com/#private-order-change-events
 166. https://docs.kucoin.com/#account-balance-notice
 167. https://docs.kucoin.com/#debt-ratio-change
 168. https://docs.kucoin.com/#position-status-change-event
 169. https://docs.kucoin.com/#margin-trade-order-enters-event
 170. https://docs.kucoin.com/#margin-order-update-event
 171. https://docs.kucoin.com/#margin-order-done-event
 172. https://docs.kucoin.com/#stop-order-event
 173. https://www.kucoin.com/
 174. https://github.com/Kucoin/kucoin-api-docs
 175. https://www.kucoin.com/account/api
 176. https://docs.kucoin.com/#signing-a-message
 177. https://docs.kucoin.com/#query-the-cross-isolated-margin-risk-limit
 178. https://docs.kucoin.com/#get-v1-historical-orders-list-deprecated
 179. https://docs.kucoin.com/#list-accounts
 180. https://docs.kucoin.com/#inner-transfer
 181. https://docs.kucoin.com/#get-the-transferable
 182. https://docs.kucoin.com/#get-currency-detail-recommend
 183. https://docs.kucoin.com/#list-of-currently-supported-symbol
 184. https://docs.kucoin.com/#get-repay-record
 185. https://docs.kucoin.com/#get-repayment-record
 186. https://docs.kucoin.com/#get-account-ledgers
 187. https://docs.kucoin.com/#request-rate-limit
 188. https://docs.kucoin.com/#get-single-active-order-by-clientoid
 189. https://docs.kucoin.com/#get-an-order
 190. https://docs.kucoin.com/#get-full-order-book-aggregated
 191. https://docs.kucoin.com/#get-full-order-book-atomic
 192. https://docs.kucoin.com/#get-full-order-book-aggregated-deprecated
 193. https://docs.kucoin.com/#get-full-order-book-atomic-deprecated
 194. https://docs.kucoin.com/#get-deposit-addresses-v2
 195. https://docs.kucoin.com/#place-a-margin-order
 196. https://docs.kucoin.com/#trade-fee
 197. https://docs.kucoin.com/#basic-user-fee
 198. https://docs.kucoin.com/#actual-fee-rate-of-the-trading-pair
 199. https://docs.kucoin.com/#get-account-ledgers
 200. https://docs.kucoin.com/#get-account-ledgers-deprecated
 201. https://docs.kucoin.com/#get-24hr-stats
 202. https://docs.kucoin.com/#get-all-tickers
 203. https://docs.kucoin.com/#transfer-between-master-user-and-sub-user
 204. https://docs.kucoin.com/#inner-transfer
 205. https://docs.kucoin.com/#transfer-between-master-user-and-sub-user
 206. https://docs.kucoin.com/#stop-order
 207. https://docs.kucoin.com/#stop-order-event
 208. https://docs.kucoin.com/#stop-order-received-event
 209. https://docs.kucoin.com/#stop-order-activate-event
 210. https://docs.kucoin.com/#cancel-single-order-by-clientoid
 211. https://docs.kucoin.com/#get-single-active-order-by-clientoid
 212. https://docs.kucoin.com/#private-order-change-events
 213. https://docs.kucoin.com/#full-matchengine-data-revision-level-nbsp-3
 214. https://docs.kucoin.com/#level2-5-best-askbid-orders
 215. https://docs.kucoin.com/#level2-50-best-askbid-orders
 216. https://docs.kucoin.com/#get-full-order-book-atomic-revision
 217. https://docs.kucoin.com/#get-account-ledgers
 218. https://docs.kucoin.com/#get-holds
 219. https://docs.kucoin.com/#account-balance-notice
 220. https://docs.kucoin.com/#list-accounts
 221. https://docs.kucoin.com/#inner-transfer
 222. https://docs.kucoin.com/#get-the-transferable
 223. https://docs.kucoin.com/#get-account-ledgers
 224. https://docs.kucoin.com/#get-account-ledgers
 225. https://docs.kucoin.com/#service-status
 226. https://docs.kucoin.com/#place-bulk-orders
 227. https://docs.kucoin.com/#place-a-new-order
 228. https://docs.kucoin.com/#place-a-new-order
 229. https://docs.kucoin.com/#get-full-order-book(atomic)
 230. https://docs.kucoin.com/#stop-order-activate-event
 231. https://docs.kucoin.com/#inner-transfer
 232. https://docs.kucoin.com/#list-accounts
 233. https://docs.kucoin.com/#get-an-account
 234. https://docs.kucoin.com/#create-an-account
 235. https://docs.kucoin.com/#get-account-ledgers
 236. https://docs.kucoin.com/#get-holds
 237. https://docs.kucoin.com/#get-account-balance-of-a-sub-account
 238. https://docs.kucoin.com/#get-the-aggregated-balance-of-all-sub-accounts
 239. https://docs.kucoin.com/#transfer-between-master-user-and-sub-user
 240. https://docs.kucoin.com/#inner-transfer
 241. https://docs.kucoin.com/#get-the-transferable
 242. https://docs.kucoin.com/#place-a-new-order
 243. https://docs.kucoin.com/#cancel-all-orders
 244. https://docs.kucoin.com/#list-orders
 245. https://docs.kucoin.com/#recent-orders
 246. https://docs.kucoin.com/#get-an-order
 247. https://docs.kucoin.com/#list-fills
 248. https://docs.kucoin.com/#recent-fills
 249. https://docs.kucoin.com/#get-symbols-list
 250. https://docs.kucoin.com/#get-currencies
 251. https://docs.kucoin.com/#get-currency-detail
 252. https://docs.kucoin.com/#margin-trade
 253. https://docs.kucoin.com/#get-deposit-list
 254. https://docs.kucoin.com/#get-withdrawals-list
 255. https://docs.kucoin.com/get-market-list
 256. https://docs.kucoin.com/#get-all-tickers
 257. https://docs.kucoin.com/#transfer-between-master-user-and-sub-user
 258. https://docs.kucoin.com/#faq
 259. https://docs.kucoin.com/#matchengine-data
 260. https://docs.kucoin.com/#Get-Market-List
 261. https://docs.kucoin.com/#inner-transfer
 262. https://docs.kucoin.com/#apply-withdraw
 263. https://docs.kucoin.com/#get-24hr-stats
 264. https://docs.kucoin.com/#create-deposit-address
 265. https://docs.kucoin.com/#get-deposit-address
 266. https://docs.kucoin.com/#get-currency-detail
 267. https://docs.kucoin.com/#get-withdrawal-quotas
 268. https://docs.kucoin.com/#apply-withdraw
 269. https://docs.kucoin.com/#inner-transfer
 270. https://docs.kucoin.com/#full-matchengine-data(level-3)
 271. https://docs.kucoin.com/#request-rate-limit
 272. https://docs.kucoin.com/#full-matchengine-data(level-3)
 273. https://docs.kucoin.com/#full-matchengine-data(level-3)
 274. https://docs.kucoin.com/#get-user-info-of-all-sub-accounts
 275. https://docs.kucoin.com/#get-account-balance-of-a-sub-account
 276. https://docs.kucoin.com/#get-the-aggregated-balance-of-all-sub-accounts-of-the-current-user
 277. https://docs.kucoin.com/#transfer-between-master-account-and-sub-account
 278. https://docs.kucoin.com/#get-symbols-list
 279. https://docs.kucoin.com/#get-all-tickers
 280. https://docs.kucoin.com/#full-matchengine-data(level-3)
 281. https://docs.kucoin.com/#account-balance-notice
 282. https://docs.kucoin.com/#get-symbols-list
 283. https://docs.kucoin.com/#get-v1-historical-deposits-list
 284. https://docs.kucoin.com/#get-v1-historical-withdrawals-list
 285. https://docs.kucoin.com/#get-v1-historical-orders-list
 286. https://docs.kucoin.com/#match-execution-data
 287. https://docs.kucoin.com/#get-fiat-price
 288. https://docs.kucoin.com/#get-24hr-stats
 289. https://docs.kucoin.com/#get-full-order-book-aggregated
 290. https://docs.kucoin.com/#get-fiat-price
 291. https://docs.kucoin.com/#get-all-tickers
 292. https://docs.kucoin.com/#get-ticker
 293. https://docs.kucoin.com/#get-all-tickers
 294. https://docs.kucoin.com/#recent-orders
 295. https://docs.kucoin.com/#recent-fills
 296. https://docs.kucoin.com/#all-symbols-ticker
 297. https://docs.kucoin.com/#permissions
 298. https://docs.kucoin.com/#client-libraries
 299. https://docs.kucoin.com/#get-market-list
 300. https://docs.kucoin.com/#symbol-snapshot
 301. https://docs.kucoin.com/#market-snapshot
 302. https://docs.kucoin.com/#client-libraries
 303. https://docs.kucoin.com/#sandbox
 304. https://docs.kucoin.com/#rest-api
 305. https://docs.kucoin.com/#server-time
 306. https://docs.kucoin.com/#service-status
 307. https://docs.kucoin.com/#authentication
 308. https://docs.kucoin.com/#inner-transfer
 309. https://docs.kucoin.com/#list-accounts
 310. https://docs.kucoin.com/#place-a-new-order
 311. https://docs.kucoin.com/#get-part-order-book-aggregated
 312. https://docs.kucoin.com/#websocket-feed
 313. https://docs.kucoin.com/#level-2-market-data
 314. https://docs.kucoin.com/#account-balance-notice
 315. https://docs.kucoin.com/#place-a-new-order
 316. https://docs.kucoin.com/#get-an-account
 317. https://docs.kucoin.com/#create-an-account
 318. https://docs.kucoin.com/#get-account-ledgers
 319. https://docs.kucoin.com/#get-holds
 320. https://docs.kucoin.com/#inner-transfer
 321. https://docs.kucoin.com/#place-a-new-order
 322. https://docs.kucoin.com/#cancel-an-order
 323. https://docs.kucoin.com/#cancel-all-orders
 324. https://docs.kucoin.com/#list-orders
 325. https://docs.kucoin.com/#recent-orders
 326. https://docs.kucoin.com/#get-an-order
 327. https://docs.kucoin.com/#list-fills
 328. https://docs.kucoin.com/#recent-fills
 329. https://docs.kucoin.com/#cancel-single-order-by-clientoid
 330. https://docs.kucoin.com/#get-single-active-order-by-clientoid
 331. https://github.com/Kucoin/KuCoin-Java-SDK
 332. https://github.com/Kucoin/KuCoin-PHP-SDK
 333. https://github.com/Kucoin/KuCoin-Go-SDK
 334. https://github.com/Kucoin/kucoin-python-sdk
 335. https://github.com/Kucoin/kucoin-node-sdk
 336. https://ccxt.trade/
 337. https://github.com/Kucoin/kucoin-api-docs/tree/master/examples/php
 338. https://sandbox.kucoin.com/
 339. https://docs.kucoin.com/cdn-cgi/l/email-protection#87e6f7eec7ecf2e4e8eee9a9e4e8ea
 340. https://docs.kucoin.com/cdn-cgi/l/email-protection
 341. https://docs.kucoin.com/cdn-cgi/l/email-protection
 342. https://docs.kucoin.com/#get-withdrawal-quotas
 343. https://www.kucoin.com/account/api
 344. https://docs.kucoin.com/#server-time
 345. https://docs.kucoin.com/#inner-transfer
 346. https://docs.kucoin.com/#get-currencies
 347. https://docs.kucoin.com/#pagination
 348. https://docs.kucoin.com/#get-user-info-of-all-sub-accounts
 349. https://docs.kucoin.com/#get-currencies
 350. https://docs.kucoin.com/#Get-Currencies
 351. https://docs.kucoin.com/#get-currencies
 352. https://docs.kucoin.com/#get-user-info-of-all-sub-accounts
 353. https://docs.kucoin.com/#Get-Currencies
 354. https://docs.kucoin.com/#get-currencies
 355. https://docs.kucoin.com/#apply-withdraw
 356. https://docs.kucoin.com/#apply-withdraw
 357. https://docs.kucoin.com/#apply-withdraw
 358. https://docs.kucoin.com/cdn-cgi/l/email-protection
 359. https://docs.kucoin.com/#pagination
 360. https://docs.kucoin.com/#apply-withdraw
 361. https://docs.kucoin.com/cdn-cgi/l/email-protection
 362. https://docs.kucoin.com/cdn-cgi/l/email-protection
 363. https://docs.kucoin.com/#get-currencies
 364. https://docs.kucoin.com/#get-currencies
 365. https://docs.kucoin.com/#apply-withdraw
 366. https://docs.kucoin.com/#get-currencies
 367. https://docs.kucoin.com/#list-fills
 368. https://docs.kucoin.com/#get-symbols-list
 369. https://docs.kucoin.com/#time-in-force
 370. https://docs.kucoin.com/#get-symbols-list
 371. https://docs.kucoin.com/#list-fills
 372. https://docs.kucoin.com/#get-symbols-list
 373. https://docs.kucoin.com/#time-in-force
 374. https://docs.kucoin.com/#time-in-force
 375. https://docs.kucoin.com/#list-orders
 376. https://docs.kucoin.com/#pagination
 377. https://docs.kucoin.com/#pagination
 378. https://docs.kucoin.com/#list-orders
 379. https://docs.kucoin.com/#pagination
 380. https://docs.kucoin.com/#time-in-force
 381. https://docs.kucoin.com/#list-orders
 382. https://docs.kucoin.com/#pagination
 383. https://docs.kucoin.com/#get-all-tickers
 384. https://docs.kucoin.com/#get-market-list
 385. https://docs.kucoin.com/#get-market-list
 386. https://docs.kucoin.com/#get-all-tickers
 387. https://docs.kucoin.com/#get-market-list
 388. https://docs.kucoin.com/#get-market-list
 389. https://docs.kucoin.com/#get-symbols-list
 390. https://docs.kucoin.com/#get-symbols-list
 391. https://docs.kucoin.com/#level-2-market-data
 392. https://docs.kucoin.com/#get-symbols-list
 393. https://docs.kucoin.com/#level-2-market-data
 394. https://docs.kucoin.com/#get-symbols-list
 395. https://docs.kucoin.com/#get-symbols-list
 396. https://docs.kucoin.com/#get-symbols-list
 397. https://docs.kucoin.com/#get-currencies
 398. https://docs.kucoin.com/#get-currencies
 399. https://docs.kucoin.com/#get-symbols-list
 400. https://docs.kucoin.com/#post-borrow-order
 401. https://docs.kucoin.com/#get-market-list
 402. https://docs.kucoin.com/#get-full-order-book-aggregated
 403. https://docs.kucoin.com/#get-part-order-book-aggregated
 404. https://docs.kucoin.com/#get-symbols-list
 405. https://docs.kucoin.com/#list-of-currently-supported-symbol
 406. https://docs.kucoin.com/#list-of-currently-supported-symbol

"""

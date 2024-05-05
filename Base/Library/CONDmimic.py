#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# MIMIC Conditional Orders - OliverTwist

# Jackrabbit Relay
# 2021 Copyright © Robert APM Darin
# All rights reserved unconditionally.

# This is the framework used by OliverTwist to process conditional orders.

import sys
sys.path.append('/home/GitHub/JackrabbitRelay/Base/Library')
import os
import json
import time
import datetime

import JRRsupport
import JackrabbitRelay as JRR

# Calculate Price Exit

def CalculatePriceExit(order,ts,dir,price):
    # Figure out TakeProfit or Stoploss
    if ts=='TakeProfit':
        if '%' in str(order[ts]):
            if dir=='long':
                val=price+((float(order[ts].replace('%','').strip())/100)*price)
            else:
                val=price-((float(order[ts].replace('%','').strip())/100)*price)
        # Pips
        elif 'p' in str(order[ts].lower()):
            if dir=='long':
                val=price+(float(order[ts].lower().replace('p','').strip())*0.0001)
            else:
                val=price-(float(order[ts].lower().replace('p','').strip())*0.0001)
        else:
            val=float(order[ts])
    elif ts=='StopLoss':
        if '%' in str(order[ts]):
            if dir=='long':
                val=price-((float(order[ts].replace('%','').strip())/100)*price)
            else:
                val=price+((float(order[ts].replace('%','').strip())/100)*price)
        # Pips
        elif 'p' in str(order[ts].lower()):
            if dir=='long':
                val=price-(float(order[ts].lower().replace('p','').strip())*0.0001)
            else:
                val=price+(float(order[ts].lower().replace('p','').strip())*0.0001)
        else:
            val=float(order[ts])

    return val

###
### Main driver
###

def OrderProcessor(Orphan):
    # Use Relay to process and validate the order, must be a string
    if type(Orphan['Order']) is dict:
        order=json.dumps(Orphan['Order'])
    else:
        order=Orphan['Order']

    relay=JRR.JackrabbitRelay(framework=Orphan['Framework'],payload=order,NoIdentityVerification=True)
    relay.JRLog.SetBaseName('OliverTwist')

    try:
        # Check to see if order is still open and return current state
        # Handle OANDa's weird order id sequencing
        id=Orphan['ID']
        saction=relay.Order['SellAction'].lower()
        if type(Orphan['Response']) is str:
            Orphan['Response']=json.loads(Orphan['Response'])
        oDetail=Orphan['Response']

        # Manage average and close extire position. Average and price are the same.
        price=float(oDetail['Price'])
        amount=float(oDetail['Amount'])
        cid=id      # This is the ID of the original order

        # Process the position

        # We need to check TakeProfit and StopLoss. If one of them is hit, we need to build and order and
        # backfeed it in to Relay. It will place a new order.

        # Get the direction of the trade, long/short
        dir=relay.Order['Direction'].lower()
        # Get Ticker
        ticker=relay.GetTicker(symbol=relay.Order['Asset'])

        # Check to see if we have enough balance, if not then delete this order. Deal with futures as well.

        base=relay.Markets[relay.Order['Asset']]['base'].upper()
        bal=relay.GetBalance(Base=base)

        # Fsilsafe, in the WORST way possible. Do NOT leave a take profit out of the order. At this stage, the
        # whole thing is an absolute nightmare to fix. The is a very brutal way of dealing with poor user
        # choices.

        if 'TakeProfit' not in relay.Order:
            relay.Order['TakeProfit']='2%'

        # Calculate Take Profit
        tp=round(CalculatePriceExit(relay.Order,'TakeProfit',dir,price),5)

        # Figure out StopLoss, if there is one
        sl=0
        if 'StopLoss' in relay.Order:
            sl=round(CalculatePriceExit(relay.Order,'StopLoss',dir,price),5)

        # find trade open time
        parts=oDetail['DateTime'].split('.')
        dsS=f"{parts[0]}.{parts[1][:6]}Z"
        ds=datetime.datetime.strptime(dsS,'%Y-%m-%d %H:%M:%S.%fZ')

        # Get the "strikePrice". This handles both TakeProfit and StopLoss. It doesn't matter which as both are processed
        # the same way.

        LogMSG=None
        StrikeHappened=False
        if dir=='long':
            if 'Diagnostics' in relay.Active:
                relay.JRLog.Write(f"{id}: {dir} Price: {price}, Bid: {ticker['Bid']} TP: {tp}/{relay.Order['TakeProfit']}, SL {sl}/{relay.Order['StopLoss']}",stdOut=False)

            if ticker['Bid']>tp or ('StopLoss' in relay.Order and ticker['Bid']<sl):
                strikePrice=ticker['Bid']
                StrikeHappened=True
        else:
            if 'Diagnostics' in relay.Active:
                relay.JRLog.Write(f"{id}: {dir} Price: {price}, Ask: {ticker['Ask']} TP: {tp}/{relay.Order['TakeProfit']}, SL {sl}/{relay.Order['StopLoss']}",stdOut=False)

            if ticker['Ask']<tp or ('StopLoss' in relay.Order and ticker['Ask']>sl):
                strikePrice=ticker['Ask']
                StrikeHappened=True

        if StrikeHappened==True:
            if 'Diagnostics' in relay.Active:
                relay.JRLog.Write(f"{id}: Amount {abs(amount)}, Balance: {abs(bal)}",stdOut=False)

            if abs(bal)>abs(amount):
                # Build "strike" order. TakeProfit or StopLoss has been triggered
                newOrder={}
                newOrder['OliverTwist']='Conditional'
                newOrder['Exchange']=relay.Order['Exchange']
                newOrder['Account']=relay.Order['Account']
                newOrder['Market']=relay.Order['Market']
                newOrder['Asset']=relay.Order['Asset']
                newOrder['Action']=relay.Order['SellAction']
                newOrder['Price']=str(strikePrice)
                newOrder['Base']=str(amount)
                if 'OrderType' in relay.Order:
                    newOrder['OrderType']=relay.Order['OrderType']
                else:
                    newOrder['OrderType']='market'

    #            relay.JRLog.Write(f"{id}: {json.dumps(newOrder)}",stdOut=False)

                newOrder['Identity']=relay.Active['Identity']

                # Feed the new order to Relay
                result=relay.SendWebhook(newOrder)
                oid=relay.GetOrderID(result)
                if oid!=None:
                    resp=relay.GetOrderDetails(id=oid,symbol=relay.Order['Asset'])
                    # Order must be closed as it succedded
                    newOrder['ID']=oid
                    relay.JRLog.Write(json.dumps(resp),stdOut=False)
                    sprice=float(resp['Price'])

                    # find trade close time and  duration
                    parts=resp['DateTime'].split('.')
                    deS=f"{parts[0]}.{parts[1][:6]}Z"
                    de=datetime.datetime.strptime(deS,'%Y-%m-%d %H:%M:%S.%fZ')
                    duration=de-ds

                    rpl=0
                    if dir=='long':
                        if ticker['Bid']>tp:
                            rpl=round((abs(amount)*sprice)-(abs(amount)*price),8)
                        if sl!=0 and ticker['Bid']<sl:
                            rpl=round((abs(amount)*price)-(abs(amount)*sprice),8)
                    else:
                        if ticker['Ask']<tp:
                            rpl=round((abs(amount)*price)-(abs(amount)*sprice),8)
                        if sl!=0 and ticker['Ask']>sl:
                            rpl=round((abs(amount)*sprice)-(abs(amount)*price),8)

                    # rpl is reported by broker. This is the actual profit/loss of trade.
                    if rpl>=0:
                        LogMSG=f"{oid} -> {cid} Prft {dir}, {amount:.8f}: {price:.8f} -> {sprice:8f}/{abs(rpl):.8f}, {duration}"
                    else:
                        LogMSG=f"{oid} -> {cid} Loss {dir}, {amount:.8f}: {price:.8f} -> {sprice:8f}/{abs(rpl):.8f}, {duration}"
                    relay.JRLog.Write(f"{LogMSG}",stdOut=False)

                    relay.WriteLedger(Order=newOrder,Response=resp)
                    return 'Delete'
                else:
                    # Give OliverTwist a response
                    relay.JRLog.Write(f"{id}: Order failed with {relay.GetFailedReason(result)}",stdOut=False)
                    return 'Delete' # 'Waiting'
            else:
                # Amount > Balance
                relay.JRLog.Write(f"{id}: Amount {amount:.8f} > Balance {bal:.8f} {base}, purge",stdOut=False)
                return 'Delete'
        else:
            # Strike did not happen
            return 'Waiting'
    except Exception as e:
        # Something went wrong
        relay.JRLog.Write(f"{Orphan['Key']}: CONDmimic {sys.exc_info()[-1].tb_lineno}/{str(e)}",stdOut=False)
        if 'Diagnostics' in relay.Active:
            relay.JRLog.Write(f"{Orphan['Key']}: {data}",stdOut=False)
        return 'Waiting'

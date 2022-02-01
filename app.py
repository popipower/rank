import re
import math
import json
from json import JSONEncoder
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
import os


class OptionsEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


def processTicker(ticker, cmp, dte):
    req = Request('https://www.barchart.com/stocks/quotes/' + ticker + '/overview',
                  headers={'User-Agent': 'Mozilla/5.0'})
    webpage = urlopen(req).read()
    soup = BeautifulSoup(webpage, "html.parser")
    spanArr = soup.find_all("span")
    ivRankIndex = 0
    ivHighIndex = 0
    ivLowIndex = 0

    for i in range(len(spanArr)):
        if spanArr[i].text == 'IV Rank':
            ivRankIndex = i

        if spanArr[i].text == 'IV High':
            ivHighIndex = i

        if spanArr[i].text == 'IV Low':
            ivLowIndex = i

    ivRank = re.findall("\d+\.\d+", spanArr[ivRankIndex + 1].text)[0]
    ivHighData = str(spanArr[ivHighIndex + 1].text).split()
    ivLowData = str(spanArr[ivLowIndex + 1].text).split()
    sd = float(re.findall("\d+\.\d+", ivRank)[0])/100 * float(cmp) * math.sqrt(int(dte) / 365)
    return IVRank(ticker, ivRank, ivHighData[0], ivHighData[2], ivLowData[0], ivLowData[2], sd)


class IVRank:

    def __init__(self, symbol, ivRank, ivHigh, ivHighDate, ivLow, ivLowDate, sd):
        self.sd = sd
        self.ivRank = ivRank
        self.ivHigh = ivHigh
        self.ivHighDate = ivHighDate
        self.ivLow = ivLow
        self.ivLowDate = ivLowDate
        self.symbol = symbol


def handler(event, context):
    IVRankList = list()
    cmp = 0
    dte = 0
    tickers = ["AAPL"]
    envTicker = os.environ.get('tickers', None)
    if event is not None:
        if event.get('queryStringParameters'):
            if event['queryStringParameters'].get('tickers'):
                tickers = event['queryStringParameters']['tickers'].split(",")
        elif envTicker:
            tickers = envTicker.split(",")
        if event.get('queryStringParameters'):
            if event['queryStringParameters'].get('tickers'):
                tickers = event['queryStringParameters']['tickers'].split(",")
        elif envTicker:
            tickers = envTicker.split(",")

        if event.get('queryStringParameters'):
            if event['queryStringParameters'].get('cmp'):
                cmp = event['queryStringParameters']['cmp']

        if event.get('queryStringParameters'):
            if event['queryStringParameters'].get('dte'):
                dte = event['queryStringParameters']['dte']

    for ticker in tickers:
        IVRankList.append(processTicker(ticker, cmp, dte))
    final_data = "{\"data\":" + json.dumps(IVRankList, cls=OptionsEncoder, indent=4) + "}"
    print(final_data)
    return final_data


#handler(None, None)

import re
import math
import json
from json import JSONEncoder
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
import os
import yfinance as yf

import calendar
from datetime import date, timedelta, datetime
from itertools import islice
import boto3
import pytz

htmlResponseStart = "<html><head><style>body,html{font-family:Verdana,sans-serif;font-size:10px;line-height:0.5}html{" \
                    "overflow-x:hidden}.w3-amber,.w3-hover-amber:hover{" \
                    "color:#000!important;background-color:#ffc107!important}.w3-hover-light-green:hover,.w3-light-green{" \
                    "color:#000!important;background-color:#8bc34a!important}.w3-deep-orange,.w3-hover-deep-orange:hover{" \
                    "color:#fff!important;background-color:#ff5722!important}.w3-responsive{" \
                    "display:block;overflow-x:auto}table.w3-table-all,table.ws-table-all{" \
                    "margin:3px;align:center}.ws-table-all{" \
                    "border-collapse:collapse;border-spacing:0;width:70%;display:table;border:3px solid " \
                    "#ccc;align:center}.ws-table-all tr{border-bottom:3px solid #ddd}.ws-table-all tr:nth-child(odd){" \
                    "background-color:#fff}.ws-table-all tr:nth-child(even){background-color:#e7e9eb}.ws-table-all td," \
                    ".ws-table-all th{padding:3px 3px;display:table-cell;text-align:left;vertical-align:top}.ws-table" \
                    "-all " \
                    "td:first-child,.ws-table-all th:first-child{padding-left:3px}.w3-blue-grey," \
                    ".w3-hover-blue-grey:hover" \
                    ",.w3-blue-gray,.w3-hover-blue-gray:hover{color:#fff!important;background-color:#607d8b!important}" \
                    ".w3-light-grey,.w3-hover-light-grey:hover,.w3-light-gray,.w3-hover-light-gray:hover" \
                    "{color:#000!important;background-color:#f1f1f1!important} .w3-orange,.w3-hover-orange:hover{color:#000!important;background-color:#ff9800!important}" \
                    "</style></head><body><div " \
                    "class=\"w3-responsive\"><table class=\"ws-table-all ws-green\"> <tbody><tr class =\"w3-blue-grey\"> <th " \
                    "style=\"width:15%\">Tick</th> <th style=\"width:15%\">CMP</th> <th " \
                    "style=\"width:10%\">Rank</th> <th style=\"width:15%\">IV</th>"

htmlResponseEnd = "</tbody></table></div></body></html>"

DAY = timedelta(1)
WEEK = 7 * DAY


def fridays(now):
    while True:
        if now.weekday() == calendar.FRIDAY:
            while True:
                yield now
                now += WEEK
        now += DAY


def next_month(now):
    """Return the first date that is in the next month."""
    return (now.replace(day=15) + 20 * DAY).replace(day=1)


def third_friday_brute_force(now):
    """the 3rd Friday of the month, not the 3rd Friday after today."""
    return next(islice(fridays(now.replace(day=1)), 2, 3))


def get_third_fris(how_many):
    result = {}
    now = date.today()

    while len(result) < how_many:
        fr = third_friday_brute_force(now)
        if fr > now:  # use only the 3rd Friday after today
            result[fr.strftime("%d%b")] = (fr - date.today()).days
            # result.append((fr-date.today()).days)
        now = next_month(now)
    return result


class OptionsEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


def processTicker(ticker, cmp, dte, responseType):
    req = Request('https://www.barchart.com/stocks/quotes/' + ticker + '/overview',
                  headers={'User-Agent': 'Mozilla/5.0'})
    webpage = urlopen(req).read()
    soup = BeautifulSoup(webpage, "html.parser")
    spanArr = soup.find_all("span")
    ivRankIndex = 0
    ivHighIndex = 0
    ivLowIndex = 0
    iv = 0

    for i in range(len(spanArr)):
        if spanArr[i].text == 'IV Rank':
            ivRankIndex = i

        if spanArr[i].text == 'IV High':
            ivHighIndex = i

        if spanArr[i].text == 'IV Low':
            ivLowIndex = i

        if spanArr[i].text == 'Implied Volatility':
            iv = i

    ivRank = re.findall("\d+\.\d+", spanArr[ivRankIndex + 1].text)[0]
    ivHighData = str(spanArr[ivHighIndex + 1].text).split()
    ivLowData = str(spanArr[ivLowIndex + 1].text).split()
    iv = str(spanArr[iv + 1].text).strip()[:5]

    if float(ivRank) < 30.0:
        selectCSS = "\"w3-light-green\""
    elif 30.0 < float(ivRank) < 50.0:
        selectCSS = "\"w3-orange\""
    elif float(ivRank) > 50.0:
        selectCSS = "\"w3-deep-orange\""

    response = "<td class=" + selectCSS + " > " + ivRank + "</td><td class =\"w3-light-grey\">" + iv + "</td>"
    sdMap = {}
    for key in dte.keys():
        # print(dte[key])
        if responseType == 'email':
            sd = round(float(re.findall("\d+\.\d+", ivRank)[0]) / 100 * float(cmp) * math.sqrt(int(dte[key]) / 365), 2)
            response = response + "<td class =\"w3-light-grey\">" + str(sd) + "</td>"
        else:
            sdMap[key] = str(
                round(float(re.findall("\d+\.\d+", ivRank)[0]) / 100 * float(cmp) * math.sqrt(int(dte[key]) / 365), 2))

    if responseType == 'email':
        return response
    else:
        return IVRank(ticker, ivRank, ivHighData[0], ivHighData[2], ivLowData[0], ivLowData[2], sdMap, iv)


class IVRank:

    def __init__(self, symbol, ivRank, ivHigh, ivHighDate, ivLow, ivLowDate, sd, iv):
        self.sd = sd
        self.ivRank = ivRank
        self.ivHigh = ivHigh
        self.ivHighDate = ivHighDate
        self.ivLow = ivLow
        self.ivLowDate = ivLowDate
        self.symbol = symbol
        self.iv = iv


def handler(event, context):
    final_data = ""
    IVRankList = list()
    envTicker = os.environ.get('tickers', None)
    responseType = os.environ.get('responseType', 'json')
    dte = os.environ.get('dteSpan', 3)
    recipient = os.environ.get('recipient', 'sumitarora.kp@gmail.com')
    sender = os.environ.get('sender', 'Volatility Notification<pahwa.saransh7@gmail.com>')

    tickers = ["AAPL","V"]
    if event is not None:
        if event.get('queryStringParameters'):
            if event['queryStringParameters'].get('tickers'):
                tickers = event['queryStringParameters']['tickers'].split(",")
        elif envTicker:
            tickers = envTicker.split(",")
        if event.get('queryStringParameters'):
            if event['queryStringParameters'].get('responseType'):
                responseType = event['queryStringParameters']['responseType'].split(",")

        # if event.get('queryStringParameters'):
        #   if event['queryStringParameters'].get('cmp'):
        #      cmp = event['queryStringParameters']['cmp']

        if event.get('queryStringParameters'):
            if event['queryStringParameters'].get('dte'):
                dte = event['queryStringParameters']['dte']
    addExpiry = ""
    dteMap = get_third_fris(int(dte))
    if responseType == 'email':
        for key in dteMap.keys():
            addExpiry = addExpiry + "<th style=\"width:15%\">" + key + "</th>"

    for ticker in tickers:
        tk = yf.Ticker(ticker)
        cmp = tk.info["regularMarketPrice"]
        if responseType == 'email':
            final_data = final_data + "<tr><td class =\"w3-light-grey\">" + ticker + "</td><td class =\"w3-light-grey\">" + str(
                cmp) + "</td>" + processTicker(ticker,
                                               cmp,
                                               dteMap,
                                               responseType) + "</tr>"
        else:
            IVRankList.append(processTicker(ticker, cmp, dteMap, responseType))
            # final_data = "{\"data\":" + json.dumps(IVRankList, cls=OptionsEncoder, indent=4) + "}"


    if responseType == 'email':
        final_data = htmlResponseStart + addExpiry + final_data + htmlResponseEnd
        send_html_email(final_data, recipient, sender)
    else:
        final_data = {
            "statusCode": 200,
            "headers": {},
            "body": json.dumps(IVRankList, cls=OptionsEncoder),
            "isBase64Encoded": False
        }
    print(final_data)
    return final_data


def send_html_email(html, recipient, sender):
    ses_client = boto3.client("ses", region_name="us-east-2")
    CHARSET = "UTF-8"
    pdt = pytz.timezone('America/Los_Angeles')
    datetime_pdt = datetime.now(pdt)

    response = ses_client.send_email(
        Destination={
            "ToAddresses": recipient.split(","),
        },
        Message={
            "Body": {
                "Html": {
                    "Charset": CHARSET,
                    "Data": html,
                }
            },
            "Subject": {
                "Charset": CHARSET,
                "Data": "IV Update at " + datetime_pdt.strftime('%Y-%m-%d %H:%M'),
            },
        },
        Source=sender,
    )

#handler(None, None)

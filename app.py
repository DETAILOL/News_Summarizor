#!/usr/bin/env python
# coding: utf-8


import pandas as pd
import configparser
from zhon.hanzi import punctuation

import requests as rq
from bs4 import BeautifulSoup
from lxml import etree
import spacy
from spacy.lang.en.stop_words import STOP_WORDS
from string import punctuation
from heapq import nlargest

from flask import Flask, request, abort

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, 
    ImageMessage, ImageSendMessage, TemplateSendMessage,
    ButtonsTemplate, MessageTemplateAction, DatetimePickerAction,
    PostbackEvent, PostbackTemplateAction, MessageAction
    )


app = Flask(__name__)
config = configparser.ConfigParser()
config.read('config.txt')

line_bot_api = LineBotApi(config.get('line-bot', 'channel_access_token'))
handler = WebhookHandler(config.get('line-bot', 'channel_secret'))

def summarize(text, per):
    nlp = spacy.load('en_core_web_sm')
    # 分句
    doc = nlp(text)

    # 分詞
    tokens = [token.text for token in doc]

    word_frequencies = {}
    for word in doc:
        if word.text.lower() not in list(STOP_WORDS):
            if word.text.lower() not in punctuation:
                if word.text not in word_frequencies.keys():
                    word_frequencies[word.text] = 1
                else:
                    word_frequencies[word.text] += 1

    max_frequency = max(word_frequencies.values())
    for word in word_frequencies.keys():
        word_frequencies[word] = word_frequencies[word] / max_frequency
    sentence_tokens = [sent for sent in doc.sents]
    sentence_scores = {}
    for sent in sentence_tokens:
        for word in sent:
            if word.text.lower() in word_frequencies.keys():
                if sent not in sentence_scores.keys():                            
                    sentence_scores[sent] = word_frequencies[word.text.lower()]
                else:
                    sentence_scores[sent] += word_frequencies[word.text.lower()]
    select_length = int(len(sentence_tokens) * per)
    summary = nlargest(select_length, sentence_scores, key = sentence_scores.get)
    final_summary = [sent.text for sent in summary]
    summary = ''.join(final_summary)
    
    return summary




@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    print('---------------------')
    print(body)
    print('---------------------')
    

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'
    
@handler.add(MessageEvent, message=TextMessage)
def summarizor(event):

    if '新聞' in event.message.text:
        spacy.cli.download("en_core_web_sm")
        line_bot_api.push_message(
                    event.source.user_id,
                    TextSendMessage(text='等我一下，我要消化一下..')
            )
        # # 擷取每日新聞摘要
        # 新聞主頁
        request = rq.get("https://venturebeat.com/")
        # print(request)
        parse_content = BeautifulSoup(request.text, "lxml")
        # print(parse_content)

        news_df = []
        articles = parse_content.findAll('article')

        for a in articles[:3]:
            if a.select('a')[0].find('h2'):
                news_title = a.select('a')[0].select('h2')[0].text
                print('新聞標題：', news_title)
                news_link = a.select('a')[0]['href']
                print('連結：', news_link)
                
            else:
                news_title = a.select('h2')[0].select('a')[0].text
                print('新聞標題：', news_title)
                news_link = a.select('a')[0]['href']
                print('連結：', news_link)

            response = rq.get(news_link)
            parse_content = response.content.decode()
            html = etree.HTML(parse_content)
            topics = html.xpath("//div[@class='viafoura'][2]//div[@class='vf-topic-follow']//span[@class='vf-topic-name']//text()")
            time = html.xpath("//time//text()")[0]
            author = html.xpath("//div[@class='viafoura'][1]//div[@class='vf-topic-follow']//span[@class='vf-topic-name']//text()")[0]
            contents = html.xpath("//div[@class='article-content']/descendant::text()[not(ancestor::div[contains(@class, 'post-boilerplate boilerplate')]) and not(ancestor::style)]")
            c_list = []
            for c in contents:
                c_list.append(c)
            content = ''.join(c_list)
            
            news_df.append([news_title, topics, time, author, content, news_link])


        news_df = pd.DataFrame(news_df, columns=['Title', 'Topics', 'Time', 'Author', 'Content', 'Link'])
        news_df.insert(6, 'Summary', '')

        for title, content in zip(news_df['Title'], news_df['Content']):
            print('ffffffffffff')
            index = news_df['Title'] == title
            content = content.replace('\n', '').replace('\t', '').replace('\xa0', '')
            summary = summarize(content, 0.1)
            news_df['Summary'][index] = summary

        
        for title, link, summary in zip(news_df['Title'], news_df['Link'], news_df['Summary']):
            print('gggggggggggggg')
            response_text = '新聞標題:{} \n連結:{} \n摘要:{}'.format(title, link, summary)
            
            line_bot_api.push_message(
                    event.source.user_id,
                    TextSendMessage(text=response_text)
            )

if __name__ == "__main__":
    app.run()




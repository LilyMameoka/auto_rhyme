# -*- coding: utf-8 -*-

import MeCab
import jaconv
import sys
import io
import json
import sqlite3
import alkana
import re

conn = sqlite3.connect('wnjpn.db')
input_text = sys.argv[1]

# g2pのみを行う(アクセント記号を揃えることはしない)
# 音素の対応表をロード
with io.open('./g2p_list.json', 'rt') as f:
    g2p_list = json.load(f)
sutegana = ["ァ", "ィ", "ゥ", "ェ", "ォ", "ヮ", "ャ", "ュ", "ョ"]
single_p = ["a", "i", "u", "e", "o", "N", "cl", "pau", "fin", "exc", "que"]

# 半角英字判定
alphaReg = re.compile(r'^[a-zA-Z]+$')
def isalpha(s):
    return alphaReg.match(s) is not None

# 文->名詞を抽出->{index:[単語,ヨミ]}
def mecab_list(text):
    tagger = MeCab.Tagger("-d /usr/local/lib/mecab/dic/unidic")
    tagger.parse('')
    node = tagger.parseToNode(text)
    word_class = {}
    word_index = -1
    while node:
        word = node.surface
        wclass = node.feature.split(',')
        if wclass[0] == '名詞':
            word_index += 1
            if len(wclass) <= 10:
                word_class[word_index] = [word, word]
            else:
                if len(wclass[9]) == 0:
                    word_class[word_index] = [word, word]
                else:
                    word_class[word_index] = [word, wclass[9]]
        node = node.next
    return word_class

# 日本語->ヨミ
def mecab_get_yomi(text):
    tagger = MeCab.Tagger("-d /usr/local/lib/mecab/dic/unidic")
    tagger.parse('')
    node = tagger.parseToNode(text)
    yomi = ''
    while node:
        word = node.surface
        wclass = node.feature.split(',')
        if len(wclass) <= 10:
            yomi += word
        else:
            if len(wclass[9]) == 0:
                yomi += word
            else:
                yomi += wclass[9]
        node = node.next

    yomi = yomi.replace('*', '')
    return yomi

# 次の文字が捨て仮名でない場合
def nonyouon(input_yomi, i, item):
    output_yomi = []
    # 捨て仮名は拗音として出力済
    if item in sutegana:
        pass
    # (通常)
    elif item in g2p_list:
        output_yomi.append(g2p_list[item])
    # 長音符は直前の母音を出力
    elif item == "ー" or item == "〜":
        output_yomi.append(g2p_list[input_yomi[i-1]][-1])
    # 不要な記号
    else:
        output_yomi.append("<unk>")

    return output_yomi

# 捨て仮名の前　且つ　拗音ではない場合
def nonyouon_before_st(i):
    output_yomi = []

    if input_yomi[i] == "ー" or input_yomi[i] == "〜":
        output_yomi.append(g2p_list[input_yomi[i-1]][-1])

    else:
        # 読みの出力
        output_yomi.append(g2p_list[input_yomi[i]])

    return output_yomi

# ヨミ->[音素]
def g2p(input_yomi):
    # 全て全角カタカナに変換
    input_yomi = jaconv.h2z(input_yomi)
    input_yomi = jaconv.hira2kata(input_yomi)

    output_yomi = []

    for i, item in enumerate(input_yomi):

        # 先頭に長音符がきたら読まない
        if i == 0 and (item == "ー" or item == "〜"):
            pass

        # 文字列の、末端で無いとき、次の文字が捨て仮名で無いか確認する
        elif i < len(input_yomi)-1:
            if input_yomi[i+1] in sutegana:
                youon = item+input_yomi[i+1]
                # 拗音の音素を出力
                if youon in g2p_list:
                    output_yomi.append(g2p_list[youon])
                # 拗音ではない場合、通常の仮名の音素を出力
                else:
                    output_yomi += nonyouon_before_st(i)
                    output_yomi += nonyouon_before_st(i+1)
            else:
                output_yomi += nonyouon(input_yomi, i, item)
        # 末端
        else:
            output_yomi += nonyouon(input_yomi, i, item)

    # 音素を出力
    return output_yomi

# 類義語を検索
def search_synonym(word):

    synonym_data = {}
    synonym_data['original'] = word
    synonym_list = []

    # 問い合わせしたい単語がWordnetに存在するか確認する
    cur = conn.execute("select wordid from word where lemma='%s'" % word)
    word_id = 99999999  #temp
    for row in cur:
        word_id = row[0]

    # Wordnetに存在する語であるかの判定
    if word_id==99999999:
        # print("「%s」は、Wordnetに存在しない単語です。" % word)
        synonym_data['synonym'] = 'none'
        return synonym_data
    # else:
        # print("【「%s」の類似語を出力します】\n" % word)

    # 入力された単語を含む概念を検索する
    cur = conn.execute("select synset from sense where wordid='%s'" % word_id)
    synsets = []
    for row in cur:
        synsets.append(row[0])

    # 概念に含まれる単語を検索して画面出力する
    # no = 1
    for synset in synsets:
        cur1 = conn.execute("select name from synset where synset='%s'" % synset)
        # for row1 in cur1:
            # print("%sつめの概念 : %s" %(no, row1[0]))
        cur2 = conn.execute("select def from synset_def where (synset='%s' and lang='jpn')" % synset)
        # sub_no = 1
        # for row2 in cur2:
            # print("意味%s : %s" %(sub_no, row2[0]))
            # sub_no += 1
        cur3 = conn.execute("select wordid from sense where (synset='%s' and wordid!=%s)" % (synset,word_id))
        # sub_no = 1
        for row3 in cur3:
            target_word_id = row3[0]
            cur3_1 = conn.execute("select lemma from word where wordid=%s" % target_word_id)
            for row3_1 in cur3_1:
                # print("類義語%s : %s" % (sub_no, row3_1[0]))
                synonym = row3_1[0]
                if '_' in synonym:
                    continue
                else:
                    if isalpha(synonym):
                        synonym = alkana.get_kana(synonym)
                    if synonym != None:





                        synonym_list.append([synonym, mecab_get_yomi(synonym)])
                # sub_no += 1
        # print("\n")
        # no += 1

    synonym_data['synonym'] = synonym_list

    return synonym_data

# 実行
# text(string)
mecab_data = mecab_list(input_text)

# 基準となる単語
criteria_word = mecab_data[0]
criteria_word.append(g2p(criteria_word[1]))
print(criteria_word)

for key, v in mecab_data.items():
    if key != 0:
        print(search_synonym(v[0]))
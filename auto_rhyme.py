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
vowel = ["a", "i", "u", "e", "o", "N"]

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
def nonyouon_before_st(input_yomi, i):
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
                    output_yomi += nonyouon_before_st(input_yomi, i)
                    output_yomi += nonyouon_before_st(input_yomi, i+1)
            else:
                output_yomi += nonyouon(input_yomi, i, item)
        # 末端
        else:
            output_yomi += nonyouon(input_yomi, i, item)

    output_str = " ".join(output_yomi)
    output_yomi = output_str.split()
    # 音素を出力
    return output_yomi

# 類義語を検索
def search_synonym(word, criteria_vowel_r):

    synonym_data = {}
    synonym_data['original'] = word

    word_yomi = mecab_get_yomi(word)
    word_phoneme = g2p(word_yomi)
    rhyme_pt = 0
    word_phoneme.reverse()
    word_vowel_r = [x for x in word_phoneme if x in vowel]
    for index, p in enumerate(criteria_vowel_r):
        if p == word_vowel_r[index]:
            rhyme_pt += 1
        else:
            break

    synonym_best = {
        'word': word,
        'rhyme_pt': rhyme_pt
    }

    # 問い合わせしたい単語がWordnetに存在するか確認する
    cur = conn.execute("select wordid from word where lemma='%s'" % word)
    word_id = 99999999  #temp
    for row in cur:
        word_id = row[0]

    # Wordnetに存在する語であるかの判定
    if word_id==99999999:
        synonym_data['synonym'] = synonym_best
        return synonym_data

    # 入力された単語を含む概念を検索する
    cur = conn.execute("select synset from sense where wordid='%s'" % word_id)
    synsets = []
    for row in cur:
        synsets.append(row[0])

    # 概念に含まれる単語を検索して画面出力する
    for synset in synsets:
        cur3 = conn.execute("select wordid from sense where (synset='%s' and wordid!=%s)" % (synset,word_id))
        for row3 in cur3:
            target_word_id = row3[0]
            cur3_1 = conn.execute("select lemma from word where wordid=%s" % target_word_id)
            for row3_1 in cur3_1:
                synonym = row3_1[0]
                if '_' in synonym:
                    continue
                else:
                    if isalpha(synonym):
                        synonym = alkana.get_kana(synonym)
                    if synonym != None:
                        synonym_yomi = mecab_get_yomi(synonym)
                        synonym_phoneme = g2p(synonym_yomi)
                        if '<unk>' in synonym_phoneme:
                            continue
                        else:
                            rhyme_pt = 0
                            # 音素を逆順にする
                            synonym_phoneme.reverse()

                            synonym_vowel_r = [x for x in synonym_phoneme if x in vowel]

                            for index in range(min(len(criteria_vowel_r), len(synonym_vowel_r))):
                                if criteria_vowel_r[index] == synonym_vowel_r[index]:
                                    rhyme_pt += 1
                                else:
                                    break

                            if rhyme_pt > synonym_best['rhyme_pt']:
                                synonym_best = {
                                    'word': synonym,
                                    'rhyme_pt': rhyme_pt
                                }

    synonym_data['synonym'] = synonym_best

    return synonym_data

# 実行
# text(string)
mecab_data = mecab_list(input_text)

recomend = ''
best_rhyme_pt_sum = 0

for criteria_word_index, criteria_word in mecab_data.items():
    # 基準となる単語の設定
    criteria_word.append(g2p(criteria_word[1]))
    criteria_phoneme = criteria_word[2]
    criteria_phoneme.reverse()
    criteria_vowel_r = [y for y in criteria_phoneme if y in vowel]

    rhyme_pt_sum = 0

    for key, v in mecab_data.items():
        if key != criteria_word_index:
            result = search_synonym(v[0], criteria_vowel_r)
            rhyme_pt_sum += result['synonym']['rhyme_pt']
            input_text_replaced = input_text.replace(v[0], result['synonym']['word'])

    if best_rhyme_pt_sum <= rhyme_pt_sum:
        best_rhyme_pt_sum = rhyme_pt_sum
        recomend = input_text_replaced

print(recomend)
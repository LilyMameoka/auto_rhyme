# -*- coding: utf-8 -*-

import MeCab
import jaconv
import sys

def mecab_list(text):
    tagger = MeCab.Tagger("-d /usr/local/lib/mecab/dic/unidic")
    tagger.parse('')
    node = tagger.parseToNode(text)
    word_class = ""
    while node:
        word = node.surface
        wclass = node.feature.split(',')
        if wclass[0] != '名詞':
          if len(wclass) <= 10:
            word_class += word
          else:
            if len(wclass[9]) == 0 :
              word_class += word
            elif len(word) != len(wclass[9]):
              word_class += word
            else:
              word_class += wclass[9]
        node = node.next
    return word_class

# text(string)
input_data = sys.argv[1]

# get pron
mecab_data = mecab_list(input_text)
mecab_data = mecab_data.replace('\n', '')
mecab_data = mecab_data.replace('[', '')
mecab_data = mecab_data.replace(']', '')

print(mecab_data)
# -*- coding:utf-8 -*-

import sqlite3

conn = sqlite3.connect('wnjpn.db')

cur = conn.execute("select name from sqlite_master where type='table'")
for row in cur:
  print(row)
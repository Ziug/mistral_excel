# db.py
import sqlite3

conn = sqlite3.connect(":memory:")
is_sql = False
columns = []
parsed_pd = None
col_uniques={}

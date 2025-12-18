import sqlite3, os, sys
path = 'database/movies.db'
print('path', os.path.abspath(path))
print('exists', os.path.exists(path))
if not os.path.exists(path):
    sys.exit(0)
print('size', os.path.getsize(path))
con = sqlite3.connect(path)
cur = con.cursor()
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('tables', tables)
for tbl in ['movies','users','payments','subscriptions','channels']:
    try:
        cnt = cur.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
        print(tbl, cnt)
    except Exception as e:
        print(tbl, 'error', e)
con.close()

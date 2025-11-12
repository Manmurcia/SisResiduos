import pymysql.cursors

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='',   # pon tu contraseña si tienes
    db='siger',
    cursorclass=pymysql.cursors.DictCursor
)

with conn:
    with conn.cursor() as cur:
        cur.execute('SHOW COLUMNS FROM contenedores')
        rows = cur.fetchall()
        for r in rows:
            print(r)
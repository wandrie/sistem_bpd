import pymysql

try:
    conn = pymysql.connect(
        host='127.0.0.1',
        user='root',
        password='',
        database='sistem_bpd',
        port=3306
    )
    cur = conn.cursor()
    cur.execute("SELECT 1")
    print("✅ Koneksi ke database BERHASIL (dari skrip tes manual)!")
    conn.close()
except Exception as e:
    print("❌ Gagal koneksi:", e)

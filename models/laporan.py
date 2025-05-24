from datetime import datetime
from typing import List, Dict
from .transaksi import TransaksiKeuangan  # Import model transaksi

class LaporanKeuangan:
    @staticmethod
    def generate_arus_kas(tahun: int = None) -> List[Dict]:
        """
        Hasilkan laporan arus kas bulanan
        Args:
            tahun (int): Tahun laporan (jika None, ambil tahun berjalan)
        Returns:
            List[Dict]: Data dalam format:
                [{
                    'tahun': 2025,
                    'bulan': 1,
                    'penerimaan': 10000000,
                    'pengeluaran': 5000000,
                    'saldo': 5000000
                }, ...]
        """
        from app import get_db_connection  # Import lokal untuk hindari circular import
        
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        
        query = """
            SELECT 
                YEAR(tanggal) AS tahun,
                MONTH(tanggal) AS bulan,
                SUM(CASE WHEN jenis='penerimaan' THEN jumlah ELSE 0 END) AS penerimaan,
                SUM(CASE WHEN jenis='pengeluaran' THEN jumlah ELSE 0 END) AS pengeluaran
            FROM bpd_laporan_keuangan
            WHERE %s IS NULL OR YEAR(tanggal) = %s
            GROUP BY YEAR(tanggal), MONTH(tanggal)
            ORDER BY tahun, bulan
        """
        cur.execute(query, (tahun, tahun))
        hasil = cur.fetchall()
        
        # Hitung saldo berjalan
        saldo = 0
        for item in hasil:
            saldo += item['penerimaan'] - item['pengeluaran']
            item['saldo'] = saldo
        
        cur.close()
        conn.close()
        return hasil

    @staticmethod
    def generate_per_kategori() -> List[Dict]:
        """Hasilkan laporan keuangan per kategori"""
        from app import get_db_connection
        
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        
        cur.execute("""
            SELECT 
                kategori,
                SUM(CASE WHEN jenis='penerimaan' THEN jumlah ELSE 0 END) AS penerimaan,
                SUM(CASE WHEN jenis='pengeluaran' THEN jumlah ELSE 0 END) AS pengeluaran,
                SUM(CASE WHEN jenis='penerimaan' THEN jumlah ELSE -jumlah END) AS netto
            FROM bpd_laporan_keuangan
            GROUP BY kategori
            ORDER BY kategori
        """)
        
        hasil = cur.fetchall()
        cur.close()
        conn.close()
        return hasil
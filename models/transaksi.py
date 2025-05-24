class TransaksiKeuangan:
    def __init__(self, tanggal, jenis, keterangan, jumlah, referensi):
        self.tanggal = tanggal
        self.jenis = jenis  # 'penerimaan' atau 'pengeluaran'
        self.keterangan = keterangan
        self.jumlah = jumlah
        self.referensi = referensi  # No bukti/kode transaksi
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Transaksi(db.Model):
    __tablename__ = 'bpd_laporan_keuangan'
    
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.Date, nullable=False)
    referensi = db.Column(db.String(50))
    keterangan = db.Column(db.String(200), nullable=False)
    jenis = db.Column(db.String(20), nullable=False)  # 'penerimaan' atau 'pengeluaran'
    jumlah = db.Column(db.Numeric(15,2), nullable=False)
    file_laporan = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Transaksi {self.id} - {self.keterangan}>'
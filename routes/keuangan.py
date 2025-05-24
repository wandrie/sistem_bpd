from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, abort
from flask_login import login_required, current_user
import pymysql
from werkzeug.utils import secure_filename
from datetime import datetime
import os

# Buat Blueprint untuk modul keuangan
bp = Blueprint('keuangan', __name__, url_prefix='/keuangan')

# Helper function untuk mendapatkan koneksi DB (dari app.py)
def get_db_connection():
    try:
        conn = pymysql.connect(
            host=current_app.config['MYSQL_HOST'],
            user=current_app.config['MYSQL_USER'],
            password=current_app.config['MYSQL_PASSWORD'],
            database=current_app.config['MYSQL_DB'],
            port=current_app.config['MYSQL_PORT'],
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        flash('Terjadi kesalahan koneksi database.', 'danger')
        return None

# Fungsi untuk mengunduh file
@bp.route('/download/<string:jenis>/<path:filename>')
def download_file(jenis, filename):
    if jenis == 'keuangan':
        upload_folder = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'keuangan')
    else:
        abort(404) # Not found if category is not 'keuangan'

    try:
        return send_from_directory(upload_folder, filename, as_attachment=True)
    except FileNotFoundError:
        flash('File tidak ditemukan.', 'danger')
        abort(404)

# Rute untuk menampilkan buku besar keuangan
@bp.route('/')
@login_required
def keuangan():
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('dashboard')) # Atau halaman error lain

    cur = conn.cursor()
    
    # Ambil semua transaksi dari bpd_laporan_keuangan
    cur.execute("SELECT id, tanggal, referensi, keterangan, jenis, jumlah, file_laporan FROM bpd_laporan_keuangan ORDER BY tanggal DESC")
    transaksi_list = cur.fetchall()

    # Hitung total penerimaan dan pengeluaran
    total_penerimaan = 0
    total_pengeluaran = 0
    for t in transaksi_list:
        if t['jenis'] == 'penerimaan':
            total_penerimaan += t['jumlah']
        elif t['jenis'] == 'pengeluaran':
            total_pengeluaran += t['jumlah']

    # --- PERUBAHAN DI SINI: Hitung saldo_awal (sebagai saldo bersih) ---
    saldo_awal = total_penerimaan - total_pengeluaran

    cur.close()
    conn.close()
    
    return render_template('administrasi/keuangan.html', # Path template yang disesuaikan
                           transaksi_list=transaksi_list,
                           total_penerimaan=total_penerimaan,
                           total_pengeluaran=total_pengeluaran,
                           saldo_awal=saldo_awal) # Variabel saldo_awal ditambahkan dan dilewatkan

# Rute untuk menambah transaksi
@bp.route('/tambah', methods=['POST'])
@login_required
def tambah_transaksi():
    if request.method == 'POST':
        tanggal = request.form['tanggal']
        referensi = request.form['referensi']
        keterangan = request.form['keterangan']
        jenis = request.form['jenis']
        jumlah = request.form['jumlah']
        file_bukti = request.files.get('bukti') # Menggunakan 'bukti' sesuai tambah.html

        nama_file = None
        if file_bukti and file_bukti.filename:
            # Pastikan folder upload ada
            upload_dir = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'keuangan')
            os.makedirs(upload_dir, exist_ok=True)
            
            filename_secure = secure_filename(file_bukti.filename)
            nama_file = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename_secure}"
            file_bukti.save(os.path.join(upload_dir, nama_file))

        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('keuangan.keuangan')) # Kembali ke halaman keuangan jika DB error

        cur = conn.cursor()
        try:
            # SQL INSERT statement yang diperbaiki untuk bpd_laporan_keuangan
            cur.execute("""
                INSERT INTO bpd_laporan_keuangan (tanggal, referensi, keterangan, jenis, jumlah, file_laporan, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (tanggal, referensi, keterangan, jenis, jumlah, nama_file, current_user.id))
            
            # Mendapatkan ID dari baris yang baru dimasukkan (MariaDB/MySQL)
            new_transaction_id = cur.lastrowid 
            
            conn.commit()
            flash('Transaksi berhasil ditambahkan!', 'success')
        except pymysql.Error as e:
            flash(f'Gagal menambah transaksi: {e}', 'danger')
            current_app.logger.error(f"Error adding transaction: {e}") # Log error untuk debugging
            conn.rollback() # Rollback jika ada error
        finally:
            cur.close()
            conn.close()
        
        return redirect(url_for('keuangan.keuangan'))
    
    # Jika metode bukan POST (misal langsung akses /keuangan/tambah), redirect
    return redirect(url_for('keuangan.keuangan'))


# Rute untuk mengedit transaksi
@bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_transaksi(id):
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('keuangan.keuangan')) # Kembali ke halaman keuangan jika DB error
    cur = conn.cursor()

    if request.method == 'POST':
        tanggal = request.form['tanggal']
        referensi = request.form['referensi']
        keterangan = request.form['keterangan']
        jenis = request.form['jenis']
        jumlah = request.form['jumlah']
        file_laporan_baru = request.files.get('file_laporan')

        # Dapatkan nama file lama (jika ada) dari bpd_laporan_keuangan
        cur.execute("SELECT file_laporan FROM bpd_laporan_keuangan WHERE id = %s", [id])
        old_file_data = cur.fetchone()
        old_file_name = old_file_data['file_laporan'] if old_file_data else None
        
        file_to_save = old_file_name # Default: tetap menggunakan file lama

        if file_laporan_baru and file_laporan_baru.filename:
            # Hapus file lama jika ada
            if old_file_name:
                old_file_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'keuangan', old_file_name)
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)

            # Simpan file baru
            upload_dir = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'keuangan')
            os.makedirs(upload_dir, exist_ok=True)
            
            filename_secure = secure_filename(file_laporan_baru.filename)
            file_to_save = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename_secure}"
            file_laporan_baru.save(os.path.join(upload_dir, file_to_save))

        try:
            # UPDATE statement untuk bpd_laporan_keuangan
            cur.execute("""
                UPDATE bpd_laporan_keuangan
                SET tanggal = %s, referensi = %s, keterangan = %s, jenis = %s, jumlah = %s, file_laporan = %s
                WHERE id = %s AND user_id = %s
            """, (tanggal, referensi, keterangan, jenis, jumlah, file_to_save, id, current_user.id))
            conn.commit()
            flash('Transaksi berhasil diperbarui!', 'success')
        except pymysql.Error as e:
            flash(f'Gagal memperbarui transaksi: {e}', 'danger')
            current_app.logger.error(f"Error updating transaction: {e}") # Log error
            conn.rollback()
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('keuangan.keuangan'))
    
    else: # GET request
        # SELECT statement untuk bpd_laporan_keuangan
        cur.execute("SELECT * FROM bpd_laporan_keuangan WHERE id = %s AND user_id = %s", (id, current_user.id))
        transaksi = cur.fetchone()
        cur.close()
        conn.close()

        if transaksi is None:
            flash('Transaksi tidak ditemukan atau Anda tidak memiliki izin untuk mengeditnya.', 'danger')
            return redirect(url_for('keuangan.keuangan'))
        
        # Asumsi edit_transaksi.html TIDAK berada di 'administrasi/'
        return render_template('edit_transaksi.html', transaksi=transaksi)

# Rute untuk menghapus transaksi
@bp.route('/hapus/<int:id>', methods=['POST'])
@login_required
def hapus_transaksi(id):
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('keuangan.keuangan'))
    
    cur = conn.cursor()
    try:
        # Ambil nama file sebelum menghapus entri dari DB
        cur.execute("SELECT file_laporan FROM bpd_laporan_keuangan WHERE id = %s AND user_id = %s", (id, current_user.id))
        data = cur.fetchone()
        
        if data and data['file_laporan']:
            file_path = os.path.join(current_app.root_path, current_app.config['UPLOAD_FOLDER'], 'keuangan', data['file_laporan'])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # DELETE statement untuk bpd_laporan_keuangan
        cur.execute("DELETE FROM bpd_laporan_keuangan WHERE id = %s AND user_id = %s", (id, current_user.id))
        conn.commit()
        flash('Transaksi berhasil dihapus!', 'success')
    except pymysql.Error as e:
        flash(f'Gagal menghapus transaksi: {e}', 'danger')
        current_app.logger.error(f"Error deleting transaction: {e}") # Log error
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('keuangan.keuangan'))
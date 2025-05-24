from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, abort, make_response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pymysql
from werkzeug.utils import secure_filename
from datetime import datetime
import io
import os
import config
import uuid # Import uuid for unique filenames
import time # Import time for unique filenames in keuangan

# Import ReportLab components
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors # PASTIKAN BARIS INI ADA DAN BENAR!

# Import blueprint laporan_bp (asumsi ada di routes/keuangan.py)
from routes.keuangan import bp as laporan_bp

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.register_blueprint(laporan_bp)

# Konfigurasi MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'sistem_bpd'
app.config['MYSQL_PORT'] = 3306
app.config['MYSQL_CURSORCLASS'] = 'DictCursor' # Menggunakan DictCursor agar hasil query berupa dictionary

def get_db_connection():
    """Membangun koneksi ke database MySQL."""
    try:
        conn = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB'],
            port=app.config['MYSQL_PORT'],
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except pymysql.MySQLError as e:
        app.logger.error(f"Error saat terhubung ke database: {e}")
        flash("Terjadi kesalahan pada database. Silakan coba lagi nanti.", "danger")
        return None

# Konfigurasi Upload
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    """Memeriksa apakah ekstensi file diizinkan."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    """Model pengguna untuk Flask-Login."""
    def __init__(self, user_data):
        self.id = user_data['id']
        self.email = user_data['email']
        self.nama = user_data['nama']
        self.role = user_data['role']
        self.foto_profil = user_data.get('foto_profil')

@login_manager.user_loader
def load_user(user_id):
    """Memuat pengguna dari ID untuk Flask-Login."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bpd_users WHERE id = %s", [user_id])
            user_data = cur.fetchone()
            if user_data:
                return User(user_data)
            return None
        except pymysql.MySQLError as e:
            app.logger.error(f"Error saat mengambil data user: {e}")
            flash("Terjadi kesalahan pada database.", "danger")
            return None
        finally:
            if conn: # Pastikan koneksi ditutup hanya jika berhasil dibuka
                cur.close()
                conn.close()
    return None

@app.before_request
def check_db_connection():
    """Memeriksa koneksi database sebelum setiap permintaan."""
    if not hasattr(app, 'db_checked'):
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
            except pymysql.MySQLError as e:
                app.logger.error(f"Error saat pengecekan koneksi database: {e}")
                flash("Terjadi kesalahan pada database. Silakan coba lagi nanti.", "danger")
            finally:
                if conn: # Pastikan koneksi ditutup hanya jika berhasil dibuka
                    conn.close()
        app.db_checked = True

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Menangani proses login pengguna."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("SELECT * FROM bpd_users WHERE email = %s", (email,))
                user_data = cur.fetchone()
                cur.close()

                if user_data and user_data['password'] == password:  # Gunakan hashing di production!
                    user = User(user_data)
                    login_user(user)
                    session['logged_in'] = True
                    session['user_id'] = user.id
                    session['user_role'] = user.role
                    flash('Login berhasil!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Email atau password salah!', 'danger')
            except pymysql.MySQLError as e:
                flash(f'Error sistem: {str(e)}', 'danger')
                app.logger.error(f"Login error: {str(e)}")
            finally:
                if conn: # Pastikan koneksi ditutup hanya jika berhasil dibuka
                    conn.close()
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    """Menangani proses logout pengguna."""
    logout_user()
    session.clear()
    flash('Anda telah logout', 'info')
    return redirect(url_for('login'))

@app.context_processor
def inject_user():
    """Menyuntikkan objek pengguna saat ini ke semua template."""
    return {'current_user': current_user}

# Rute Dashboard
@app.route('/')
@login_required
def dashboard():
    """Menampilkan halaman dashboard dengan ringkasan data."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Jumlah anggota
            cur.execute("SELECT COUNT(*) as total FROM bpd_anggota")
            total_anggota = cur.fetchone()['total']

            # Jumlah kegiatan
            cur.execute("SELECT COUNT(*) as total FROM bpd_kegiatan")
            total_kegiatan = cur.fetchone()['total']

            # Jumlah surat masuk
            cur.execute("SELECT COUNT(*) as total FROM bpd_surat_masuk")
            total_surat_masuk = cur.fetchone()['total']

            # Jumlah surat keluar
            cur.execute("SELECT COUNT(*) as total FROM bpd_surat_keluar")
            total_surat_keluar = cur.fetchone()['total']

            # Kegiatan terbaru
            cur.execute("SELECT * FROM bpd_kegiatan ORDER BY tanggal DESC LIMIT 5")
            kegiatan_terbaru = cur.fetchall()
            cur.close()

            return render_template('dashboard.html',
                                 total_anggota=total_anggota,
                                 total_kegiatan=total_kegiatan,
                                 total_surat_masuk=total_surat_masuk,
                                 total_surat_keluar=total_surat_keluar,
                                 kegiatan_terbaru=kegiatan_terbaru)
        except pymysql.MySQLError as e:
            flash(f"Error database: {e}", "danger")
            app.logger.error(f"DB error di dashboard: {e}")
            return render_template('dashboard.html',
                                 total_anggota=0,
                                 total_kegiatan=0,
                                 total_surat_masuk=0,
                                 total_surat_keluar=0,
                                 kegiatan_terbaru=[])
        finally:
            if conn:
                conn.close()
    else:
         return render_template('dashboard.html',
                                 total_anggota=0,
                                 total_kegiatan=0,
                                 total_surat_masuk=0,
                                 total_surat_keluar=0,
                                 kegiatan_terbaru=[])

# Rute Profil
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Menampilkan dan memperbarui profil pengguna."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            if request.method == 'POST':
                nama = request.form['nama']
                email = request.form['email']
                password = request.form.get('password', None)
                
                # Handle upload foto profil
                foto_profil = None
                if 'foto_profil' in request.files:
                    file = request.files['foto_profil']
                    if file and allowed_file(file.filename):
                        try:
                            # Hapus foto lama jika ada
                            cur.execute("SELECT foto_profil FROM bpd_users WHERE id = %s", [current_user.id])
                            user = cur.fetchone()
                            if user and user['foto_profil']:
                                old_file = os.path.join(app.config['UPLOAD_FOLDER'], 'profil', user['foto_profil'])
                                if os.path.exists(old_file):
                                    os.remove(old_file)
                            
                            # Simpan file baru
                            filename = secure_filename(f"user_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profil'), exist_ok=True)
                            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profil', filename)
                            file.save(filepath)
                            foto_profil = filename # Simpan hanya nama file, karena folder 'profil' sudah di hardcode di sini
                        except Exception as e:
                            app.logger.error(f"Error saat mengupload foto profil: {e}")
                            flash("Gagal mengupload foto profil", "danger")

                # Update data user
                update_fields = []
                update_values = []
                
                if nama:
                    update_fields.append("nama=%s")
                    update_values.append(nama)
                
                if email:
                    update_fields.append("email=%s")
                    update_values.append(email)
                
                if password:
                    update_fields.append("password=%s")
                    update_values.append(password)
                
                if foto_profil:
                    update_fields.append("foto_profil=%s")
                    update_values.append(foto_profil)
                
                if update_fields:
                    update_values.append(current_user.id)
                    query = f"UPDATE bpd_users SET {', '.join(update_fields)} WHERE id=%s"
                    cur.execute(query, update_values)
                    conn.commit()
                    flash('Profil berhasil diperbarui!', 'success')

            # GET request
            cur.execute("SELECT * FROM bpd_users WHERE id=%s", [current_user.id])
            user_data = cur.fetchone()
            cur.close()
            return render_template('profile.html', user=user_data)
            
        except pymysql.MySQLError as e:
            flash(f"Error saat mengakses/update profil: {e}", "danger")
            app.logger.error(f"DB error di profile: {e}")
            return render_template('profile.html', user=None)
        finally:
            if conn:
                conn.close()
    else:
        return render_template('profile.html', user=None)
    
# Rute Anggota BPD
@app.route('/anggota')
@login_required
def anggota():
    """Menampilkan daftar anggota BPD."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bpd_anggota")
            anggota = cur.fetchall()
            cur.close()
            return render_template('anggota/index.html', anggota=anggota)
        except pymysql.MySQLError as e:
            flash(f"Error database: {e}", "danger")
            app.logger.error(f"DB error di anggota: {e}")
            return render_template('anggota/index.html', anggota=[])
        finally:
            if conn:
                conn.close()
    else:
        return render_template('anggota/index.html', anggota=[])

@app.route('/anggota/tambah', methods=['GET', 'POST'])
@login_required
def tambah_anggota():
    """Menambah anggota BPD baru."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nama = request.form['nama']
        jabatan = request.form['jabatan']
        alamat = request.form['alamat']
        telepon = request.form['telepon']
        email = request.form['email']

        # Upload foto
        foto = None
        if 'foto' in request.files:
            file = request.files['foto']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'anggota')
                os.makedirs(upload_path, exist_ok=True)
                filepath = os.path.join(upload_path, filename)
                file.save(filepath)
                foto = f"anggota/{filename}" # Simpan path relatif ke UPLOAD_FOLDER
                print(f"DEBUG: Foto anggota disimpan di: {filepath}, DB value: {foto}") # Debugging
        
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("INSERT INTO bpd_anggota (nama, jabatan, alamat, telepon, email, foto) VALUES (%s, %s, %s, %s, %s, %s)",
                           (nama, jabatan, alamat, telepon, email, foto))
                conn.commit()
                flash('Anggota berhasil ditambahkan!', 'success')
                return redirect(url_for('anggota'))
            except pymysql.MySQLError as e:
                flash(f"Error saat menambah anggota: {e}", "danger")
                app.logger.error(f"DB error di tambah_anggota: {e}")
                return render_template('anggota/form.html', mode='tambah') # Atau tampilkan form dengan pesan error
            finally:
                if conn:
                    cur.close()
                    conn.close()
        else:
             return render_template('anggota/form.html', mode='tambah')

    return render_template('anggota/form.html', mode='tambah')


@app.route('/anggota/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_anggota(id):
    """Mengedit data anggota BPD."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            if request.method == 'POST':
                nama = request.form['nama']
                jabatan = request.form['jabatan']
                alamat = request.form['alamat']
                telepon = request.form['telepon']
                email = request.form['email']

                foto = None
                update_foto = False

                # Cek apakah ada file baru diupload
                if 'foto' in request.files:
                    file = request.files['foto']
                    if file and allowed_file(file.filename):
                        update_foto = True
                        # Hapus foto lama jika ada
                        cur.execute("SELECT foto FROM bpd_anggota WHERE id = %s", [id])
                        anggota_lama = cur.fetchone()
                        if anggota_lama and anggota_lama['foto']:
                            old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], anggota_lama['foto'])
                            if os.path.exists(old_file_path):
                                os.remove(old_file_path)

                        # Simpan foto baru
                        filename = secure_filename(file.filename)
                        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], 'anggota')
                        os.makedirs(upload_path, exist_ok=True)
                        filepath = os.path.join(upload_path, filename)
                        file.save(filepath)
                        foto = f"anggota/{filename}" # Simpan path relatif ke UPLOAD_FOLDER
                        print(f"DEBUG: Foto anggota baru disimpan di: {filepath}, DB value: {foto}") # Debugging
                
                # Bangun query update secara dinamis
                update_fields = []
                update_values = []
                
                update_fields.append("nama=%s")
                update_values.append(nama)
                update_fields.append("jabatan=%s")
                update_values.append(jabatan)
                update_fields.append("alamat=%s")
                update_values.append(alamat)
                update_fields.append("telepon=%s")
                update_values.append(telepon)
                update_fields.append("email=%s")
                update_values.append(email)

                if update_foto:
                    update_fields.append("foto=%s")
                    update_values.append(foto)

                update_values.append(id) # ID untuk klausa WHERE
                
                query = f"UPDATE bpd_anggota SET {', '.join(update_fields)} WHERE id=%s"
                cur.execute(query, update_values)
                conn.commit()
                
                flash('Data anggota berhasil diperbarui!', 'success')
                return redirect(url_for('anggota'))

            # GET request
            cur.execute("SELECT * FROM bpd_anggota WHERE id = %s", [id])
            anggota = cur.fetchone()
            cur.close()

            if not anggota:
                flash('Anggota tidak ditemukan!', 'danger')
                return redirect(url_for('anggota'))

            return render_template('anggota/form.html', mode='edit', anggota=anggota)
        except pymysql.MySQLError as e:
            flash(f"Error saat mengedit anggota: {e}", "danger")
            app.logger.error(f"DB error di edit_anggota: {e}")
            return redirect(url_for('anggota'))
        finally:
            if conn:
                conn.close()
    else:
        return redirect(url_for('anggota'))


@app.route('/anggota/hapus/<int:id>')
@login_required
def hapus_anggota(id):
    """Menghapus anggota BPD."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Hapus foto jika ada
            cur.execute("SELECT foto FROM bpd_anggota WHERE id = %s", [id])
            anggota = cur.fetchone()
            if anggota and anggota['foto']: # Pastikan anggota ada dan memiliki foto
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], anggota['foto']) # Path sudah relatif
                if os.path.exists(filepath):
                    os.remove(filepath)

            # Hapus data dari database
            cur.execute("DELETE FROM bpd_anggota WHERE id = %s", [id])
            conn.commit()
            cur.close()

            flash('Anggota berhasil dihapus!', 'success')
            return redirect(url_for('anggota'))
        except pymysql.MySQLError as e:
            flash(f"Error saat menghapus anggota: {e}", "danger")
            app.logger.error(f"DB error di hapus_anggota: {e}")
            return redirect(url_for('anggota'))
        finally:
            if conn:
                conn.close()
    else:
        return redirect(url_for('anggota'))


# Rute Kegiatan BPD
@app.route('/kegiatan')
@login_required
def kegiatan():
    """Menampilkan daftar kegiatan BPD."""
    # Perbaikan: Tidak perlu cek session['logged_in'] lagi karena sudah ada @login_required
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bpd_kegiatan ORDER BY tanggal DESC")
            kegiatan = cur.fetchall()
            cur.close()
            return render_template('kegiatan/index.html', kegiatan=kegiatan)
        except pymysql.MySQLError as e:
            flash(f"Error database: {e}", "danger")
            app.logger.error(f"DB error di kegiatan: {e}")
            return render_template('kegiatan/index.html', kegiatan=[]) # Return []
        finally:
            if conn:
                conn.close()
    else:
        return render_template('kegiatan/index.html', kegiatan=[])


@app.route('/kegiatan/tambah', methods=['GET', 'POST'])
@login_required
def tambah_kegiatan():
    """Menambah kegiatan BPD baru."""
    if request.method == 'POST':
        tanggal = request.form.get('tanggal')
        waktu = request.form.get('waktu')
        jenis = request.form.get('jenis')
        judul = request.form.get('judul')
        deskripsi = request.form.get('deskripsi')
        tempat = request.form.get('tempat')
        file_dokumentasi = request.files.get('dokumentasi')
        file_notulen = request.files.get('notulen')

        # Validasi wajib
        if not all([tanggal, waktu, jenis, judul, deskripsi, tempat]):
            flash('Semua kolom wajib diisi: Tanggal, Waktu, Jenis, Judul, Deskripsi, dan Tempat.', 'danger')
            return redirect(url_for('kegiatan'))

        # Upload dokumentasi
        dokumentasi_filename = None
        if file_dokumentasi and file_dokumentasi.filename and allowed_file(file_dokumentasi.filename):
            upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'kegiatan')
            os.makedirs(upload_dir, exist_ok=True)
            secure_name = secure_filename(file_dokumentasi.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_doc_{secure_name}"
            full_path = os.path.join(upload_dir, unique_filename)
            file_dokumentasi.save(full_path)
            dokumentasi_filename = f"kegiatan/{unique_filename}" # <-- SIMPAN PATH RELATIF KE UPLOAD_FOLDER
            print(f"DEBUG: Dokumentasi disimpan di: {full_path}, DB value: {dokumentasi_filename}") # Debugging

        # Upload notulen
        notulen_filename = None
        if file_notulen and file_notulen.filename and allowed_file(file_notulen.filename):
            upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'kegiatan')
            os.makedirs(upload_dir, exist_ok=True)
            secure_name = secure_filename(file_notulen.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_notulen_{secure_name}"
            full_path = os.path.join(upload_dir, unique_filename)
            file_notulen.save(full_path)
            notulen_filename = f"kegiatan/{unique_filename}" # <-- SIMPAN PATH RELATIF KE UPLOAD_FOLDER
            print(f"DEBUG: Notulen disimpan di: {full_path}, DB value: {notulen_filename}") # Debugging

        # Simpan ke database
        conn = get_db_connection()
        if conn is None:
            flash('Gagal terhubung ke database.', 'danger')
            return redirect(url_for('kegiatan'))

        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO bpd_kegiatan 
                (jenis, judul, deskripsi, tempat, tanggal, waktu, dokumentasi, notulen)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (jenis, judul, deskripsi, tempat, tanggal, waktu, dokumentasi_filename, notulen_filename))
            conn.commit()
            flash('Kegiatan berhasil ditambahkan!', 'success')
        except pymysql.Error as e:
            flash(f'Gagal menambah kegiatan: {e}', 'danger')
            app.logger.error(f"Error adding kegiatan: {e}")
            conn.rollback()
        finally:
            if conn:
                cur.close()
                conn.close()
        return redirect(url_for('kegiatan'))

    return render_template('kegiatan/form.html', mode='tambah')

@app.route('/kegiatan/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_kegiatan(id):
    """Mengedit data kegiatan BPD."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            if request.method == 'POST':
                jenis = request.form['jenis']
                judul = request.form['judul']
                deskripsi = request.form['deskripsi']
                tempat = request.form['tempat']
                tanggal = request.form['tanggal']
                waktu = request.form['waktu']

                update_fields = []
                update_values = []

                update_fields.append("jenis=%s")
                update_values.append(jenis)
                update_fields.append("judul=%s")
                update_values.append(judul)
                update_fields.append("deskripsi=%s")
                update_values.append(deskripsi)
                update_fields.append("tempat=%s")
                update_values.append(tempat)
                update_fields.append("tanggal=%s")
                update_values.append(tanggal)
                update_fields.append("waktu=%s")
                update_values.append(waktu)

                # Handle dokumentasi
                if 'dokumentasi' in request.files:
                    file = request.files['dokumentasi']
                    if file and file.filename and allowed_file(file.filename):
                        # Hapus file lama jika ada
                        cur.execute("SELECT dokumentasi FROM bpd_kegiatan WHERE id = %s", [id])
                        kegiatan_lama = cur.fetchone()
                        if kegiatan_lama and kegiatan_lama['dokumentasi']:
                            old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], kegiatan_lama['dokumentasi'])
                            if os.path.exists(old_file_path):
                                os.remove(old_file_path)

                        # Simpan file baru
                        secure_name = secure_filename(file.filename)
                        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_doc_{secure_name}"
                        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'kegiatan')
                        os.makedirs(upload_dir, exist_ok=True) # Pastikan folder ada
                        full_path = os.path.join(upload_dir, unique_filename)
                        file.save(full_path)
                        
                        dokumentasi_filename_db = f"kegiatan/{unique_filename}" # <-- SIMPAN PATH RELATIF
                        update_fields.append("dokumentasi=%s")
                        update_values.append(dokumentasi_filename_db)
                        print(f"DEBUG: Dokumentasi diupdate ke: {full_path}, DB value: {dokumentasi_filename_db}") # Debugging
                    elif not file.filename: # Jika input file kosong (user tidak upload file baru)
                        # Jangan update kolom dokumentasi, biarkan nilai lama
                        pass
                
                # Handle notulen
                if 'notulen' in request.files:
                    file = request.files['notulen']
                    if file and file.filename and allowed_file(file.filename):
                        # Hapus file lama jika ada
                        cur.execute("SELECT notulen FROM bpd_kegiatan WHERE id = %s", [id])
                        kegiatan_lama = cur.fetchone()
                        if kegiatan_lama and kegiatan_lama['notulen']:
                            old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], kegiatan_lama['notulen'])
                            if os.path.exists(old_file_path):
                                os.remove(old_file_path)

                        # Simpan file baru
                        secure_name = secure_filename(file.filename)
                        unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_notulen_{secure_name}"
                        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'kegiatan')
                        os.makedirs(upload_dir, exist_ok=True) # Pastikan folder ada
                        full_path = os.path.join(upload_dir, unique_filename)
                        file.save(full_path)
                        
                        notulen_filename_db = f"kegiatan/{unique_filename}" # <-- SIMPAN PATH RELATIF
                        update_fields.append("notulen=%s")
                        update_values.append(notulen_filename_db)
                        print(f"DEBUG: Notulen diupdate ke: {full_path}, DB value: {notulen_filename_db}") # Debugging
                    elif not file.filename: # Jika input file kosong (user tidak upload file baru)
                        # Jangan update kolom notulen, biarkan nilai lama
                        pass


                # Update database
                update_values.append(id) # ID untuk klausa WHERE
                query = f"UPDATE bpd_kegiatan SET {', '.join(update_fields)} WHERE id=%s"
                cur.execute(query, update_values)
                conn.commit()
                flash('Kegiatan berhasil diperbarui!', 'success')
                return redirect(url_for('kegiatan'))

            # GET request
            cur.execute("SELECT * FROM bpd_kegiatan WHERE id = %s", [id])
            kegiatan = cur.fetchone()
            cur.close()

            if not kegiatan:
                flash('Kegiatan tidak ditemukan!', 'danger')
                return redirect(url_for('kegiatan'))

            return render_template('kegiatan/form.html', mode='edit', kegiatan=kegiatan)
        except pymysql.MySQLError as e:
            flash(f"Error saat mengedit kegiatan: {e}", "danger")
            app.logger.error(f"DB error di edit_kegiatan: {e}")
            return redirect(url_for('kegiatan'))
        finally:
            if conn:
                conn.close()
    else:
        return redirect(url_for('kegiatan'))


@app.route('/kegiatan/hapus/<int:id>')
@login_required
def hapus_kegiatan(id):
    """Menghapus kegiatan BPD dan file terkait."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Hapus file terkait
            cur.execute("SELECT dokumentasi, notulen FROM bpd_kegiatan WHERE id = %s", [id])
            kegiatan = cur.fetchone()
            
            if kegiatan and kegiatan['dokumentasi']:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], kegiatan['dokumentasi']) # Path sudah relatif
                if os.path.exists(filepath):
                    os.remove(filepath)
            if kegiatan and kegiatan['notulen']:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], kegiatan['notulen']) # Path sudah relatif
                if os.path.exists(filepath):
                    os.remove(filepath)

            # Hapus data dari database
            cur.execute("DELETE FROM bpd_kegiatan WHERE id = %s", [id])
            conn.commit()
            cur.close()

            flash('Kegiatan berhasil dihapus!', 'success')
            return redirect(url_for('kegiatan'))
        except pymysql.MySQLError as e:
            flash(f"Error saat menghapus kegiatan: {e}", "danger")
            app.logger.error(f"DB error di hapus_kegiatan: {e}")
            return redirect(url_for('kegiatan'))
        finally:
            if conn:
                conn.close()
    else:
        return redirect(url_for('kegiatan'))


# Rute Administrasi - Surat Masuk
@app.route('/surat-masuk')
@login_required # Tambahkan login_required
def surat_masuk():
    """Menampilkan daftar surat masuk."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bpd_surat_masuk ORDER BY tanggal_surat DESC")
            surat = cur.fetchall()
            cur.close()
            return render_template('administrasi/surat_masuk.html', surat=surat)
        except pymysql.MySQLError as e:
            flash(f"Error database: {e}", "danger")
            app.logger.error(f"DB error di surat_masuk: {e}")
            return render_template('administrasi/surat_masuk.html', surat=[])
        finally:
            if conn:
                conn.close()
    else:
        return render_template('administrasi/surat_masuk.html', surat=[])


@app.route('/surat-masuk/tambah', methods=['POST'])
@login_required # Tambahkan login_required
def tambah_surat_masuk():
    """Menambah surat masuk baru."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nomor_surat = request.form['nomor_surat']
        tanggal_surat = request.form['tanggal_surat']
        pengirim = request.form['pengirim']
        perihal = request.form['perihal']
        keterangan = request.form['keterangan']
        
        # Upload file
        file_surat_db = None
        if 'file_surat' in request.files:
            file = request.files['file_surat']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'surat')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                file_surat_db = f"surat/{filename}" # Simpan path relatif
                print(f"DEBUG: Surat masuk disimpan di: {filepath}, DB value: {file_surat_db}") # Debugging

        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO bpd_surat_masuk (nomor_surat, tanggal_surat, pengirim, perihal, keterangan, file_surat)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (nomor_surat, tanggal_surat, pengirim, perihal, keterangan, file_surat_db))
                conn.commit()
                cur.close()
                flash('Surat masuk berhasil ditambahkan!', 'success')
                return redirect(url_for('surat_masuk'))
            except pymysql.MySQLError as e:
                flash(f"Error saat menambah surat masuk: {e}", "danger")
                app.logger.error(f"DB error di tambah_surat_masuk: {e}")
                return render_template('administrasi/surat_masuk.html')
            finally:
                if conn:
                    conn.close()
        else:
            return render_template('administrasi/surat_masuk.html')


@app.route('/surat-masuk/hapus/<int:id>')
@login_required # Tambahkan login_required
def hapus_surat_masuk(id):
    """Menghapus surat masuk."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Hapus file jika ada
            cur.execute("SELECT file_surat FROM bpd_surat_masuk WHERE id = %s", [id])
            surat = cur.fetchone()
            if surat and surat['file_surat']:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], surat['file_surat']) # Path sudah relatif
                if os.path.exists(filepath):
                    os.remove(filepath)

            # Hapus data dari database
            cur.execute("DELETE FROM bpd_surat_masuk WHERE id = %s", [id])
            conn.commit()
            cur.close()

            flash('Surat masuk berhasil dihapus!', 'success')
            return redirect(url_for('surat_masuk'))
        except pymysql.MySQLError as e:
            flash(f"Error saat menghapus surat masuk: {e}", "danger")
            app.logger.error(f"DB error di hapus_surat_masuk: {e}")
            return redirect(url_for('surat_masuk'))
        finally:
            if conn:
                conn.close()
    else:
        return redirect(url_for('surat_masuk'))

# Rute Administrasi - Surat Keluar
@app.route('/surat-keluar')
@login_required # Tambahkan login_required
def surat_keluar():
    """Menampilkan daftar surat keluar."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bpd_surat_keluar ORDER BY tanggal_surat DESC")
            surat = cur.fetchall()
            cur.close()
            return render_template('administrasi/surat_keluar.html', surat=surat)
        except pymysql.MySQLError as e:
            flash(f"Error database: {e}", "danger")
            app.logger.error(f"DB error di bpd_surat_keluar: {e}")
            return render_template('administrasi/surat_keluar.html', surat=[])
        finally:
            if conn:
                conn.close()
    else:
        return render_template('administrasi/surat_keluar.html', surat=[])


@app.route('/surat-keluar/tambah', methods=['POST'])
@login_required # Tambahkan login_required
def tambah_surat_keluar():
    """Menambah surat keluar baru."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nomor_surat = request.form['nomor_surat']
        tanggal_surat = request.form['tanggal_surat']
        tujuan = request.form['tujuan']
        perihal = request.form['perihal']
        keterangan = request.form['keterangan']

        # Upload file
        file_surat_db = None
        if 'file_surat' in request.files:
            file = request.files['file_surat']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'surat')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                file_surat_db = f"surat/{filename}" # Simpan path relatif
                print(f"DEBUG: Surat keluar disimpan di: {filepath}, DB value: {file_surat_db}") # Debugging

        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                # Perbaikan: Ganti 'surat_keluar' menjadi 'bpd_surat_keluar' jika itu nama tabel yang benar
                cur.execute("""
                    INSERT INTO bpd_surat_keluar (nomor_surat, tanggal_surat, tujuan, perihal, keterangan, file_surat)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (nomor_surat, tanggal_surat, tujuan, perihal, keterangan, file_surat_db))
                conn.commit()
                cur.close()
                flash('Surat keluar berhasil ditambahkan!', 'success')
                return redirect(url_for('surat_keluar'))
            except pymysql.MySQLError as e:
                flash(f"Error saat menambah surat keluar: {e}", "danger")
                app.logger.error(f"DB error di tambah_surat_keluar: {e}")
                return render_template('administrasi/surat_keluar.html')
            finally:
                if conn:
                    conn.close()
        else:
            return render_template('administrasi/surat_keluar.html')


@app.route('/surat-keluar/hapus/<int:id>')
@login_required # Tambahkan login_required
def hapus_surat_keluar(id):
    """Menghapus surat keluar."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Hapus file jika ada
            # Perbaikan: Ganti 'surat_keluar' menjadi 'bpd_surat_keluar'
            cur.execute("SELECT file_surat FROM bpd_surat_keluar WHERE id = %s", [id])
            surat = cur.fetchone()
            if surat and surat['file_surat']:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], surat['file_surat']) # Path sudah relatif
                if os.path.exists(filepath):
                    os.remove(filepath)

            # Hapus data dari database
            # Perbaikan: Ganti 'surat_keluar' menjadi 'bpd_surat_keluar'
            cur.execute("DELETE FROM bpd_surat_keluar WHERE id = %s", [id])
            conn.commit()
            cur.close()

            flash('Surat keluar berhasil dihapus!', 'success')
            return redirect(url_for('surat_keluar'))
        except pymysql.MySQLError as e:
            flash(f"Error saat menghapus surat keluar: {e}", "danger")
            app.logger.error(f"DB error di hapus_surat_keluar: {e}")
            return redirect(url_for('surat_keluar'))
        finally:
            if conn:
                conn.close()
    else:
        return redirect(url_for('surat_keluar'))

@app.template_filter('format_date')
def format_date_filter(date_str): # Ubah nama fungsi agar tidak konflik dengan format_date di bawah
    """Filter Jinja2 untuk memformat tanggal."""
    try:
        if isinstance(date_str, datetime): # Jika sudah objek datetime
            return date_str.strftime('%d/%m/%Y')
        date_obj = datetime.strptime(str(date_str), '%Y-%m-%d') # Pastikan input adalah string
        return date_obj.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return str(date_str) # Kembalikan string asli jika gagal format
    
@app.route('/keuangan')
@login_required
def keuangan():
    """Menampilkan laporan keuangan."""
    if session.get('user_role') != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database!', 'danger')
        return redirect(url_for('dashboard'))

    cur = conn.cursor()

    try:
        # Get saldo awal
        cur.execute("""
            SELECT SUM(CASE WHEN jenis='penerimaan' THEN jumlah ELSE -jumlah END) AS saldo 
            FROM bpd_laporan_keuangan
        """)
        saldo_awal_data = cur.fetchone()
        saldo_awal = saldo_awal_data['saldo'] if saldo_awal_data and saldo_awal_data['saldo'] is not None else 0

        # Get all transactions
        cur.execute("""
            SELECT *
            FROM bpd_laporan_keuangan
            ORDER BY tanggal
        """)
        transaksi_raw = cur.fetchall()
        
        transaksi = []
        saldo_berjalan_current = 0
        for t in transaksi_raw:
            saldo_berjalan_current += t['jumlah'] if t['jenis'] == 'penerimaan' else -t['jumlah']
            t['saldo_berjalan'] = saldo_berjalan_current
            transaksi.append(t)

        # Hitung Total Penerimaan
        cur.execute("SELECT SUM(jumlah) AS total FROM bpd_laporan_keuangan WHERE jenis = 'penerimaan'")
        total_penerimaan_data = cur.fetchone()
        total_penerimaan = total_penerimaan_data['total'] if total_penerimaan_data and total_penerimaan_data['total'] is not None else 0

        # Hitung Total Pengeluaran
        cur.execute("SELECT SUM(jumlah) AS total FROM bpd_laporan_keuangan WHERE jenis = 'pengeluaran'")
        total_pengeluaran_data = cur.fetchone()
        total_pengeluaran = total_pengeluaran_data['total'] if total_pengeluaran_data and total_pengeluaran_data['total'] is not None else 0

        cur.close()

        return render_template('administrasi/keuangan.html',
                               transaksi=transaksi,
                               saldo_awal=saldo_awal,
                               total_penerimaan=total_penerimaan,
                               total_pengeluaran=total_pengeluaran)

    except pymysql.Error as e:
        flash(f'Terjadi kesalahan database: {e}', 'danger')
        conn.rollback()
        return redirect(url_for('dashboard'))
    finally:
        if conn:
            cur.close()
            conn.close()

@app.route('/keuangan/tambah', methods=['POST'])
@login_required
def tambah_transaksi():
    """Menambah transaksi keuangan baru."""
    if current_user.role != 'admin':
        flash('Akses ditolak! Hanya admin yang dapat menambah transaksi', 'danger')
        return redirect(url_for('keuangan'))

    if request.method == 'POST':
        conn = None
        try:
            required_fields = ['tanggal', 'jenis', 'jumlah', 'keterangan']
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'Field {field} harus diisi', 'danger')
                    return redirect(url_for('keuangan'))

            data = {
                'tanggal': request.form['tanggal'],
                'jenis': request.form['jenis'],
                'jumlah': float(request.form['jumlah']),
                'keterangan': request.form['keterangan'],
                'referensi': request.form.get('referensi', ''),
                'file_laporan': None
            }
            
            if 'bukti' in request.files:
                file = request.files['bukti']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(f"bukti_{int(time.time())}_{file.filename}")
                    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'keuangan')
                    os.makedirs(upload_dir, exist_ok=True)
                    filepath = os.path.join(upload_dir, filename)
                    file.save(filepath)
                    data['file_laporan'] = f"keuangan/{filename}"
                    print(f"DEBUG: Bukti keuangan disimpan di: {filepath}, DB value: {data['file_laporan']}")

            conn = get_db_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO bpd_laporan_keuangan 
                (tanggal, jenis, jumlah, keterangan, referensi, file_laporan)
                VALUES (%(tanggal)s, %(jenis)s, %(jumlah)s, %(keterangan)s, %(referensi)s, %(file_laporan)s)
            """, data)
            
            conn.commit()
            flash('Transaksi berhasil ditambahkan!', 'success')
            return redirect(url_for('keuangan'))
            
        except ValueError:
            flash('Jumlah harus berupa angka yang valid.', 'danger')
        except pymysql.Error as e:
            if conn:
                conn.rollback()
            flash(f'Gagal menambah transaksi: {str(e)}', 'danger')
            app.logger.error(f"Error adding keuangan: {e}")
        finally:
            if conn:
                conn.close()
    
    return redirect(url_for('keuangan'))

@app.route('/keuangan/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_keuangan(id):
    """Mengedit transaksi keuangan yang sudah ada."""
    if current_user.role != 'admin':
        flash('Akses ditolak! Hanya admin yang dapat mengedit transaksi', 'danger')
        return redirect(url_for('keuangan'))

    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database.', 'danger')
        return redirect(url_for('keuangan'))

    cur = conn.cursor()
    try:
        if request.method == 'POST':
            # Ambil data dari form
            tanggal = request.form['tanggal']
            jenis = request.form['jenis']
            jumlah = float(request.form['jumlah'])
            keterangan = request.form['keterangan']
            referensi = request.form.get('referensi', '')
            
            update_fields = []
            update_values = []

            update_fields.append("tanggal=%s")
            update_values.append(tanggal)
            update_fields.append("jenis=%s")
            update_values.append(jenis)
            update_fields.append("jumlah=%s")
            update_values.append(jumlah)
            update_fields.append("keterangan=%s")
            update_values.append(keterangan)
            update_fields.append("referensi=%s")
            update_values.append(referensi)

            # Handle file upload (bukti)
            if 'bukti' in request.files:
                file = request.files['bukti']
                if file and file.filename != '' and allowed_file(file.filename):
                    # Hapus file lama jika ada
                    cur.execute("SELECT file_laporan FROM bpd_laporan_keuangan WHERE id = %s", [id])
                    keuangan_lama = cur.fetchone()
                    if keuangan_lama and keuangan_lama['file_laporan']:
                        old_file_path = os.path.join(app.config['UPLOAD_FOLDER'], keuangan_lama['file_laporan'])
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)

                    # Simpan file baru
                    filename = secure_filename(f"bukti_{int(time.time())}_{file.filename}")
                    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'keuangan')
                    os.makedirs(upload_dir, exist_ok=True)
                    filepath = os.path.join(upload_dir, filename)
                    file.save(filepath)
                    file_laporan_db = f"keuangan/{filename}" # Simpan path relatif
                    update_fields.append("file_laporan=%s")
                    update_values.append(file_laporan_db)
                    print(f"DEBUG: Bukti keuangan diupdate ke: {filepath}, DB value: {file_laporan_db}")
                elif not file.filename: # Jika input file kosong (user tidak upload file baru)
                    # Jangan update kolom file_laporan, biarkan nilai lama
                    pass

            update_values.append(id) # ID untuk klausa WHERE
            query = f"UPDATE bpd_laporan_keuangan SET {', '.join(update_fields)} WHERE id=%s"
            cur.execute(query, update_values)
            conn.commit()
            flash('Transaksi berhasil diperbarui!', 'success')
            return redirect(url_for('keuangan'))

        # GET request: Tampilkan form dengan data yang sudah ada
        cur.execute("SELECT * FROM bpd_laporan_keuangan WHERE id = %s", [id])
        transaksi = cur.fetchone()
        cur.close()

        if not transaksi:
            flash('Transaksi tidak ditemukan!', 'danger')
            return redirect(url_for('keuangan'))
        
        # Format tanggal ke YYYY-MM-DD untuk input date HTML
        if isinstance(transaksi['tanggal'], datetime):
            transaksi['tanggal'] = transaksi['tanggal'].strftime('%Y-%m-%d')

        # Asumsi Anda menggunakan modal yang sama dengan tambah transaksi
        # Anda perlu memastikan modal di HTML dapat menerima data ini
        return render_template('administrasi/keuangan.html', 
                               transaksi_edit=transaksi, # Kirim data transaksi yang akan diedit
                               mode='edit') # Indikator mode edit
    
    except ValueError:
        flash('Jumlah harus berupa angka yang valid.', 'danger')
        return redirect(url_for('keuangan'))
    except pymysql.Error as e:
        if conn:
            conn.rollback()
        flash(f'Gagal mengedit transaksi: {str(e)}', 'danger')
        app.logger.error(f"Error editing keuangan: {e}")
        return redirect(url_for('keuangan'))
    finally:
        if conn:
            conn.close()

@app.route('/keuangan/hapus/<int:id>', methods=['POST'])
@login_required
def hapus_keuangan(id):
    """Menghapus transaksi keuangan."""
    if current_user.role != 'admin':
        flash('Akses ditolak! Hanya admin yang dapat menghapus transaksi', 'danger')
        return redirect(url_for('keuangan'))

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Hapus file bukti jika ada
        cur.execute("SELECT file_laporan FROM bpd_laporan_keuangan WHERE id = %s", (id,))
        keuangan_data = cur.fetchone()
        if keuangan_data and keuangan_data['file_laporan']:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], keuangan_data['file_laporan']) # Path sudah relatif
            if os.path.exists(filepath):
                os.remove(filepath)

        # Hapus dari database
        cur.execute("DELETE FROM bpd_laporan_keuangan WHERE id = %s", (id,))
        conn.commit()
        
        flash('Transaksi berhasil dihapus', 'success')
    except pymysql.Error as e: # Ubah dari Exception ke pymysql.Error
        if conn:
            conn.rollback()
        flash(f'Gagal menghapus transaksi: {str(e)}', 'danger')
        app.logger.error(f"Error deleting keuangan: {e}") # Log error
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('keuangan'))

@app.template_filter('format_currency')
def format_currency(value):
    """Filter Jinja2 untuk memformat nilai mata uang."""
    return "Rp {:,.2f}".format(value) if value is not None else "Rp 0,00" # Perbaiki format default

@app.route('/peraturan')
@login_required
def peraturan():
    """Menampilkan daftar peraturan desa."""
    if session.get('user_role') != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database!', 'danger')
        return redirect(url_for('dashboard'))

    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM bpd_peraturan_desa ORDER BY tanggal DESC")
        peraturan = cur.fetchall()
        cur.close()
        return render_template('administrasi/peraturan.html', peraturan=peraturan)
    except pymysql.Error as e:
        flash(f"Error database: {e}", "danger")
        app.logger.error(f"DB error di peraturan: {e}")
        return render_template('administrasi/peraturan.html', peraturan=[])
    finally:
        if conn:
            conn.close()


@app.route('/peraturan/tambah', methods=['POST'])
@login_required
def tambah_peraturan():
    """Menambah peraturan desa baru."""
    if session.get('user_role') != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    nomor = request.form['nomor']
    judul = request.form['judul']
    tanggal = request.form['tanggal']
    keterangan = request.form['keterangan']
    file_peraturan_db = None

    if 'file_peraturan' in request.files:
        file = request.files['file_peraturan']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'dokumen')
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            file_peraturan_db = f"dokumen/{filename}" # Simpan path relatif
            print(f"DEBUG: Peraturan disimpan di: {filepath}, DB value: {file_peraturan_db}") # Debugging

    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database.', 'danger')
        return redirect(url_for('peraturan'))

    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO bpd_peraturan_desa (nomor, judul, tanggal, keterangan, file_peraturan)
            VALUES (%s, %s, %s, %s, %s)
        """, (nomor, judul, tanggal, keterangan, file_peraturan_db))
        conn.commit()
        flash('Peraturan desa berhasil ditambahkan!', 'success')
    except pymysql.Error as e:
        flash(f"Gagal menambah peraturan: {e}", "danger")
        app.logger.error(f"DB error di tambah_peraturan: {e}")
        conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()

    return redirect(url_for('peraturan'))


@app.route('/peraturan/hapus/<int:id>')
@login_required
def hapus_peraturan(id):
    """Menghapus peraturan desa."""
    if session.get('user_role') != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database.', 'danger')
        return redirect(url_for('peraturan'))
        
    cur = conn.cursor()
    try:
        # hapus file
        cur.execute("SELECT file_peraturan FROM bpd_peraturan_desa WHERE id = %s", (id,))
        data = cur.fetchone()
        if data and data['file_peraturan']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], data['file_peraturan']) # Path sudah relatif
            if os.path.exists(file_path):
                os.remove(file_path)

        cur.execute("DELETE FROM bpd_peraturan_desa WHERE id = %s", (id,))
        conn.commit()
        flash('Peraturan desa berhasil dihapus!', 'success')
    except pymysql.Error as e:
        flash(f"Gagal menghapus peraturan: {e}", "danger")
        app.logger.error(f"DB error di hapus_peraturan: {e}")
        conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()

    return redirect(url_for('peraturan'))


# Rute Keputusan BPD
@app.route('/keputusan')
@login_required
def keputusan():
    """Menampilkan daftar keputusan BPD."""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM bpd_keputusan_bpd ORDER BY tanggal_penetapan DESC")
            keputusan = cur.fetchall()
            cur.close()
            return render_template('keputusan/index.html', keputusan=keputusan)
        except pymysql.MySQLError as e:
            flash(f"Error database: {e}", "danger")
            app.logger.error(f"DB error di keputusan: {e}")
            return render_template('keputusan/index.html', keputusan=[])
        finally:
            if conn:
                conn.close()
    else:
        return render_template('keputusan/index.html', keputusan=[])


@app.route('/keputusan/tambah', methods=['POST'])
@login_required
def tambah_keputusan():
    """Menambah keputusan BPD baru."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nomor_keputusan = request.form['nomor_keputusan']
        tanggal_penetapan = request.form['tanggal_penetapan']
        tentang = request.form['tentang']
        uraian = request.form['uraian']

        # Upload file
        file_keputusan_db = None
        if 'file_keputusan' in request.files:
            file = request.files['file_keputusan']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'keputusan')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                file_keputusan_db = f"keputusan/{filename}" # Simpan path relatif
                print(f"DEBUG: Keputusan disimpan di: {filepath}, DB value: {file_keputusan_db}") # Debugging

        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO bpd_keputusan_bpd (nomor_keputusan, tanggal_penetapan, tentang, uraian, file_keputusan)
                    VALUES (%s, %s, %s, %s, %s)
                """, (nomor_keputusan, tanggal_penetapan, tentang, uraian, file_keputusan_db))
                conn.commit()
                cur.close()
                flash('Keputusan BPD berhasil ditambahkan!', 'success')
                return redirect(url_for('keputusan'))
            except pymysql.MySQLError as e:
                flash(f"Error saat menambah keputusan: {e}", "danger")
                app.logger.error(f"DB error di tambah_keputusan: {e}")
                return render_template('keputusan/index.html')
            finally:
                if conn:
                    conn.close()
        else:
            return render_template('keputusan/index.html')


@app.route('/keputusan/hapus/<int:id>')
@login_required
def hapus_keputusan(id):
    """Menghapus keputusan BPD."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Hapus file jika ada
            cur.execute("SELECT file_keputusan FROM bpd_keputusan_bpd WHERE id = %s", [id])
            keputusan = cur.fetchone()
            if keputusan and keputusan['file_keputusan']:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], keputusan['file_keputusan']) # Path sudah relatif
                if os.path.exists(filepath):
                    os.remove(filepath)

            # Hapus data dari database
            cur.execute("DELETE FROM bpd_keputusan_bpd WHERE id = %s", [id])
            conn.commit()
            cur.close()

            flash('Keputusan BPD berhasil dihapus!', 'success')
            return redirect(url_for('keputusan'))
        except pymysql.MySQLError as e:
            flash(f"Error saat menghapus keputusan: {e}", "danger")
            app.logger.error(f"DB error di hapus_keputusan: {e}")
            return redirect(url_for('keputusan'))
        finally:
            if conn:
                conn.close()
    else:
        return redirect(url_for('keputusan'))

@app.route('/laporan-tahunan')
@login_required
def laporan_tahunan():
    """Menampilkan laporan tahunan kegiatan dan keuangan."""
    tahun_selected = request.args.get('tahun', str(datetime.now().year))
    
    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database!', 'danger')
        return redirect(url_for('dashboard'))

    cur = conn.cursor()
    
    try:
        # Ambil data kegiatan untuk tahun terpilih
        cur.execute("""
            SELECT * FROM bpd_kegiatan 
            WHERE YEAR(tanggal) = %s 
            ORDER BY tanggal ASC
        """, (tahun_selected,))
        kegiatan_tahunan = cur.fetchall()
        
        # Ambil data keuangan untuk tahun terpilih
        cur.execute("""
            SELECT * FROM bpd_laporan_keuangan 
            WHERE YEAR(tanggal) = %s 
            ORDER BY tanggal ASC
        """, (tahun_selected,))
        transaksi_tahunan = cur.fetchall()

        # Hitung total penerimaan dan pengeluaran
        total_penerimaan_tahun = 0
        total_pengeluaran_tahun = 0
        for t in transaksi_tahunan:
            jumlah = t['jumlah'] if t['jumlah'] is not None else 0
            if t['jenis'] == 'penerimaan':
                total_penerimaan_tahun += jumlah
            elif t['jenis'] == 'pengeluaran':
                total_pengeluaran_tahun += jumlah
        
        saldo_bersih_tahun = total_penerimaan_tahun - total_pengeluaran_tahun
        
        cur.close()
        
        # Render template
        return render_template('laporan/tahunan.html', 
                            kegiatan_tahunan=kegiatan_tahunan,
                            transaksi_tahunan=transaksi_tahunan,
                            tahun_selected=tahun_selected,
                            total_penerimaan_tahun=total_penerimaan_tahun,
                            total_pengeluaran_tahun=total_pengeluaran_tahun,
                            saldo_bersih_tahun=saldo_bersih_tahun)
    except pymysql.Error as e:
        flash(f"Error database: {e}", "danger")
        app.logger.error(f"DB error di laporan_tahunan: {e}")
        return render_template('laporan/tahunan.html', 
                                kegiatan_tahunan=[], 
                                transaksi_tahunan=[], 
                                tahun_selected=tahun_selected,
                                total_penerimaan_tahun=0,
                                total_pengeluaran_tahun=0,
                                saldo_bersih_tahun=0)
    finally:
        if conn:
            conn.close()

@app.route('/download-laporan-tahunan/<tahun>')
@login_required
def download_laporan_tahunan(tahun):
    """Menghasilkan dan mengunduh laporan tahunan dalam format PDF."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Judul Laporan
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontSize=16,
        alignment=1,
        spaceAfter=20
    )
    
    elements.append(Paragraph("LAPORAN TAHUNAN BPD PAOKMOTONG", title_style))
    elements.append(Paragraph(f"Tahun {tahun}", styles['Heading2']))
    elements.append(Spacer(1, 20))
    
    # Ambil data dari database
    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database untuk membuat laporan!', 'danger')
        return redirect(url_for('laporan_tahunan'))

    cur = conn.cursor()
    
    try:
        # --- DATA KEGIATAN ---
        elements.append(Paragraph("Kegiatan BPD", styles['Heading2']))
        cur.execute("""
            SELECT * FROM bpd_kegiatan 
            WHERE YEAR(tanggal) = %s 
            ORDER BY tanggal ASC
        """, (tahun,))
        kegiatan_data = cur.fetchall()
        
        if not kegiatan_data:
            elements.append(Paragraph("Tidak ada kegiatan pada tahun ini.", styles['Normal']))
        else:
            # Tabel Kegiatan
            kegiatan_table_data = [
                ['No', 'Tanggal', 'Jenis Kegiatan', 'Judul', 'Tempat']
            ]
            for idx, item in enumerate(kegiatan_data, 1):
                kegiatan_table_data.append([
                    str(idx),
                    item['tanggal'].strftime('%d-%m-%Y'),
                    item['jenis'],
                    item['judul'],
                    item['tempat']
                ])
            
            kegiatan_table = Table(kegiatan_table_data, colWidths=[0.5*inch, 1.2*inch, 1.5*inch, 3*inch, 1.5*inch])
            kegiatan_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 10),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F0F9FF')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#BFDBFE')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
            ]))
            elements.append(kegiatan_table)
        
        elements.append(Spacer(1, 24))
        
        # --- DATA KEUANGAN ---
        elements.append(Paragraph("Laporan Keuangan", styles['Heading2']))
        
        # 1. Ringkasan Keuangan
        cur.execute("""
            SELECT 
                SUM(CASE WHEN jenis='penerimaan' THEN jumlah ELSE 0 END) as total_penerimaan,
                SUM(CASE WHEN jenis='pengeluaran' THEN jumlah ELSE 0 END) as total_pengeluaran
            FROM bpd_laporan_keuangan
            WHERE YEAR(tanggal) = %s
        """, (tahun,))
        ringkasan = cur.fetchone()
        
        total_penerimaan = ringkasan['total_penerimaan'] or 0
        total_pengeluaran = ringkasan['total_pengeluaran'] or 0
        saldo_bersih = total_penerimaan - total_pengeluaran
        
        # Tabel Ringkasan
        ringkasan_data = [
            ['Total Penerimaan', 'Total Pengeluaran', 'Saldo Bersih'],
            [
                f"Rp {total_penerimaan:,.2f}", 
                f"Rp {total_pengeluaran:,.2f}", 
                f"Rp {saldo_bersih:,.2f}"
            ]
        ]
        
        ringkasan_table = Table(ringkasan_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
        ringkasan_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#166534')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#F0FDF4')),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#BBF7D0')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        elements.append(ringkasan_table)
        elements.append(Spacer(1, 15))
        
        # 2. Detail Transaksi
        cur.execute("""
            SELECT * FROM bpd_laporan_keuangan 
            WHERE YEAR(tanggal) = %s 
            ORDER BY tanggal ASC
        """, (tahun,))
        transaksi_data = cur.fetchall()
        
        if not transaksi_data:
            elements.append(Paragraph("Tidak ada transaksi keuangan pada tahun ini.", styles['Normal']))
        else:
            # Tabel Transaksi
            transaksi_table_data = [
                ['No', 'Tanggal', 'Referensi', 'Keterangan', 'Jenis', 'Jumlah (Rp)']
            ]
            
            for idx, item in enumerate(transaksi_data, 1):
                transaksi_table_data.append([
                    str(idx),
                    item['tanggal'].strftime('%d-%m-%Y'),
                    item['referensi'] or '-',
                    item['keterangan'],
                    item['jenis'].capitalize(),
                    f"{item['jumlah']:,.2f}"
                ])
            
            transaksi_table = Table(transaksi_table_data, 
                                  colWidths=[0.5*inch, 1*inch, 1.2*inch, 2.5*inch, 1*inch, 1.2*inch])
            transaksi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (3,0), 'LEFT'),
                ('ALIGN', (4,0), (-1,0), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 9),
                ('BOTTOMPADDING', (0,0), (-1,0), 8),
                ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#F0F9FF')),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#BFDBFE')),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (5,1), (5,-1), 'RIGHT')  # Rata kanan untuk kolom jumlah
            ]))
            elements.append(transaksi_table)
        
        # Footer
        elements.append(Spacer(1, 30))
        elements.append(Paragraph(f"Dicetak pada: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                               ParagraphStyle('Footer', alignment=2, fontSize=9)))
        
        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        
        # Close database connection
        cur.close()
        
        # Prepare response
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=laporan_tahunan_bpd_{tahun}.pdf'
        
        return response
    except pymysql.Error as e:
        flash(f"Error saat membuat laporan PDF: {e}", "danger")
        app.logger.error(f"DB error di download_laporan_tahunan: {e}")
        return redirect(url_for('laporan_tahunan'))
    finally:
        if conn:
            conn.close()


@app.route('/download/<jenis>/<path:filename>')
def download_file(jenis, filename):
    """Melayani file yang diunggah dari subfolder tertentu."""
    try:
        # Validasi jenis folder
        valid_folders = ['kegiatan', 'keuangan', 'profil', 'surat', 'dokumen', 'keputusan', 'struktur', 'anggota']
        if jenis not in valid_folders:
            app.logger.error(f"Jenis folder tidak valid: {jenis}")
            abort(404, description="Jenis file tidak valid")
        
        # Perbaikan: Hapus awalan 'jenis/' dari filename jika sudah ada
        if filename.startswith(f"{jenis}/"):
            filename = filename.replace(f"{jenis}/", "", 1)
            app.logger.info(f"DEBUG: Filename setelah stripping prefix: {filename}")

        upload_dir = os.path.join(app.root_path, 'static', 'uploads', jenis)
        file_path = os.path.join(upload_dir, filename) 
        
        app.logger.info(f"Mencoba akses file: {file_path}")
        
        if not os.path.exists(file_path):
            app.logger.error(f"File tidak ditemukan: {file_path}")
            abort(404, description="File tidak ditemukan")
        
        return send_from_directory(upload_dir, filename, as_attachment=False)
        
    except Exception as e:
        app.logger.error(f"Error saat download: {str(e)}")
        abort(500, description="Terjadi kesalahan server")
    
@app.template_filter('format_date_display')
def format_date_display(value, format_str='%d-%m-%Y'):
    """Filter Jinja2 untuk memformat objek tanggal untuk tampilan."""
    if isinstance(value, datetime):
        return value.strftime(format_str)
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').strftime(format_str)
    except (ValueError, TypeError):
        return str(value)

# Route untuk menampilkan struktur organisasi
@app.route('/struktur-organisasi')
@login_required
def struktur_organisasi():
    """Menampilkan struktur organisasi BPD."""
    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database.', 'danger')
        return redirect(url_for('dashboard'))

    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM bpd_struktur_organisasi ORDER BY urutan ASC")
        struktur = cur.fetchall()
        cur.close()
        return render_template('profil/struktur_organisasi.html', struktur=struktur)
    except pymysql.Error as e:
        flash(f"Error database: {e}", "danger")
        app.logger.error(f"DB error di struktur_organisasi: {e}")
        return render_template('profil/struktur_organisasi.html', struktur=[])
    finally:
        if conn:
            conn.close()

# Route untuk mengelola struktur organisasi (admin only)
@app.route('/admin/struktur-organisasi', methods=['GET', 'POST'])
@login_required
def admin_struktur_organisasi():
    """Mengelola struktur organisasi BPD (admin saja)."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        jabatan = request.form['jabatan']
        nama_pejabat = request.form['nama_pejabat']
        urutan = request.form['urutan']
        
        # Handle upload foto
        foto_db = None
        if 'foto' in request.files:
            file = request.files['foto']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"struktur_{jabatan.lower().replace(' ', '_')}_{file.filename}")
                upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'struktur')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                foto_db = f"struktur/{filename}" # Simpan path relatif
                print(f"DEBUG: Foto struktur disimpan di: {filepath}, DB value: {foto_db}") # Debugging

        conn = get_db_connection()
        if conn is None:
            flash('Gagal terhubung ke database.', 'danger')
            return redirect(url_for('admin_struktur_organisasi'))

    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO bpd_struktur_organisasi (jabatan, nama_pejabat, foto, urutan)
            VALUES (%s, %s, %s, %s)
        """, (jabatan, nama_pejabat, foto_db, urutan))
        conn.commit()
        flash('Data struktur organisasi berhasil ditambahkan!', 'success')
    except pymysql.Error as e:
        flash(f"Gagal menambah struktur organisasi: {e}", "danger")
        app.logger.error(f"DB error di admin_struktur_organisasi (tambah): {e}")
        conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()
    return redirect(url_for('admin_struktur_organisasi'))

    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database.', 'danger')
        return render_template('profil/admin_struktur.html', struktur=[])

    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM bpd_struktur_organisasi ORDER BY urutan ASC")
        struktur = cur.fetchall()
        cur.close()
        return render_template('profil/admin_struktur.html', struktur=struktur)
    except pymysql.Error as e:
        flash(f"Error database: {e}", "danger")
        app.logger.error(f"DB error di admin_struktur_organisasi (get): {e}")
        return render_template('profil/admin_struktur.html', struktur=[])
    finally:
        if conn:
            conn.close()

# Route untuk menghapus anggota struktur
@app.route('/admin/struktur-organisasi/hapus/<int:id>')
@login_required
def hapus_struktur(id):
    """Menghapus anggota struktur organisasi."""
    if current_user.role != 'admin':
        flash('Akses ditolak!', 'danger')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    if conn is None:
        flash('Gagal terhubung ke database.', 'danger')
        return redirect(url_for('admin_struktur_organisasi'))

    cur = conn.cursor()
    try:
        # Hapus file foto jika ada
        cur.execute("SELECT foto FROM bpd_struktur_organisasi WHERE id = %s", [id])
        data = cur.fetchone()
        if data and data['foto']:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], data['foto']) # Path sudah relatif
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Hapus dari database
        cur.execute("DELETE FROM bpd_struktur_organisasi WHERE id = %s", [id])
        conn.commit()
        flash('Anggota struktur berhasil dihapus!', 'success')
    except pymysql.Error as e:
        flash(f"Gagal menghapus anggota struktur: {e}", "danger")
        app.logger.error(f"DB error di hapus_struktur: {e}")
        conn.rollback()
    finally:
        if conn:
            cur.close()
            conn.close()
    
    return redirect(url_for('admin_struktur_organisasi'))

@app.context_processor
def inject_now():
    """Menyuntikkan objek datetime 'now' ke semua template."""
    return {'now': datetime.now()}


if __name__ == '__main__':
    # Pastikan folder UPLOAD_FOLDER itu sendiri ada
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 
    
    # Buat subfolder di dalam UPLOAD_FOLDER jika belum ada
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'anggota'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'kegiatan'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'surat'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'keputusan'), exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'dokumen'), exist_ok=True) # Untuk peraturan
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'keuangan'), exist_ok=True) # Untuk bukti keuangan
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profil'), exist_ok=True) # Untuk foto profil
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'struktur'), exist_ok=True) # Untuk foto struktur

    app.run(debug=config.DEBUG, port=config.PORT)
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import firebase_admin
from firebase_admin import credentials, firestore
import os
from datetime import datetime, timedelta
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # O'zgartiring!

# ===============================
# 🔥 FIREBASE INIT
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_KEY_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

cred = credentials.Certificate(SERVICE_KEY_PATH)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ===============================
# 🔐 LOGIN CONFIG
# ===============================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Oddiy admin user (ishlab chiqish uchun)
# Real proyektda bazadan olinishi kerak
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = generate_password_hash('admin123')  # Parolni o'zgartiring!

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Admin tekshirish decoratori
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.id != ADMIN_USERNAME:
            flash('Bu sahifaga kirish uchun admin huquqi kerak', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ===============================
# 📊 STATISTIKA FUNKSIYALARI
# ===============================

def get_payments_by_status(status):
    """Status bo'yicha to'lovlarni olish"""
    payments_ref = db.collection('payments')
    if status == 'all':
        docs = payments_ref.stream()
    else:
        docs = payments_ref.where('status', '==', status).stream()
    
    payments = []
    for doc in docs:
        data = doc.to_dict()
        data['id'] = doc.id
        payments.append(data)
    return payments

def update_payment_status(doc_id, new_status):
    """To'lov statusini yangilash"""
    try:
        doc_ref = db.collection('payments').document(doc_id)
        doc_ref.update({
            'status': new_status,
            'updated_at': datetime.now().isoformat(),
            'updated_by': current_user.id if current_user.is_authenticated else 'system'
        })
        return True
    except Exception as e:
        print(f"Error updating status: {e}")
        return False

def auto_fix_pending_payments():
    """Pending statusidagi to'lovlarni avtomatik tekshirish va tuzatish"""
    fixed_count = 0
    error_count = 0
    
    # Pending statusidagi to'lovlarni olish
    pending_ref = db.collection('payments').where('status', '==', 'pending').stream()
    
    for doc in pending_ref:
        try:
            data = doc.to_dict()
            doc_id = doc.id
            
            # Agar used True bo'lsa, statusni success ga o'zgartirish
            if data.get('used') == True:
                doc_ref = db.collection('payments').document(doc_id)
                doc_ref.update({
                    'status': 'success',
                    'fixed_by_system': True,
                    'fixed_at': datetime.now().isoformat()
                })
                fixed_count += 1
                print(f"✅ Fixed: {doc_id} -> success")
            
            # Agar used False bo'lsa va eski bo'lsa (24 soatdan oshgan)
            elif data.get('used') == False:
                created_at = data.get('date') or data.get('created_at')
                if created_at:
                    try:
                        # Vaqtni parse qilish
                        if isinstance(created_at, str):
                            if ':' in created_at:
                                doc_time = datetime.fromisoformat(created_at.replace(' ', 'T'))
                            else:
                                doc_time = datetime.strptime(created_at, '%Y-%m-%d')
                        else:
                            doc_time = created_at
                        
                        # 24 soatdan oshganmi?
                        if datetime.now() - doc_time > timedelta(hours=24):
                            doc_ref = db.collection('payments').document(doc_id)
                            doc_ref.update({
                                'status': 'expired',
                                'expired_at': datetime.now().isoformat()
                            })
                            print(f"⏰ Expired: {doc_id} -> expired")
                    except:
                        pass
        except Exception as e:
            error_count += 1
            print(f"❌ Error fixing {doc.id}: {e}")
    
    return fixed_count, error_count

# ===============================
# 🚀 ROUTES
# ===============================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD, password):
            user = User(username)
            login_user(user)
            flash('Muvaffaqiyatli kirdingiz!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Noto\'g\'ri username yoki parol', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Chiqib ketdingiz', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
@admin_required
def dashboard():
    """Asosiy dashboard - statistik ma'lumotlar"""
    try:
        # Barcha to'lovlar
        all_payments = list(db.collection('payments').stream())
        
        # Statuslar bo'yicha guruhlash
        total = len(all_payments)
        pending = sum(1 for p in all_payments if p.to_dict().get('status') == 'pending')
        success = sum(1 for p in all_payments if p.to_dict().get('status') == 'success')
        expired = sum(1 for p in all_payments if p.to_dict().get('status') == 'expired')
        
        # So'nggi 10 to'lov
        recent_payments = []
        for doc in sorted(all_payments, 
                         key=lambda x: x.to_dict().get('date', ''), 
                         reverse=True)[:10]:
            data = doc.to_dict()
            data['id'] = doc.id
            recent_payments.append(data)
        
        # Kunlik statistika
        today = datetime.now().date().isoformat()
        today_payments = [p for p in all_payments 
                         if p.to_dict().get('date', '').startswith(today)]
        
        today_total = len(today_payments)
        today_amount = sum(float(p.to_dict().get('amount', 0)) for p in today_payments)
        
        return render_template('dashboard.html',
                             total=total,
                             pending=pending,
                             success=success,
                             expired=expired,
                             recent_payments=recent_payments,
                             today_total=today_total,
                             today_amount=today_amount)
    except Exception as e:
        flash(f'Xatolik yuz berdi: {str(e)}', 'danger')
        return render_template('dashboard.html', error=str(e))

@app.route('/payments')
@login_required
@admin_required
def payments():
    """Barcha to'lovlar ro'yxati"""
    status = request.args.get('status', 'all')
    
    try:
        if status == 'all':
            docs = db.collection('payments').order_by('date', direction=firestore.Query.DESCENDING).stream()
        else:
            docs = db.collection('payments')\
                    .where('status', '==', status)\
                    .order_by('date', direction=firestore.Query.DESCENDING)\
                    .stream()
        
        payments = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            payments.append(data)
        
        return render_template('payments.html', 
                             payments=payments, 
                             current_status=status)
    except Exception as e:
        flash(f'Xatolik yuz berdi: {str(e)}', 'danger')
        return render_template('payments.html', payments=[], current_status='all')

@app.route('/payment/<doc_id>')
@login_required
@admin_required
def payment_detail(doc_id):
    """Bitta to'lov haqida batafsil"""
    try:
        doc_ref = db.collection('payments').document(doc_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            data['id'] = doc.id
            return render_template('payment_detail.html', payment=data)
        else:
            flash('To\'lov topilmadi', 'warning')
            return redirect(url_for('payments'))
    except Exception as e:
        flash(f'Xatolik yuz berdi: {str(e)}', 'danger')
        return redirect(url_for('payments'))

@app.route('/update_status/<doc_id>/<new_status>', methods=['POST'])
@login_required
@admin_required
def update_status(doc_id, new_status):
    """To'lov statusini yangilash"""
    if new_status not in ['pending', 'success', 'expired']:
        flash('Noto\'g\'ri status', 'danger')
        return redirect(url_for('payments'))
    
    try:
        doc_ref = db.collection('payments').document(doc_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            flash('To\'lov topilmadi', 'danger')
            return redirect(url_for('payments'))
        
        # Statusni yangilash
        data = doc.to_dict()
        
        # Agar success qilinsa, used ni ham True qilish
        updates = {
            'status': new_status,
            'updated_at': datetime.now().isoformat(),
            'updated_by': current_user.id
        }
        
        if new_status == 'success':
            updates['used'] = True
        
        doc_ref.update(updates)
        
        flash(f'Status muvaffaqiyatli "{new_status}" ga o\'zgartirildi', 'success')
    except Exception as e:
        flash(f'Xatolik yuz berdi: {str(e)}', 'danger')
    
    return redirect(url_for('payments', status='all'))

@app.route('/auto_fix', methods=['POST'])
@login_required
@admin_required
def auto_fix():
    """Pending to'lovlarni avtomatik tuzatish"""
    try:
        fixed, errors = auto_fix_pending_payments()
        flash(f'✅ {fixed} ta to\'lov tuzatildi. ❌ {errors} ta xatolik', 
              'success' if fixed > 0 else 'info')
    except Exception as e:
        flash(f'Xatolik yuz berdi: {str(e)}', 'danger')
    
    return redirect(url_for('payments'))

@app.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """API: Statistika ma'lumotlari"""
    try:
        all_payments = list(db.collection('payments').stream())
        
        total = len(all_payments)
        pending = sum(1 for p in all_payments if p.to_dict().get('status') == 'pending')
        success = sum(1 for p in all_payments if p.to_dict().get('status') == 'success')
        expired = sum(1 for p in all_payments if p.to_dict().get('status') == 'expired')
        
        total_amount = sum(float(p.to_dict().get('amount', 0)) for p in all_payments)
        
        return jsonify({
            'total': total,
            'pending': pending,
            'success': success,
            'expired': expired,
            'total_amount': total_amount
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
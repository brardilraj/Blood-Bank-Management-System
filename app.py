from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_mysqldb import MySQL
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import MySQLdb.cursors
import csv
import io
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize MySQL
mysql = MySQL(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id, username, role):
        self.id = user_id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    cursor.close()
    if user:
        return User(user['id'], user['username'], user['role'])
    return None


# ======================
# Authentication Routes
# ======================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Basic input validation
        if not username or not password:
            flash('Please fill in all fields', 'danger')
            return redirect(url_for('login'))
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
            
            if user and check_password_hash(user['password'], password):
                user_obj = User(user['id'], user['username'], user['role'])
                login_user(user_obj)
                
                # Record login activity
                cursor.execute('''
                    INSERT INTO user_activities (user_id, action)
                    VALUES (%s, 'login')
                ''', (user['id'],))
                mysql.connection.commit()
                
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'danger')
        except Exception as e:
            mysql.connection.rollback()
            flash('Login failed. Please try again.', 'danger')
        finally:
            cursor.close()
            
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validate inputs
        errors = []
        if not all([username, email, password, confirm_password]):
            errors.append('All fields are required')
        if len(username) < 4:
            errors.append('Username must be 4+ characters')
        if len(password) < 8:
            errors.append('Password must be 8+ characters')
        if password != confirm_password:
            errors.append('Passwords do not match')
            
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html',
                                 username=username,
                                 email=email)

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            # Check existing user
            cursor.execute('''
                SELECT id FROM users 
                WHERE username = %s OR email = %s
            ''', (username, email))
            if cursor.fetchone():
                flash('Username/email already exists', 'danger')
                return render_template('auth/register.html',
                                    username=username,
                                    email=email)
            
            # Hash password
            hashed_password = generate_password_hash(password)
            
            # Insert user
            cursor.execute('''
                INSERT INTO users 
                (username, email, password, role)
                VALUES (%s, %s, %s, 'staff')
            ''', (username, email, hashed_password))
            mysql.connection.commit()
            
            flash('Registration successful!', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error: {str(e)}', 'danger')
            return render_template('auth/register.html',
                                 username=username,
                                 email=email)
        finally:
            cursor.close()
    
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ======================
# Dashboard Routes
# ======================
@app.route('/')
@login_required
def dashboard():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Dashboard stats
    cursor.execute('SELECT COUNT(*) AS total FROM Donor')
    donor_count = cursor.fetchone()['total']
    
    cursor.execute('SELECT SUM(Units) AS total FROM Blood_Stock')
    blood_units = cursor.fetchone()['total'] or 0
    
    cursor.execute('SELECT COUNT(*) AS total FROM Recipient')
    recipient_count = cursor.fetchone()['total']
    
    # Blood stock data for chart
    cursor.execute('SELECT Blood_Group, SUM(Units) AS total FROM Blood_Stock GROUP BY Blood_Group')
    blood_data = cursor.fetchall()
    blood_groups = [item['Blood_Group'] for item in blood_data]
    blood_units_data = [item['total'] for item in blood_data]
    
    cursor.close()
    
    return render_template('dashboard.html',
                           donor_count=donor_count,
                           blood_units=blood_units,
                           recipient_count=recipient_count,
                           blood_groups=blood_groups,
                           blood_units_data=blood_units_data)

# ======================
# Donor Management
# ======================
@app.route('/donors')
@login_required
def donor_list():
    search = request.args.get('search', '')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    query = "SELECT * FROM Donor"
    params = []
    
    if search:
        query += " WHERE Name LIKE %s OR Email LIKE %s"
        params.extend([f"%{search}%", f"%{search}%"])
    
    cursor.execute(query, params)
    donors = cursor.fetchall()
    cursor.close()
    return render_template('donor/list.html', donors=donors)

@app.route('/donors/add', methods=['GET', 'POST'])
@login_required
def add_donor():
    if request.method == 'POST':
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            # Get the next available Donor_ID
            cursor.execute('SELECT MAX(Donor_ID) AS max_id FROM Donor')
            result = cursor.fetchone()
            next_donor_id = 1  # Default if table is empty
            if result and result['max_id'] is not None:  # Use dictionary key 'max_id'
                next_donor_id = int(result['max_id']) + 1
            
            # Print for debugging
            print(f"Next Donor ID: {next_donor_id}")
            
            donor_data = {
                'donor_id': next_donor_id,
                'name': request.form['name'],
                'age': request.form['age'],
                'contact': request.form['contact'],
                'email': request.form['email'],
                'gender': request.form['gender'],
                'blood_group': request.form['blood_group'],
                'last_donation': request.form['last_donation'] or None,
                'eligibility': 'Eligible' if request.form.get('eligibility') else 'Not Eligible'
            }
            
            # Print for debugging
            print(f"Donor data: {donor_data}")
            
            insert_query = '''
                INSERT INTO Donor 
                (Donor_ID, Name, Age, Contact_Number, Email, Gender, Blood_Group, Last_Donation_Date, Eligibility_Status)
                VALUES (%(donor_id)s, %(name)s, %(age)s, %(contact)s, %(email)s, %(gender)s, %(blood_group)s, %(last_donation)s, %(eligibility)s)
            '''
            
            # Print for debugging
            print(f"Query: {insert_query}")
            
            cursor.execute(insert_query, donor_data)
            mysql.connection.commit()
            flash('Donor added successfully!', 'success')
            return redirect(url_for('donor_list'))
        except Exception as e:
            mysql.connection.rollback()
            import traceback
            error_details = traceback.format_exc()
            print(f"Error details: {error_details}")
            flash(f'Error: {str(e)}\n\nDetails: {error_details}', 'danger')
        finally:
            cursor.close()
    
    return render_template('donor/form.html', title='Add Donor')
@app.route('/export/donors')
@login_required
def export_donors_csv():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('''
            SELECT Donor_ID, Name, Age, 
                   Blood_Group, Contact_Number, Email
            FROM Donor
        ''')
        
        def generate():
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Donor ID', 'Name', 'Age', 
                'Blood Group', 'Contact', 'Email'
            ])
            
            for donor in cursor:
                writer.writerow([
                    donor['Donor_ID'],
                    donor['Name'],
                    donor['Age'],
                    donor['Blood_Group'],
                    donor['Contact_Number'],
                    donor['Email']
                ])
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
            
            cursor.close()
        
        return Response(
            generate(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=donors.csv"}
        )
    
    except Exception as e:
        flash(f'Export failed: {str(e)}', 'danger')
        return redirect(url_for('donor_list'))

# ======================
# Recipient Management
# ======================
@app.route('/recipients')
@login_required
def recipient_list():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM Recipient')
    recipients = cursor.fetchall()
    cursor.close()
    return render_template('recipient/list.html', recipients=recipients)

@app.route('/recipients/add', methods=['GET', 'POST'])
@login_required
def add_recipient():
    if request.method == 'POST':
        recipient_data = {
            'name': request.form['name'],
            'age': request.form['age'],
            'contact': request.form['contact'],
            'email': request.form['email'],
            'gender': request.form['gender'],
            'blood_group': request.form['blood_group']
        }
        
        cursor = mysql.connection.cursor()
        try:
            cursor.execute('''
                INSERT INTO Recipient 
                (Name, Age, Contact_Number, Email, Gender, Blood_Group)
                VALUES (%(name)s, %(age)s, %(contact)s, %(email)s, %(gender)s, %(blood_group)s)
            ''', recipient_data)
            mysql.connection.commit()
            flash('Recipient added successfully!', 'success')
            return redirect(url_for('recipient_list'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error: {str(e)}', 'danger')
        finally:
            cursor.close()
    
    return render_template('recipient/form.html', title='Add Recipient')

# ======================
# Blood Request Management
# ======================
@app.route('/blood-requests')
@login_required
def blood_request_list():
    search = request.args.get('search', '')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        query = '''
            SELECT br.*, h.Name AS Hospital_Name, bb.Bank_Name
            FROM Blood_Request br
            LEFT JOIN Hospital h ON br.Hospital_ID = h.Hospital_ID
            LEFT JOIN Blood_Bank bb ON br.Bank_ID = bb.Bank_ID
        '''
        params = []
        
        if search:
            query += '''
                WHERE h.Name LIKE %s
                OR bb.Bank_Name LIKE %s
                OR br.Blood_Group LIKE %s
            '''
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        print("Executing query:", query, "with params:", params)  # Debug
        cursor.execute(query, params)
        requests = cursor.fetchall()
        print("Fetched requests:", requests)  # Debug
        return render_template('blood/requests_list.html', requests=requests)
    except Exception as e:
        flash(f'Error loading blood requests: {str(e)}', 'danger')
        return render_template('blood/requests_list.html', requests=[])
    finally:
        cursor.close()

@app.route('/blood-requests/add', methods=['GET', 'POST'])
@login_required
def add_blood_request():
    if request.method == 'POST':
        # Get data from the form
        hospital_id = request.form.get('hospital_id')
        bank_id = request.form.get('bank_id', '1')  # Default Bank_ID
        blood_group = request.form.get('blood_group')
        units_requested = request.form.get('units')
        notes = request.form.get('notes', '')

        # Validate inputs
        if not hospital_id:
            flash('Please select a hospital.', 'danger')
            return redirect(url_for('add_blood_request'))
        if not blood_group:
            flash('Please select a blood group.', 'danger')
            return redirect(url_for('add_blood_request'))
        try:
            units = int(units_requested)
            if units <= 0:
                flash('Units requested must be greater than 0.', 'danger')
                return redirect(url_for('add_blood_request'))
        except (ValueError, TypeError):
            flash('Please enter a valid number of units.', 'danger')
            return redirect(url_for('add_blood_request'))

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            # Get next Request_ID
            cursor.execute('SELECT MAX(Request_ID) AS max_id FROM Blood_Request')
            result = cursor.fetchone()
            next_id = 1
            if result and result['max_id'] is not None:
                next_id = int(result['max_id']) + 1

            # Insert into Blood_Request
            query = '''
                INSERT INTO Blood_Request 
                (Request_ID, Hospital_ID, Bank_ID, Blood_Group, Units_Requested, Status, Request_Date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            cursor.execute(query, (
                next_id,
                hospital_id,
                bank_id,
                blood_group,
                units,
                'Pending',
                datetime.now().strftime('%Y-%m-%d')
            ))

            # Check if stock exists for this Bank_ID and Blood_Group
            cursor.execute('''
                SELECT Units FROM Blood_Stock 
                WHERE Bank_ID = %s AND Blood_Group = %s
            ''', (bank_id, blood_group))
            stock = cursor.fetchone()

            if stock:
                # Stock exists, check if enough units are available
                available_units = stock['Units']
                if available_units < units:
                    flash(f'Not enough units available. Only {available_units} units of {blood_group} in stock.', 'danger')
                    mysql.connection.rollback()
                    return redirect(url_for('add_blood_request'))
                # Update stock by reducing units
                cursor.execute('''
                    UPDATE Blood_Stock 
                    SET Units = Units - %s 
                    WHERE Bank_ID = %s AND Blood_Group = %s
                ''', (units, bank_id, blood_group))
            else:
                # Stock doesn't exist, initialize it (Stock_ID will auto-increment)
                cursor.execute('''
                    INSERT INTO Blood_Stock (Bank_ID, Blood_Group, Units)
                    VALUES (%s, %s, %s)
                ''', (bank_id, blood_group, 0))  # Initialize with 0 units
                flash(f'No stock available for {blood_group}. Stock initialized, please add units.', 'warning')
                mysql.connection.rollback()
                return redirect(url_for('add_blood_request'))

            mysql.connection.commit()
            flash('Blood request added successfully!', 'success')
            return redirect(url_for('blood_request_list'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error adding blood request: {str(e)}', 'danger')
            print("Error adding blood request:", str(e))  # Debug
        finally:
            cursor.close()
    
    # Get hospitals for dropdown
    hospitals = []
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT Hospital_ID, Name FROM Hospital')  # Ensure exact table name
        hospitals = cursor.fetchall()
        print("Hospitals fetched:", hospitals)  # Debug
        cursor.close()
    except Exception as e:
        flash(f'Error loading hospitals: {str(e)}', 'warning')
        print("Error loading hospitals:", str(e))  # Debug

    return render_template('blood/request.html',
                         hospitals=hospitals,
                         title='New Blood Request')



@app.route('/donor/delete/<int:id>', methods=['POST'])
@login_required
def delete_donor(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        # Check if donor has any donations
        cursor.execute('SELECT COUNT(*) as count FROM Transaction WHERE Donor_ID = %s', (id,))
        result = cursor.fetchone()
        
        if result and result['count'] > 0:
            flash('Cannot delete donor with existing donations. Please remove donations first.', 'danger')
            return redirect(url_for('donor_list'))
        
        # Delete the donor
        cursor.execute('DELETE FROM Donor WHERE Donor_ID = %s', (id,))
        mysql.connection.commit()
        flash('Donor deleted successfully!', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error deleting donor: {str(e)}', 'danger')
    finally:
        cursor.close()
        
    return redirect(url_for('donor_list'))

@app.route('/donor/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_donor(id):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Get the donor by ID
    cursor.execute('SELECT * FROM Donor WHERE Donor_ID = %s', (id,))
    donor = cursor.fetchone()
    
    if not donor:
        flash('Donor not found', 'danger')
        return redirect(url_for('donor_list'))
    
    # If form submitted
    if request.method == 'POST':
        # Update donor information from form
        donor_data = {
            'name': request.form.get('name'),
            'age': request.form.get('age'),
            'gender': request.form.get('gender'),
            'blood_group': request.form.get('blood_group'),
            'contact': request.form.get('contact'),
            'email': request.form.get('email'),
            'last_donation': request.form.get('last_donation') or None,
            'eligibility': request.form.get('eligibility', 'Not Eligible'),
            'id': id
        }
        
        try:
            cursor.execute('''
                UPDATE Donor 
                SET Name = %(name)s, Age = %(age)s, Gender = %(gender)s, 
                    Blood_Group = %(blood_group)s, Contact_Number = %(contact)s, 
                    Email = %(email)s, Last_Donation_Date = %(last_donation)s,
                    Eligibility_Status = %(eligibility)s
                WHERE Donor_ID = %(id)s
            ''', donor_data)
            mysql.connection.commit()
            flash('Donor updated successfully!', 'success')
            return redirect(url_for('donor_list'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error updating donor: {str(e)}', 'danger')
        finally:
            cursor.close()
    
    # Display form with current donor data
    return render_template('donor/edit.html', donor=donor)

@app.route('/blood-requests/update-status/<int:request_id>', methods=['POST'])
@login_required
def update_request_status(request_id):
    new_status = request.form['status']
    cursor = mysql.connection.cursor()
    try:
        cursor.execute('''
            UPDATE Blood_Request 
            SET status = %s 
            WHERE request_id = %s
        ''', (new_status, request_id))
        mysql.connection.commit()
        flash('Status updated successfully!', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        cursor.close()
    return redirect(url_for('blood_request_list'))

# ======================
# Blood Stock Management
# ======================
@app.route('/blood-stock', methods=['GET', 'POST'])
@login_required
def blood_stock():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Fetching data on GET request
    cursor.execute('SELECT Blood_Group, Units as units, Expiry_Date as expiry FROM Blood_Stock')
    stock_data = cursor.fetchall()
    
    # Process stock data
    stock = []
    for item in stock_data:
        stock.append({
            'blood_group': item['Blood_Group'],
            'units': item['units'],
            'expiry': item['expiry'],
            'last_updated': None  # Set to None since this field isn't used
        })
    
    # Handling POST request
    if request.method == 'POST':
        # Get form data
        blood_group = request.form.get('blood_group')
        try:
            units = int(request.form.get('units', 0))
        except ValueError:
            units = 0
            
        expiry_date = request.form.get('expiry')
        
        try:
            # Insert data into the Blood_Stock table - removed last_updated field
            cursor.execute('''
                INSERT INTO Blood_Stock (Blood_Group, Units, Expiry_Date) 
                VALUES (%s, %s, %s)
            ''', (blood_group, units, expiry_date))
            mysql.connection.commit()
            flash('Blood stock updated successfully!', 'success')
            return redirect(url_for('blood_stock'))
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error updating blood stock: {str(e)}', 'danger')
        finally:
            cursor.close()

    return render_template('blood/stock.html', stock=stock)
# ======================
# User Activities
# ======================
@app.route('/user-activities')
@login_required
def user_activities():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('''
        SELECT * FROM user_activities 
        WHERE user_id = %s 
        ORDER BY timestamp DESC 
        LIMIT 50
    ''', (current_user.id,))
    activities = cursor.fetchall()
    cursor.close()
    return render_template('user/activities.html', activities=activities)

# ======================
# Reports
# ======================
@app.route('/reports')
@login_required
def generate_reports():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Blood Stock Report
    cursor.execute('SELECT Blood_Group, SUM(Units) AS total FROM Blood_Stock GROUP BY Blood_Group')
    blood_report = cursor.fetchall()
    
    # Donation Activity
    cursor.execute('''
        SELECT DATE(Transaction_Date) AS date, 
               COUNT(*) AS donations,
               SUM(Units) AS total_units
        FROM Transaction
        GROUP BY DATE(Transaction_Date)
        ORDER BY date DESC
        LIMIT 7
    ''')
    donation_activity = cursor.fetchall()
    
    cursor.close()
    
    return render_template('report/main.html',
                          blood_report=blood_report,
                          donation_activity=donation_activity)

# ======================
# Activity Tracking
# ======================
@app.after_request
def log_activity(response):
    if current_user.is_authenticated:
        cursor = mysql.connection.cursor()
        
        # Sanitize form data (exclude passwords)
        sanitized_data = {
            k: v for k, v in request.form.items() 
            if k.lower() not in ['password', 'confirm_password']
        }
        
        try:
            cursor.execute('''
                INSERT INTO user_activities 
                (user_id, action, details)
                VALUES (%s, %s, %s)
            ''', (
                current_user.id,
                request.endpoint,
                str(sanitized_data)
            ))
            mysql.connection.commit()
        except Exception as e:
            mysql.connection.rollback()
        finally:
            cursor.close()
    return response

if __name__ == '__main__':
    app.run(debug=True)
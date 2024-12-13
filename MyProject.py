from flask import Flask, render_template, flash, request, redirect, url_for, session, logging, jsonify
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators
from passlib.hash import sha256_crypt
from functools import wraps
from web3 import Web3
from solcx import compile_source, install_solc
import json

# Installer la version spécifique de solc
install_solc('0.8.0')

app = Flask(__name__)

# Config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'SendInfos'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# Init MySQL
mysql = MySQL(app)

@app.route('/')
def helo():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('login'))
    return wrap

def admin_only(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session and session.get('username') == 'admin':
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Admin access only', 'danger')
            return redirect(url_for('login'))
    return wrap

@app.route('/articles')
@is_logged_in
@admin_only
def articles():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM articles")
    articles = cur.fetchall()
    if result > 0:
        return render_template('articles.html', articles=articles)
    else:
        msg = 'No Articles Found'
        return render_template('articles.html', msg=msg)
    cur.close()

class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=25)])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (name, email, username, password) VALUES(%s, %s, %s, %s)", (name, email, username, password))
        mysql.connection.commit()
        cur.close()

        flash('You are now registered and can log in', 'success')
        return redirect(url_for('helo'))

    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_candidate = request.form['password']

        cur = mysql.connection.cursor()
        result = cur.execute("SELECT * FROM users WHERE username = %s", [username])

        if result > 0:
            data = cur.fetchone()
            password = data['password']

            if sha256_crypt.verify(password_candidate, password):
                session['logged_in'] = True
                session['username'] = username

                flash('You are now logged in', 'success')
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid login'
                return render_template('login.html', error=error)
            cur.close()
        else:
            error = 'Username not found'
            return render_template('login.html', error=error)

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@is_logged_in
@admin_only
def dashboard():
    cur = mysql.connection.cursor()
    result = cur.execute("SELECT * FROM articles")
    articles = cur.fetchall()
    if result > 0:
        return render_template('dashboard.html', articles=articles)
    else:
        msg = 'No Articles Found'
        return render_template('dashboard.html', msg=msg)
    cur.close()

class ArticleForm(Form):
    firstname = StringField('firstname', [validators.Length(min=1, max=22)])
    lastname = StringField('lastname', [validators.Length(min=2, max=22)])
    CIN     = StringField('CIN', [validators.Length(min=3, max=13)])

@app.route('/add_article', methods=['GET', 'POST'])
@is_logged_in
def add_article():
    form = ArticleForm(request.form)
    if request.method == 'POST' and form.validate():
        firstname = form.firstname.data   
        lastname = form.lastname.data
        CIN = form.CIN.data
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO articles(firstname, lastname, CIN) VALUES(%s, %s, %s)", (firstname, lastname, CIN))
        mysql.connection.commit()
        cur.close()
        flash('Demande envoyée', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_article.html', form=form)

@app.route('/delete_article/<int:id>', methods=['POST'])
@is_logged_in
def delete_article(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM articles WHERE id = %s", [id])
    mysql.connection.commit()
    cur.close()

    flash('Request Deleted', 'success')
    return redirect(url_for('dashboard'))

@app.route('/create_certificate', methods=['POST'])
@is_logged_in
def create_certificate():
    data = request.get_json()
    firstname = data['firstname']
    lastname = data['lastname']
    CIN = data['CIN']
    current_date = data['current_date']

    # Lire le contrat Solidity
    with open('./MyContract.sol', 'r') as file:
        contract_source_code = file.read()
    
    # Compiler le contrat
    compiled_sol = compile_source(contract_source_code, solc_version='0.8.0')
    contract_id, contract_interface = compiled_sol.popitem()
    
    # Connexion à Ganache
    ganache_url = "http://127.0.0.1:7545"
    web3 = Web3(Web3.HTTPProvider(ganache_url))
    
    # Vérifier la connexion
    if not web3.is_connected():
        return jsonify({"status": "Failed to connect to Ganache"}), 500
    
    # Charger le compte pour le déploiement
    web3.eth.default_account = web3.eth.accounts[0]
    
    # Créer l'objet contrat
    Certificate = web3.eth.contract(abi=contract_interface['abi'], bytecode=contract_interface['bin'])
    
    # Construire les informations du certificat
    name = f"{lastname} {firstname}"
    name_ck = "Monsieur Amine // Par exemple"
    arnd = "Agdal, Rabat"
    declaration = f"Je suis le cheick d'arrondissement {arnd}, {name_ck} et je reconnais que {name} qui a la {CIN} n'exerce actuellement aucune profession"
    
    # Déployer le contrat en passant les valeurs des paramètres du constructeur
    tx_hash = Certificate.constructor(name, current_date, declaration).transact()
    tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    
    # Adresse du contrat déployé
    contract_address = tx_receipt.contractAddress
    print(f"Contract deployed at address: {contract_address}")
    # Utilisation du contexte de gestion pour ouvrir et écrire dans un fichier
    with open("mon_contrat.txt", "w", encoding='utf-8') as fichier:
        fichier.write(f"Je suis le cheick d'arrondissement {arnd}, {name_ck} et je reconnais que {name} qui a la {CIN} n'exerce actuellement aucune profession\n")
        fichier.write(f"Contrat déployé à l'adresse : {contract_address}\n")

    return jsonify({"status": "Certificate created", "contract_address": contract_address})

if __name__ == '__main__':
    app.secret_key = 'super secret key'
    app.run(host='0.0.0.0', port=88, debug=False)

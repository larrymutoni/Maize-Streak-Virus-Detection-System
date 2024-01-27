from flask import Flask, render_template, request, jsonify, send_from_directory, g, session, redirect, flash
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.vgg16 import preprocess_input
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from flask_bcrypt import Bcrypt
import os
import numpy as np
import mysql.connector
from datetime import datetime

app = Flask(__name__)
bcrypt = Bcrypt(app)

app.config.from_mapping(
    DATABASE_HOST="localhost",
    DATABASE_USER="root",
    DATABASE_PASSWORD="",
    DATABASE_NAME="msv2"
)
app.secret_key = '2024'
model_path = os.path.join("model", "combined_model2.h5")
model = load_model(model_path)
upload_folder = 'uploads'
allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}

test_datagen = ImageDataGenerator(rescale=1./255)

def get_db():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=app.config['DATABASE_HOST'],
            user=app.config['DATABASE_USER'],
            password=app.config['DATABASE_PASSWORD'],
            database=app.config['DATABASE_NAME']
        )
    return g.db

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/')
def index():
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])

def login():
    if request.method == 'POST':
        email = request.form['email']

       
        session['user_info'] = {
            'email': email,
            'first_name': 'J',  
            'last_name': 'D',  
        }

        return redirect('/home')

    return render_template('login.html')




@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        return perform_registration(request.form)
    else:
        return render_template('register.html')

def perform_registration(form_data):
    db = get_db()
    email = form_data.get('email')
    first_name = form_data.get('first_name')
    last_name = form_data.get('last_name')
    password = form_data.get('password')

    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()

        if existing_user:
            flash('Email already registered', 'error')
            return render_template('register.html')

       
        with db.cursor() as cursor:
            query = "INSERT INTO users (email, first_name, last_name, password) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (email, first_name, last_name, password))
            db.commit()

            session['user_info'] = {
                'email': email,
                'first_name': first_name,
                'last_name': last_name
            }

            return redirect('/home')

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        flash('Registration failed', 'error')

    return render_template('register.html')





@app.route('/logout')
def logout():
    
    session.pop('user_info', None)

    
    return redirect('/login')

@app.route('/home')
def home():
    
    user_info = session.get('user_info', None)
    
    
    if user_info:
        return render_template('home.html', user_info=user_info)
    else:
        
        return redirect('/login')

@app.route('/predict', methods=['POST'])
def predict():
    db = get_db()

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    if file and allowed_file(file.filename):
        img_path = os.path.join("uploads", file.filename)
        file.save(img_path)

       
        img = image.load_img(img_path, target_size=(224, 224))
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)
        img_array = test_datagen.standardize(img_array) 

        
        prediction = model.predict(img_array)
        class_label = "Healthy" if prediction[0] > 0.5 else "MSV"
        confidence = prediction[0][0] if class_label == "Healthy" else 1 - prediction[0][0]

        
        save_to_database(file.filename, class_label, confidence)

        return render_template('home.html', prediction={'class_label': class_label, 'confidence': confidence * 100, 'image_path': file.filename})

    else:
        return jsonify({'error': 'File type not allowed'})

def save_to_database(image_path, class_label, confidence):
    try:
        query = "INSERT INTO predictions (image_path, class_label, confidence, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)"
        timestamp = datetime.now()
        
        confidence = float(confidence)
        values = (image_path, class_label, confidence, timestamp, timestamp)

        with get_db().cursor() as cursor:
            cursor.execute(query, values)
            get_db().commit()
            print("Record inserted successfully")

    except mysql.connector.Error as err:
        print(f"Error: {err}")
        

@app.route('/history')
def history():
    db = get_db()
    query = "SELECT * FROM predictions ORDER BY created_at DESC"
    with db.cursor(dictionary=True) as cursor:
        cursor.execute(query)
        past_predictions = cursor.fetchall()
    return render_template('history.html', past_predictions=past_predictions)

@app.route('/past_predictions')
def past_predictions():
    db = get_db()
    query = "SELECT * FROM predictions ORDER BY created_at DESC"
    with db.cursor(dictionary=True) as cursor:
        cursor.execute(query)
        past_predictions = cursor.fetchall()
    return render_template('past_predictions.html', past_predictions=past_predictions)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(upload_folder, filename)

if __name__ == '__main__':
    app.run(debug=True)

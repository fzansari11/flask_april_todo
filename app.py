from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
import os
import boto3
import json
import logging

logging.basicConfig(
    filename = 'app.log',
    level=logging.INFO)

app = Flask(__name__)
db_user = os.environ.get('DB_USER')
db_pass = os.environ.get('DB_PASS')
db_host = os.environ.get('DB_HOST')
db_name = os.environ.get('DB_NAME')

def get_db_secret(secret_name, region_name='us-east-2'):
    client = boto3.client('secretsmanager', region_name=region_name)
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    
    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

# Fetch credentials from Secrets Manager
secret = get_db_secret('prod/rds/mydb')



basedir = os.path.abspath(os.path.dirname(__file__)) # Get the directory of the current file
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db') 
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{secret['username']}:{secret['password']}@{secret['host']}/{secret['dbname']}"
#app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
BUCKET_NAME = 'flask-todo-april-bucket'

def upload_to_s3(file_path, s3_key):
    s3 = boto3.client('s3')
    try:
        s3.upload_file(file_path, BUCKET_NAME, s3_key)
        logging.info(f"File {file_path} uploaded to S3 bucket {BUCKET_NAME} with key {s3_key}")
    except Exception as e:
        logging.error(f"Error uploading file to S3: {e}")


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(100), nullable=False)
    completed = db.Column(db.Boolean, default=False)

@app.route('/')
def home():
    tasks = Task.query.all()
    return render_template('index.html', tasks = tasks)

@app.route('/add', methods= ['POST'])
def add_task():
    task = request.form.get('task')
    file = request.files.get('file')
    if file:
        # Save the file locally and then upload to S3
        logging.info(f"Received file: {file.filename}")
        file_path = os.path.join(basedir, file.filename)
        file.save(file_path)
        upload_to_s3(file_path, file.filename)
        os.remove(file_path)
    else:
        logging.info("No file received")
    new_task = Task(title=task)
    db.session.add(new_task)
    db.session.commit()
    return redirect('/')

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    task = Task.query.get(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect('/')

@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    task = Task.query.get(task_id)
    task.completed = True
    db.session.commit()
    return redirect('/')

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    task = Task.query.get(task_id)
    if request.method == 'POST':
        task.title = request.form.get('task')
        db.session.commit()
        return redirect('/')
    return render_template('edit.html', task=task)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0',debug=True)
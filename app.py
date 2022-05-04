
from datetime import datetime, time
import cv2
from flask import Flask, render_template, request, redirect, Blueprint, flash, Response, make_response, url_for, \
    send_file, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import numpy as np
import face_recognition
import time


app = Flask (__name__)
app.config['SECRET_KEY'] = 'fctvbgyijnhubgyftvcdrftvgbyh'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vkr.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['UPLOAD_FOLDER'] = "/Users/el/Desktop/flask/KnownFaces"
db = SQLAlchemy(app)
path = app.config['UPLOAD_FOLDER']

login_manager = LoginManager()
login_manager.login_view = '/login'
login_manager.init_app(app)


camera = cv2.VideoCapture (0)


@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

    def __repr__(self):
        return '<User %r>' % self.id


class Worker(UserMixin,db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.ForeignKey(User.id))
    fio = db.Column (db.String (1000))
    image = db.Column (db.String (255), nullable=False)

    def __repr__(self):
        return  self.fio


class Result(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_users = db.Column(db.ForeignKey(User.id))
    fio = db.Column(db.String(255))
    time = db.Column(db.String(255))

    def __repr__(self):
        return  self.time


@app.route('/')
@app.route('/home')
def index():
    return render_template("index.html")


@app.route('/profile')
@login_required
def profile():
    return render_template("profile.html", name=current_user.name)


@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == "POST":
        try:
            email = request.form.get('email')
            password = request.form.get('password')
            remember = True if request.form.get('remember') else False

            user = User.query.filter_by (email=email).first ( )

            # check if the user actually exists
            # take the user-supplied password, hash it, and compare it to the hashed password in the database
            if not user or not check_password_hash (user.password, password):
                flash ('Please check your login details and try again.')
                return redirect ('/login')
            login_user (user, remember=remember)
            return redirect('/profile')
        except:
            return "Ошибка при авторизации"
    else:
        return render_template("login.html")


@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == "POST":
        try:
            email = request.form.get('email')
            name = request.form.get('name')
            password = request.form.get('password')

            user = User.query.filter_by (
                email=email).first( )  # if this returns a user, then the email already exists in database

            if user:  # if a user is found, we want to redirect back to signup page so user can try again
                return redirect('/signup')

            # create a new user with the form data. Hash the password so the plaintext version isn't saved.
            new_user = User(email=email, name=name, password=generate_password_hash (password, method='sha256'))

            # add the new user to the database
            db.session.add(new_user)
            db.session.commit( )
            return redirect('/login')
        except:
            return "Ошибка при создании пользователя"
    else:
        flash ('Email address already exists')
        return render_template("signup.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return render_template("index.html")


@app.route('/upload', methods=['POST', 'GET'])

def upload():
    if request.method == 'POST':
        pic = request.files['pic']
        username = current_user.name.strip ( ).capitalize ( )
        user_folder = os.path.join (app.config['UPLOAD_FOLDER'], username)
        pic.save (os.path.join (user_folder, secure_filename(pic.filename)))
        filename = secure_filename(pic.filename)
        worker = Worker (image=pic.read ( ), fio=filename, id_user=current_user.id)
        db.session.add(worker)
        db.session.commit()
        return redirect('/upload')
    if request.method == 'GET':
        workers = Worker.query.filter_by(id_user = current_user.id)
        return render_template ('upload.html', workers=workers)




@app.route ("/edit/<int:worker_id>/", methods=['GET', 'POST'])
@login_required
def edit(worker_id):
    editedWorker = db.session.query (Worker).filter_by (id=worker_id).one ( )
    if request.method == 'POST':

        if request.form['name'] :
            editedWorker.fio = request.form['name']

            return redirect('/upload')
    else:
        return render_template ('edit.html', workers=editedWorker)




@app.route ('/delete/<int:worker_id>/', methods=['GET', 'POST'])
@login_required
def delete(worker_id):
    workerToDelete = db.session.query (Worker).filter_by (id=worker_id).one()
    if request.method == 'POST':
        db.session.delete (workerToDelete)
        db.session.commit ( )
        return redirect  ('/upload')
    else:
        return render_template ('delete.html', workers=workerToDelete)


@app.route('/recognition')
@login_required
def recognition():
    return render_template("recognition.html")


@app.route('/video_feed', methods=['GET'])
@login_required
def video_feed():
    if request.method == 'GET':
        username = current_user.name.strip ( ).capitalize ( )
        user_folder = os.path.join (app.config['UPLOAD_FOLDER'], username)

        images = []
        classNames = []
        myList = []

        for file in os.listdir (user_folder):
            if file.endswith (".jpg") or file.endswith(".jpeg"):
                myList.append(file)


        print(myList)

        for cls in myList:
            curImg = cv2.imread (f'{user_folder}/{cls}')
            images.append (curImg)
            classNames.append (os.path.splitext (cls)[0])

        print (classNames)  # имена всех фото

        def findEncodings(images):  # декодирует фото
            encodeList = []
            for img in images:
                img = cv2.cvtColor (img, cv2.COLOR_BGR2RGB)
                encode = face_recognition.face_encodings (img)[0]
                encodeList.append (encode)
            return encodeList  # декодируемые фото

        id_us = current_user.id
        def markAttendance(name):  # записывает имя человека в кадре и время

            res = Result.query.filter_by(fio = name).first()
            now = datetime.now ( )
            if res:
                time.sleep(5)
            result = Result (time=now, fio=name, id_users=id_us)
            db.session.add (result)
            db.session.commit ( )

        encodeListKnown = findEncodings (images)
        print ("Декодирование закончено")

        def gen_frames():
            while True:
                success, frame = camera.read ( )

                imgS = cv2.resize (frame, (0, 0), None, 0.25, 0.25)
                imgS = cv2.cvtColor (imgS, cv2.COLOR_BGR2RGB)

                facesCurFrame = face_recognition.face_locations (imgS)
                encodeCurFrame = face_recognition.face_encodings (imgS, facesCurFrame)

                # цикл для распознавания ниже
                for encodeFace, faceLoc in zip (encodeCurFrame, facesCurFrame):
                    matches = face_recognition.compare_faces (encodeListKnown, encodeFace)  # распознавание
                    faceDis = face_recognition.face_distance (encodeListKnown, encodeFace)  # вероятность
                    #print (faceDis)
                    matchIndex = np.argmin (faceDis)

                    if matches[matchIndex]:  # проверка на известные лица
                        name = classNames[matchIndex]
                        # рисуем рамку с именем вокруг лица
                        y1, x2, y2, x1 = faceLoc
                        y1, x2, y2, x1 = y1 * 4, x2 * 4, y2 * 4, x1 * 4
                        cv2.rectangle (frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.rectangle (frame, (x1, y2 - 35), (x2, y2), (0, 255, 0), cv2.FILLED)
                        cv2.putText (frame, name, (x1 + 6, y2 - 6), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 2)
                        markAttendance (name)

                # read the camera frame
                if not success:
                    break
                else:
                    ret, buffer = cv2.imencode ('.jpg', frame)
                    frame = buffer.tobytes ( )
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


        return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/result', methods=['GET'])
@login_required
def result():
    results = Result.query.filter_by(id_users = current_user.id)
    return render_template ('result.html', results=results)

if __name__ == '__main__':
    app.run (debug=True)

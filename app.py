from flask import Flask, request, jsonify, render_template,redirect,make_response
import base64
from datetime import datetime

import pgapp as pg

app = Flask(__name__)

@app.route('/img_upload', methods=['POST'])
def upload_image():
    uploaded_file = request.files['image']
    binary_data=uploaded_file.read()
    mimetype = uploaded_file.mimetype
    pg.cursor.execute("INSERT INTO images(data,mimetype) VALUES(%s,%s) RETURNING id",(binary_data,mimetype))
    pg.conn.commit()
    return {"status_code":200,"message":"Ok","id":pg.cursor.fetchone()[0]}
    
@app.route('/',methods=['GET'])
def index():
    if request.cookies.get("secret_key"):
        username=request.cookies.get("username")
        secret_key=request.cookies.get("secret_key")
        pg.cursor.execute("SELECT * FROM user_stats WHERE username=%s;",(username,))
        user=pg.cursor.fetchone()
        points=0
        for i in user[3]:
            points+=i["points"]
            
        current_datetime = datetime.now()
        formatted_datetime = str(current_datetime.strftime("%Y-%m-%d %H:%M:%S"))

        upcoming_events=[]
        for event_id in user[1]:
            event=pg.pgGetEvent(event_id)
            if str(event[4])>formatted_datetime:
                upcoming_events.append(event)
        upcoming_events=sorted(upcoming_events,key=lambda i:i[4])
        
        #get images
        for i in range(len(upcoming_events)):
            if (len(upcoming_events[i][5])==0):
                upcoming_events[i]=list(upcoming_events[i])
                upcoming_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
                upcoming_events[i]=tuple(upcoming_events[i])
            else:
                upcoming_events[i]=list(upcoming_events[i])
                upcoming_events[i][5]=pg.pgGetImage(upcoming_events[i][5][0])
                upcoming_events[i]=tuple(upcoming_events[i])
                
        registered_events=[]
        if secret_key!=None:
            for event_id in pg.pgGetRecentEvents(username,secret_key):
                event = pg.pgGetEvent(event_id)
                if str(event[4])>formatted_datetime:
                    registered_events.append(event)
        #get images
        for i in range(len(registered_events)):
            if (len(registered_events[i][5])==0):
                registered_events[i]=list(registered_events[i])
                registered_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
                registered_events[i]=tuple(registered_events[i])
            else:
                registered_events[i]=list(registered_events[i])
                registered_events[i][5]=pg.pgGetImage(registered_events[i][5][0])
                registered_events[i]=tuple(registered_events[i])
        print(registered_events[0][5][:100])
        
        for i in range(len(registered_events)):
            date = registered_events[i][4]
            time_difference=date-datetime.now()
            registered_events[i]=list(registered_events[i])
            registered_events[i][4]=time_difference.days
            registered_events[i]=tuple(registered_events[i])
        
        pg.cursor.execute("SELECT * FROM events ORDER BY date DESC;")
        latest=pg.cursor.fetchall()[0]
        if len(latest[5])==0:
            latest=list(latest)
            latest[5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
            latest=tuple(latest)
        else:
            latest=list(latest)
            latest[5]=pg.pgGetImage(latest[5][0])
            latest=tuple(latest)
        return render_template('index.html',
                               username=request.cookies.get("username"),
                               profile_link='/myprofile',
                               points=points,
                               rank=pg.pgGetRank(username),
                               attended_events=len(user[1]),
                               upcoming_events=upcoming_events,
                               registered_events=registered_events,
                               latest=latest
                               )
    else:
        return render_template('index.html',
                               username="Guest User",
                               profile_link='/login')

@app.route('/login',methods=["GET"])
def login():
    if request.cookies.get("secret_key")!=None:
        return redirect('/')
    else:
        return render_template('login.html',username="Guest User",profile_link='/login')

@app.route('/signup',methods=["GET"])
def signup():
    if request.cookies.get("secret_key"):
        return redirect('/')
    else:
        return render_template('signup.html',username="Guest User",profile_link='/login')

@app.route('/api/login',methods=["POST"])
def apiLogin():
    resp = pg.pgLogin(request.form['username'],request.form['password'])
    if resp["status_code"]==200:
        secret_key=resp["secret_key"]
        response = make_response(redirect('/'))
        response.set_cookie('username',request.form['username'])
        response.set_cookie('secret_key',secret_key)
        return response
    else:
        return render_template('login.html',username="Guest User",profile_link='/login',message=resp['message'])

@app.route('/api/logout',methods=["POST"])
def apiLogout():
    pg.pgLogout(request.cookies['username'],request.cookies['secret_key'])
    response = make_response(redirect('/login'))
    response.set_cookie['secret_key',None]
    response.set_cookie['username',None]
    return response

@app.route('/create_event',methods=['GET'])
def createEvent():
    if request.cookies.get('username')!=None:
        roles=pg.pgUserFetch(request.cookies.get('username'))["data"]["roles"]
        if "organizer" in roles or "admin" in roles:
            return render_template('createEvent.html',username=request.cookies.get("username"),profile_link='/myprofile',auth=True)
        else:
            return render_template('createEvent.html',username=request.cookies.get("username"),profile_link='/myprofile',auth=False)
        
    else:
        return redirect('/login')

@app.route('/api/create_event',methods=["POST"])
def apiCreateEvent():
    binary_data=request.files['image'].read()
    mimetype=request.files['image'].mimetype
    pg.cursor.execute("INSERT INTO images(data,mimetype) VALUES(%s,%s) RETURNING id",(binary_data,mimetype))
    pg.conn.commit()
    image_id=pg.cursor.fetchone()[0]
    if pg.pgAuthorizeCreateEvent(request.cookies.get('username'),request.cookies.get('secret_key')):
        date={
            "year":int(request.form['year']),
            "month":int(request.form['month']),
            "day":int(request.form['day']),
            "hour":int(request.form['hour']),
            "minute":int(request.form['minute']),
        }
        resp = pg.pgCreateEvent(request.cookies.get('username'),
                         request.form['eventName'],
                         request.form['description'],
                         request.form['category'],
                         date,
                         [image_id],
                         [request.cookies.get('username')]
                         )
        if resp['status_code']==200:
            return render_template('createEventConfirm.html')
        else:
            return render_template('createEvent.html',username=request.cookies.get("username"),profile_link='/myprofile',message=resp['message'])

@app.route('/myprofile',methods=["GET"])
def myprofile():
    username=request.cookies.get('username')
    secret_key=request.cookies.get('secret_key')
    if username==None:
        return redirect('/login')
    pg.cursor.execute("SELECT * FROM user_stats WHERE username=%s;",(username,))
    user=pg.cursor.fetchone()
    points=0
    for i in user[3]:
        points+=i["points"]
    recent_events_ids=pg.pgGetRecentEvents(username,secret_key)
    if recent_events_ids==False:
        return redirect('/login')
    recent_events=[]
    for id in recent_events_ids:
        recent_events.append(pg.pgGetEvent(id))
        
    #get image
    for i in range(len(recent_events)):
        if (len(recent_events[i][5])==0):
            recent_events[i]=list(recent_events[i])
            recent_events[i][5]="https://cdn.builder.io/api/v1/image/assets/TEMP/9d3041a297c47abe0747b9f55a58146e9ae55c83be378abf990f357e4b053464?placeholderIfAbsent=true&apiKey=2cbf1f5487444b28a9e58914868be763"
            recent_events[i]=tuple(recent_events[i])
        else:
            recent_events[i]=list(recent_events[i])
            recent_events[i][5]=pg.pgGetImage(recent_events[i][5][0])
            recent_events[i]=tuple(recent_events[i])
    return render_template('/myprofile.html',username=username,workshop_count=len(user[1]),points=points,rank=pg.pgGetRank(username),recent_events=recent_events)

@app.route('/test',methods=["GET"])
def test():
    return render_template('myprofile.html')
if __name__ == "__main__":
    app.run(debug=True)
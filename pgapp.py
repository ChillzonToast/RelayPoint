import hmac
import hashlib
import dotenv,os
import psycopg2
import random
import json

dotenv.load_dotenv()
psql_password=os.getenv("POSTGRESQL_PASSWORD")
hash_key=os.getenv("HASH_KEY")

def hasher(password: str) -> str:
    """
    Hashes a password using HMAC with a provided key (without salting).
    
    Args:
        password (str): The plain text password.
        
    Returns:
        str: The hashed password as a hexadecimal string.
    """
    
    password_bytes = password.encode('utf-8')
    key_bytes = hash_key.encode('utf-8')
    hash_object = hmac.new(key_bytes, password_bytes, hashlib.sha256)
    return hash_object.hexdigest()

def pgConnect():
    try:
        return psycopg2.connect(
            database="relaypoint",
            user="postgres",
            password=psql_password,
            host="localhost",
            port=5432,
        )
    except:
        return False

conn = pgConnect()
cursor = conn.cursor()

def pgCreateUser(username:str,password:str,roles:list):
    cursor.execute("SELECT * FROM users WHERE username=%s;",(username,))
    if username not in (i[0] for i in cursor.fetchall()):
        cursor.execute("INSERT INTO USERS VALUES(%s ,%s, %s)",(username,hasher(password),roles))
        cursor.execute("INSERT INTO user_stats VALUES(%s ,%s, %s, %s)",(username,None,None,None))
        conn.commit()
        return {"status_code":200,"message":"Ok"}
    else:
        return {"status_code":409,"message":f"Username \'{username}\' already exists."}
    

def pgLogin(username:str,password:str):
    cursor.execute("SELECT * FROM users WHERE username=%s;",(username,))
    users=cursor.fetchall()
    if len(users)!=0:
        if users[0][1]==hasher(password):
            secret_key=hasher("BinaryBoys"+str(random.randint(1,10000)))
            cursor.execute("UPDATE users SET secret_key=%s WHERE username=%s;",(secret_key,username))
            conn.commit()
            return {"status_code":200,"message":"Ok","secret_key":secret_key}
        else:
            return {"status_code":401,"message":"Incorrect credentials"}
    else:
        return {"status_code":404,"message":"User not found"}
    
def pgLogout(username:str,secret_key:str):
    cursor.execute("SELECT * FROM users WHERE username=%s;",(username,))
    users=cursor.fetchall()
    if len(users)!=0:
        if users[0][3]==secret_key:
            cursor.execute("UPDATE users SET secret_key=%s WHERE username=%s;",(None,username))
            conn.commit()
            return {"status_code":200,"message":"Ok"}
        else:
            return {"status_code":404,"message":"Forbidden"}
    else:
        return {"status_code":404,"message":"User not found"}
        
    
def pgUserFetch(username:str):
    cursor.execute("SELECT * FROM users WHERE username=%s;",(username,))
    users=cursor.fetchall()
    if len(users)!=0:
        return {"status_code":200,"message":"Ok","data":{"username":username,"roles":users[0][2]}}
    else:
        return {"status_code":404,"message":"User not found"}

def pgUserAddEvents(username:str,secret_key:str,events):
    cursor.execute("SELECT * FROM users WHERE username=%s;",(username,))
    users=cursor.fetchall()
    if users[0][3]==secret_key:
        cursor.execute("SELECT events_ids FROM user_stats WHERE username=%s;",(username,))
        existing_events=cursor.fetchall()[0][0]
        if existing_events!=None:
            for id in events:
                if id not in existing_events:
                    cursor.execute("""UPDATE user_stats SET events_ids = events_ids || %s WHERE username=%s;""",(id,username))
        else:
            for id in events:
                cursor.execute("""UPDATE user_stats SET events_ids = events_ids || %s WHERE username=%s;""",(id,username))
        conn.commit()
        return {"status_code":200,"message":"Ok"}
    else:
        return {"status_code":404,"message":"Forbidden"}


def pgAuthorizeCreateEvent(username,secret_key):
    cursor.execute("SELECT * FROM users WHERE username=%s;",(username,))
    users=cursor.fetchall()
    if users[0][3]==secret_key:
        if "admin" in users[0][2] or "organizer" in users[0][2]:
            return True
    return False
  
def pgCreateEvent(username,title,description,category,date,imageIds=[],organizers=[],access=["all"]):
    sql_date = "{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00".format(
        year=date["year"],
        month=date["month"],
        day=date["day"],
        hour=date["hour"],
        minute=date["minute"]
    )
    cursor.execute("SELECT title FROM events;")
    events=cursor.fetchall()
    for event in events:
        if event[0]==title:
            return {"status_code":409,"message":f"Event \'{title}\' already exists."}
    else:
        cursor.execute("INSERT INTO events (title,description,category,date,image_ids,organizers,access) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (title,description,category,sql_date,imageIds,organizers,access))
        conn.commit()
        cursor.execute("SELECT * FROM events WHERE title=%s;",(title,))
        eventid=cursor.fetchall()[0][0]
        
        cursor.execute("SELECT created_events_ids FROM user_stats WHERE username=%s;",(username,))
        if cursor.fetchall()[0][0]==None:
            cursor.execute("UPDATE user_stats SET created_events_ids = %s WHERE username=%s;",([eventid],username))
        else:
            cursor.execute("UPDATE user_stats SET created_events_ids = created_events_ids || %s WHERE username=%s;",(eventid,username))
        conn.commit()
        return {"status_code":200,"message":"Ok","data":{"id":eventid}}
    
def pgRegisterEvent(username,secret_key,eventid):
    cursor.execute("SELECT * FROM users WHERE username=%s;",(username,))
    users=cursor.fetchall()
    if users[0][3]==secret_key:
        cursor.execute("SELECT registered_users FROM events WHERE id=%s;",(eventid,))
        registered_users=cursor.fetchall()[0][0]
        if registered_users==None:
            cursor.execute("UPDATE events SET registered_users = %s WHERE id=%s;",([username],eventid))
            
            cursor.execute("SELECT events_ids FROM user_stats WHERE username=%s;",(username,))
            if cursor.fetchall()[0][0]==None:
                cursor.execute("UPDATE user_stats SET events_ids = %s WHERE username=%s;",([eventid],username))
            else:
                cursor.execute("UPDATE user_stats SET events_ids = events_ids || %s WHERE username=%s;",(eventid,username))
            conn.commit()
            return {"status_code":200,"message":"Ok"}
        elif username  in registered_users:
            return {"status_code":409,"message":f"Event \'{eventid}\' already registered."}
        else:
            cursor.execute("UPDATE events SET registered_users = array_append(registered_users, %s) WHERE id=%s;",(username,eventid))
            cursor.execute("UPDATE user_stats SET events_ids = events_ids || %s WHERE username=%s;",(eventid,username))
            conn.commit()
            return {"status_code":200,"message":"Ok"}
    else:
        return {"status_code":404,"message":"Forbidden"}

def pgAwardPoints(organizerUsername,secret_key,studentUsername,eventId,points):
    cursor.execute("SELECT * FROM users WHERE username=%s;",(organizerUsername,))
    users=cursor.fetchall()
    if users[0][3]==secret_key:
        roles=pgUserFetch(organizerUsername)["data"]["roles"]
        if "organizer" in roles or "admin" in roles:
            cursor.execute("SELECT organizers FROM events WHERE id=%s;",(eventId,))
            organizers=cursor.fetchall()[0][0]
            if organizerUsername in organizers or "admin" in roles:
                cursor.execute("SELECT points FROM user_stats WHERE username=%s;",(studentUsername,))
                user=cursor.fetchall()[0]
                if user[0]!=None:
                    awarded_events=list(user[0])
                    for event in awarded_events:
                        if int(event["event_id"])==int(eventId):
                            return {"status_code":409,"message":f"Event \'{eventId}\' already awarded to \'{studentUsername}\'."}
                    else:
                        awarded_events.append({"event_id":eventId,"points":points})
                        cursor.execute("UPDATE user_stats SET points=%s WHERE username=%s;",(json.dumps(awarded_events),studentUsername))
                        conn.commit()
                        return {"status_code":200,"message":"Ok"}
                else:
                    cursor.execute("UPDATE user_stats SET points=%s WHERE username=%s;",(json.dumps([{"event_id":eventId,"points":points}]),studentUsername))
                    conn.commit()
                    return {"status_code":200,"message":"Ok"}
            else:
                return {"status_code":404,"message":"Event not Organized by User"}
        else:
            return {"status_code":404,"message":"User not an Organizer"}
    else:
        return {"status_code":404,"message":"Forbidden"}
    

# resp = pgLogin("Ibilees","Binubinu")

# if pgAuthorizeCreateEvent("Ibilees",resp["secret_key"]):
#     date={
#         "day":26,
#         "month":1,
#         "year":2025,
#         "hour":15,
#         "minute":30
#     }
#     print(pgCreateEvent("Ibilees","nigga","descripta","hackathono",date,organizers=["Ibilees"]))

# print(pgRegisterEvent("Ibilees",resp["secret_key"],8))

# resp=pgLogout("Ibilees",resp["secret_key"])
# if resp["status_code"]==200:
#     print("\nLogout successful\n")
# else:
#     print("Error Logging out:"+resp["message"])



# print(pgCreateUser("Ibilees","Binubinu",["admin","cse-student"]))
# print(pgCreateUser("Jissykutty","Binaryboys@123",["organizer"]))
# print(pgCreateUser("Shalumol","iloveibinu",["organizer"]))
# print(pgCreateUser("Richu","Shiningstar",["cse-student"]))
username="Ibilees"
password="Binubinu"
resp=pgLogin(username,password)
print(pgRegisterEvent(username,resp["secret_key"],12))
print(pgAwardPoints(username,resp["secret_key"],"Ibilees",12,10))
pgLogout(username,resp["secret_key"])
conn.close()
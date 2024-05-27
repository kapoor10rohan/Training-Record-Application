#!/usr/bin/env python

# This is a simple web server for a training record application.
# It's your job to extend it by adding the backend functionality to support
# recording training in an SQL database. You will also need to support
# user access/session control. You should only need to extend this file.
# The client side code (html, javascript and css) is complete and does not
# require editing or detailed understanding, it serves only as a
# debugging/development aid.

# import the various libraries needed
import http.cookies as Cookie   # some cookie handling support
from http.server import BaseHTTPRequestHandler, HTTPServer # the heavy lifting of the web server
import urllib # some url parsing support
import json   # support for json encoding
import sys    # needed for agument handling
import time   # time support

import base64 # some encoding support
import sqlite3 # sql database
import random # generate random numbers
import datetime

def random_digits(n):
    """This function provides a random integer with the specfied number of digits and no leading zeros."""
    range_start = 10**(n-1)
    range_end = (10**n)-1
    return random.randint(range_start, range_end)

# The following three functions issue SQL queries to the database.

def do_database_execute(op):
    """Execute an sqlite3 SQL query to database.db that does not expect a response."""
    print(op)
    try:
        db = sqlite3.connect('database.db')
        cursor = db.cursor()
        cursor.execute(op)
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()

def do_database_fetchone(op):
    """Execute an sqlite3 SQL query to database.db that expects to extract a single row result. Note, it may be a null result."""
    print(op)
    try:
        db = sqlite3.connect('database.db')
        cursor = db.cursor()
        cursor.execute(op)
        result = cursor.fetchone()
        print(result)
        db.close()
        return result
    except Exception as e:
      print(e)
      return None

def do_database_fetchall(op):
    """Execute an sqlite3 SQL query to database.db that expects to extract a multi-row result. Note, it may be a null result."""
    print(op)
    try:
        db = sqlite3.connect('database.db')
        cursor = db.cursor()
        cursor.execute(op)
        result = cursor.fetchall()
        print(result)
        db.close()
        return result
    except Exception as e:
        print(e)
        return None

# The following build_ functions return the responses that the front end client understands.
# You can return a list of these.

def build_response_message(code, text):
    """This function builds a message response that displays a message
       to the user on the web page. It also returns an error code."""
    return {"type":"message","code":code, "text":text}

def build_response_skill(id,name,gained,trainer,state):
    """This function builds a summary response that contains one summary table entry."""
    return {"type":"skill","id":id,"name":name, "gained":gained,"trainer":trainer,"state":state}

def build_response_class(id, name, trainer, when, notes, size, max, action):
    """This function builds an activity response that contains the id and name of an activity type,"""
    return {"type":"class", "id":id, "name":name, "trainer":trainer, "when":when, "notes":notes, "size":size, "max":max, "action":action}

def build_response_attendee(id, name, action):
    """This function builds an activity response that contains the id and name of an activity type,"""
    return {"type":"attendee", "id":id, "name":name, "action":action}

def build_response_redirect(where):
    """This function builds the page redirection response
       It indicates which page the client should fetch.
       If this action is used, it should be the only response provided."""
    return {"type":"redirect", "where":where}

# The following handle_..._request functions are invoked by the corresponding /action?command=.. request

def handle_login_request(iuser, imagic, content):
    """A user has supplied a username and password. Check if these are
       valid and if so, create a suitable session record in the database
       with a random magic identifier that is returned.
       Return the username, magic identifier and the response action set."""
    response = []
    username=content['username']
    password=content['password']
    check_username = f"SELECT COUNT(*) FROM users WHERE username = '{username}'"
    user_count = do_database_fetchone(check_username)[0]
    if user_count == 0:
        response.append(build_response_message(202, "Username does not exist. Please try again."))
        return [iuser, imagic, response]
    check_password = f"""SELECT userid FROM users
                        WHERE username = '{content['username']}'
                        AND password = '{content['password']}'"""
    user_data = do_database_fetchone(check_password)
    if user_data is not None: # check login details
        userid=user_data[0]
        session_magic = random_digits(8)
        insert_session_query = f"""INSERT INTO session (userid, magic)
                                VALUES ('{userid}', '{session_magic}')"""
        do_database_execute(insert_session_query)
        response.append(build_response_message(200, "Login successful!")) # response
        response.append(build_response_redirect("/index.html"))
        imagic=session_magic
        iuser=username
        return [iuser, session_magic, response]
    else: # for wrong password
        response.append(build_response_message(201, "Invalid Password! Please try again."))
        return [iuser, imagic, response]

def handle_logout_request(iuser, imagic, parameters):
    """This code handles the selection of the logout button.
       You will need to ensure the end of the session is recorded in the database
       And that the session magic is revoked."""
    response = []
    check_for_session = f"SELECT * FROM session WHERE magic = '{imagic}'"
    session_exists = do_database_fetchone(check_for_session)
    if session_exists: # delete session for the particular login
        delete_session_query = f"DELETE FROM session WHERE magic = '{imagic}'"
        do_database_execute(delete_session_query)
        # Response
        response.append(build_response_message(200, "Logout successful!"))
        response.append(build_response_redirect("/logout.html"))
        return [iuser, imagic, response]
    else: # session not present
        response.append(build_response_redirect("/login.html"))
        return [iuser, imagic, response]
def handle_get_my_skills_request(iuser, imagic):
    """This code handles a request for a list of a user's skills.
       You must return a value for all skills, even when it's zero."""
    response = []
    # login
    session_query = f"SELECT * FROM session WHERE magic = '{imagic}'"
    existing_session = do_database_fetchone(session_query)
    userid_extract = f"SELECT userid FROM users WHERE username = '{iuser}'"
    get_userid = do_database_fetchone(userid_extract)
    userid=get_userid[0]
    if existing_session:
        query = f"""
        SELECT main.skillid, main.name, main.start, main.trainerid, main.userid, main.state FROM 
            (SELECT s.skillid, s.name, c.start, c.trainerid, a.userid,
            CASE 
                WHEN a.status = 1 AND c.start < strftime('%s',DATETIME('NOW')) THEN 'passed'
                WHEN a.status = 0 AND c.start > strftime('%s',DATETIME('NOW')) THEN 'scheduled'
                WHEN a.status = 0 AND c.start < strftime('%s',DATETIME('NOW')) THEN 'pending'
                WHEN a.status = 2 AND c.start < strftime('%s',DATETIME('NOW')) THEN 'failed'
            END AS state
            FROM class c
            LEFT JOIN skill s ON c.skillid = s.skillid
            LEFT JOIN attendee a ON a.classid=c.classid
            WHERE a.userid = {userid} AND a.status NOT IN (3, 4)) AS main
        JOIN (SELECT skillid, MAX(start) AS max_start FROM 
            (SELECT s.skillid, c.start
            FROM class c
            LEFT JOIN skill s ON c.skillid = s.skillid
            LEFT JOIN attendee a ON a.classid = c.classid
            WHERE a.userid = {userid} AND a.status NOT IN (3, 4)) AS sub
            GROUP BY skillid) AS sub ON main.skillid = sub.skillid AND main.start = sub.max_start
        """
        skills_data = do_database_fetchall(query)
        trainer_skill=f"""SELECT skillid from trainer where trainerid={userid}"""
        get_trainer_skill=do_database_fetchall(trainer_skill)
        list_skill=[]
        for each in get_trainer_skill:
            list_skill.append(each[0])
        #print(list_skill)
        for skill in skills_data:
            trainer=skill[3]
            query_trainer=f"""SELECT fullname from users where userid={trainer}"""
            get_trainer_name=do_database_fetchone(query_trainer)
            trainer_name=get_trainer_name[0]
            if skill[0] in list_skill:         # response
                skill_response = build_response_skill(skill[0], \
                    skill[1],skill[2] ,trainer_name, "trainer")
                response.append(skill_response)
            else:
                skill_response = build_response_skill(skill[0], skill[1],skill[2],\
                                                trainer_name, skill[5])
                response.append(skill_response)
        state_priority = {'trainer': 1, 'passed': 2, 'scheduled': 3, 'pending': 4, 'failed': 5}
        response = sorted(response, key=lambda sk: state_priority.get(sk['state'],5))
        response.append(build_response_message(0, "Skill list provided"))
        return [iuser, imagic, response]
    else: # User not logged
        response.append(build_response_redirect("/login.html"))
        return [iuser, imagic, response]

def handle_get_upcoming_request(iuser, imagic):
    """Handle a request for upcoming classes."""
    response = []
    session_query = f"SELECT * FROM session WHERE magic = '{imagic}'"
    existing_session = do_database_fetchone(session_query)
    #current_time=datetime.datetime.now().strftime(f"%Y-%m-%d %H:%M:%S")
    userid_extract = f"SELECT userid FROM users WHERE username = '{iuser}'"
    get_userid = do_database_fetchone(userid_extract)
    userid=get_userid[0]
    if existing_session: # check for trainer
        check_for_trainer = f"SELECT trainerid FROM trainer WHERE trainerid = '{userid}'"
        #is_trainer = do_database_fetchone(check_for_trainer)
        #trainer_id=is_trainer[0]
        query = f"""
            SELECT c.classid, s.name AS skill_name, u.fullname,
            c.start, c.note, 
            (SELECT COUNT(*) from attendee a where a.classid=c.classid and status = 0) AS count_size, 
            c.max,
                CASE
                    WHEN c.max = 0 THEN 'cancelled'
                    WHEN c.trainerid = {userid} THEN 'edit'
                    WHEN a.status = 0 AND a.userid = {userid} THEN 'leave'
                    WHEN a.status NOT IN (0,1,4) THEN 'join'
                    WHEN a.status IS NULL then 'join'
                    ELSE 'unavailable'
                END AS action, a.status
            FROM class c
            LEFT JOIN skill s ON c.skillid = s.skillid
            LEFT JOIN users u ON c.trainerid=u.userid 
            LEFT JOIN attendee a ON c.classid= a.classid
            WHERE strftime('%s',DATETIME('NOW')) < c.start
            ORDER BY c.start
                    """
        upcoming_classes = do_database_fetchall(query)
        for cls in upcoming_classes:
                #response.append(class_response)
            class_response=build_response_class(cls[0], cls[1], cls[2], cls[3],\
                                            cls[4], cls[5], cls[6], cls[7])
            response.append(class_response)
            response.append(build_response_message(0, "Upcoming Class List provided"))
        return [iuser, imagic, response]
    else:
        response.append(build_response_redirect("/login.html"))
    return [iuser, imagic, response]
def handle_get_class_detail_request(iuser, imagic, content):
    """This code handles a request for a list of upcoming classes."""
    response = []
    userid_extract = f"SELECT userid FROM users WHERE username = '{iuser}'"
    get_userid = do_database_fetchone(userid_extract)
    userid=get_userid[0]
    session_query = f"SELECT * FROM session WHERE magic = '{imagic}'"
    existing_session = do_database_fetchone(session_query)
    if existing_session:
        # Get class id
        class_id = content.get('id')
        trainerid_extract = f"SELECT trainerid FROM class WHERE classid = '{class_id}'"
        get_trainerid = do_database_fetchone(trainerid_extract)
        if not get_trainerid:
            response.append(build_response_message(203, "Class doesn't exist"))
            return [iuser, imagic, response]
        trainerid=get_trainerid[0]
        if trainerid == userid:
            query = f"""
                SELECT c.classid, s.name AS skill_name, u.fullname,
                c.start, c.note,
                (SELECT COUNT(*) from attendee where classid={class_id} and status IN (0,1,2)) AS count_size,
                c.max,
                CASE
                    WHEN c.max=0 then 'cancelled'
                    WHEN c.start > strftime('%s',DATETIME('NOW')) THEN "cancel"
                    ELSE ""
                END as action    
                FROM class c
                LEFT JOIN skill s ON c.skillid = s.skillid
                LEFT JOIN users u ON c.trainerid=u.userid 
                LEFT JOIN attendee a ON c.classid= a.classid
                WHERE c.classid={class_id}
                GROUP BY c.classid, s.name, c.trainerid, c.start, c.max
                ORDER BY c.start
                """
            upcoming_classes = do_database_fetchall(query)
            attendee_query = f"""SELECT a.attendeeid, u.fullname,
                                        CASE
                                        WHEN a.status = 0 THEN
                                            CASE
                                                WHEN a.status = 0 AND c.start > strftime('%s',DATETIME('NOW')) THEN 'remove'
                                                ELSE 'update'
                                            END    
                                        WHEN a.status = 1 THEN 'passed'
                                        WHEN a.status = 2 THEN 'failed'
                                        WHEN a.status IN (3,4) THEN 'cancelled'
                                        END as action
                                        FROM attendee a
                                        INNER JOIN users u ON a.userid = u.userid
                                        INNER JOIN class c ON a.classid = c.classid
                                        where a.classid={class_id}
                                        """
            attendees = do_database_fetchall(attendee_query)
            if not upcoming_classes:
                response.append(build_response_message(204, "Class details not found"))
            elif upcoming_classes:
                for cls in upcoming_classes:
                        #action="edit"
                    class_response=build_response_class(cls[0], cls[1], cls[2], \
                                            cls[3], cls[4], cls[5], cls[6], cls[7])
                    response.append(class_response)
                # responses
                for attendee in attendees:
                    attendee_response = build_response_attendee(attendee[0],\
                                                attendee[1], attendee[2])
                    response.append(attendee_response)
                response.append(build_response_message(0, " "))
            else:
                response.append(build_response_message(254, "Class details not found"))
        else: # user not the trainer
            response.append(build_response_message(203, "You are not the trainer of this class"))
    else:
        response.append(build_response_redirect("/login.html"))
    return [iuser, imagic, response]

def handle_join_class_request(iuser, imagic, content):
    """This code handles a request by a user to join a class."""
    response = []
    session_query = f"SELECT * FROM session WHERE magic = '{imagic}'"
    existing_session = do_database_fetchone(session_query)
    userid_extract = f"SELECT userid FROM users WHERE username = '{iuser}'"
    get_userid = do_database_fetchone(userid_extract)
    userid=get_userid[0]
    if existing_session:
        class_id = content.get('id')
        class_exists=f"""SELECT classid from class where classid={class_id}"""
        check_class=do_database_fetchone(class_exists)
        if check_class is not None: # class id valid or not
            # class unavailable or not
            check_unavailability_query = f"""
                SELECT COUNT(*) FROM class c
                LEFT JOIN attendee a ON c.classid = a.classid
                WHERE c.classid = '{class_id}' AND (a.status = 1 OR a.status = 0 OR a.status=4) AND a.userid={userid} AND strftime('%s',DATETIME('NOW')) > c.start
                """
            class_unavailability_count = do_database_fetchone(check_unavailability_query)[0]
            if class_unavailability_count is None:
                response.append(build_response_message(108, "Class unavailable for user"))
            elif class_unavailability_count == 0:
                # User can join, check for space
                check_space_query = f"""
                    SELECT count(a.classid) FROM attendee a
                    where a.classid={class_id} and a.status=0
                    """
                space_info = do_database_fetchone(check_space_query)[0]
                get_class_max= f"""
                            SELECT max, trainerid from class where classid={class_id}
                            """
                max_class = do_database_fetchone(get_class_max)
                max_info=max_class[0]
                trainerid=max_class[1]
                if trainerid!=userid:
                    if space_info < max_info:
                    # User can join so insertion
                        join_query = f"""INSERT INTO attendee (userid, classid, status)
                            VALUES ('{userid}', '{class_id}', 0)"""
                        do_database_execute(join_query)
                    # Class info after join
                        updated_class_query = f"SELECT * FROM class WHERE classid = '{class_id}'"
                        updated_class_info = do_database_fetchone(updated_class_query)
                        skillid=updated_class_info[2]
                        get_attendeeid_query=f"""SELECT attendeeid from attendee
                                        where userid={userid} and classid={class_id} and status=0
                                        """
                        get_attendeeid=do_database_fetchone(get_attendeeid_query)
                        if get_attendeeid is None:
                            response.append(build_response_message(101, "User information invalid"))
                        if updated_class_info:
                            attendeeid=get_attendeeid[0]
                            query = f"""
                                SELECT c.classid, s.name AS skill_name, u.fullname,
                                c.start, c.note,
                                (SELECT COUNT(*) from attendee a where a.classid={class_id} and status IN (0,1,2)) AS count_size,
                                c.max,
                                CASE
                                    WHEN a.attendeeid={attendeeid} THEN 'leave'
                                    ELSE 'unavailable'
                                END AS action
                                FROM class c
                                JOIN skill s ON c.skillid = s.skillid
                                JOIN users u ON c.trainerid=u.userid 
                                JOIN attendee a ON c.classid= a.classid
                                WHERE strftime('%s',DATETIME('NOW')) < c.start and c.classid={class_id} and a.attendeeid={attendeeid}
                                """
                            update_classes = do_database_fetchall(query)
                            for cls in update_classes:
                                class_response=build_response_class(cls[0], cls[1], cls[2],\
                                    cls[3], cls[4], cls[5], cls[6], cls[7])
                                response.append(class_response)
                                response.append(build_response_message(0, "Joined class successfully"))
                            return [iuser, imagic, response]
                        else: # can't get class info
                            response.append(build_response_message(101, "Can't get updated class info"))
                    else: # no space to join
                        response.append(build_response_message(201, "Class is full"))
                else: # user is trainer of the class
                    response.append(build_response_message(222, "Cannot join own class"))
            else: #can't join
                response.append(build_response_message(202, "Class is unavailable for joining"))
        else:  # class id not valid
            response.append(build_response_message(133, "Class doesn't exist"))
    else:
        response.append(build_response_redirect("/login.html"))
    return [iuser, imagic, response]

def handle_leave_class_request(iuser, imagic, content):
    """This code handles a request by a user to leave a class."""
    response = []
    # Login
    session_query = f"SELECT * FROM session WHERE magic = '{imagic}'"
    existing_session = do_database_fetchone(session_query)
    userid_extract = f"SELECT userid FROM users WHERE username = '{iuser}'"
    get_userid = do_database_fetchone(userid_extract)
    userid=get_userid[0]
    if existing_session:
        class_id = content.get('id')
        # Checking user enrollment
        check_enrollment_query = f"""SELECT * FROM attendee
                            WHERE userid = '{userid}' AND classid = '{class_id}' AND status = 0
                            """
        enrollment_info = do_database_fetchone(check_enrollment_query)
        if enrollment_info:
            # Leaving class
            leave_query = f"""UPDATE attendee set status=3
                    WHERE userid = '{userid}' AND classid = '{class_id}'
                        """
            do_database_execute(leave_query)
            # Updated class info when leaves
            updated_class_query = f"SELECT * FROM class WHERE classid = '{class_id}'"
            updated_class_info = do_database_fetchone(updated_class_query)
            skillid=updated_class_info[2]
            get_attendeeid_query=f"""SELECT attendeeid from attendee
                                        where userid={userid} and classid={class_id} and status=3
                                        """
            get_attendeeid=do_database_fetchone(get_attendeeid_query)
            if get_attendeeid is not None:
                if updated_class_info:
                    attendeeid=get_attendeeid[0]
                    query = f"""
                            SELECT c.classid, s.name AS skill_name, u.fullname,
                            c.start, c.note,
                            (SELECT COUNT(*) from attendee where classid={class_id} and status=0) AS count_size,
                            c.max,
                            CASE
                                WHEN a.attendeeid={attendeeid} THEN 'join'
                                ELSE 'unavailable'
                            END AS action
                            FROM class c
                            JOIN skill s ON c.skillid = s.skillid
                            JOIN users u ON c.trainerid=u.userid 
                            JOIN attendee a ON c.classid= a.classid
                            WHERE strftime('%s',DATETIME('NOW')) < c.start and c.classid={class_id} and a.attendeeid={attendeeid}
                            """
                    update_classes = do_database_fetchall(query)
                    for cls in update_classes:
                        class_response=build_response_class(cls[0], cls[1], \
                            cls[2], cls[3], cls[4], cls[5], cls[6], cls[7])
                        response.append(class_response)
                    response.append(build_response_message(0, "Left class successfully"))
                else:
                    response.append(build_response_message(104, "Can't get updated class info"))
            else:
                response.append(build_response_message(105, "No user attendee available"))
        else:
            response.append(build_response_message(103, "Cannot leave class"))
    else:  # User not logged in
        response.append(build_response_redirect("/login.html"))
    return [iuser, imagic, response]

def handle_cancel_class_request(iuser, imagic, content):
    """This code handles a request to cancel an entire class."""
    response = []
    # Login
    session_query = f"SELECT * FROM session WHERE magic = '{imagic}'"
    existing_session = do_database_fetchone(session_query)
    if existing_session:
        class_id = content.get('id')
        trainerid_extract = f"""SELECT trainerid FROM class
                                WHERE classid = '{class_id}' AND start>strftime('%s',DATETIME('NOW'))
                                """
        get_trainerid = do_database_fetchone(trainerid_extract)
        if get_trainerid is not None:
            trainerid=get_trainerid[0]
            userid_extract = f"SELECT userid FROM users WHERE username = '{iuser}'"
            get_userid = do_database_fetchone(userid_extract)
            userid=get_userid[0]
            if trainerid==userid:
                # Cancelling class and update attendee
                cancel_class_query = f"""
                                UPDATE attendee SET status = 3
                                WHERE classid = '{class_id}' AND status = 0
                                """
                do_database_execute(cancel_class_query)  # Update class
                update_class_query = f"""UPDATE class SET max = 0
                                WHERE classid = '{class_id}'"""
                do_database_execute(update_class_query) # check updated class info
                updated_class_query = f"""
                                        SELECT c.classid, s.name AS skill_name,
                                        u.fullname, c.start, c.note,
                                        COUNT(a.userid) AS count_size, c.max,
                                        CASE
                                            WHEN a.status=3 THEN "cancelled"
                                        END as action    
                                        FROM class c
                                        LEFT JOIN skill s ON c.skillid = s.skillid
                                        LEFT JOIN users u ON u.userid = c.trainerid
                                        LEFT JOIN attendee a ON c.classid= a.classid
                                        WHERE c.classid={class_id}
                                        GROUP BY c.classid, s.name, c.trainerid
                                        ORDER BY c.start
                                    """
                updated_class_info = do_database_fetchone(updated_class_query)
                if updated_class_info:
                    class_response=build_response_class(updated_class_info[0], \
                                        updated_class_info[1], updated_class_info[2], \
                                        updated_class_info[3], updated_class_info[4], \
                                        0, 0, \
                                        updated_class_info[7])
                    response.append(class_response)
                    # check updated attendee info
                    updated_attendees_query = f"""
                                    SELECT a.attendeeid, u.fullname FROM attendee a
                                    JOIN users u ON a.userid=u.userid
                                    WHERE classid = '{class_id}' AND status = 3
                                    """
                    updated_attendees_info = do_database_fetchall(updated_attendees_query)
                    if updated_attendees_info:
                        for attendee_info in updated_attendees_info:
                            attendee_response = build_response_attendee(attendee_info[0],\
                                attendee_info[1], "cancelled")
                            response.append(attendee_response)
                        response.append(build_response_message(0, "Class cancelled successfully"))
                    else: # updated attendee information not found
                        response.append(build_response_message(0, "Class cancelled succesfully"))
                else: # Updated class information not found
                    response.append(build_response_message(204, "Can't get updated class info"))
            else: # User not trainer
                response.append(build_response_message(203, "Permission denied,User isn't trainer"))
        else: # Either class already over or it doesn't exist
            response.append(build_response_message(111, "Class doesnt exist or already over"))
    else: # user not logged in
        response.append(build_response_redirect("/login.html"))

    return [iuser, imagic, response]

def handle_update_attendee_request(iuser, imagic, content):
    """This code handles a request to cancel a user attendance at a class by a trainer"""
    response = []
    # User and session check
    session_query = f"SELECT * FROM session WHERE magic = '{imagic}'"
    existing_session = do_database_fetchone(session_query)
    userid_extract = f"SELECT userid FROM users WHERE username = '{iuser}'"
    get_userid = do_database_fetchone(userid_extract)
    userid=get_userid[0]
    if existing_session:
        attendee_id = content.get('id')
        new_state = content.get('state')
        # Check attendee and its class info
        attendee_query = f"SELECT * FROM attendee WHERE attendeeid = '{attendee_id}'"
        attendee_info = do_database_fetchone(attendee_query)
        if attendee_info:
            class_query = f"SELECT * FROM class WHERE classid = '{attendee_info[2]}'"
            class_info = do_database_fetchone(class_query)
            if class_info and (userid == class_info[1]):
                start_time = class_info[3]
                current_time = datetime.datetime.now()
                unix_timestamp = int(current_time.timestamp())
                if new_state in ('pass','fail'):
                    # update state to 'passed' or 'failed'
                    if start_time < unix_timestamp:
                        if new_state=='pass':
                            update_query = f"""
                            UPDATE attendee SET status = 1 
                            WHERE attendeeid = '{attendee_id}'
                            """
                        else:
                            update_query = f"""
                            UPDATE attendee SET status = 2
                            WHERE attendeeid = '{attendee_id}'
                            """
                        do_database_execute(update_query)
                        # Check updated attendee info
                        updated_attendee_query = f"""
                                                SELECT a.attendeeid,
                                                u.fullname,
                                                CASE 
                                                WHEN a.status=1 then 'passed'
                                                WHEN a.status=2 then 'failed'
                                                END as action
                                                FROM attendee a
                                                JOIN users u ON a.userid=u.userid
                                                WHERE attendeeid = '{attendee_id}'
                                                """
                        updated_attendee_info = do_database_fetchone(updated_attendee_query)
                        if updated_attendee_info:
                            attendee_response = build_response_attendee(updated_attendee_info[0],\
                                            updated_attendee_info[1], updated_attendee_info[2])
                            response.append(attendee_response)
                            response.append(build_response_message(0, "Attendee status updated successfully"))
                        else:
                            response.append(build_response_message(111, "Failed to fetch updated attendee information"))
                    else:
                        response.append(build_response_message(207, "Cannot update attendee status before start time"))
                elif new_state == 'remove':
                    if start_time > unix_timestamp:
                        update_query = f"""UPDATE attendee SET status = 4
                                    WHERE attendeeid = '{attendee_id}'"""
                        do_database_execute(update_query)
                        # Check updated attendee information
                        updated_attendee_query = f"""SELECT a.attendeeid,
                                                u.fullname
                                                FROM attendee a
                                                JOIN users u ON a.userid=u.userid
                                                WHERE attendeeid = '{attendee_id}'
                                                """
                        updated_attendee_info = do_database_fetchone(updated_attendee_query)
                        if updated_attendee_info:
                            attendee_response = build_response_attendee(updated_attendee_info[0],\
                                                updated_attendee_info[1], 'removed')
                            response.append(attendee_response)
                            # Check updated class info
                            query = f"""
                            SELECT c.classid, s.name AS skill_name,
                            u.fullname, c.start, c.note,
                            (SELECT COUNT(a.attendeeid) from attendee a where a.classid={attendee_info[2]} and a.status IN (0,1,2)) AS count_size,
                            c.max  
                            FROM class c
                            LEFT JOIN skill s ON c.skillid = s.skillid
                            LEFT JOIN users u ON u.userid = c.trainerid
                            LEFT JOIN attendee a ON c.classid= a.classid
                            WHERE c.classid={attendee_info[2]}
                            GROUP BY c.classid, s.name, c.trainerid, c.start, c.max
                            ORDER BY c.start
                                    """
                            updated_class_info=do_database_fetchall(query)
                            if updated_class_info:
                                for cls in updated_class_info:
                                    class_response = build_response_class(cls[0],\
                                                    cls[1], cls[2],\
                                                    cls[3], cls[4],\
                                                    cls[5], cls[6],\
                                                    'cancel')
                                    response.append(class_response)
                                    response.append(build_response_message(0, "Attendee status updated successfully"))
                            else:
                                # No updated class information
                                response.append(build_response_message(144, "Can't get updated class info"))
                        else:
                            # No updated attendee information
                            response.append(build_response_message(134, "Can't get attendee class info"))
                    else:
                        # Start time passed
                        response.append(build_response_message(223, "Cannot remove attendee after start time"))
                else:
                    # Invalid new_state provided
                    response.append(build_response_message(210, "Invalid state provided"))
            else:
                # User is not the trainer for the class
                response.append(build_response_message(203, "Cannot access, user isn't trainer"))
        else:
            # No Attendee info
            response.append(build_response_message(104, "Attendee information not found"))
    else:
        # User not logged in
        response.append(build_response_redirect("/login.html"))
    return [iuser, imagic, response]

def handle_create_class_request(iuser, imagic, content):
    response = []
    max_class_size = 10
    skill_id = content.get("id")
    note = content.get("note")
    day = content.get("day")
    month = content.get("month")
    year = content.get("year")
    hour = content.get("hour")
    minute = content.get("minute")
    max_students = content.get("max")
    userid_extract = f"SELECT userid FROM users WHERE username = '{iuser}'"
    get_userid = do_database_fetchone(userid_extract)
    userid=get_userid[0]
    check_for_trainer = f"SELECT trainerid FROM trainer WHERE trainerid = '{userid}'"
    is_trainer = do_database_fetchone(check_for_trainer)
    if is_trainer is not None:
        trainerid=is_trainer[0]
        # Validate skill
        skill_query = f"""SELECT * FROM trainer t JOIN skill s ON t.skillid = s.skillid
                        WHERE t.trainerid = '{trainerid}' AND t.skillid = '{skill_id}'
                        """
        skill_info = do_database_fetchall(skill_query)
        if not skill_info:
            response.append(build_response_message(201,"Invalid skill for creating a class"))
            return [iuser, imagic, response]
    # Check for incorrect date
        try:
            class_time = datetime.datetime(year, month, day, hour, minute)
            if class_time <= datetime.datetime.now():
                response.append(build_response_message(210,"Class time must be in the future"))
                return [iuser, imagic, response]
        except ValueError:
            response.append(build_response_message(220,"Invalid date or time"))
            return [iuser, imagic, response]
        class_time=datetime.datetime.timestamp(class_time)
    # Check size of class
        if not ((1 <= max_students) and max_students<= max_class_size):
            response.append(build_response_message(230,f"Maximum class size should be between 1 and {max_class_size}"))
            return [iuser, imagic, response]
        add_class = f"""INSERT INTO class (trainerid, skillid, start, max, note)
                    VALUES ({trainerid}, {skill_id},{class_time},{max_students},'{note}')
                    """
        do_database_execute(add_class)
        fetch_class = "SELECT classid FROM class ORDER BY classid Desc"
        class_id = do_database_fetchone(fetch_class)
        response.append(build_response_message(0,"Class created successfully"))
        response.append(build_response_redirect(f"/class/{class_id[0]}"))
        return [iuser, imagic, response]
    else:
        response.append(build_response_message(210,"Class can only be created by trainer"))
        return [iuser, imagic, response]

# HTTPRequestHandler class
class myHTTPServer_RequestHandler(BaseHTTPRequestHandler):

    # POST This function responds to GET requests to the web server.
    def do_POST(self):

        # The set_cookies function adds/updates two cookies returned with a webpage.
        # These identify the user who is logged in. The first parameter identifies the user
        # and the second should be used to verify the login session.
        def set_cookies(x, user, magic):
            ucookie = Cookie.SimpleCookie()
            ucookie['u_cookie'] = user
            x.send_header("Set-Cookie", ucookie.output(header='', sep=''))
            mcookie = Cookie.SimpleCookie()
            mcookie['m_cookie'] = magic
            x.send_header("Set-Cookie", mcookie.output(header='', sep=''))

        # The get_cookies function returns the values of the user and magic cookies if they exist
        # it returns empty strings if they do not.
        def get_cookies(source):
            rcookies = Cookie.SimpleCookie(source.headers.get('Cookie'))
            user = ''
            magic = ''
            for keyc, valuec in rcookies.items():
                if keyc == 'u_cookie':
                    user = valuec.value
                if keyc == 'm_cookie':
                    magic = valuec.value
            return [user, magic]

        # Fetch the cookies that arrived with the GET request
        # The identify the user session.
        user_magic = get_cookies(self)

        print(user_magic)

        # Parse the GET request to identify the file requested and the parameters
        parsed_path = urllib.parse.urlparse(self.path)

        # Decided what to do based on the file requested.

        # The special file 'action' is not a real file, it indicates an action
        # we wish the server to execute.
        if parsed_path.path == '/action':
            self.send_response(200) #respond that this is a valid page request

            # extract the content from the POST request.
            # This are passed to the handlers.
            length =  int(self.headers.get('Content-Length'))
            scontent = self.rfile.read(length).decode('ascii')
            print(scontent)
            if length > 0 :
              content = json.loads(scontent)
            else:
              content = []

            # deal with get parameters
            parameters = urllib.parse.parse_qs(parsed_path.query)

            if 'command' in parameters:
                # check if one of the parameters was 'command'
                # If it is, identify which command and call the appropriate handler function.
                # You should not need to change this code.
                if parameters['command'][0] == 'login':
                    [user, magic, response] = handle_login_request(user_magic[0], user_magic[1], content)
                    #The result of a login attempt will be to set the cookies to identify the session.
                    set_cookies(self, user, magic)
                elif parameters['command'][0] == 'logout':
                    [user, magic, response] = handle_logout_request(user_magic[0], user_magic[1], parameters)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'get_my_skills':
                    [user, magic, response] = handle_get_my_skills_request(user_magic[0], user_magic[1])
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')

                elif parameters['command'][0] == 'get_upcoming':
                    [user, magic, response] = handle_get_upcoming_request(user_magic[0], user_magic[1])
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'join_class':
                    [user, magic, response] = handle_join_class_request(user_magic[0], user_magic[1],content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                elif parameters['command'][0] == 'leave_class':
                    [user, magic, response] = handle_leave_class_request(user_magic[0], user_magic[1],content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')

                elif parameters['command'][0] == 'get_class':
                    [user, magic, response] = handle_get_class_detail_request(user_magic[0], user_magic[1],content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')

                elif parameters['command'][0] == 'update_attendee':
                    [user, magic, response] = handle_update_attendee_request(user_magic[0], user_magic[1],content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')

                elif parameters['command'][0] == 'cancel_class':
                    [user, magic, response] = handle_cancel_class_request(user_magic[0], user_magic[1],content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')

                elif parameters['command'][0] == 'create_class':
                    [user, magic, response] = handle_create_class_request(user_magic[0], user_magic[1],content)
                    if user == '!': # Check if we've been tasked with discarding the cookies.
                        set_cookies(self, '', '')
                else:
                    # The command was not recognised, report that to the user. This uses a special error code that is not part of the codes you will use.
                    response = []
                    response.append(build_response_message(901, 'Internal Error: Command not recognised.'))

            else:
                # There was no command present, report that to the user. This uses a special error code that is not part of the codes you will use.
                response = []
                response.append(build_response_message(902,'Internal Error: Command not found.'))

            text = json.dumps(response)
            print(text)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(bytes(text, 'utf-8'))

        else:
            # A file that does n't fit one of the patterns above was requested.
            self.send_response(404) # a file not found html response
            self.end_headers()
        return

   # GET This function responds to GET requests to the web server.
   # You should not need to change this function.
    def do_GET(self):

        # Parse the GET request to identify the file requested and the parameters
        parsed_path = urllib.parse.urlparse(self.path)

        # Decided what to do based on the file requested.

        # Return a CSS (Cascading Style Sheet) file.
        # These tell the web client how the page should appear.
        if self.path.startswith('/css'):
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())

        # Return a Javascript file.
        # These contain code that the web client can execute.
        elif self.path.startswith('/js'):
            self.send_response(200)
            self.send_header('Content-type', 'text/js')
            self.end_headers()
            with open('.'+self.path, 'rb') as file:
                self.wfile.write(file.read())

        # A special case of '/' means return the index.html (homepage)
        # of a website
        elif parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('./pages/index.html', 'rb') as file:
                self.wfile.write(file.read())

        # Pages of the form /create/... will return the file create.html as content
        # The ... will be a class id
        elif parsed_path.path.startswith('/class/'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('./pages/class.html', 'rb') as file:
                self.wfile.write(file.read())

        # Pages of the form /create/... will return the file create.html as content
        # The ... will be a skill id
        elif parsed_path.path.startswith('/create/'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('./pages/create.html', 'rb') as file:
                self.wfile.write(file.read())

        # Return html pages.
        elif parsed_path.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open('./pages'+parsed_path.path, 'rb') as file:
                self.wfile.write(file.read())
        else:
            # A file that does n't fit one of the patterns above was requested.
            self.send_response(404)
            self.end_headers()

        return

def run():
    """This is the entry point function to this code."""
    print('Starting server...')

    # Check if a port number is provided as a command-line argument
    if len(sys.argv) < 2:
        print("Port argument not provided.")
        return

    # Set up the server address using the provided port number
    server_address = ('127.0.0.1', int(sys.argv[1]))

    # Create an HTTP server with the defined server address and request handler
    httpd = HTTPServer(server_address, myHTTPServer_RequestHandler)

    print('Running server on port =', sys.argv[1], '...')
    try:
        # Start the HTTP server to listen for incoming requests indefinitely
        httpd.serve_forever()
    except KeyboardInterrupt:
        # If a KeyboardInterrupt (Ctrl+C) is raised, stop the server gracefully
        print('Stopping server...')
        httpd.server_close()

# Entry point to start the server
run()

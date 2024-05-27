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
import time # needed to record when stuff happened
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
        db = sqlite3.connect('./db/just_users.db')
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
        db = sqlite3.connect('./db/just_users.db')
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
        db = sqlite3.connect('./db/just_users.db')
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

    # Fetch user credentials from the database
    query = f"SELECT userid FROM users WHERE username = '{content['username']}' AND password = '{content['password']}'"
    user_data = do_database_fetchone(query)

    if user_data:
        # If credentials are valid, create a session for the user
        session_magic = random_digits(8)  # Generating a random session ID
        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Store session details in the database
        insert_session_query = f"INSERT INTO session (username, session_id, created_at) VALUES ('{iuser}', '{session_magic}', '{current_time}')"
        do_database_execute(insert_session_query)

        # Build response: username, session ID (magic), and response action set
        response.append(build_response_message(200, "Login successful!"))
        response.append(build_response_redirect("/index.html"))  # Redirect to the dashboard or desired page
        return [iuser, session_magic, response]

    # If credentials are invalid, return an appropriate response
    response.append(build_response_message(401, "Invalid credentials! Please try again."))
    return [iuser, imagic, response]


def handle_logout_request(iuser, imagic, parameters):
    """This code handles the selection of the logout button.
       You will need to ensure the end of the session is recorded in the database
       And that the session magic is revoked."""

    response = []

    # Revoke or delete the session from the database
    delete_session_query = f"DELETE FROM session WHERE username = '{iuser}' AND sessionid = '{imagic}'"
    do_database_execute(delete_session_query)

    # Log the end of the session (optional but recommended for audit purposes)
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_end_session_query = f"UPDATE session SET ended_at = '{current_time}' WHERE username = '{iuser}' AND sessionid = '{imagic}'"
    do_database_execute(log_end_session_query)

    # Build response: username, session ID (magic), and response action set
    response.append(build_response_message(200, "Logout successful!"))
    response.append(build_response_redirect("/login"))  # Redirect to the login page or desired destination after logout

    return [iuser, imagic, response]


def handle_get_my_skills_request(iuser, imagic):
    """This code handles a request for a list of a user's skills.
       You must return a value for all skills, even when it's zero."""

    response = []

    # Fetch all skills of the user from the database
    skills_query = f"SELECT * FROM skill WHERE username = '{iuser}'"
    user_skills = do_database_fetchall(skills_query)

    # Define a list of all possible skills (assuming a predefined set of skills)
    all_skills = ['Skill A', 'Skill B', 'Skill C', 'Skill D']  # Add all skill names here

    # Initialize a dictionary to hold user skills and their counts
    user_skill_counts = {skill: 0 for skill in all_skills}

    # Update user_skill_counts with the actual counts from the database, if available
    if user_skills:
        for skill_data in user_skills:
            skill_name = skill_data[1]  # Assuming the skill name is in the second column
            skill_count = skill_data[2]  # Assuming the skill count is in the third column
            user_skill_counts[skill_name] = skill_count

    # Build the response including all skills, even if the user has none of that skill
    for skill_name, skill_count in user_skill_counts.items():
        response.append(build_response_skill(
            id=random_digits(6),  # Generate a unique ID for each skill (replace with appropriate IDs)
            name=skill_name,
            gained=skill_count,
            trainer="",
            state=""
        ))

    return [iuser, imagic, response]


def handle_get_upcoming_request(iuser, imagic):
    """This code handles a request for the details of a class."""

    response = []

    # Fetch upcoming classes for the user from the database
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    upcoming_classes_query = f"SELECT * FROM classes WHERE when > '{current_time}'"
    upcoming_classes = do_database_fetchall(upcoming_classes_query)

    if upcoming_classes:
        # If there are upcoming classes, build the response for each class
        for class_data in upcoming_classes:
            class_id = class_data[0]  # Assuming the ID is in the first column
            class_name = class_data[1]  # Assuming the class name is in the second column
            class_trainer = class_data[2]  # Assuming the trainer's name is in the third column
            class_when = class_data[3]  # Assuming the class time is in the fourth column
            class_notes = class_data[4]  # Assuming class notes are in the fifth column
            class_size = class_data[5]  # Assuming the class size is in the sixth column
            class_max = class_data[6]  # Assuming the maximum class size is in the seventh column

            # Build the response for each upcoming class
            response.append(build_response_class(
                id=class_id,
                name=class_name,
                trainer=class_trainer,
                when=class_when,
                notes=class_notes,
                size=class_size,
                max=class_max,
                action=""  # Add any specific action here, if needed
            ))
    else:
        # If there are no upcoming classes, provide a message in the response
        response.append(build_response_message(404, "No upcoming classes found."))

    return [iuser, imagic, response]


def handle_get_class_detail_request(iuser, imagic, content):
    """This code handles a request for a list of upcoming classes."""

    response = []

    # Extract the class ID from the request content
    class_id = content.get('class_id', None)  # Assuming the content contains a 'class_id' field

    if class_id is not None:
        # Fetch details of the requested class from the database
        class_details_query = f"SELECT * FROM classes WHERE class_id = '{class_id}'"
        class_details = do_database_fetchone(class_details_query)

        if class_details:
            # If the class details are found, construct the response
            class_name = class_details[1]  # Assuming the class name is in the second column
            class_trainer = class_details[2]  # Assuming the trainer's name is in the third column
            class_when = class_details[3]  # Assuming the class time is in the fourth column
            class_notes = class_details[4]  # Assuming class notes are in the fifth column
            class_size = class_details[5]  # Assuming the class size is in the sixth column
            class_max = class_details[6]  # Assuming the maximum class size is in the seventh column

            # Build the response for the requested class
            response.append(build_response_class(
                id=class_id,
                name=class_name,
                trainer=class_trainer,
                when=class_when,
                notes=class_notes,
                size=class_size,
                max=class_max,
                action=""  # Add any specific action here, if needed
            ))
        else:
            # If the requested class is not found, provide a message in the response
            response.append(build_response_message(404, "Class not found."))
    else:
        # If no class ID is provided in the request content, provide an error message
        response.append(build_response_message(400, "Class ID not provided."))

    return [iuser, imagic, response]



def handle_join_class_request(iuser, imagic, content):
    """This code handles a request by a user to join a class."""

    response = []

    # Extract necessary details from the request content
    class_id = content.get('class_id', None)  # Assuming the content contains a 'class_id' field

    if class_id is not None:
        # Check if the user is already enrolled in the class (you might have a separate table for enrollments)
        enrollment_check_query = f"SELECT * FROM enrollments WHERE username = '{iuser}' AND class_id = '{class_id}'"
        existing_enrollment = do_database_fetchone(enrollment_check_query)

        if existing_enrollment:
            # If the user is already enrolled, provide a message in the response
            response.append(build_response_message(409, "Already enrolled in this class."))
        else:
            # If the user is not enrolled, proceed with the enrollment
            enroll_user_query = f"INSERT INTO enrollments (username, class_id) VALUES ('{iuser}', '{class_id}')"
            do_database_execute(enroll_user_query)

            # Provide a success message in the response
            response.append(build_response_message(200, "Successfully joined the class!"))
    else:
        # If no class ID is provided in the request content, provide an error message
        response.append(build_response_message(400, "Class ID not provided."))

    return [iuser, imagic, response]


def handle_leave_class_request(iuser, imagic, content):
    """This code handles a request by a user to leave a class."""

    response = []

    # Extract necessary details from the request content
    class_id = content.get('class_id', None)  # Assuming the content contains a 'class_id' field

    if class_id is not None:
        # Check if the user is enrolled in the class
        enrollment_check_query = f"SELECT * FROM enrollments WHERE username = '{iuser}' AND class_id = '{class_id}'"
        existing_enrollment = do_database_fetchone(enrollment_check_query)

        if existing_enrollment:
            # If the user is enrolled, proceed with unenrollment
            unenroll_user_query = f"DELETE FROM enrollments WHERE username = '{iuser}' AND class_id = '{class_id}'"
            do_database_execute(unenroll_user_query)

            # Provide a success message in the response
            response.append(build_response_message(200, "Successfully left the class!"))
        else:
            # If the user is not enrolled, provide a message in the response
            response.append(build_response_message(404, "Not enrolled in this class."))
    else:
        # If no class ID is provided in the request content, provide an error message
        response.append(build_response_message(400, "Class ID not provided."))

    return [iuser, imagic, response]


def handle_cancel_class_request(iuser, imagic, content):
    """This code handles a request to cancel an entire class."""

    response = []

    # Extract necessary details from the request content
    class_id = content.get('class_id', None)  # Assuming the content contains a 'class_id' field

    if class_id is not None:
        # Check if the class exists in the database
        class_check_query = f"SELECT * FROM classes WHERE class_id = '{class_id}'"
        existing_class = do_database_fetchone(class_check_query)

        if existing_class:
            # If the class exists, delete the class from the database
            delete_class_query = f"DELETE FROM classes WHERE class_id = '{class_id}'"
            do_database_execute(delete_class_query)

            # Additionally, you might want to remove enrolled users from this class
            remove_enrollments_query = f"DELETE FROM enrollments WHERE class_id = '{class_id}'"
            do_database_execute(remove_enrollments_query)

            # Provide a success message in the response
            response.append(build_response_message(200, "Successfully canceled the class!"))
        else:
            # If the class doesn't exist, provide a message in the response
            response.append(build_response_message(404, "Class not found."))
    else:
        # If no class ID is provided in the request content, provide an error message
        response.append(build_response_message(400, "Class ID not provided."))

    return [iuser, imagic, response]



def handle_update_attendee_request(iuser, imagic, content):
    """This code handles a request to cancel a user attendance at a class by a trainer"""

    response = []

    # Extract necessary details from the request content
    attendee_id = content.get('attendee_id', None)  # Assuming the content contains an 'attendee_id' field
    class_id = content.get('class_id', None)  # Assuming the content contains a 'class_id' field
    attendance_status = content.get('attendance_status', None)  # Assuming the content contains an 'attendance_status' field

    if attendee_id is not None and class_id is not None and attendance_status is not None:
        # Update the attendee's attendance status for the specified class
        update_attendance_query = f"UPDATE attendee_records SET attendance_status = '{attendance_status}' WHERE attendee_id = '{attendee_id}' AND class_id = '{class_id}'"
        do_database_execute(update_attendance_query)

        # Provide a success message in the response
        response.append(build_response_message(200, f"Updated attendee {attendee_id} attendance status to {attendance_status} for class {class_id}"))
    else:
        # If any required information is missing in the request content, provide an error message
        response.append(build_response_message(400, "Incomplete information provided."))

    return [iuser, imagic, response]


def handle_create_class_request(iuser, imagic, content):
    """This code handles a request to create a class."""

    response = []

    # Extract necessary details from the request content
    class_name = content.get('class_name', None)  # Assuming the content contains a 'class_name' field
    class_trainer = content.get('class_trainer', None)  # Assuming the content contains a 'class_trainer' field
    class_when = content.get('class_when', None)  # Assuming the content contains a 'class_when' field
    class_notes = content.get('class_notes', '')  # Assuming the content contains a 'class_notes' field (optional)

    if class_name is not None and class_trainer is not None and class_when is not None:
        # Insert the new class into the database
        create_class_query = f"INSERT INTO classes (class_name, class_trainer, class_when, class_notes) VALUES ('{class_name}', '{class_trainer}', '{class_when}', '{class_notes}')"
        do_database_execute(create_class_query)

        # Provide a success message in the response
        response.append(build_response_message(200, "Class created successfully!"))
    else:
        # If any required information is missing in the request content, provide an error message
        response.append(build_response_message(400, "Incomplete information provided."))

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



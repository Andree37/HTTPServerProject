"""
 Implements a simple HTTP/1.0 Server

"""

import socket
import time
from threading import Thread, Timer, Semaphore
import json
from Utilities import Logger, Statistics

# Define socket host and port
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000
MAX_TIME = 10


def close_client(connection):
    print(f"Connection closed: {connection}")
    connection.close()


def do_head(req, contents):
    return Response(status="HTTP/1.1 200 OK", content_length=len(contents), content_type=req.file_type,
                    connection=req.connection, referer=req.referer, host=req.host)


def get_user_input(req):
    # Get new user input
    body = req.body.split("&")
    new_values = {}
    # Each argument of the post
    for arg in body:
        # Turn it into a key value
        pair = arg.split("=")
        arg_key = pair[0]
        arg_value = pair[1]

        # check if value is valid, raise ValueError otherwise
        if arg_value is "":
            raise ValueError
        new_values[arg_key] = arg_value

    return new_values


def do_post(req, connection):
    if req.link == "/login":
        new_values = get_user_input(req)

        # Build cookies
        cookies = []
        for k, v in new_values.items():
            cookie = f"{k}={v}"
            cookies.append(cookie)

        # Finally add the address of the client as a cookie
        address = connection.getpeername()[0]
        address_cookie = f"address={address}"
        cookies.append(address_cookie)
        content = "Logged in, if admin then u can access private file"
        return Response(status="HTTP/1.1 200 OK", content_type="text", content=content, content_length=len(content),
                        cookie=cookies, host=req.host)

    if req.link == "/form":
        # Dictionary and list for the json file
        top_dic = {}
        persons = []
        # Open json file if exists to mantain data
        try:
            file = open("name.json", "r", encoding="utf-8")
            json_str = str(file.read())
            if json_str is not "":
                top_dic = json.loads(json_str)
                persons = top_dic["persons"]
            file.close()
        except FileNotFoundError:
            print("File not found")

        new_values = get_user_input(req)

        # Add new user input into the json file
        persons.append(new_values)
        top_dic["persons"] = persons

        # Writes to file so the data stays
        file = open("name.json", "w", encoding="utf-8")
        json.dump(top_dic, file)
        file.close()

        # Write to output
        output = json.dumps(top_dic)

        return Response(status="HTTP/1.1 200 OK", content_type="application/json",
                        content=output, referer=req.referer, content_length=len(output), host=req.host)


def start_thread(function, args=()):
    thread = Thread(target=function, args=args)
    thread.start()


class Server:
    def __init__(self):
        # Create socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((SERVER_HOST, SERVER_PORT))
        self.server_socket.listen(1)
        print('Listening on port %s ...' % SERVER_PORT)
        # Image types
        self.image_types = ["png", "jpeg", "jpg", "gif", "mp4", "MP4"]
        self.cache = []
        self.sem_stats = Semaphore()
        self.server_statistics = Statistics()
        # localhost with username admin should be the only one that is admin
        self.admin_list = [{"admin": "127.0.0.1"}]

    def handle_request(self, request, connection):
        req = Request(request=request)
        print(request)

        if req.link is None:
            return Response(status="HTTP/1.1 400 BAD REQUEST", content="Bad user request",
                            connection="close")

        # If response is in cache, then return this response already created
        response = self.server_statistics.get_link_in_most_visited(req.link)
        if response is not None:
            start_thread(function=self.server_statistics.visit_link, args=[req.link, response])
            return response

        # simulate a long response from server
        time.sleep(.1)

        # Check for POST
        if req.method == "POST":
            try:
                return do_post(req, connection)
            except ValueError:
                return Response(status="HTTP/1.1 400 BAD REQUEST", content="Bad user request",
                                connection="close", referer=req.referer, host=req.host)

        # If private return 403
        if req.status == "private":
            # Check if client cookie is in the admin list
            for user in self.admin_list:
                for k, v in user.items():
                    print(v)
                    if k != req.username or v != req.address:
                        return Response(status="HTTP/1.0 403 Forbidden", content="Can't access this file",
                                        connection="close", referer=req.referer, host=req.host)

        filename = "htdocs" + req.link
        # Get type of file
        filename_type = req.file_type
        file = None
        try:
            if filename_type in self.image_types:
                # Image
                file = open(filename, "rb")
            else:
                # Web page
                file = open(filename, "r")

            # Read contents and close file
            contents = file.read()

            # Check for HEAD
            if req.method == "HEAD":
                return do_head(req, contents)

        except PermissionError:
            return Response(status="HTTP/1.1 400 BAD REQUEST", content="Bad user request",
                            connection="close", referer=req.referer, host=req.host)
        except FileNotFoundError:
            # If None return 404
            return Response(status="HTTP/1.1 404 NOT FOUND", content="File not found",
                            connection="close", referer=req.referer, host=req.host)
        finally:
            if file is not None:
                file.close()
        response = Response(status="HTTP/1.1 200 OK", content_length=len(contents), content_type=req.file_type,
                            content=contents, connection=req.connection, referer=req.referer, host=req.host)

        # Create thread so client doesn't get stuck and continues
        # Save the link to the cache
        if req.status != "private":
            start_thread(function=self.add_to_cache, args=[response, req.link])

        return response

    def add_to_cache(self, response, link):

        # Save in cache the response
        self.sem_stats.acquire()
        response_dic = {"response": response, "link": link}
        self.cache.append(response_dic)
        self.sem_stats.release()

        # End the thread
        return 0

    def visit_link(self, link, response):
        self.server_statistics.visit_link(link=link, response=response)

        # End the thread
        return 0

    def stats_handle(self):
        while True:
            # sleep for not too much server consumption
            time.sleep(5)

            self.sem_stats.acquire()
            cache = self.cache.copy()
            self.cache.clear()
            self.sem_stats.release()

            # Update server cache
            for item in cache:
                response = None
                link = None
                for k, v in item.items():
                    if k == "response":
                        response = v
                    else:
                        link = v
                self.server_statistics.visit_link(response=response, link=link)

    def main_loop(self):
        # Create thread for statistics
        start_thread(function=self.stats_handle)

        while True:
            # Wait for client connections and creates client threads
            client_connection, client_address = self.server_socket.accept()
            start_thread(function=self.handle_client, args=[client_connection])

    def handle_client(self, connection):
        # Logger for writing to text file
        logger = Logger.get_instance()

        while True:
            # Restart timer
            timer = Timer(10.0, close_client, args=[connection])
            timer.start()

            # Handle client request
            try:
                request = connection.recv(1024).decode()
                response = self.handle_request(request=request, connection=connection)
            except (ConnectionAbortedError, ConnectionResetError):
                # Exits the while and finishes the thread
                return 0

            # Write to logger if has content in it
            if response.referer is not "":
                date_now = time.strftime("%a, %d %b %Y %H:%M:%S")
                logger.write_to_file(f"{date_now} IP/Port: {connection.getpeername()} \t URL: {response.referer}\n")

            # Shuts connection with the client after 10 seconds
            timer.cancel()

            # send response to the client
            connection.sendall(response.http_response())
            # Connection check
            if response.connection == "close":
                close_client(connection)
                return 0

    def close_server(self):
        # Close socket
        self.server_socket.close()


class Response:
    def __init__(self, status="", content_length=None, content_type=None, content=None, connection=None, referer=None,
                 cookie=None, host=None):
        self.status = status
        self.content_length = content_length
        self.content_type = content_type
        self.date = time.strftime("%a, %d %b %Y %H:%M:%S")
        self.content = content
        self.connection = connection
        self.referer = referer
        self.cookie = cookie
        self.host = host

    def http_response(self):
        response = f"{self.status}\n"

        if self.content_length is not None:
            response += f"Content-length:{self.content_length}\n"

        if self.content_type is not None:
            response += f"Content-type:{self.content_type}\n"

        if self.date is not None:
            response += f"Date:{self.date}\n"

        if self.connection is not None:
            response += f"Connection:{self.connection}\n"

        if self.cookie:
            for cookie in self.cookie:
                response += f"Set-Cookie:{cookie}\n"

        if self.host is not None:
            response += f"Host: {self.host}\n"

        response += "\n"

        # If response is text or image, has to be taken cared differently
        if self.content is not None:
            if isinstance(self.content, bytes):
                final_response = response.encode()
                final_response += self.content
            else:
                response += self.content
                final_response = response.encode()
        else:
            final_response = response.encode()
        return final_response


class Request:
    def __init__(self, request=""):
        self.request = request
        self.__get_parameters__()

    def __get_parameters__(self):
        headers = self.request.split("\n")
        first_line = headers[0]
        first_line_split = first_line.split(" ")
        self.method = first_line_split[0]
        if len(first_line_split) > 1:
            self.link = first_line_split[1]
        else:
            self.link = None

        # In case of a bad request with no link, returns
        if self.link is None:
            return

        # Get the file link and all the folders that the file is in
        folders_file = self.link.split("/")
        self.file = folders_file[len(folders_file) - 1]
        self.folders = folders_file[1:len(folders_file) - 1]

        # If file is "/" then it should be redirected to the index
        if self.link == "/":
            self.link = "/index.html"
            self.file = "index.html"

        # Check if client can access this file
        if "private" in self.folders:
            self.status = "private"
        else:
            self.status = "public"

        # File type is on the link, being the last thing after the dot(.)
        split_link = self.link.split(".")
        self.file_type = split_link[len(split_link) - 1]

        # Get connection type (close or keep alive), referer and host from headers
        connection = ""
        referer = ""
        host = ""
        name = ""
        address = ""
        for head in headers:
            split_head = head.split(":")
            if split_head[0] == "Connection":
                connection = split_head[1]
            if split_head[0] == "Referer":
                referer = split_head[1::]
            if split_head[0] == "Host":
                host = split_head[1::]
            if split_head[0] == "Cookie":
                whole_cookie = split_head[1]

                split_cookie = whole_cookie.split(";")

                username_cookie = split_cookie[0].split("=")
                name = username_cookie[1]

                address_cookie = split_cookie[1].split("=")
                address = address_cookie[1]

        host = "".join(host)
        referer = "".join(referer)
        self.username = name.strip()
        self.address = address.strip()
        self.host = host.strip()
        self.referer = referer.strip()
        self.connection = connection.strip()
        self.cookies = [name, address]

        # Get body of request if it is post which is the last statement
        if self.method == "POST":
            self.body = headers[len(headers) - 1]


server = Server()
server.main_loop()

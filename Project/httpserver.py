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
                    connection=req.connection, referer=req.referer)


def do_post(req):
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

    # Get new user input
    body = req.body.split("&")
    new_values = {}
    # Each argument of the post
    for arg in body:
        # Turn it into a key value
        pair = arg.split("=")
        arg_key = pair[0]
        arg_value = pair[1]
        new_values[arg_key] = arg_value

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
                    content=output, referer=req.referer, content_length=len(output))


class Server:
    def __init__(self):
        # Create socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((SERVER_HOST, SERVER_PORT))
        self.server_socket.listen(1)
        print('Listening on port %s ...' % SERVER_PORT)
        # Image types
        self.image_types = ["png", "jpeg", "jpg"]
        self.cache = []
        self.sem_stats = Semaphore()
        self.server_statistics = Statistics()

    def handle_request(self, request):
        req = Request(request=request)
        print(request)

        # If reponse is in cache, then return this response already created
        response = self.server_statistics.get_link_in_most_visited(req.link)
        if response is not None:
            return response

        # simulate a long response from server
        time.sleep(.1)

        # Check for POST
        if req.method == "POST":
            return do_post(req)

        # If private return 403
        if req.status == "private":
            return Response(status="HTTP/1.0 403 Forbidden", content="Can't access this file",
                            connection="close", referer=req.referer)
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
                            connection="close", referer=req.referer)
        except FileNotFoundError:
            # If None return 404
            return Response(status="HTTP/1.1 404 NOT FOUND", content="File not found",
                            connection="close", referer=req.referer)
        finally:
            if file is not None:
                file.close()
        response = Response(status="HTTP/1.1 200 OK", content_length=len(contents), content_type=req.file_type,
                            content=contents, connection=req.connection, referer=req.referer)

        # Save in cache the response
        self.sem_stats.acquire()
        response_dic = {"response": response, "link": req.link}
        self.cache.append(response_dic)
        self.sem_stats.release()

        return response

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
        stats_thread = Thread(target=self.stats_handle, args=[])
        stats_thread.start()
        while True:
            # Wait for client connections and creates client threads
            client_connection, client_address = self.server_socket.accept()
            thread = Thread(target=self.handle_client, args=[client_connection])
            thread.start()

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
                response = self.handle_request(request)
            except ConnectionAbortedError:
                # Exits the while and finishes the thread
                return 0

            # Write to logger if has content in it
            if response.referer is not "":
                date_now = time.strftime("%a, %d %b %Y %H:%M:%S")
                logger.write_to_file(f"{date_now} IP/Port: {connection.getpeername()} \t URL: {response.referer}\n")

            # Shuts connection with the client after 10 seconds
            timer.cancel()

            # If image or text
            if isinstance(response.content, bytes):
                connection.sendall(response.http_response(type="image"))
            else:
                connection.sendall(response.http_response().encode())

            # Connection check
            if response.connection == "close":
                close_client(connection)
                return 0

    def close_server(self):
        # Close socket
        self.server_socket.close()


class Response:
    def __init__(self, status="", content_length=None, content_type=None, content=None, connection=None, referer=None):
        self.status = status
        self.content_length = content_length
        self.content_type = content_type
        self.date = time.strftime("%a, %d %b %Y %H:%M:%S")
        self.content = content
        self.connection = connection
        self.referer = referer

    def http_response(self, type="text"):
        response = f"{self.status}\n"

        if self.content_length is not None:
            response += f"Content-length:{self.content_length}\n"

        if self.content_type is not None:
            response += f"Content-type:{self.content_type}\n"

        if self.date is not None:
            response += f"Date:{self.date}\n"

        if self.connection is not None:
            response += f"Connection:{self.connection}\n"

        response += "\n"

        # If response is text or image, has to be taken cared differently
        if self.content is not None:
            if type == "text":
                response += self.content
            elif type == "image":
                response = response.encode()
                response += self.content
        return response


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
            self.link = "/index.html"

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

        # Get connection type (close or keep alive)
        connection = ""
        referer = ""
        for head in headers:
            split_head = head.split(":")
            if split_head[0] == "Connection":
                connection = split_head[1]
            if split_head[0] == "Referer":
                referer = split_head[1::]
        referer = "".join(referer)
        self.referer = referer.strip()
        self.connection = connection.strip()

        # Get body of request if it is post which is the last statement
        if self.method == "POST":
            self.body = headers[len(headers) - 1]


server = Server()
server.main_loop()

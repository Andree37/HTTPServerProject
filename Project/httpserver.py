"""
 Implements a simple HTTP/1.0 Server

"""

import socket

# Define socket host and port
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000


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

    def handle_request(self, request):
        req = Request(request=request)
        print(req.link)
        try:
            filename = "htdocs" + req.link
            # Get type of file
            filename_type = req.file_type

            if filename_type in self.image_types:
                # Image
                file = open(filename, "rb")
            else:
                # Web page
                file = open(filename, "r")

            # Read contents and close file
            contents = file.read()
            file.close()
        except FileNotFoundError:
            return None

        return contents

    def main_loop(self):
        while True:
            # Wait for client connections
            client_connection, client_address = self.server_socket.accept()

            # Handle client request
            request = client_connection.recv(1024).decode()
            content = self.handle_request(request)

            # If 404
            if content is None:
                response = Response(status="HTTP/1.0 404 NOT FOUND", content="File not found")
                client_connection.sendall(response.http_response().encode())
            # Build the response
            else:
                status = "HTTP/1.1 200 OK"
                content_length = len(content)
                response = Response(status=status, content_length=content_length, content=content)
                # If image or text
                if isinstance(content, bytes):
                    client_connection.sendall(response.http_response(type="image"))
                else:
                    client_connection.sendall(response.http_response().encode())
            client_connection.close()

    def close_server(self):
        # Close socket
        self.server_socket.close()


class Response:
    def __init__(self, status="", content_length=None, date=None, content=None):
        self.status = status
        self.content_length = content_length
        self.date = date
        self.content = content

    def http_response(self, type="text"):
        response = f"{self.status}\n"

        if self.content_length is not None:
            response += f"Content-length:{self.content_length}\n"

        if self.date is not None:
            response += f"Date: Tue, 15 Nov 1994 08:12:31 GMT\n"

        response += "\n"

        # If response is text or image, has to be taken cared differently
        if type == "text":
            response += self.content
        elif type == "image":
            response = response.encode()
            response += self.content

        return response


class Request:
    def __init__(self, request=""):
        self.request = request
        self.__method_and_link__()

    def __method_and_link__(self):
        headers = self.request.split("\n")
        first_line = headers[0]
        first_line_split = first_line.split(" ")
        self.method = first_line_split[0]
        self.link = first_line_split[1]
        # If link is with nothing after the last "/", then index.html should be returned
        last = self.link.split("/")
        if last[len(last) - 1] == "":
            self.link = "/index.html"
        # File type is on the link, being the last thing after the dot(.)
        split_link = self.link.split(".")
        self.file_type = split_link[len(split_link) - 1]


server = Server()
server.main_loop()

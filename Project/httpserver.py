"""
 Implements a simple HTTP/1.0 Server

"""

import socket

image_types = ["png", "jpeg", "jpg"]


def handle_request(request):
    headers = request.split("\n")
    print(headers[0])
    first_line = headers[0]
    first_line_split = first_line.split(" ")
    try:
        filename = "htdocs" + first_line_split[1]
        filename_type = filename.split(".")[1]
        if filename_type in image_types:
            # Image
            file = open(filename, "rb")
        else:
            # Web page
            file = open(filename, "r")
        contents = file.read()
        file.close()
    except FileNotFoundError:
        return None
    return contents


# Define socket host and port
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 8000

# Create socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((SERVER_HOST, SERVER_PORT))
server_socket.listen(1)
print('Listening on port %s ...' % SERVER_PORT)

while True:
    # Wait for client connections
    client_connection, client_address = server_socket.accept()

    # Handle client request
    request = client_connection.recv(1024).decode()
    content = handle_request(request)

    # Send HTTP response
    if content is None:
        response = 'HTTP/1.0 404 NOT FOUND\n\nFile not found'
    else:
        response = 'HTTP/1.1 200 OK\nContent-length:%s\n\n' % len(content)
        if isinstance(content, bytes):
            byte_response = response.encode()
            byte_response += content
            client_connection.sendall(byte_response)
        else:
            response += content
            client_connection.sendall(response.encode())
        client_connection.close()

# Close socket
server_socket.close()

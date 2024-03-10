# Client Server Msg Passing.
## Background
A client/server based system the synchronizes a client directory with a server directory using simple sockets and msg passing 
to give commands through defined actions

This software is writen on Windows 10 to use Python 3.8.9 - it is not compatible with Python 2. Python 3 versions 
prior to 3.8.9 are untested. It is also entirely untested on any flavour of Linux.

Virtual env was used to create a reproducible environment in which to run the software see:<br> 
<code> virtualenv --version</code><br>
<code>virtualenv 20.4.7 from e:\program\python\python38\lib\site-packages\virtualenv\__init__.py</code>

Pip was used to install packages in the virtual environement see:<br>
<code>pip --version</code><br>
<code>pip 21.1.3 from e:\program\python\python38\lib\site-packages\pip (python 3.8)</code> 

Package requirement in <code>requirements.txt</code>

If virtual env is not already installed on your machine run:
 <code>pip install virtualenv</code><br>

To create the virtual environment:<br>
In the project directory<br>
 <code>virtualenv <venv-name> </code>(default is <code>venv</code>)<br>

On Windows, run start the virtual environment with:<br>
 <code><venv-name>\Scripts\activate</code><br>

Install the packages required by the project with:<br>
 <code>pip install -r requirements.txt</code><br>
 
See <https://python-docs.readthedocs.io/en/latest/dev/virtualenvs.html>

The path to the root of src directory (homework) needs to be in the PYTHON_PATH on the machine on which you run the code.
On windows this command will look something like:<br>
<code>set "PYTHONPATH=< full-project-dir-name >;%PYTHONPATH%"</code><br>

Currently, both client and server run on one machine. I don't have a proper network at home and there was no requirement 
given to be able to configure the ip addresses of either the client or server .

## Running the software
The software consists of two programs; a client and a server.
In order to achieve a full directory synch the server should be running first. 
### Run the server
From the project src directory start the virtual environment and type:<br>
 <code>python server\server.py -d <server-directory></code><br>
E.g <code>(venv) <project-src-directory>> python server\server.py -d <server-directory></code><br>

### Run the client
In another terminal or console start the virtual environment and type:<br>
<code>python client\client.py -d <client-directory></code><br>
E.g. <code>(venv) <project-src-directory>> python client\client.py -d <client-directory></code>

When server and client are started in correct order, within the virtual environment, then the directories should be
synchronised automatically and any files in the client directory not already on the server should be copied there. 
Any file on the server and not on the client should be deleted. Any files that have the same name on the client and 
server but different contents should be updated automatically on the server to reflect those on the client. 
Subsequently, if any files are created, deleted moved or edited in the client directory then these changes will be 
automatically reflected in the server directory as long as the client is running.<br>

The software was manually tested using the directories<br>
<code>client_synch_test_dir</code> and<br>
<code>server_test_dir</code><br>
as <client-directory> and <server-directory> arguments. There are some test files in <code>client_synch_test_dir</code>

*N.B.* At this time the directory monitoring does not work recursively and subdirectories on the client and their changes
will not be mirrored on the server.

### Stopping the software
On Windows both the server and client should terminate with Ctrl-C.

## Running tests
There are tests in the <code>test</code> directory, these can be run with:

<code>python test\test_fileactions.py</code><br>
<code>python test\test_end_to_end.py</code><br>

## Criticisms

As it stand the software is a simple proof of concept that show that the imprecise requirements asked for can be met.
I have some criticisms of the implementation, covered below:

### 1. Security
Security is an important consideration if a program/library is to be used seriously. The sockets used in this code are 
_not_ secure. Potentially, this exposes the contents of the messages to anyone that can intercept the TCP/IP packets 
transmitted. <br>

1.1 A good method to secure the communication would be to use TLS (transport layer security)
to wrap the TCP/IP socket. This will ensure that the packets sent are encrypted and not readable without the secure keys 
needed to decrypt the IP packets. Python provides a library to do this which is available here
<https://docs.python.org/3.8/library/ssl.html> I believe that the minimum safe version of TSL is v1.2, but v1.3 might
be a better choice.<br>

### 2. Hard coding of message structure
The client and server exchange messages in a simple request/response format. The client makes a request to the server 
which replies with a response. A messages is constructed in three parts. 
1. A fixed length pre-header that is an  integer value that denote the length to the following header.<br>
2. A variable length header formatted as JSON text that describes the message contents.<br>
3. The message contents, also constructed as JSON which contains file information and possibly raw byte data.<br>

The encoding and decoding of the messages is hardcoded, mainly in the message class. Personally, I don't like this.
The messages should be defined in a JSON schema. The exchanged messages would then be validated against this 
schema when received. Separation of the logic about a messages structure and its contents and that performing the actual
transmission of the messages could then take place. 

2.1. Refactor the message classes to use a class that validates messages against a json schema for each message type<br>
2.2 After this refactor the unit testing of messages should be easy.<br>

### 3. Real world testing
The host and port are currently hardcoded in the client and server code to use localhost. 
5.1 The host and port used by each should be configurable and tested across a real network.

### 4. The update file algorithm - calculating what data should be sent
The reasoning about which blocks to update  relies an a block size to be maintained and calculated from the start of 
the file, the file being divided into blocks of equal size. In effect, this considers the file to be an array of byte 
arrays. This means that if a relativeley small number of of bytes are inserted at the beginning of a file then this will
result in the contents of all the blocks being shifted in their array by a number of places equal to the number of bytes
inserted. This will change the hash-digest all the blocks in the array and therefore all the blocks will need to be 
resent. The algorithm is then not particularly efficient is this use-case. 
However, if a large number of bytes are inserted near the end of the document then the hash digest of the preceding
blocks will remain unchanged. In this case only the changed final blocks and possibly added blocks will be need to be 
sent. The algorithm becomes more efficient in terms of bytes sent with smaller block-size and when the changes/additions
happen closer to the end of file. <br>

4.1 This algorithm could be improved so that if edits occur at the beginning of the file then less data would need to 
be sent across the network from client to server. My first approach would be to try to use variable length byte arrays 
rather than the square arrays mandated by using a fixed block size. This would mean changes the information contained in the JSON header in order for 
the server to correctly recreate the file from the partial information sent. This requires a change to the message 
structure and Point 2.1 should be implemented first. 

### 5. The implementation is not complete
5.1. The client/server system is point-to-point. The server only serves one client. The server should be able to
accept connections from multiple clients. Use of framework such as Flask or Torado should help with this.

5.2 The directory monitoring doesn't recurse into subdirectories, this is a relatively easy next step. On the client the 
DirectoryMonitoring class need to be changed to handle directory changes and the observer object changed to monitor 
recursively. This might require more information in the JSON header, so that the server and place files in the correct
location. 

5.3 Neither client nor server are configurable - they should be. As a next step, IP addresses, file block size, 
   logging etc should be a configurable setting file. At least for the server.

5.4 Logging could be improved. Logging of the messages should be separate from debug and information, perhaps to a file.

### 6. Handling of byte arrays (future improvement)
6.1  For the update file functionality, file I/O on the server could possibly be improved using mmap objects for 
handling bytes read and written to the file. This would require the server to be able to predict in advance that a update
message will be sent and prepare for it. This is possible because immediately prior to an update file request the client
sends a file recipe request, which would warm the server that an update request is likely. 
  
6.2. As it stands any file content data - the byte contents of files -  are contained in JSON structure. 
It would be better to refactor the message structure to contain an optional and variable array of raw bytes at the end
of message immediately after the variable length content. Point 2.1 needs to be implemented first.



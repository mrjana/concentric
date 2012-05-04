#!/usr/bin/env python
# encoding: utf-8
import BaseHTTPServer, os, cgi
import cgitb; cgitb.enable()
import urllib
import django

from aws import aws_file_op

import dropbox
from dropbox import client, rest, session

import os

upload_form = """
<html>
<body>
<form action="" method="POST" enctype="multipart/form-data">
File upload: <input type="file" name="upfile">
<input type="submit" value="upload">
</form>
</body>
</html>
"""

# Amazon Info
bucket_name = "media.morecloud.com"
key_name = "samples/file_list"

# DropBox Info
APP_KEY="4v0s2ns4a47533h"
APP_SECRET="3solvck0dm89voy"
ACCESS_TYPE="app_folder"
ACCESS_TOKEN_KEY="tzey0jn1pqj525z"
ACCESS_TOKEN_SECRET="k0zwnkqw2c3dd60"

class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
	def write_form(self, file_list=""):
		file_list = os.listdir(os.path.join('meta'))
		self.wfile.write(upload_form)
		f_html = open("file_list.html", "w")
		f_html.write('<html><body><ul>')	   
		f_html.writelines(['<li><a href="%s">%s</a></li>' % (f, f) for f in file_list])
		f_html.write('</ul></body></html>')
		f_html.close()
		f_html = open("file_list.html", "r+")
		self.wfile.write(f_html.read())
		f_html.close()
		
	def do_GET(self):
		self.send_response(200)
		self.send_header("content-type", "text/html;charset=utf-8")
		self.end_headers()
		self.write_form()
		
	def do_POST(self):
		self.populenv()
		form = cgi.FieldStorage(fp=self.rfile)
		upfilecontent = form['upfile'].value
		if upfilecontent:
			# Create Meta data file
			fout = open(os.path.join('meta', form['upfile'].filename), 'wb')
			fout.write(form['upfile'].filename)
			fout.close()
			# Create a temporary file
			fout = open(os.path.join('tmp', form['upfile'].filename), 'wb')
			fout.write(upfilecontent)
			fout.close()
			
		# Upload to AWS
		self.upload_amazon(form['upfile'].filename)
		
		# Upload to Dropbox
		self.upload_dropbox(form['upfile'].filename)
		
		# Check by downloading from Amazon
		self.download_amazon(form['upfile'].filename)
		
		# Check by downloading from Dropbox
		self.download_dropbox(form['upfile'].filename)
		
		# Delete temporary file
		os.remove(os.path.join('tmp', form['upfile'].filename))
		self.do_GET()
		
	def upload_amazon(self, filename):
		# Upload to AWS
		aws_file_op.aws_upload(bucket_name, key_name, os.path.join('tmp', filename))
	
	def download_amazon(self, filename):
		# Download from AWS
		aws_file_op.aws_download(bucket_name, key_name, os.path.join('tmp',
		 											filename + ".aws" ))
		
	def create_dropbox_client(self):
		session1 = session.DropboxSession(APP_KEY, APP_SECRET, ACCESS_TYPE)
		session1.set_token(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
		return client.DropboxClient(session1)
	
	def upload_dropbox(self, filename):
		db_client = self.create_dropbox_client()
		resp = db_client.put_file("/" + filename, 
								os.path.join('tmp', filename))
								
	def download_dropbox(self, filename):
		db_client = self.create_dropbox_client()
		f, metadata = db_client.get_file_and_metadata("/" + filename)
		tofile= open(os.path.join('tmp', filename + ".dbx"), "wb")
		tofile.write(f.read())
		tofile.close()
		tofile= open(os.path.join('tmp', filename + ".dbx.meta"), "wb")
		tofile.write(str(metadata))
		tofile.close()
							
	def populenv(self):
		path = self.path
		dir, rest = '.', 'ciao'

		# find an explicit query string, if present.
		i = rest.rfind('?')
		if i >= 0:
			rest, query = rest[:i], rest[i+1:]
		else:
			query = ''

		# dissect the part after the directory name into a script name &
		# a possible additional path, to be stored in PATH_INFO.
		i = rest.find('/')
		if i >= 0:
			script, rest = rest[:i], rest[i:]
		else:
			script, rest = rest, ''

		# Reference: http://hoohoo.ncsa.uiuc.edu/cgi/env.html
		# XXX Much of the following could be prepared ahead of time!
		env = {}
		env['SERVER_SOFTWARE'] = self.version_string()
		env['SERVER_NAME'] = self.server.server_name
		env['GATEWAY_INTERFACE'] = 'CGI/1.1'
		env['SERVER_PROTOCOL'] = self.protocol_version
		env['SERVER_PORT'] = str(self.server.server_port)
		env['REQUEST_METHOD'] = self.command
		uqrest = urllib.unquote(rest)
		env['PATH_INFO'] = uqrest
		env['SCRIPT_NAME'] = 'ciao'
		if query:
			env['QUERY_STRING'] = query
		host = self.address_string()
		if host != self.client_address[0]:
			env['REMOTE_HOST'] = host
		env['REMOTE_ADDR'] = self.client_address[0]
		authorization = self.headers.getheader("authorization")
		if authorization:
			authorization = authorization.split()
			if len(authorization) == 2:
				import base64, binascii
				env['AUTH_TYPE'] = authorization[0]
				if authorization[0].lower() == "basic":
					try:
						authorization = base64.decodestring(authorization[1])
					except binascii.Error:
						pass
					else:
						authorization = authorization.split(':')
						if len(authorization) == 2:
							env['REMOTE_USER'] = authorization[0]
		# XXX REMOTE_IDENT
		if self.headers.typeheader is None:
			env['CONTENT_TYPE'] = self.headers.type
		else:
			env['CONTENT_TYPE'] = self.headers.typeheader
		length = self.headers.getheader('content-length')
		if length:
			env['CONTENT_LENGTH'] = length
		referer = self.headers.getheader('referer')
		if referer:
			env['HTTP_REFERER'] = referer
		accept = []
		for line in self.headers.getallmatchingheaders('accept'):
			if line[:1] in "\t\n\r ":
				accept.append(line.strip())
			else:
				accept = accept + line[7:].split(',')
		env['HTTP_ACCEPT'] = ','.join(accept)
		ua = self.headers.getheader('user-agent')
		if ua:
			env['HTTP_USER_AGENT'] = ua
		co = filter(None, self.headers.getheaders('cookie'))
		if co:
			env['HTTP_COOKIE'] = ', '.join(co)
		# XXX Other HTTP_* headers
		# Since we're setting the env in the parent, provide empty
		# values to override previously set values
		for k in ('QUERY_STRING', 'REMOTE_HOST', 'CONTENT_LENGTH',
				  'HTTP_USER_AGENT', 'HTTP_COOKIE', 'HTTP_REFERER'):
			env.setdefault(k, "")
		os.environ.update(env)

if __name__ == '__main__':
	server = BaseHTTPServer.HTTPServer(("127.0.0.1", 8082), Handler)
	print('web server on 8082..')
	server.serve_forever()


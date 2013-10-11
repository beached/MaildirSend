#Copyright (c) 2013, Darrell Wright
#All rights reserved.
#
#Redistribution and use in source and binary forms, with or without modification,
#are permitted provided that the following conditions are met:
#
#  Redistributions of source code must retain the above copyright notice, this
#  list of conditions and the following disclaimer.
#
#  Redistributions in binary form must reproduce the above copyright notice, this
#  list of conditions and the following disclaimer in the documentation and/or
#  other materials provided with the distribution.
#
#THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
#ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
#WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
#ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
#SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
__author__ = 'Darrell Wright'

userFolders = '/home'
maildirName = '.maildir'
outboxFolder = 'Outbox'
sentFolder = 'Sent'

host = 'localhost'
port = 25

import email.errors
import mailbox
import os.path
import smtplib
import watchdog
import sys

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer



def find_outbox_parents( path, outboxName ):
	print 'Testing: ' + path + ', ' + outboxName
	d = {}
	if os.path.isdir( path ):
		for name in os.listdir( path ):
			currentTestPath = os.path.join( path, name, maildirName )
			if os.path.isdir( currentTestPath ):
				d[name] = mailbox.Maildir( currentTestPath, factory=None )
	return d

def get_base_maildir_from_file( filename, watchedMailDirs ):
	for curDir in watchedMailDirs:
		if filename.startswith( curDir ):
			return mailbox.Maildir( curDir, factory=None )
	print 'Inconsistency error:  Watching a folder that was not tracked'
	sys.exit( 1 )

def send_message( message ):
	assert isinstance( message, mailbox.MaildirMessage )
	if 'T' not in message.get_flags( ):  #do not process trashed messages
		recipients = []
		if 'To' in message:
			recipients.extend( message['To'].split( ) )
		if 'CC' in message:
			recipients.extend( message['CC'].split( ) )
		smtpObj = smtplib.SMTP( host=host, port=port )
		#smtpObj.set_debuglevel( debuglevel=1 )
		if len( recipients ) > 0:
			smtpObj.sendmail( message['From'], recipients, str( message ) )
		if 'BCC' in message:
			for bccRecipient in message['BCC'].split( ):
				smtpObj.sendmail( message['From'], bccRecipient, str( message ) )
		smtpObj.quit( )

class NewOutboxMessageHandler( FileSystemEventHandler ):
	def __init__( self, observer ):
		self.observer = observer
		self.watchedMailDirs = []

	def schedule(self, outboxPath, inboxPath ):
		self.observer.schedule( self, outboxPath, recursive=True )
		self.watchedMailDirs.append( inboxPath )

	def on_created( self, event ):
		if not event.is_directory and '.lock' not in event.src_path:
			o = Observer( )
			inbox = get_base_maildir_from_file( event.src_path, self.watchedMailDirs )
			outbox = inbox.get_folder( outboxFolder )
			outbox.lock( )
			try:
				sentbox = inbox.get_folder( sentFolder )
				for key in outbox.iterkeys( ):
					try:
						message = outbox[key]
					except email.Errors.MessageParseError:
						continue
					send_message( message )
					sentbox.lock( )
					try:
						message.set_flags( 'S' )
						sentbox.add( message )
						sentbox.flush( )
					finally:
						sentbox.unlock( )
					outbox.remove( key )
					del outbox[key]
				outbox.flush( )
			finally:
				outbox.unlock( )

def main( argv=None ):
	inboxes = find_outbox_parents( path=userFolders, outboxName=outboxFolder )
	observer = Observer( )
	event_handler = NewOutboxMessageHandler( observer )

	for name in inboxes:
		inbox = inboxes[name]
		assert isinstance( inbox, mailbox.Maildir )
		try:
			outbox = inbox.get_folder( outboxFolder )
		except mailbox.NoSuchMailboxError:
			continue

		try:
			sentbox = inbox.get_folder( sentFolder )
		except mailbox.NoSuchMailboxError:
			print 'No Sent folder in ', name, ' , creating'
			inbox.add_folder( sentFolder )
			sentbox = inbox.get_folder( sentFolder )

		#watchedMailDirs.append( inbox._path )
		#observer.schedule( event_handler, outbox._path, recursive=True )
		event_handler.schedule( outboxPath=outbox._path, inboxPath=inbox._path )
		observer.start( )
		observer.join( )

if __name__ == '__main__':
	sys.exit( main( sys.argv ) )

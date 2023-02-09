import os
import pickle
# Gmail API utils
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
# for encoding/decoding messages in base64
from base64 import urlsafe_b64decode, urlsafe_b64encode
# for dealing with attachement MIME types
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from mimetypes import guess_type as guess_mime_type
import base64


# Request all access (permission to read/send/receive emails, manage the inbox, and more)
SCOPES = ['https://mail.google.com/']
our_email = #email_here

def gmail_authenticate():
    creds = None
    # the file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # if there are no (valid) credentials availablle, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

# get the Gmail API service
service = gmail_authenticate()

def search_messages(service, query):
    result = service.users().messages().list(userId='me',q=query).execute()
    messages = [ ]
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me',q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages
                                    
def line_prepender(filename, line):
    with open(filename, 'r+') as f:
        content = f.read()
        f.seek(0, 0)
        f.write(line.rstrip('\r\n') + '\n' + content)

def read_message(service, message,db):
    """
    This function takes Gmail API `service` and the given `message_id` and does the following:
        - Downloads the content of the email
        - Prints email basic information (To, From, Subject & Date) and plain/text parts
        - Creates a folder for each email based on the subject
        - Downloads text/html content (if available) and saves it under the folder created as index.html
        - Downloads any file that is attached to the email and saves it in the folder created
    """
    msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
    # parts can be the message body, or attachments
    payload = msg['payload']
    headers = payload.get("headers")
    parts = payload.get("parts")
    folder_name = "email"
    has_subject = False
    if headers:
        # this section prints email basic info & creates a folder for the email
        email_headers={}
        for header in headers:
            name = header.get("name")
            value = header.get("value")
            if name.lower() == 'from':
                # we print the From address
                source=value
                email_headers["From"]=source
            if name.lower() == "to":
                # we print the To address
                to=value
                email_headers["To"]=to
            if name.lower() == "subject":
                # make our boolean True, the email has "subject"
                has_subject = True
                subject=value
                email_headers["Subject"]=subject
            if name.lower() == "date":
                # we print the date when the message was sent
                date=value.rsplit(" ",1)[0].replace(":","_").split(" ", 1)[1].split(" ")
                date = date[2]+"-"+date[1]+"-"+date[0]+"-"+date[3]
                email_headers["Date"]=value
                
    if not has_subject:
         # if the email does not have a subject, then make a folder with "email" name
         # since folders are created based on subjects
         if not os.path.isdir(folder_name):
             os.mkdir(folder_name)
    
    string_enc = msg["payload"]["body"]["data"]
    filename = f"{date}.txt"
    filepath = os.path.join(db, filename)
    with open(filepath, "wb") as f:
        f.write(base64.urlsafe_b64decode(string_enc))
    
    line_prepender(filepath,"="*50)
    
    for items in email_headers:
        line = items+":"+email_headers[items]
        line_prepender(filepath,line)

    
if __name__ == "__main__":
    databases = ["payments-db-production","fave-production-main-v1","maps-cache-db-production"]
    for db in databases:
        # get emails that match the query you specify
        results = search_messages(service, f"RDS Notification Message,Event Source : db-snapshot,SourceId: rds:{db},after:2022/04/01")
        print(f"Found {len(results)} email results for {db} db-snapshots notifications.")
        # for each email matched, read it (output plain/text to console & save HTML and attachments)
        for msg in results:
            read_message(service, msg,db)

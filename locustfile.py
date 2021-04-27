import random
import json
import os.path
import sys
import hashlib
import hmac
from locust import HttpUser, between, constant, events # pylint: disable=import-error
from locust.runners import MasterRunner, LocalRunner # pylint: disable=import-error


#########
## SETUP
#########

AVAILABLE_USERS = []
CONFIG = {}
USER_DATA_FILE_PATH = 'data/users.json'
CONFIG_FILE_PATH = 'data/config.json'

@events.init.add_listener
def on_locust_init(runner, environment, web_ui):
    determine_runner(runner)
    load_config()
    load_user_data()

def determine_runner(runner):
    if isinstance(runner, LocalRunner):
        print("Running in standalone node.")
    elif isinstance(runner, MasterRunner):
        print("Running as master node.")
    else:
        print("Running as worker node.")

def load_config():
    if not os.path.exists(CONFIG_FILE_PATH):
        print("No config file found! Create '%s' to configure the runner." % CONFIG_FILE_PATH)
    else:
        with open(CONFIG_FILE_PATH) as json_file:
            global CONFIG
            CONFIG = json.load(json_file)

def load_user_data():
    if not os.path.exists(USER_DATA_FILE_PATH):
        print("Please create file '%s' to provide test users." % USER_DATA_FILE_PATH)
        sys.exit()

    with open(USER_DATA_FILE_PATH) as json_file:
        global AVAILABLE_USERS
        AVAILABLE_USERS = json.load(json_file)

def get_random_user_data():
    return random.choice(AVAILABLE_USERS)


##########
## HELPER
##########

def sync_request(self, timeout, since=""):
    payload = {
        "timeout": timeout
    }

    name = "/_matrix/client/r0/sync?timeout=%i" % timeout
    if since != "":
        payload["since"] = since
        name = "/_matrix/client/r0/sync?timeout=%i&since=[timestamp]" % timeout

    if self.filter_id:
        payload["filter"] = self.filter_id
        name += "&filter=[filter_id]"

    response = self.client.get("/_matrix/client/r0/sync", params=payload, name=name)
    if response.status_code != 200:
        return

    json_response_dict = response.json()
    if 'next_batch' in json_response_dict:
        self.next_batch = json_response_dict['next_batch']


    # extract rooms
    if 'rooms' in json_response_dict and 'join' in json_response_dict['rooms']:
        # ToDo: check if user has permission to write in rooms
        room_ids = list(json_response_dict['rooms']['join'].keys())
        if len(room_ids) > 0:
            self.room_ids = room_ids


#########
## TASKS
#########

def task_init_on_page_load(self):
    if not self.token:
        return
    # GET /_matrix/client/versions (no auth)
    self.client.get("/_matrix/client/versions")

    # GET /_matrix/client/unstable/room_keys/version (no auth)
    # self.client.get("/nstable/room_keys/version") # not implemented

    # GET /_matrix/client/r0/voip/turnServer
    self.client.get("/_matrix/client/r0/voip/turnServer")

    # GET /_matrix/client/r0/pushrules/
    self.client.get("/_matrix/client/r0/pushrules/")

    # GET /_matrix/client/r0/joined_groups
    self.client.get("/_matrix/client/r0/joined_groups")

    # GET /_matrix/client/r0/profile/[user-id]
    self.client.get(
        "/_matrix/client/r0/profile/%s" % self.user_id,
        name="/_matrix/client/r0/profile/[user-id]"
    )

    # Filter
    if self.filter_id:
        # GET /_matrix/client/r0/user/[user-id]/filter/1
        self.client.get(
            "/_matrix/client/r0/user/%s/filter/%s" % (self.user_id, self.filter_id),
            name="/_matrix/client/r0/user/[user-id]/filter/[filter]"
        )
    else:
        # POST /_matrix/client/r0/user/[user-id]/filter
        # body: {"room":{"timeline":{"limit":20},"state":{"lazy_load_members":true}}}
        # response: {"filter_id": "1"}
        body = {"room":{"timeline":{"limit":20}, "state":{"lazy_load_members":True}}}
        response = self.client.post(
            "/_matrix/client/r0/user/%s/filter" % self.user_id,
            json=body,
            name="/_matrix/client/r0/user/[user-id]/filter"
        )

        # store filter id
        if response.status_code == 200:
            json_response_dict = response.json()
            if 'filter_id' in json_response_dict:
                self.filter_id = json_response_dict['filter_id']

    # GET /_matrix/client/r0/capabilities
    self.client.get("/_matrix/client/r0/capabilities")

    # PUT /_matrix/client/r0/presence/[user-id]/status {"presence":"online"}
    self.client.put(
        "/_matrix/client/r0/presence/%s/status" % self.user_id,
        json={"presence":"online"},
        name="/_matrix/client/r0/presence/[user-id]/status"
    )

    # Encryption keys:
    # POST /_matrix/client/r0/keys/upload (complicated)
    # POST /_matrix/client/r0/keys/query (complicated)

    # First sync
    sync_request(self, 0, self.next_batch)

def task_background_sync(self):
    if not self.filter_id:
        return # only sync after initial setup

    # Background sync:
    # GET /_matrix/client/r0/sync?filter=1&timeout=0&since=s1051_37479_38_115_105_1_219_1489_1
    sync_request(self, 0, self.next_batch)

    # GET /_matrix/client/r0/sync?filter=1&timeout=30000&since=s1051_37491_38_115_105_1_219_1489_1
    # (long-pooling messes up timing overview)
    sync_request(self, 30000, self.next_batch)


def task_send_message(self):
    if len(self.room_ids) == 0:
        return # rooms needed

    # select random room
    room_id = random.choice(self.room_ids)

    # PUT /_matrix/client/r0/rooms/[room_id]/typing/[user_id] {"typing":true,"timeout":30000}
    self.client.put(
        "/_matrix/client/r0/rooms/%s/typing/%s" % (room_id, self.user_id),
        json={"typing": True, "timeout":30000},
        name="/_matrix/client/r0/rooms/[room_id]/typing/[user_id] - true"
    )

    # PUT /_matrix/client/r0/rooms/[room-id]/typing/[user-id] {"typing":false}
    self.client.put(
        "/_matrix/client/r0/rooms/%s/typing/%s" % (room_id, self.user_id),
        json={"typing": False},
        name="/_matrix/client/r0/rooms/[room_id]/typing/[user_id] - false"
    )

    # POST /_matrix/client/r0/rooms/[room-id]/send/m.room.message { "msgtype": "m.text", "body": "msg"}
    message = {
        "msgtype": "m.text",
        "body": "Load Test Message",
    }
    self.client.post(
        "/_matrix/client/r0/rooms/%s/send/m.room.message" % room_id,
        json=message,
        name="/_matrix/client/r0/rooms/[room_id]/send/m.room.message"
    )

def task_login(self):
    if not 'shared_secret' in CONFIG:
        return
    secret = bytes(CONFIG['shared_secret'], 'ascii')
    password = hmac.new(secret, str(self.user_id).encode('utf-8'), hashlib.sha512).hexdigest()

    message = {
        "type": "m.login.password",
        "user": self.user_id,
        "initial_device_display_name": "load_test",
        "device_id": self.user_id[1:16],
        "password": password,
    }

    response = self.client.post(
        "/_matrix/client/r0/login",
        json=message
    )

    if response.status_code == 200:
        # store and use access token
        json_response_dict = response.json()
        self.token = json_response_dict['access_token']
        self.client.headers["authorization"] = "Bearer " + self.token


#########
## USERS
#########

class BaseUser(HttpUser):
    wait_time = constant(10) # execute tasks with seconds delay
    weight = 0 # how likely to simulate user
    tasks = {}

    # user data
    user_id = ""
    token = ""
    next_batch = ""
    filter_id = None
    room_ids = []

    def on_start(self):
        # select random user
        user_data = get_random_user_data()
        self.user_id = user_data['userId']
        self.token = "" # user_data['accessToken']

        # authenticate user
        self.client.headers["authorization"] = "Bearer " + self.token
        self.client.headers["accept"] = "application/json"

        # login user befor doing other tasks
        task_login(self)

class IdleUser(BaseUser):
    wait_time = between(5, 30) # execute tasks with seconds delay
    weight = 3 # how likely to simulate user
    tasks = {task_login: 1, task_init_on_page_load: 10, task_background_sync: 10}

class ActiveUser(BaseUser):
    wait_time = between(2, 10) # execute tasks with seconds delay
    weight = 2 # how likely to simulate user
    tasks = {task_login: 1, task_init_on_page_load: 10, task_background_sync: 100, task_send_message: 20}

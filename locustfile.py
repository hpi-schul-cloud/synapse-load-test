import random
import json
import os.path
from locust import HttpUser, task, TaskSet, between, constant, events
from locust.runners import MasterRunner, LocalRunner


#########
## SETUP
#########

AVAILABLE_USERS = []
USER_DATA_FILE_PATH = 'data/users.json'

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    determine_runner(environment)
    load_user_data()

def determine_runner(environment):
    if isinstance(environment.runner, LocalRunner):
        print("Running in standalone node.")
    elif isinstance(environment.runner, MasterRunner):
        print("Running as master node.")
    else:
        print("Running as worker node.")

def load_user_data():
    if not os.path.exists(USER_DATA_FILE_PATH):
        print("Please create file '%s' to provide test users." % USER_DATA_FILE_PATH)
        exit()

    with open(USER_DATA_FILE_PATH) as json_file:
        global AVAILABLE_USERS
        AVAILABLE_USERS = json.load(json_file)

def get_random_user_data():
    return random.choice(AVAILABLE_USERS)


#########
## TASKS
#########

def task_init_on_page_load(self):
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
    self.client.get("/_matrix/client/r0/profile/%s" % self.user_id, name="/_matrix/client/r0/profile/[user-id]")

    # GET /_matrix/client/r0/user/[user-id]/filter/1
    # (does only work if filter haver been creaded)
    # self.client.get("/_matrix/client/r0/user/%s/filter/%i" % (self.user_id, 2), name="/_matrix/client/r0/user/[user-id]/filter/[filter]")

    # GET /_matrix/client/r0/capabilities
    self.client.get("/_matrix/client/r0/capabilities")

    # PUT /_matrix/client/r0/presence/[user-id]/status {"presence":"online"}
    self.client.put("/_matrix/client/r0/presence/%s/status" % self.user_id, json={"presence":"online"}, name="/_matrix/client/r0/presence/[user-id]/status")

    # Encryption keys:
    # POST /_matrix/client/r0/keys/upload (complicated)
    # POST /_matrix/client/r0/keys/query (complicated)

def task_background_sync(self):
    
    def syncRequest(timeout, since = ""):
        payload = {
            #"filter": 1,
            "timeout": timeout
        }
        
        name = "/_matrix/client/r0/sync?timeout=%i" % timeout
        if since != "":
            payload["since"] = since
            name = "/_matrix/client/r0/sync?timeout=%i&since=[timestamp]" % timeout

        response = self.client.get("/_matrix/client/r0/sync", params=payload, name=name)
        if response.status_code != 200:
            response.failure()
        
        json_response_dict = response.json()
        if 'next_batch' in json_response_dict:
            self.next_batch = json_response_dict['next_batch']


        # extract rooms
        if 'rooms' in json_response_dict and 'join' in json_response_dict['rooms']:
            room_ids = list(json_response_dict['rooms']['join'].keys())
            if len(room_ids):
                self.room_ids = room_ids

    # Background sync:
    # GET /_matrix/client/r0/sync?filter=1&timeout=0&since=s1051_37479_38_115_105_1_219_1489_1
    syncRequest(0, self.next_batch)
    
    # GET /_matrix/client/r0/sync?filter=1&timeout=30000&since=s1051_37491_38_115_105_1_219_1489_1
    # (long-pooling messes up timing overview)
    # self.syncRequest(30000, self.next_batch)

def task_send_message(self):
    if len(self.room_ids) == 0:
        return

    # select random room
    room_id = random.choice(self.room_ids)    

    # PUT /_matrix/client/r0/rooms/[room_id]/typing/[user_id] {"typing":true,"timeout":30000}
    self.client.put("/_matrix/client/r0/rooms/%s/typing/%s" % (room_id, self.user_id), json={"typing": True, "timeout":30000}, name= "/_matrix/client/r0/rooms/[room_id]/typing/[user_id] - true")
    
    # PUT /_matrix/client/r0/rooms/[room-id]/typing/[user-id] {"typing":false}
    self.client.put("/_matrix/client/r0/rooms/%s/typing/%s" % (room_id, self.user_id), json={"typing": False}, name= "/_matrix/client/r0/rooms/[room_id]/typing/[user_id] - false")

    # POST /_matrix/client/r0/rooms/[room-id]/send/m.room.message { "msgtype": "m.text", "body": "msg"}
    message = {
        "msgtype": "m.text",
        "body": "Load Test Message",
    }
    with self.client.post("/_matrix/client/r0/rooms/%s/send/m.room.message" % room_id, json=message, name="/_matrix/client/r0/rooms/[room_id]/send/m.room.message", catch_response=True) as response:
        if response.status_code == 200 or response.status_code == 403: # even if user is not allowed to post into room, count the request as success
            response.success()
        else:
            response.failure()


#########
## USERS
#########

class BaseUser(HttpUser):
    wait_time = between(5, 15) # execute tasks with seconds delay
    weight = 0 # how likely to simulate user
    tasks = {}

    # user data
    user_id = ""
    token = ""
    next_batch = ""
    room_ids = []

    def on_start(self):
        # select random user
        user_data = get_random_user_data();
        self.user_id = user_data['userId']
        self.token = user_data['accessToken']

        # authenticate user
        self.client.headers["authorization"] = "Bearer " + self.token
        self.client.headers["accept"] = "application/json"

class IdleUser(BaseUser):
    wait_time = between(5, 15) # execute tasks with seconds delay
    weight = 3 # how likely to simulate user
    tasks = {task_init_on_page_load: 1, task_background_sync: 1}

class ActiveUser(BaseUser):
    wait_time = constant(2) # execute tasks with seconds delay
    weight = 2 # how likely to simulate user
    tasks = {task_init_on_page_load: 1, task_background_sync: 3, task_send_message: 8}

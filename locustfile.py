import random
import json
from locust import HttpUser, task, TaskSet, between, constant, events
from locust.runners import MasterRunner, LocalRunner

AVAILABLE_USERS = []

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    if isinstance(environment.runner, LocalRunner):
        print("I'm on a standalone node")
    elif isinstance(environment.runner, MasterRunner):
        print("I'm on master node")
    else:
        print("I'm on a worker node")

    with open('data/users.json') as json_file:
        global AVAILABLE_USERS
        AVAILABLE_USERS = json.load(json_file)

def get_random_user_data():
    return random.choice(AVAILABLE_USERS)



class MessengerInitialization(TaskSet):
    @task
    def init(self): # on every page load
        # GET https://matrix.test.messenger.schule/_matrix/client/versions (no auth)
        self.client.get("/_matrix/client/versions")

        # GET https://matrix.test.messenger.schule/_matrix/client/unstable/room_keys/version (no auth)
        # self.client.get("/nstable/room_keys/version") # not implemented

        # GET https://matrix.test.messenger.schule/_matrix/client/r0/voip/turnServer
        self.client.get("/_matrix/client/r0/voip/turnServer")

        # GET https://matrix.test.messenger.schule/_matrix/client/r0/pushrules/
        self.client.get("/_matrix/client/r0/pushrules/")

        # GET https://matrix.test.messenger.schule/_matrix/client/r0/joined_groups
        self.client.get("/_matrix/client/r0/joined_groups")

        # GET https://matrix.test.messenger.schule/_matrix/client/r0/profile/%40sso_0000d231816abba584714c9e%3Atest.messenger.schule
        self.client.get("/_matrix/client/r0/profile/%s" % self.user.user_id, name="/_matrix/client/r0/profile/[user-id]")

        # GET https://matrix.test.messenger.schule/_matrix/client/r0/user/%40sso_0000d231816abba584714c9e%3Atest.messenger.schule/filter/1
        #self.client.get("/_matrix/client/r0/user/%s/filter/%i" % (self.user.user_id, 2), name="/_matrix/client/r0/user/[user-id]/filter/[filter]")

        # GET https://matrix.test.messenger.schule/_matrix/client/r0/capabilities
        self.client.get("/_matrix/client/r0/capabilities")

        # PUT https://matrix.test.messenger.schule/_matrix/client/r0/presence/%40sso_0000d231816abba584714c9e%3Atest.messenger.schule/status {"presence":"online"}
        self.client.put("/_matrix/client/r0/presence/%s/status" % self.user.user_id, json={"presence":"online"}, name="/_matrix/client/r0/presence/[user-id]/status")

        # Encryption keys:
        # POST https://matrix.test.messenger.schule/_matrix/client/r0/keys/upload (complicated)
        # POST https://matrix.test.messenger.schule/_matrix/client/r0/keys/query (complicated)

    @task
    def sync(self): # background sync requests
        # Background sync:
        # GET https://matrix.test.messenger.schule/_matrix/client/r0/sync?filter=1&timeout=0&since=s1051_37479_38_115_105_1_219_1489_1
        self.syncRequest(0, self.user.next_batch)
        
        # GET https://matrix.test.messenger.schule/_matrix/client/r0/sync?filter=1&timeout=30000&since=s1051_37491_38_115_105_1_219_1489_1
        # long-pooling messes up timing overview
        #self.syncRequest(30000, self.user.next_batch)

    def syncRequest(self, timeout, since = ""):
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
            self.user.next_batch = json_response_dict['next_batch']


        # extract rooms
        if 'rooms' in json_response_dict and 'join' in json_response_dict['rooms']:
            room_ids = list(json_response_dict['rooms']['join'].keys())
            if len(room_ids):
                self.user.room_ids = room_ids

    @task
    def sendMessage(self):
        if len(self.user.room_ids) == 0:
            return

        # POST /_matrix/client/r0/rooms/${room_id}/send/m.room.message`, message
        room_id = random.choice(self.user.room_ids)    
        message = {
            "msgtype": "m.text",
            "body": "Load Test Message",
        }
        self.client.post("/_matrix/client/r0/rooms/%s/send/m.room.message" % room_id, json=message, name="/_matrix/client/r0/rooms/[room_id]/send/m.room.message")


class IdleUser(HttpUser):
    wait_time = constant(1) # between(5, 15) # execute tasks with seconds delay
    weight = 3 # how likely to simulate user
    tasks = {MessengerInitialization:2}

    user_id = ""
    token = ""
    next_batch = ""
    room_ids = []

    def on_start(self):
        user_data = get_random_user_data();
        self.user_id = user_data['userId']
        self.token = user_data['accessToken']

        self.client.headers["authorization"] = "Bearer " + self.token
        self.client.headers["accept"] = "application/json"


#class ActiveUser(HttpUser):
#    wait_time = between(5, 15) # execute tasks with seconds delay
#    weight = 1 # how likely to simulate user
#    tasks = {MessengerInitialization:1}
#    
#    @task
#    def load(self):
#        self.client.get("/versions")


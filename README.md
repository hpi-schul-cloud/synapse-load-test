# Synapse Load Tests

## Test User Creation

The [schulcloud-synapse-synchronization](https://github.com/hpi-schul-cloud/schulcloud-synapse-synchronization) project is used to generate random test users on a test system. 

### Setup

1. Clone the synchronization project:
```
git clone git@github.com:hpi-schul-cloud/schulcloud-synapse-synchronization.git
```

2. Create a `.env` file in the cloned project to configure the system to test:
```
MATRIX_URI = https://matrix.domain.tld
MATRIX_SERVERNAME = matrix.domain.tld
MATRIX_SYNC_USER_NAME = sync
MATRIX_SECRET = XXX
```

3. Install the dependencies
```
npm install
```

### Execute

Run the integration tests to create test users and save them in a file (`users.json`):
```
npm run test:integration
```


## Simulate User Actions

### Setup

1. Clone this project:
```
git clone git@github.com:hpi-schul-cloud/synapse-load-test.git
```

2. Setup python dependencies:
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Copy the generated `users.json` file to the data folder of this project.

### Execute

Validate the setup by simulating only one user:
```
locust -u 1 -r 1 -H https://matrix.domain.tld
```
Open the Locust UI in your browser [http://127.0.0.1:8089/](http://127.0.0.1:8089/) and start it.

If everything works more users could be simulated. The following command starts more and more users to see at what number problems arise:
```
locust -u 3000 -r 100 --step-load --step-users 200 --step-time 30s -H https://matrix.domain.tld
```

### Cloud Setup

To avoid limitations of a desktop computer or its internet connection it is advisable to execute locust on a remote machine.

Setup for ubuntu 18.04 with 4 cores:
```
# dependencies
sudo apt update
sudo apt install python3-pip
sudo get install python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# increase open files limitations
ulimit -n 65535

# start worker in the background
locust --worker &
locust --worker &
locust --worker &

# start the master and configure locust via the ui on port 8089
locust --master
```

## Author

- [Max Klenk](https://github.com/maxklenk)
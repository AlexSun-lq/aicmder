from multiprocessing import Process, Event
import logging
import zmq, sys
from termcolor import colored
import json
# from .helper import set_logger

# 3s for timeout
REQUEST_TIMEOUT = 5000 #2500 
REQUEST_RETRIES = 3
SERVER_ENDPOINT = "tcp://localhost:5555"
logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)

class HTTPProxy(Process):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.is_ready = Event()
    
    def send_request(self, request):
        self.client.send(request)

        retries_left = REQUEST_RETRIES
        while True:
            
            if (self.client.poll(REQUEST_TIMEOUT) & zmq.POLLIN) != 0:
                reply = self.client.recv()
                # logging.info("Server replied msg (%s)", reply.decode())
                return reply
            
            retries_left -= 1
            logging.warning("No response from server")
            # Socket is confused. Close and remove it.
            self.client.setsockopt(zmq.LINGER, 0)
            self.client.close()
            if retries_left == 0:
                logging.error("Server seems to be offline, abandoning")
                raise Exception("Server seems to be offline, abandoning")
                # sys.exit()

            logging.info("Reconnecting to server…")
            # Create new connection
            self.client = self.context.socket(zmq.REQ)
            self.client.connect(SERVER_ENDPOINT)
            logging.info("Resending (%s)", request)
            self.client.send(request)
            
    def create_fastapi_app(self):
        
        from fastapi import FastAPI, Request
        from flask_json import JsonError
        

        app = FastAPI()

        # logger = set_logger(colored('PROXY', 'red'), self.args.verbose)

      
        # @app.get('/status/server')
        # def get_server_status():
        #     return bc.server_status

        # @app.get('/status/client')
        # def get_client_status():
        #     return bc.status

        @app.post('/predict')
        def predict(data: dict, request: Request):
            # data = request.form if request.form else request.json
            try:
                print(request, data)
                json_str = json.dumps(data)
                # logger.info('new request from %s' % request.client.host)
                result = self.send_request(json_str.encode())
                return result
            except Exception as e:
                # logger.error('error when handling HTTP request', exc_info=True)
                raise JsonError(description=str(e), type=str(type(e).__name__))

        return app


    def run(self):
        import uvicorn
        app = self.create_fastapi_app()
        self.context = zmq.Context()

        logging.info("Connecting to server…")
        self.client = self.context.socket(zmq.REQ)
        self.client.connect(SERVER_ENDPOINT)
        self.is_ready.set()
        uvicorn.run(app, host="0.0.0.0", port=self.args.http_port)

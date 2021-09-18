import argparse
import os
from flask import Flask, request
from models import *
from utils import call_next_destination, cast_and_execute

parser = argparse.ArgumentParser()

parser.add_argument('--service-name', action='store', type=str, default="Undefined",
                    help='The name set on the response')
parser.add_argument('--port', action='store', type=int, default=8080, help='The port the web server will bind to')

args = parser.parse_args()

# override of if ENV is present
args.service_name = os.getenv("SERVICE_NAME", args.service_name)

app = Flask('service')


@app.before_request
def log_request_info():
    app.logger.info(f'RemoteAddr:{request.remote_addr} Method:{request.method} Body:{request.get_json()}')


@app.after_request
def add_header(response):
    response.headers['content-type'] = 'application/json'
    return response


@app.route("/", methods=["POST"])
def handler():
    res = Response(args.service_name, "", [], [])

    try:
        payload = Route.from_json(request.data)

        # Set the incoming request designation as the address for this service
        res.address = payload.designation

        # Run fault faults
        for fault in payload.faults.before:
            err = cast_and_execute(fault)
            if err:
                res.errors.append(err)

        # Forward the request to next service if the destination is defined
        if payload.routes:
            for route in payload.routes:
                try:
                    dest_res = call_next_destination(route)
                    res.response.append(dest_res)
                except Exception as e:
                    app.logger.exception("error while forwarding request")
                    res.errors.append(str(e))
                    res.response.append(None)

        # Run post faults
        for fault in payload.faults.after:
            err = cast_and_execute(fault)
            if err:
                res.errors.append(err)

        # Return the response to calling service
        return res.to_json()
    except (AttributeError, KeyError) as e:
        return {"error": str(e)}, 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=args.port)

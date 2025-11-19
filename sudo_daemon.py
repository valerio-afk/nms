import os
import grp
import json
import pwd
import struct
import socket
from constants import SOCK_PATH
from importlib import import_module
from socketserver import UnixStreamServer, StreamRequestHandler
from nms_utils import setup_logger
from cmdl import LocalCommandLineTransaction, CommandLineTransaction



ALLOWED_UID = None
LOGGER = None


def load_cmd_from_json(d):
    module = import_module("cmdl")
    clsname = d.pop('__class__')
    cls = getattr(module, clsname)
    obj = cls(**d)
    return obj


def hook_pre_command(command, revert):
    global LOGGER

    cmd = command.command if not revert else command.revert_command
    if (isinstance(cmd,list)):
        LOGGER.info(f"Executing: {' '.join(cmd)}")


def hook_post_command(output):
    global LOGGER

    LOGGER.info(f"Exit code : {output.returncode}")
    LOGGER.info(f"Error : {output.stderr}")

def run_commands(commands):
    cmds = []

    for d in commands:
        cmd = load_cmd_from_json(d)
        cmds.append(cmd)

    trans = LocalCommandLineTransaction(*cmds)
    trans.add_hook_handler(hook_pre_command, CommandLineTransaction.Hooks.PRE_COMMAND)
    trans.add_hook_handler(hook_post_command, CommandLineTransaction.Hooks.POST_COMMAND)
    outputs = trans.run()

    return outputs






ALLOWED_ACTIONS = {
    "run": run_commands
}

def get_uid_for_user(username):
    try:
        return pwd.getpwnam(username).pw_uid
    except KeyError:
        raise SystemExit(f"user {username} not found")




class Handler(StreamRequestHandler):
    def handle(this):
        global LOGGER

        fmt = '3i'
        try:
            LOGGER.info("Received new request - checking permissions")
            creds = this.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(fmt))
            pid, uid, gid = struct.unpack(fmt, creds)
        except Exception as e:
            LOGGER.warning(f"Failed to obtain SO_PEERCRED information: {str(e)}")
            this.wfile.write(json.dumps({"error": "auth_failed", "message": "Unable to determine request permissions"}).encode() + b'\n')
            return

        LOGGER.info("Request received from pid=%d uid=%d gid=%d", pid, uid, gid)

        # Basic auth check: only allow configured UID (and optionally GID)
        if uid != ALLOWED_UID:
            LOGGER.error(f"Unauthorised request received by {uid}. Discarding request")
            this.wfile.write(json.dumps({"error": "unauthenticated", "message": "Unauthorised user"}).encode() + b'\n')
            return

        LOGGER.info("Parsing request")
        # Read a single JSON line (simple protocol)
        line = this.rfile.readline().decode('utf-8').strip()
        if not line:
            LOGGER.warning("Request was empty")
            this.wfile.write(json.dumps({"error": "empty", "message": "No request"}).encode() + b'\n')
            return

        try:
            req = json.loads(line)
        except Exception:
            LOGGER.error("Request didn't have a valid JSON format")
            this.wfile.write(json.dumps({"error": "bad_json", "message": "Malformed request"}).encode() + b'\n')
            return


        try:
            action = req['action']
            fn = ALLOWED_ACTIONS[action]
        except Exception:
            LOGGER.error(f"Invalid action `{action}` received. Discarding request")
            this.wfile.write(json.dumps({"error": "invalid_action", "message": f"Action `{action}` is not valid"}).encode() + b'\n')
            return


        try:
            args = req.get('args',{})
            parsed_args = ",".join([ f"{k}={v}" for k,v in args.items() ])

            LOGGER.info(f"Executing action `{action}` with the following arguments: {parsed_args}")


            output = fn(**args)
            this.wfile.write(json.dumps(output).encode() + b"\n")
                #logging.warning("action %s rejected: %s", action, message)
        except Exception as e:
            LOGGER.error(f"Failed action `{action}`: {str(e)}")
            this.wfile.write(json.dumps({"error": "handler_error", "message": f"Error occurred for `{action}`: {str(e)}"}).encode() + b"\n")
            raise e


def run_server(allowed_username="www-data"):
    global ALLOWED_UID, LOGGER
    LOGGER = setup_logger("SUDO DAEMON")

    ALLOWED_UID = get_uid_for_user(allowed_username)

    try:
        LOGGER.info(f"Deleting previously created socket file `{SOCK_PATH}`")
        os.unlink(SOCK_PATH)
    except FileNotFoundError:
        LOGGER.info(f"Stale socket file `{SOCK_PATH}` not found - this is good.")
        pass

    LOGGER.info(f"Opening new socket {SOCK_PATH}")
    server = UnixStreamServer(SOCK_PATH, Handler)

    socket_perm = 0o660
    socket_uid = get_uid_for_user("sudodaemon")
    socket_gid = grp.getgrnam("www-data").gr_gid

    LOGGER.info(f"Opening new socket {SOCK_PATH}: UID {socket_uid} - GID {socket_gid} - PERMISSION {oct(socket_perm)}")

    os.chmod(SOCK_PATH, socket_perm)
    os.chown(SOCK_PATH, socket_uid, socket_gid)

    LOGGER.info("Listening on %s (allowed uid=%d)", SOCK_PATH, ALLOWED_UID)
    server.serve_forever()


if __name__ == "__main__":
    run_server(allowed_username="www-data")
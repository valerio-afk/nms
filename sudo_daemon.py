import os
import json
import pwd
import struct
import socket
from importlib import import_module
from socketserver import UnixStreamServer, StreamRequestHandler

from cmdl import LocalCommandLineTransaction

SOCK_DIR = "/var/run/nms"
SOCK_FILE= "privileged_cmdl.sock"

SOCK_PATH = os.path.join(SOCK_DIR,SOCK_FILE)

ALLOWED_UID = None


def load_cmd_from_json(d):
    module = import_module("cmdl")
    clsname = d.pop('__class__')
    cls = getattr(module, clsname)
    obj = cls(**d)
    return obj

#    except Exception:
#        this.wfile.write(
#            json.dumps({"error": "bad_cmd", "message": f"Command `{clsname}` is not authorised"}).encode() + b'\n')

#        return

def run_commands(commands):
    cmds = []

    for d in commands:
        cmd = load_cmd_from_json(d)
        cmds.append(cmd)

    trans = LocalCommandLineTransaction(*cmds)
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
        # Obtain peer credentials via SO_PEERCRED (Linux)
        # struct is three ints: pid, uid, gid
        fmt = '3i'
        try:
            creds = this.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize(fmt))
            pid, uid, gid = struct.unpack(fmt, creds)
        except Exception as e:
            #logging.warning("Failed to obtain SO_PEERCRED: %s", e)
            this.wfile.write(json.dumps({"error": "auth_failed", "message": "Unable to determine request permissions"}).encode() + b'\n')
            return

        #logging.info("connection from pid=%d uid=%d gid=%d", pid, uid, gid)

        # Basic auth check: only allow configured UID (and optionally GID)
        if uid != ALLOWED_UID:
            #logging.warning("unauthorised uid %d (expected %d)", uid, ALLOWED_UID)
            this.wfile.write(json.dumps({"error": "unauthenticated", "message": "Unauthorised user"}).encode() + b'\n')
            return

        # Optional: verify the exe path for extra assurance (defense-in-depth)
        try:
            exe_path = os.readlink(f"/proc/{pid}/exe")
            #logging.debug("peer exe: %s", exe_path)
            # if you want to enforce a specific client binary, check exe_path here
        except Exception:
            exe_path = None

        # Read a single JSON line (simple protocol)
        line = this.rfile.readline().decode('utf-8').strip()
        if not line:
            this.wfile.write(json.dumps({"error": "empty", "message": "No request"}).encode() + b'\n')
            return

        try:
            req = json.loads(line)
        except Exception:
            this.wfile.write(json.dumps({"error": "bad_json", "message": "Malformed request"}).encode() + b'\n')
            return


        try:
            action = req['action']
            fn = ALLOWED_ACTIONS[action]
        except Exception:
            this.wfile.write(json.dumps({"error": "invalid_action", "message": f"Action `{action}` is not valid"}).encode() + b'\n')
            return


        try:
            output = fn(**req.get('args',{}))
            this.wfile.write(json.dumps(output).encode() + b"\n")
                #logging.warning("action %s rejected: %s", action, message)
        except Exception as e:
            #logging.exception("action handler failed")
            this.wfile.write(json.dumps({"error": "handler_error", "message": f"Error occurred for `{action}`: {str(e)}"}).encode() + b"\n")
            raise e


def run_server(allowed_username="www-data"):
    global ALLOWED_UID
    # set allowed UID from username
    ALLOWED_UID = get_uid_for_user(allowed_username)

    # ensure socket dir exists with correct perms
    os.makedirs(SOCK_DIR, exist_ok=True)
    #os.chown(SOCK_DIR, 0, grp.getgrnam("pihelper").gr_gid)
    os.chmod(SOCK_DIR, 0o777)

    # remove stale socket
    try:
        os.unlink(SOCK_PATH)
    except FileNotFoundError:
        pass

    server = UnixStreamServer(SOCK_PATH, Handler)
    # ensure socket file has secure perms: root:pihelper 660
    os.chmod(SOCK_PATH, 0o666)
    #os.chown(SOCK_PATH, 0, grp.getgrnam("pihelper").gr_gid)

    #logging.info("pi-helper listening on %s (allowed uid=%d)", SOCK_PATH, ALLOWED_UID)
    server.serve_forever()


if __name__ == "__main__":
    run_server(allowed_username="tuttoweb")
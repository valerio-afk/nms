import grp
import json
import pwd
import socket

from cmdl import RemoteCommandLineTransaction, Chown
from constants import SOCK_PATH


class FSMixin:

    def change_ownership(this, path:str) -> None:
        account = this._cfg.get("access", {}).get("account", {})

        try:
            uid = pwd.getpwnam(account.get("username","")).pw_uid
            gid = grp.getgrnam(account.get("group","")).gr_gid

            trans = RemoteCommandLineTransaction(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
                SOCK_PATH,
                Chown(uid,gid,path,True)
            )

            output = trans.run()

            if (trans.success):
                this.logger.info(f"Changed ownership: {path}")
            else:
                this.logger.error(f"Error while changing ownership: {output['stderr']}")

        except Exception as e:
            this.logger.error(f"Error while changing ownership: {str(e)}")

    def change_permissions(this) -> None:
        if (this.is_mounted):
            message = {
                "action": "ch_tank_perm",
                "args": {"pool": this.pool_name,"dataset":this.dataset_name,"group":"users"}
            }

            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(SOCK_PATH)

            s.sendall(json.dumps(message, default=lambda x: x.to_dict()).encode() + b'\n')

            response = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b"\n" in chunk:
                    break

            s.close()